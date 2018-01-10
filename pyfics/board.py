#!/usr/bin/env python
# -*-coding: utf-8-*-

"""PyFics"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)


from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject

import textwrap
import sys  # pylint: disable=W0611
import os
import collections
import logging

from . import config

logger = logging.getLogger(__name__)


class Clock(object):
    """The right pane items of the chess board with the names,clocks"""

    def __init__(self):
        self.players = {}
        for color in ["W", "B"]:
            player = {}
            player["name"] = Gtk.Label(color, name="name")
            player["name"].set_alignment(0, 0)

            player["seconds"] = 0

            player["rating"] = Gtk.Label(name="rating")

            player["time"] = Gtk.Label(name="time")
            player["time"].set_alignment(0, 0)

            namerating = Gtk.HBox()
            namerating.pack_start(player["name"], True, True, 0)
            namerating.pack_start(player["rating"], True, True, 0)

            player["nametime"] = Gtk.VBox()
            player["nametime"].pack_start(namerating, True, True, 0)
            player["nametime"].pack_start(player["time"], True, True, 0)
            self.players[color] = player
        self.info = Gtk.Label(name="info", label="info")  # last move
        self.timing = Gtk.Label(name="timing", label="time control")

        self.active = "W"  # which clock is ticking
        self.clock_proc_id = None  # proccess id of the ticking clock

    def set_name(self, color, name, rating=""):
        """Set the names"""
        self.players[color]["name"].set_text(name)
        self.players[color]["rating"].set_text(" " + rating)

    def set_seconds(self, color, seconds):
        """Set the number of seconds"""
        self.players[color]["seconds"] = seconds

    def set_info(self, info=""):
        """Current info (last move)"""
        self.info.set_text("\n".join(textwrap.wrap(info, 25)))

    def set_timing(self, timing):
        """Current info (last move)"""
        self.timing.set_text(timing)
        self.set_info()

    def update_clocks(self):
        """Set the names"""

        for color in ["W", "B"]:
            self.players[color]["time"].set_text(
                "{sign}{minutes:d}:{seconds:02d}".format(
                    minutes=abs(self.players[color]["seconds"]) // 60,
                    seconds=abs(self.players[color]["seconds"]) % 60,
                    sign="-" if self.players[color]["seconds"] < 0 else " "))
            if self.active == color:
                self.players[color]["time"].set_name("time_active")
                self.players[color]["name"].set_name("name_active")
                self.players[color]["rating"].set_name("rating_active")
            else:
                self.players[color]["time"].set_name("time")
                self.players[color]["name"].set_name("name")
                self.players[color]["rating"].set_name("rating")

    def switch(self):
        """Switch the ticking clock"""
        self.active = "W" if self.active == "B" else "B"
        if self.clock_proc_id is not None:
            self.start(self.active)
        else:
            self.update_clocks()

    def stop(self):
        """Stop any ticking clock"""
        if self.clock_proc_id is not None:
            GObject.source_remove(self.clock_proc_id)
            self.clock_proc_id = None
            self.update_clocks()

    def start(self, color):
        """Start the clock for color and stop all clocks"""
        if self.clock_proc_id is not None:
            GObject.source_remove(self.clock_proc_id)
        self.active = color
        self.clock_proc_id = GObject.timeout_add(1000, self.countdown_clock)
        self.update_clocks()

    def countdown_clock(self):
        """Decrease clock by one second"""
        self.players[self.active]["seconds"] -= 1
        self.update_clocks()
        return True


class Board(Gtk.Layout):
    """The graphical chess board"""
    # (too many public methods) pylint: disable=R0904

    def __init__(self, clock):
        super(Board, self).__init__()

        self.attention = 0  # 1: opponent move 2: first move
        self.size = 1  # size of field
        self.pieces = {}  # dict of square -> piece
        self.moves = collections.defaultdict(list)  # last and pre move
        self.drag = {"button": -1}  # dict which holds drag info
        self.orientation = 0  # 0: white at bottom, 1: black at bottom

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.POINTER_MOTION_HINT_MASK)
        self.connect("motion_notify_event", self.on_mouse_motion)
        self.connect("button_press_event", self.on_mouse_press)
        self.connect("button_release_event", self.on_mouse_release)

        self.clock = clock
        self.put(clock.info, 0, 0)
        self.put(clock.timing, 0, 0)
        for player in clock.players.values():
            self.put(player["nametime"], 0, 0)
        clock.update_clocks()

        self.connect("draw", self.on_draw)
        self.connect("size-allocate", self.on_size_allocate)

    def reset(self):
        """Reset the board"""
        self.moves["pre"] = []
        self.moves["last"] = []
        self.queue_draw()

    def on_size_allocate(self, _widget, cairo):
        """Resize the window, with maximum vertical space for the board"""
        height_board = min(cairo.height, cairo.width - config.INFO_WIDTH)
        if height_board > 1:
            new_size = height_board // 9
            if new_size != self.size and new_size > 0:
                self.size = new_size
                self.update()
                self.queue_draw()

    def on_draw(self, _widget, cairo):
        """Show the squares of the board"""
        if not self.size:
            return
        for i, letter in enumerate("abcdefgh"):
            for number in range(1, 9):
                square = "{0}{1}".format(letter, number)
                xval, yval = self.square_to_xy(square)
                cairo.rectangle(xval, yval, self.size, self.size)
                cairo.set_source_rgb(
                    *config.SETTINGS["rgb_"]["white"] if (i + number) % 2 == 0
                    else
                    config.SETTINGS["rgb_"]["black"])
                cairo.fill()

        linewidth = self.size // (10 if self.attention >= 1 else 20)
        for square in self.moves["last"]:
            cairo.set_line_width(2 * linewidth)
            xval, yval = self.square_to_xy(square)
            cairo.rectangle(
                xval + linewidth,
                yval + linewidth,
                self.size - 2 * linewidth,
                self.size - 2 * linewidth)
            cairo.set_source_rgb(*config.SETTINGS["rgb_"]["move"])
            cairo.stroke()

        cairo.set_line_width(2 * linewidth)
        for square in self.moves["pre"]:
            xval, yval = self.square_to_xy(square)
            cairo.rectangle(
                xval + linewidth,
                yval + linewidth,
                self.size - 2 * linewidth,
                self.size - 2 * linewidth)
            cairo.set_source_rgb(*config.SETTINGS["rgb_"]["premove"])
            cairo.stroke()

    def on_mouse_motion(self, _widget, _event):
        """Mouse motion on the board"""

        if self.drag["button"] == -1:
            return

        pointer_x, pointer_y = self.get_pointer()
        if (pointer_x, pointer_y) != self.drag["pointer"]:
            if self.drag["offset_x"] > - self.size / 2:
                self.drag["offset_x"] -= config.SPEED
            elif self.drag["offset_x"] < - self.size / 2:
                self.drag["offset_x"] += config.SPEED
            if self.drag["offset_y"] > - self.size / 2:
                self.drag["offset_y"] -= config.SPEED
            elif self.drag["offset_y"] < - self.size / 2:
                self.drag["offset_y"] += config.SPEED
            self.drag["pointer"] = pointer_x, pointer_y
        xval = self.drag["offset_x"] + pointer_x
        yval = self.drag["offset_y"] + pointer_y
        xval, yval = self.limit(xval, yval)
        piece = self.pieces[self.drag["square"]]
        self.move(piece, xval, yval)

    def on_mouse_press(self, _widget, event):
        """Mouse click on the board"""

        min_distance = (3 * self.size) ** 2
        min_square = None
        for square in self.pieces.keys():
            xval, yval = self.square_to_xy(square)
            distance = ((xval + self.size / 2 - event.x) ** 2 +
                        (yval + self.size / 2 - event.y) ** 2)
            if distance < min_distance:
                min_square = square
                min_distance = distance
        if min_square is not None:
            piece = self.pieces[min_square]
            xval, yval = self.square_to_xy(min_square)
            self.drag["piece"] = piece
            self.drag["square"] = min_square
            self.drag["button"] = event.button
            self.drag["offset_x"] = xval - event.x
            self.drag["offset_y"] = yval - event.y
            self.drag["pointer"] = event.x, event.y

            # reput, so it is on top
            self.remove(piece)
            alloc = piece.get_allocation()
            self.put(piece, alloc.x, alloc.y)

    def on_mouse_release(self, _widget, event):
        """Mouse release on the board"""

        if self.drag["button"] == -1:
            return

        self.drag["button"] = -1
        xval = self.drag["offset_x"] + event.x
        yval = self.drag["offset_y"] + event.y
        xval, yval = self.limit(xval, yval)
        piece = self.pieces[self.drag["square"]]
        square = self.xy_to_square(xval, yval)
        if square == self.drag["square"]:
            xval, yval = self.square_to_xy(square)
            self.move(piece, xval, yval)
            self.moves["pre"] = []
            self.queue_draw()
        else:
            self.emit("moved_board", [self.drag["square"], square])

    def set_attention(self, attention):
        """Set the attention of the board"""
        self.attention = attention
        self.set_name("attention" if attention == 2 else "")

    def update(self, position=None):
        """Update the pieces on the board"""

        if position is None:
            for square, piece in self.pieces.items():
                symbol = piece.symbol
                piece.destroy()
                xval, yval = self.square_to_xy(square)
                piece = self.create_piece(symbol)
                self.put(piece, xval, yval)
                self.pieces[square] = piece
        else:
            symbols = collections.defaultdict(list)
            for piece in self.pieces.values():
                symbols[piece.symbol].append(piece)
            self.pieces = {}
            for square, symbol in position.items():
                xval, yval = self.square_to_xy(square)
                if len(symbols[symbol]) > 0:
                    piece = symbols[symbol].pop()
                    self.move(piece, xval, yval)
                else:
                    piece = self.create_piece(symbol)
                    self.put(piece, xval, yval)
                self.pieces[square] = piece
            for pieces in symbols.values():
                for piece in pieces:
                    piece.destroy()
#         else:
#             for piece in self.pieces.values():
#                 piece.destroy()
#             self.pieces = {}
#             for square, symbol in position.items():
#                 xval, yval = self.square_to_xy(square)
#                 piece = self.create_piece(symbol)
#                 self.put(piece, xval, yval)
#                 self.pieces[square] = piece

        top, bottom = "B", "W"
        if self.orientation:
            top, bottom = "W", "B"
        board_size = 9 * self.size
        self.move(self.clock.players[top]["nametime"], board_size,
                  int(0.5 * self.size))
        self.move(self.clock.info, board_size, int(3 * self.size))
        self.move(self.clock.players[bottom]["nametime"], board_size,
                  int(5.5 * self.size))
        self.move(self.clock.timing, board_size,
                  int(8.5 * self.size) -
                  self.clock.timing.size_request().height)

    def create_piece(self, symbol):
        """Return a piece which reacts to movements"""
        piece = Gtk.Image()
        filename = (
            os.path.join(config.DATA_DIR, "pieces",
                         "w{0}.svg".format(symbol.lower()))
            if symbol.upper() == symbol else
            os.path.join(config.DATA_DIR, "pieces", "b{0}.svg".format(symbol)))
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            filename, self.size, self.size)
        piece.set_from_pixbuf(pixbuf)
        piece.symbol = symbol
        piece.show()
        return piece

    def limit(self, xval, yval):
        """Pieces can not be dragged out of the board"""
        x_a1, y_a1 = self.square_to_xy("a1")
        x_h8, y_h8 = self.square_to_xy("h8")
        return sorted([xval, x_a1, x_h8])[1], sorted([yval, y_a1, y_h8])[1]

    def remove_drag(self, square):
        """If we are dragging a piece from this square, stop it"""
        if "square" in self.drag and self.drag["square"] == square:
            self.drag["button"] = -1

    def undo_move(self, clicks):
        """Undo a move on the board"""
        piece = self.pieces[clicks[0]]
        xval, yval = self.square_to_xy(clicks[0])
        self.move(piece, xval, yval)
        self.queue_draw()  # after piece moving, redraw

    def make_move(self, move):
        """Move a piece on the board"""

        piece = self.pieces[move["squares"][0]]
        self.moves["last"] = list(move["squares"])
        if "squares2" in move:
            self.moves["last"].extend(move["squares2"])
        xval, yval = self.square_to_xy(move["squares"][1])
        self.remove_drag(move["squares"][0])
        self.move(piece, xval, yval)
        if move["squares"][1] in self.pieces:
            taken_piece = self.pieces[move["squares"][1]]
            self.remove_drag(move["squares"][1])
            taken_piece.destroy()
        self.pieces[move["squares"][1]] = piece
        del self.pieces[move["squares"][0]]

        if "enpassant" in move:
            # the 3rd place is en passant
            piece = self.pieces[move["enpassant"]]
            self.remove_drag(move["enpassant"])
            del self.pieces[move["enpassant"]]
            piece.destroy()
        if "promotion" in move:
            # the 3rd place is promotion piece
            piece.destroy()
            piece = self.create_piece(move["promotion"])
            self.pieces[move["squares"][1]] = piece
            self.put(piece, xval, yval)
        elif "squares2" in move:
            piece = self.pieces[move["squares2"][0]]
            self.remove_drag(move["squares2"][0])
            xval, yval = self.square_to_xy(move["squares2"][1])
            self.move(piece, xval, yval)
            self.pieces[move["squares2"][1]] = piece
            del self.pieces[move["squares2"][0]]
        self.queue_draw()  # after piece moving, redraw

    def xy_to_square(self, xval, yval):
        """Convert xy coordinates to square coordinate"""
        row, col = int(yval) // self.size, int(xval) // self.size
        if self.orientation:
            row, col = 7 - row, 7 - col
        return "{0}{1}".format("abcdefgh"[col], 8 - row)

    def square_to_xy(self, square):
        """Convert square coordinate to xy coordinates"""
        row, col = 8 - int(square[1]), "abcdefgh".index(square[0])
        if self.orientation:
            row, col = 7 - row, 7 - col
        return (col * self.size + self.size // 2,
                row * self.size + self.size // 2)

GObject.signal_new("moved_board", Board, GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, (GObject.TYPE_PYOBJECT,))
