#!/usr/bin/env python
# -*-coding: utf-8-*-

"""Stockfish module"""

# (has no member) pylint: disable=E1101, E1103

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

from gi.repository import GObject

import subprocess
import collections
import re
import logging
import threading
import sys

from . import config, tools

logger = logging.getLogger(__name__)


class Stockfish(GObject.Object):
    """Analyse position with stockfish"""
    # (too many public methods) pylint: disable=R0904

    def __init__(self):
        super(Stockfish, self).__init__()

        logger.debug("Stockfish started")
        self.stock = subprocess.Popen(
            ["nice", "stockfish"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            bufsize=1,
            close_fds="posix" in sys.builtin_module_names,
            universal_newlines=True)
        # GObject.io_add_watch(self.stock.stdout, GObject.IO_IN, self.handle)
        thread = threading.Thread(target=self.parse_output, args=(self.stock,))
        thread.daemon = True  # thread dies with the program
        thread.start()

        self.ready = False
        self.finding_best_move = False
        self.enabled = True
        self.options = {}
        self.queue = []
        self.halfmove = 0
        self.write("uci", True)
        self.write(
            "setoption name Threads value {0}".format(config.THREADS), True)

    def search(self, halfmove=0, fen=None, moves=None, stocktime=None):
        """Start a new game"""
        self.halfmove = halfmove
        if fen:
            self.write("position fen %s" % fen)
        elif moves:
            self.write("position startpos moves %s" % " ".join(moves))
        else:
            self.write("position startpos")

        self.finding_best_move = True
        self.write("go movetime {0}".format(stocktime) if stocktime else
                   "go infinite")

    def write(self, line, wait=False):
        """Give command to stockfish"""
        if not self.ready:
            logger.debug("queue: {0}".format(line))
            self.queue.append((line, wait))
        else:
            logger.debug("write: {0}".format(line))
            self.stock.stdin.write(line + "\n")
        if wait:
            self.ready = False
            logger.debug("write: isready")
            self.stock.stdin.write("isready\n")
            # self.stock.stdin.flush()

    def parse_output(self, proc):
        """thread which reads output"""
        line = ""
        while proc.poll() is None:
            char = proc.stdout.read(1)
            if char == "\n":
                self.handle(line)
                line = ""
            else:
                line += char

    def handle(self, line):
        """Data from stockfish received"""
        if line == "readyok":
            self.on_ready()
        elif line == "uciok":
            pass
        elif line.startswith("info"):
            self.on_info(line)
        elif line.startswith("bestmove"):
            self.finding_best_move = False
            self.emit("bestmove")
        elif line.startswith("id"):
            pass
        elif line.startswith("option"):
            self.on_option(line)
        elif line == "":
            pass
        elif line.startswith("Stockfish"):
            pass
        elif line == "Unknown command: stop":
            pass
        else:
            logger.error("Unknown: {0}".format(line))
        return True

    def on_ready(self):
        """A ready command is received"""
        self.ready = True
        while len(self.queue) > 0 and self.ready:
            line, wait = self.queue.pop(0)
            self.write(line, wait)

    def on_option(self, line):
        """Option line"""
        options = self.get_dict(line, config.OPTION)
        name = options.pop("name")
        self.options[name] = options

    @staticmethod
    def get_dict(line, keys):
        """Return the line as a dictionary"""
        mydict = collections.defaultdict(list)
        for elem in line.split(" "):
            if elem in keys:
                key = elem
            else:
                mydict[key].append(elem)
        for key, values in mydict.items():
            mydict[key] = " ".join(values).strip()
            try:
                mydict[key] = int(mydict[key])
            except ValueError:
                pass
        return dict(mydict)

    def on_info(self, line):
        """Fill the info variable"""
        info = self.get_dict(line, config.INFO)
        info["halfmove"] = self.halfmove
        if "time" not in info or "score" not in info:
            # maybe nodes usefull?
            return
        info["seconds"] = info["time"] / 1000
        info["pscore"] = self.get_pscore(info["score"])
        self.emit("sf_info", info)

    def get_pscore(self, score):
        """Return the score for white"""

        cache = tools.Cache()
        if self.halfmove % 2 == 0:
            white = 1
        else:
            white = -1
        if cache(re.search(r"cp ([-\d]+)", score)):
            return white * int(cache.output.groups()[0]) / 100
        if cache(re.search(r"mate ([-\d]+)", score)):
            if "-" in cache.output.groups()[0]:
                return white * -999
            else:
                return white * 999
        return 0

GObject.signal_new("sf_info", Stockfish, GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, (GObject.TYPE_PYOBJECT,))
GObject.signal_new("bestmove", Stockfish, GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, ())
