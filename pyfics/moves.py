#!/usr/bin/env python
# -*-coding: utf-8-*-

"""The moves tab with the stockfish interaction"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

from gi.repository import Gtk, Gdk, GObject, Pango
import logging

from . import config

logger = logging.getLogger(__name__)


class MovesTab(Gtk.VPaned):
    """The tab which shows the moves and analyses"""
    # (too many public methods) pylint: disable=R0904

    def __init__(self, game):
        super(MovesTab, self).__init__()
        self.game = game
        moves_terminal, self.moves_buffer = self.get_terminal()
        self.tags = {}
        self.marks = {}
        stock_terminal, self.stock_buffer = self.get_terminal()

        stock_box = Gtk.VBox()
        stock_buttons = Gtk.HBox()
        self.enable_button = Gtk.CheckButton("Enable")
        stock_buttons.pack_start(self.enable_button, True, True, 0)
        self.show_button = Gtk.CheckButton("Show")
        stock_buttons.pack_start(self.show_button, True, True, 0)
        stock_box.pack_start(stock_buttons, False, True, 0)
        stock_box.pack_start(stock_terminal, True, True, 10)

        self.show_stockfish = False

        self.add(moves_terminal)
        self.add(stock_box)
        self.set_position(config.SETTINGS["window"]["moves_tab"])
        self.halfmove = 0

        iter2 = self.moves_buffer.get_end_iter()
        mark = Gtk.TextMark(left_gravity=True)
        self.moves_buffer.add_mark(mark, iter2)
        self.marks[0] = mark

    @staticmethod
    def get_terminal():
        """Return a scrollable textview"""
        terminal = Gtk.ScrolledWindow()
        terminal.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        textview = Gtk.TextView()
        textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        terminal.add(textview)
        return terminal, textview.get_buffer()

    def on_tag_hover(self, _tag, _textview, event, _textiter, halfmove):
        """Cursor is above a move tag"""
        if event.type == Gdk.EventType.BUTTON_RELEASE:
            self.emit("step", halfmove)

    def update(self):
        """Add a move link"""
        halfmove = self.game.get("halfmove")
        if halfmove == 0:
            return
        delete_moves = [delete_move for delete_move in self.tags.keys()
                        if delete_move >= halfmove]
        if len(delete_moves) > 0:
            mark = self.marks[min(delete_moves)]
            iter1 = self.moves_buffer.get_iter_at_mark(mark)
            self.moves_buffer.delete(iter1, self.moves_buffer.get_end_iter())
            for delete_move in delete_moves:
                del self.tags[delete_move]
                del self.marks[delete_move]

        short = self.game.get("last_move_short")
        if self.game.get("next_color") == "B":
            short = "{0}.{1}".format(self.game.get("next_move_number"), short)

        tag = self.moves_buffer.create_tag(foreground="white")
        tag.connect("event", self.on_tag_hover, halfmove)
        iter1 = self.moves_buffer.get_end_iter()
        mark = Gtk.TextMark(left_gravity=True)
        self.moves_buffer.add_mark(mark, iter1)
        self.moves_buffer.insert_with_tags(iter1, short, tag)
        self.tags[halfmove] = tag
        self.marks[halfmove] = mark
        self.highlight_move(halfmove)

        self.moves_buffer.insert(self.moves_buffer.get_end_iter(), " ")

    def set_show_stockfish(self, show_stockfish):
        """Show or hide stockfish info"""
        self.show_stockfish = show_stockfish
        logger.debug("Stockfish output is now {0}".format(
            "enabled" if self.show_stockfish else "disabled"))
        for halfmove, tag in self.tags.items():
            if self.show_stockfish:
                self.update_info(halfmove)
            else:
                tag.set_property(
                    "foreground-gdk", Gdk.Color(65535, 65535, 65535))

    def update_info(self, halfmove):
        """New info is received for a move"""

        if halfmove == self.halfmove:
            self.update_stockfish()
        if (not self.show_stockfish or
                halfmove not in self.tags or
                halfmove not in self.game.info):
            return

        info = self.game.info[halfmove]
        if "pscore_prev" not in info or "pscore" not in info:
            return
        pscore_prev = info["pscore_prev"]
        pscore = info["pscore"]
        if halfmove % 2 == 0:
            pscore *= -1
            pscore_prev *= -1
        scoredif = min(max(0, pscore_prev - pscore), config.MAX_DIF)
        if abs(pscore) > config.LOST and abs(pscore_prev) > config.LOST:
            # when the position is hopeless, all moves are ok
            color = Gdk.Color(0, 0, 65535)
        else:
            color = Gdk.Color(
                scoredif / config.MAX_DIF * 65535, 0,
                (config.MAX_DIF - scoredif) / config.MAX_DIF * 65535)
        self.tags[halfmove].set_property("foreground-gdk", color)

    def highlight_move(self, halfmove):
        """Highlight the halfmove"""
        # remove highlight from current move
        if self.halfmove in self.tags:
            self.tags[self.halfmove].set_property(
                "weight", Pango.Weight.NORMAL)
            self.tags[self.halfmove].set_property(
                "underline", Pango.Underline.NONE)

        # highlight current move
        self.halfmove = halfmove
        if self.halfmove in self.tags:
            self.tags[self.halfmove].set_property("weight", Pango.Weight.BOLD)
            self.tags[self.halfmove].set_property(
                "underline", Pango.Underline.SINGLE)
        self.update_stockfish()

    def update_stockfish(self):
        """Update the stockfish panel"""
        if (self.show_stockfish and
                "pscore" in self.game.info[self.halfmove]):
            self.stock_buffer.set_text(
                ("Score: {pscore:.1f} ({score})\n" +
                 "Depth: {depth} ({seconds:.1f} sec)\n" +
                 "PV   : {pv}").format(
                     **self.game.info[self.halfmove]))
        else:
            self.stock_buffer.set_text("")

GObject.signal_new("step", MovesTab, GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, (GObject.TYPE_PYOBJECT,))
