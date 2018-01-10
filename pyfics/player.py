#!/usr/bin/env python
# -*-coding: utf-8-*-

"""PyFics"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

from gi.repository import Notify, Gtk, GLib
import io
import re
import os
import logging

from .game import Game, Position
from .board import Board, Clock
from .moves import MovesTab
from .interface import Interface
from .stockfish import Stockfish
from .fics import Fics
from . import config, tools
from .exceptions import PyficsError

logger = logging.getLogger(__name__)


class Player(object):
    """Main PyFics program"""

    def __init__(self):
        Notify.init("PyFics")
        self.game = Game()
        self.clock = Clock()
        self.board = Board(self.clock)
        self.movestab = MovesTab(self.game)
        self.interface = Interface(self.board, self.movestab)
        self.stock = Stockfish()
        self.server = Fics(self.interface.fics_buffer)
        self.board.update(self.game.get("board"))

        self.fics_game = False

        self.board.connect("moved_board", self.on_board_move)
        self.movestab.connect("step", self.on_step)
        self.movestab.enable_button.connect(
            "clicked", self.on_enable_stockfish)
        self.movestab.show_button.connect("clicked", self.on_show_stockfish)

        self.interface.connect("step", self.on_step)
        self.interface.connect("command", self.on_command)
        self.interface.connect("login", self.server.on_login)
        self.interface.connect("destroy", self.on_destroy)

        self.server.connect("fics", self.on_fics)

        self.stock.connect("sf_info", self.on_sf_info)
        self.stock.connect("bestmove", self.on_bestmove)

    def on_board_move(self, _widget, move):
        """A move was done on the board"""
        GLib.idle_add(self.board_move, move)

    def on_show_stockfish(self, widget):
        """Show the stockfish analyses"""
        logger.debug("on_show_stockfish")
        GLib.idle_add(self.movestab.set_show_stockfish, widget.get_active())

    def on_command(self, _widget, command):
        """Show the stockfish analyses"""
        logger.debug("on_command")
        GLib.idle_add(self.server.command, command)

    def on_enable_stockfish(self, widget):
        """Toggle stop/start stockfish"""
        if widget.get_active():
            logger.debug("Stockfish enabled")
            self.stock.enabled = True
            GLib.idle_add(self.analyse)
        else:
            logger.debug("Stockfish disabled")
            self.stock.enabled = False
            self.stock.write("stop", True)

    def on_sf_info(self, _widget, info):
        """New stockfish info received"""
        GLib.idle_add(self.add_info, info)

    def add_info(self, info):
        """Update stockfish info"""
        halfmove = self.game.update_info(info)
        if halfmove is not None:
            self.movestab.update_info(halfmove)
            self.movestab.update_info(halfmove + 1)

    def reset(self):
        """Reset the interface"""
        self.game.setup()
        self.board.reset()
        self.board.update(self.game.get("board"))
        self.movestab.moves_buffer.set_text("")
        self.fics_game = True

    def on_fics(self, _widget, data):
        """Receive fics data"""
        GLib.idle_add(self.parse_fics, data)

    def parse_fics(self, data):
        """Parse output from fics"""
        # pylint: disable=R0911,R0912,R0915
        # R0912 = Too many branches
        # R0915 = Too many statemnts

        logger.debug("Received: {0}".format(data))
        cache = tools.Cache()

        # username
        if re.match("login:", data):
            logger.debug("Send username")
            self.server.command(config.SETTINGS["fics"]["user"], True)

        # password
        elif re.match("password:", data):
            logger.debug("Send password")
            self.server.command(config.SETTINGS["fics"]["password"], True)

        # logged in
        elif re.match(".*Starting FICS session", data):
            logger.debug("Set fics parameters")
            self.server.command("set style 12")
            self.server.command("set bell off")
            if config.SETTINGS["fics"]["password"] == "":
                for cmd in config.SETTINGS["fics"]["guest_init"]:
                    self.server.command(cmd)

        # logged out
        elif re.match(r"\W*Logging you out|\*\*\*\* Auto-logout", data):
            logger.debug("Logging out")
            self.server.output(data + "\n")
            self.server.logout()

        # a style12 move
        elif cache(re.match("(<12>.*)", data, re.DOTALL)):
            logger.debug("Style12")
            self.fics_move(cache.output.group(1))

        # a result message
        elif cache(re.match(
                r"{Game (?P<game_no>\d+) \((?P<players>.*)\)" +
                " (?P<action>.+)} (?P<result>.+)", data)):
            logger.debug("Game finished")
            self.clock.set_info("{action} ({result})".format(
                **cache.output.groupdict()))
            self.fics_game = False
            self.clock.stop()
            self.board.moves["pre"] = []
            self.board.set_attention(0)
            self.board.queue_draw()
            self.interface.show_move_buttons()
            self.server.output("{action} ({result})\n\n".format(
                **cache.output.groupdict()))

        # stopped examing
        elif re.match("You are no longer examining game" +
                      " (?P<game_no>.*)", data):
            logger.debug("Stop examine")
            self.clock.stop()
            self.clock.set_info("Stopped examing")
            self.fics_game = False

        # ignore seek acceptance messages
        elif re.match("(?P<opponent>.*) accepts your seek.", data):
            logger.debug("Ignore")
        elif re.match("Your seek matches", data):
            logger.debug("Ignore")
        elif re.match("Your seek intercepts .*'s getgame.", data):
            logger.debug("Ignore")
        elif re.match("Your opponent has aborted the game", data):
            logger.debug("Ignore")

        # show feedback for the flag command
        elif re.match("Checking if really out of time", data):
            logger.debug("Info message")
            self.clock.set_info(data)
        elif re.match("Opponent is not out of time, priming autoflag", data):
            logger.debug("Info message")
            self.clock.set_info(data)

        # ignore move messages
        elif re.match(r"Game (?P<game_no>\d*): (?P<opponent>.*)" +
                      " moves: (?P<move>.*)", data):
            logger.debug("Ignore")
        # but display all other info
        elif cache(re.match(r"Game (?P<game_no>\d*): (?P<message>.*)", data)):
            logger.debug("Info message")
            self.clock.set_info(cache.output.group("message"))

        elif cache(re.match(
                r"Creating: (?P<white>.*) (?P<white_rating>\(.*\))" +
                r"(?P<black>.*) (?P<black_rating>\(.*\))" +
                "(?P<timing>.*)\n" +
                r"{Game (?P<game_no>\d)* .*}", data)):
            logger.debug("Start game")
            self.clock.set_name("W", cache.output.group("white"),
                                cache.output.group("white_rating"))
            self.clock.set_name("B", cache.output.group("black"),
                                cache.output.group("black_rating"))
            self.clock.set_timing(cache.output.group("timing"))
            self.interface.show_game_buttons()
            self.reset()
            self.server.output((
                "Creating: {white} {white_rating}" +
                " vs. {black} {black_rating}:" +
                " {timing}\n\n").format(**cache.output.groupdict()))
            notification = Notify.Notification.new(
                "New chess game",
                ("{white} {white_rating}\n" +
                 " vs. {black} {black_rating}\n" +
                 "{timing}").format(**cache.output.groupdict()),
                config.ICON)
            notification.show()

        elif re.match(r"Starting a game in examine \(scratch\) mode", data):
            logger.debug("Start examine")
            self.clock.set_name("B", "BLACK")
            self.clock.set_name("W", "WHITE")
            self.clock.set_timing("Examine mode")
            self.reset()

        elif re.match("Illegal move", data):
            logger.debug("Info message")
            self.clock.set_info(data)

        else:
            logger.debug("Just display")
            # everything else
            self.server.output("%s\n" % data)

    def after_move(self):
        """Redraw board after move"""
        self.clock.set_info("")
        if (self.game.get("halfmove") == 0 and
                self.game.get("relation") in [1, -1] and
                self.fics_game):
            self.board.set_attention(2)
        elif self.game.get("relation") == 1:
            self.board.set_attention(1)
        else:
            self.board.set_attention(0)

        self.board.queue_draw()

    def board_move(self, clicks):
        """A move was made on the board"""

        logger.debug("board_move: {0}".format(clicks))

        if self.fics_game and self.game.get("relation") == -1:
            self.board.moves["pre"] = clicks
            self.board.undo_move(clicks)
            self.board.queue_draw()
            return

        try:
            notation = self.game.clicks_to_notation(clicks)
            move = self.game.notation_to_move(notation)
            self.game.check_move(move)
        except PyficsError as error:
            logger.debug("Failed clicks: {0}".format(clicks))
            self.board.undo_move(clicks)
            self.clock.set_info(error.args[0])
            return

        self.game.make_move(move)
        self.server.command(move["sf_move"])
        logger.debug("Made move: {0}".format(notation))
        self.movestab.update()
        self.board.make_move(move)
        self.clock.switch()
        self.after_move()

    def fics_move(self, style12):
        """A move was received from fics"""

        position = Position(style12)
        notation = position.props["notation"]
        if position.halfmove - 1 == self.game.get("halfmove"):
            try:
                move = self.game.notation_to_move(notation)
                self.game.check_move(move)
                self.board.make_move(move)
                self.game.make_move(move)
            except PyficsError as error:
                logger.error("Cannot perform fics move {0}".format(notation))
                logger.debug(error)
        if (self.game.get("board") != position.board or
                self.board.orientation != position.props["orientation"]):
            logger.error("Updating board")
            self.board.orientation = position.props["orientation"]
            self.board.update(position.board)
        self.game.set_position(position)
        self.movestab.update()

        self.clock.set_seconds("W", position.props["white_time"])
        self.clock.set_seconds("B", position.props["black_time"])
        self.clock.start(position.props["next_color"])

        if self.board.moves["pre"] != []:
            # remove premoves and send them as clicks from the board
            # if it is not my move yet, they will be readded as premoves
            clicks = self.board.moves["pre"]
            self.board.moves["pre"] = []
            self.board_move(clicks)
            self.after_move()

    def analyse(self):
        """Analyse one move at a time"""
        if not self.stock.enabled:
            return
        for stocktime in [1000 * 2 ** i for i in range(10)]:
            for halfmove in reversed(self.game.get_halfmoves()):
                info = self.game.info[halfmove]
                if "time" in info and info["time"] > stocktime:
                    # the previous analyses is beter
                    continue
                if "score" in info and "mate" in info["score"]:
                    # a mate was already found
                    continue
                all_moves = [self.game.moves[gamemove]
                             for gamemove in self.game.get_halfmoves()
                             if gamemove <= halfmove and gamemove > 0]
                self.stock.search(
                    halfmove, moves=all_moves, stocktime=stocktime)
                return

    def on_bestmove(self, _widget):
        """A bestmove is found, so the analyses is finished"""
        GLib.idle_add(self.analyse)

    def on_step(self, _widget, step):
        """Step button clicked"""
        GLib.idle_add(self.make_step, step)

    def make_step(self, step):
        """Do a step"""
        self.clock.set_info("")
        all_moves = self.game.get_halfmoves()
        halfmove = (
            min(all_moves) if step == "start" else
            max(all_moves) if step == "end" else
            self.game.get("halfmove") - 1 if step == "back" else
            self.game.get("halfmove") + 1 if step == "forward" else
            step)
        if halfmove not in all_moves:
            return

        position = self.game.get_history(halfmove)
        notation = position.props["notation"]
        if halfmove - 1 in all_moves:
            self.game.position = self.game.get_history(halfmove - 1)
            self.board.update(self.game.get("board"))
            move = self.game.position.notation_to_move(notation)
            self.board.make_move(move)
            self.game.position = position
        else:
            self.game.position = position
            self.board.update(self.game.get("board"))

        self.clock.set_seconds("W", self.game.get("white_time"))
        self.clock.set_seconds("B", self.game.get("black_time"))
        self.clock.active = position.props["next_color"]
        self.clock.update_clocks()
        self.movestab.highlight_move(halfmove)
        self.board.queue_draw()
        # self.analyse()

    def on_destroy(self, interface):
        """Exit the program"""
        config.SETTINGS["window"]["pane"] = interface.hpane.get_property(
            "position")
        fobj = io.open(os.path.join(config.LOCAL_DIR, "settings.ini"), "wb")
        config.SETTINGS.write(fobj)
        fobj.close()
        self.server.logout()
        Gtk.main_quit()
