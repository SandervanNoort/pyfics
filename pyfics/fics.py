#!/usr/bin/env python
# -*-coding: utf-8-*-

"""Fics commands"""


from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

from gi.repository import GObject
import socket
import threading
import re
import errno
import telnetlib
import random
import time
import platform
import getpass
import six
import logging

from . import config

logger = logging.getLogger(__name__)


class Fics(GObject.Object):
    """The main connection to fics"""
    # (too many public methods) pylint: disable=R0904

    def __init__(self, fics_buffer):
        #  super(Fics, self).__init__()
        GObject.Object.__init__(self)
        self.conn = Timeseal()
        self.watch = 0  # process id that monitor fics output
        self.fics_buffer = fics_buffer

    def on_login(self, _widget, _data=None):
        """Connect to fics"""

        self.output("Connecting to fics....\n")
        if self.watch > 0:
            GObject.source_remove(self.watch)
        self.watch = GObject.io_add_watch(
            self.conn.sock, GObject.IO_IN, self.handle_data)
        threading.Thread(target=self.connect_thread).start()

    def logout(self):
        """Logout"""
        self.conn.close()

    def connect_thread(self):
        """The thread in which the initial Fics connection is run"""
        try:
            self.conn.open(config.SETTINGS["fics"]["server"],
                           config.SETTINGS["fics"]["port"])
        except socket.gaierror:
            self.output("No internet connection")
            return

    def handle_data(self, _source, _condition):
        """Handle fics data"""
        self.conn.receive()
        if self.conn.connected:
            lines = re.split("fics%|\n\n", self.conn.get_buffer())
            for line in lines[:-1]:
                line = line.strip()
                line = line.replace("\n\\   ", "")
                self.emit("fics", line)
            self.conn.set_buffer(lines[-1])
        else:
            lines = re.split("\n", self.conn.get_buffer())
            for line in lines:
                self.emit("fics", line.rstrip())
            self.conn.set_buffer("")

        if self.conn.closed:
            self.output(self.conn.get_buffer() + "\n\n")
            self.output("Disconnected from FICS\n\n")
            return False
        else:
            return True

    def command(self, cmd, login=False):
        """Execute fics command"""
        if self.conn.connected or login:
            self.conn.write(cmd + "\n")
        else:
            self.output("Not connected to Fics\n")

    def output(self, text):
        """Write output to the textview window"""
        if self.conn.connected and text != "\n":
            text += "\n"
        end_iter = self.fics_buffer.get_end_iter()
        self.fics_buffer.insert(end_iter, text, len(text))


class Timeseal(object):
    """Timeseal class"""
    ENCODE = [ord(char) for char in
              "Timestamp (FICS) v1.0 - programmed by Henrik Gram."]
    ENCODELEN = len(ENCODE)
    G_RESPONSE = "\x029"
    FILLER = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    IAC_WONT_ECHO = b"".join([
        telnetlib.IAC, telnetlib.WONT, telnetlib.ECHO]).decode("iso8859")
    IAC_WILL_ECHO = b"".join([
        telnetlib.IAC, telnetlib.WILL, telnetlib.ECHO]).decode("iso8859")

    # IAC_WILL_ECHO = "".join([telnetlib.IAC, telnetlib.WILL, telnetlib.ECHO])
    BUFFER_SIZE = 4096
    INIT_STRING = "TIMESTAMP|{user}|{uname}|".format(
        user=getpass.getuser(), uname=" ".join(list(platform.uname())))
    # self.IAC = \xff, WONT = \xfc, ECHO = \x01, WILL = \xfb

    def __init__(self):
        self.connected = False
        self.closed = False
        self.writebuf = ""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buf = ""
        self.stateinfo = None

    def get_buffer(self):
        "return the buffer"
        return self.buf

    def set_buffer(self, buf):
        """Return the buffer"""
        self.buf = buf

    def open(self, address, port):
        """Connect to server"""
        self.connected = False
        self.closed = False
        self.stateinfo = None

        try:
            self.sock.connect((address, port))
        except socket.error as error:
            if error.errno != errno.EINPROGRESS:
                raise
        self.buf = ""
        self.writebuf = ""

        self.write(self.INIT_STRING + "\n")
        # self.receive()

    def close(self):
        """Close connection"""
        self.closed = True
        if hasattr(self, "sock"):
            self.sock.close()
        self.connected = False

    def encode(self, text):
        """Encode a string"""
        timestamp = int(time.time() * 1000 % 1e7)
        enc = "{0}\x18{1:d}\x19".format(text, timestamp)
        padding = 12 - len(enc) % 12
        filler = random.sample(self.FILLER, padding)
        enc += "".join(filler)

        buf = [ord(i) for i in enc]

        for i in range(0, len(buf), 12):
            buf[i + 11], buf[i] = buf[i], buf[i + 11]
            buf[i + 9], buf[i + 2] = buf[i + 2], buf[i + 9]
            buf[i + 7], buf[i + 4] = buf[i + 4], buf[i + 7]

        encode_offset = random.randrange(self.ENCODELEN)

        for i in range(len(buf)):
            buf[i] |= 0x80
            j = (i + encode_offset) % self.ENCODELEN
            buf[i] = six.unichr((buf[i] ^ self.ENCODE[j]) - 32)

        buf.append(six.unichr(0x80 | encode_offset))
        return "".join(buf)

    def decode(self, text):
        """Decode a string"""
        expected_table = "\n\r[G]\n\r"
        final_state = len(expected_table)
        g_count = 0
        result = []
        (state, lookahead) = self.stateinfo if self.stateinfo else (0, [])

        lenb = len(text)
        idx = 0
        while idx < lenb:
            char = text[idx]
            expected = expected_table[state]
            if char == expected:
                state += 1
                if state == final_state:
                    g_count += 1
                    lookahead = []
                    state = 0
                else:
                    lookahead.append(char)
                idx += 1
            elif state == 0:
                result.append(char)
                idx += 1
            else:
                result.extend(lookahead)
                lookahead = []
                state = 0

        self.stateinfo = (state, lookahead)
        return "".join(result), g_count

    def write(self, text):
        """Append string to the writebuf"""
        self.writebuf += text
        if "\n" not in self.writebuf:
            return

        if self.closed:
            return

        i = self.writebuf.rfind("\n")
        text = self.writebuf[:i]
        self.writebuf = self.writebuf[i + 1:]

        text = self.encode(text)
        self.sock.send((text + "\n").encode("iso8859"))

    def receive(self):
        """Receive data"""
        recv = self.sock.recv(self.BUFFER_SIZE).decode("iso8859")
        if len(recv) == 0:
            return

        if not self.connected:
            recv = recv.replace("\r", "")
            recv = recv.replace(self.IAC_WONT_ECHO, "")
            recv = recv.replace(self.IAC_WILL_ECHO, "")
            self.buf += recv

            if "Starting FICS session" in self.buf:
                self.connected = True

        else:
            recv, g_count = self.decode(recv)
            recv = recv.replace("\r", "")
#             recv = recv.replace("\n\\   ", "")
#             recv = recv.replace("\nfics%", "\n\n")

            for _counter in range(g_count):
                self.write(self.G_RESPONSE + "\n")
            self.buf += recv

    def __repr__(self):
        return self.sock.getpeername()

GObject.signal_new("fics", Fics, GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, (GObject.TYPE_PYOBJECT,))
