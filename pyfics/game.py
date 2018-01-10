#!/usr/bin/env python
# -*-coding: utf-8-*-

"""PyFics"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

import re
import sys  # pylint: disable=W0611
import copy
import logging
import collections

from .exceptions import PyficsError
from . import config

logger = logging.getLogger(__name__)


def get_color(symbol):
    """The color of the symbol"""
    return "W" if symbol.upper() == symbol else "B"


def switch_color(color):
    """Return opposite color"""
    return "W" if color == "B" else "B"


def get_short_move(notation, move):
    """short move notation"""
    if "/" not in notation:
        short = notation
    else:
        if move["letter"] == "P":
            if "taken" in move:
                short = "{0}x{1}".format(
                    move["squares"][0][0], move["squares"][1])
            else:
                short = move["squares"][1]
        else:
            if "taken" in move:
                short = "{0}x{1}".format(
                    move["letter"], move["squares"][1])
            else:
                short = "{0}{1}".format(
                    move["letter"], move["squares"][1])
        if "promotion" in move:
            # promotion
            short += "={0}".format(move["promotion"].upper())
    return short


def notation_to_sf_move(notation, color):
    """Convert notation to sf-compatible move"""
    if notation == "none":
        return ""
    if notation == "o-o" and color == "W":
        return "e1g1"
    if notation == "o-o" and color == "B":
        return "e8g8"
    if notation == "o-o-o" and color == "W":
        return "e1c1"
    if notation == "o-o-o" and color == "B":
        return "e8c8"
    return notation.split("/")[1].replace("-", "")


def rowcol_to_square(row, col, color):
    """Convert row/col numbers to square"""
    # row: 1..8, col: 1..8
    row, col = row - 1, col - 1
    if color == "B":
        row, col = 7 - row, 7 - col
    return "%s%d" % ("abcdefgh"[col], row + 1)


def square_to_rowcol(square, color):
    """Convert square to row/col number"""
    # row: 1..8, col: 1..8
    row = int(square[1]) - 1
    col = "abcdefgh".index(square[0])
    if color == "B":
        row, col = 7 - row, 7 - col
    return row + 1, col + 1


class Position(object):
    """The current position on the board"""

    def __init__(self, style12):
        self.props = {}
        for name, val in zip(config.STYLE12, style12.split(" ")):
            try:
                val = int(val)
            except ValueError:
                pass
            self.props[name] = val

        self.halfmove = (2 * (self.props["next_move_number"] - 1) +
                         (self.props["next_color"] == "B"))
        self.board = {
            "{0}{1}".format(coord, number): symbol
            for number in range(1, 9)
            for coord, symbol in zip("abcdefgh", self.props[number])
            if symbol != "-"}
        self.props["sf_move"] = notation_to_sf_move(
            self.props["notation"], switch_color(self.props["next_color"]))

    def check_move(self, move, check=True):
        """Check if the proposed move is legal"""

        if move["color"] != self.props["next_color"]:
            raise PyficsError("{0} is to move".format(
                "White" if move["color"] == "B" else "Black"))

        if not (move["squares"][0] in self.board and
                self.board[move["squares"][0]] == move["symbol"]):
            raise PyficsError(
                "No piece {0} on {1}".format(
                    move["symbol"], move["squares"][0]))

        if ("squares2" in move and not (
                move["squares2"][0] in self.board and
                self.board[move["squares2"][0]] == move["symbol2"])):
            raise PyficsError(
                "No piece {0} on {1}".format(
                    move["symbol2"], move["squares2"][0]))

        if "taken" in move:
            color_taken = get_color(move["taken"])
            if color_taken == move["color"]:
                raise PyficsError("Cannot eat own color")

        self.check_movement(move)
        self.check_blocking(move)

        # add "+" to short notation if checked
        if check:
            new_position = copy.deepcopy(self)
            new_position.make_move(move)
            if new_position.is_check():
                raise PyficsError("You're checked")

    @staticmethod
    def check_movement(move):
        """Check if the piece moves according to its characteristics"""

        if (move["letter"] == "B" and
                not (move["col_start"] + move["row_start"] ==
                     move["col_end"] + move["row_end"] or
                     move["col_start"] - move["row_start"] ==
                     move["col_end"] - move["row_end"])):
            raise PyficsError("Illegal bishop move")
        elif (move["letter"] == "R" and
              not (move["col_start"] == move["col_end"] or
                   move["row_start"] == move["row_end"])):
            raise PyficsError("Illegal rook move")
        elif (move["letter"] == "N" and
              not ((abs(move["col_end"] - move["col_start"]),
                    abs(move["row_end"] - move["row_start"])) in
                   [(1, 2), (2, 1)])):
            raise PyficsError("Illegal knight move")
        elif (move["letter"] == "K" and
              "squares2" not in move and  # exclude rocade
              not (abs(move["col_end"] - move["col_start"]) <= 1 and
                   abs(move["row_end"] - move["row_start"]) <= 1)):
            raise PyficsError("Illegal king move")
        elif (move["letter"] == "Q" and
              not (move["col_start"] + move["row_start"] ==
                   move["col_end"] + move["row_end"] or
                   move["col_start"] - move["row_start"] ==
                   move["col_end"] - move["row_end"] or
                   move["col_start"] == move["col_end"] or
                   move["row_start"] == move["row_end"])):
            raise PyficsError("Illegal queen move")
        elif move["letter"] == "P":
            # pawn capture
            if "enpassant" in move:
                pass
            elif "taken" in move:
                if not (move["row_end"] - move["row_start"] == 1 and
                        abs(move["col_start"] - move["col_end"]) == 1):
                    raise PyficsError("Illegal pawn capture")
            else:
                if not (move["col_start"] == move["col_end"] and (
                        (move["row_end"] - move["row_start"] == 1) or
                        (move["row_end"] == 4 and move["row_start"] == 2))):
                    raise PyficsError("Illegal pawn move")

    def check_blocking(self, move):
        """Check if pieces are blocking the way"""
        if move["letter"] == "N":
            return

        col_range = (range(move["col_start"] + 1, move["col_end"])
                     if move["col_end"] > move["col_start"] else
                     range(move["col_start"] - 1, move["col_end"], -1))
        row_range = (range(move["row_start"] + 1, move["row_end"])
                     if move["row_end"] > move["row_start"] else
                     range(move["row_start"] - 1, move["row_end"], -1))
        if move["row_start"] == move["row_end"]:
            fields = [(move["row_start"], col) for col in col_range]
        elif move["col_start"] == move["col_end"]:
            fields = [(row, move["col_start"]) for row in row_range]
        else:
            fields = zip(row_range, col_range)
        for row, col in fields:
            square = rowcol_to_square(row, col, move["color"])
            if square in self.board:
                raise PyficsError("Piece is blocking on {0}".format(square))

    def make_move(self, move):
        """Make a move and update style12"""

        self.props["notation"] = move["notation"]
        self.props["last_move_short"] = move["short"]
        self.props["sf_move"] = move["sf_move"]

        self.props["next_color"] = switch_color(self.props["next_color"])
        if self.props["relation"] in (1, -1):
            self.props["relation"] *= -1

        # castle
        if "h1" in move["squares"] or "e1" in move["squares"]:
            self.props["white_castle_short"] = 0
        if "a1" in move["squares"] or "e1" in move["squares"]:
            self.props["white_castle_long"] = 0
        if "h8" in move["squares"] or "e8" in move["squares"]:
            self.props["black_castle_short"] = 0
        if "a8" in move["squares"] or "e8" in move["squares"]:
            self.props["black_castle_long"] = 0

        self.props["double_pawn_move"] = (
            "abcdefgh".index(move["squares"][0][0])
            if (move["letter"] == "P" and
                abs(int(move["squares"][1][1]) -
                    int(move["squares"][0][1])) == 2) else
            0-1)  # pep8 cannot start with -

        self.props["moves_irreversible"] = (
            0 if move["letter"] == "P" or "taken" in move else
            1)

        if move["color"] == "B":
            self.props["next_move_number"] += 1

        # capture piece
        if "taken" in move:
            self.props["{0}_material".format(
                "black" if move["color"] == "W" else "white")] -= (
                    config.PIECE_VALUE[move["taken"].upper()])

        if "promotion" in move:
            self.props["{0}_material".format(
                "black" if move["color"] == "B" else "white")] += (
                    config.PIECE_VALUE[move["promotion"].upper()] - 1)

        self.board[move["squares"][1]] = self.board.pop(move["squares"][0])
        if "squares2" in move:
            self.board[move["squares2"][1]] = self.board.pop(
                move["squares2"][0])
        if "enpassant" in move:
            del self.board[move["enpassant"]]
        if "promotion" in move:
            self.board[move["squares"][1]] = move["promotion"]

        # this has to be done after board update
        if self.is_check(True):
            self.props["last_move_short"] += "+"
        self.halfmove += 1

    def is_check(self, switch=False):
        """In the current position, is color checked"""

        if switch:
            new_position = copy.deepcopy(self)
            new_position.props["next_color"] = switch_color(
                new_position.props["next_color"])
            return new_position.is_check()

        checked_color = switch_color(self.props["next_color"])
        king = "K" if checked_color == "W" else "k"
        king_pos = [square for square, symbol in self.board.items()
                    if symbol == king][0]
        for square, symbol in self.board.items():
            notation = "{0}/{1}-{2}".format(symbol.upper(), square, king_pos)
            try:
                move = self.notation_to_move(notation)
                self.check_move(move, check=False)
                return True
            except PyficsError:
                pass
        return False

    def clicks_to_notation(self, clicks):
        """Return notation based on the clicks"""
        clicks = tuple(clicks)
        if clicks[0] in self.board:
            symbol = self.board[clicks[0]]
        else:
            raise PyficsError("No piece to move on %s" % clicks[0])

        if symbol.upper() == "K" and clicks in [("e1", "g1"), ("e8", "g8")]:
            notation = "o-o"
        elif symbol.upper() == "K" and clicks in [("e1", "c1"), ("e8", "c8")]:
            notation = "o-o-o"
        else:
            notation = "{0}/{1}-{2}".format(
                symbol.upper(), clicks[0], clicks[1])
            # add promotion piece
            if symbol.upper() == "P" and int(clicks[1][1]) in (1, 8):
                notation += "=%s" % config.PROMOTION
        return notation

    def get_style12(self):
        """return style12_string"""

        # convert position to rows
        for number in range(1, 9):
            self.props[number] = ""
            for letter in "abcdefgh":
                square = "{0}{1}".format(letter, number)
                if square in self.board:
                    self.props[number] += self.board[square]
                else:
                    self.props[number] += "-"
        return " ".join(["%s" % self.props[key] for key in config.STYLE12])

    def get_fen(self):
        """Return fen string"""
        fens = []

        lines = []
        for number in range(8, 0, -1):
            line = ""
            for letter in "abcdefgh":
                square = "{0}{1}".format(letter, number)
                line += self.board[square] if square in self.board else "-"
            lines.append(line)
        board = "/".join(lines)
        board = re.sub("(-+)", lambda match: str(len(match.group())), board)
        fens.append(board)

        fens.append(self.props["next_color"].lower())

        castle = (
            "K" if self.props["white_castle_short"] else "" +
            "Q" if self.props["white_castle_long"] else "" +
            "k" if self.props["black_castle_short"] else "" +
            "q" if self.props["black_castle_long"] else "")
        if castle == "":
            castle = "-"
        fens.append(castle)

        if self.props["double_pawn_move"] >= 0:
            letter = "abcdefgh"[self.props["double_pawn_move"]]
            square = (
                "{0}6".format(letter) if self.props["next_color"] == "W" else
                "{0}3".format(letter))
        else:
            square = "-"
        fens.append(square)

        fens.append(str(self.props["moves_irreversible"]))
        fens.append(str(self.props["next_move_number"]))

        return " ".join(fens)

    def get_board(self):
        """ASCII board"""
        lines = []
        for number in range(8, 0, -1):
            lines.append(33 * "-")
            line = "|"
            for letter in "abcdefgh":
                square = "{0}{1}".format(letter, number)
                line += " {0} |".format(
                    self.board[square] if square in self.board else
                    " ")
            lines.append(line)
        lines.append(33 * "-")
        return "\n".join(lines)

    def notation_to_move(self, notation):
        """Transform the notation to the actual moves to be excecuted"""

        move = {"notation": notation}
        if notation == "none":
            return move

        move["color"] = self.props["next_color"]
        if notation == "o-o" and move["color"] == "W":
            move["squares"] = ["e1", "g1"]
            move["symbol"] = "K"
            move["squares2"] = ["h1", "f1"]
            move["symbol2"] = "R"
        elif notation == "o-o" and move["color"] == "B":
            move["squares"] = ["e8", "g8"]
            move["symbol"] = "k"
            move["squares2"] = ["h8", "f8"]
            move["symbol2"] = "r"
        elif notation == "o-o-o" and move["color"] == "W":
            move["squares"] = ["e1", "c1"]
            move["symbol"] = "K"
            move["squares2"] = ["a1", "d1"]
            move["symbol2"] = "R"
        elif notation == "o-o-o" and move["color"] == "B":
            move["squares"] = ["e8", "c8"]
            move["symbol"] = "k"
            move["squares2"] = ["a8", "d8"]
            move["symbol2"] = "r"
        else:
            letter, squares = re.split("/", notation)
            move["symbol"] = letter if move["color"] == "W" else letter.lower()

            squares = re.split("-|=", squares)

            # a possible promotion piece, get 3rd place in moves
            if len(squares) == 3:
                move["promotion"] = squares.pop()
            move["squares"] = squares

        move["letter"] = move["symbol"].upper()
        move["row_start"], move["col_start"] = square_to_rowcol(
            move["squares"][0], move["color"])
        move["row_end"], move["col_end"] = square_to_rowcol(
            move["squares"][1], move["color"])

        if (move["letter"] == "P" and
                move["row_start"] == 5 and move["row_end"] == 6 and
                abs(move["col_end"] - move["col_start"]) == 1 and
                "abcdefgh".index(move["squares"][1][0]) ==
                self.props["double_pawn_move"]):
            move["enpassant"] = rowcol_to_square(
                5, move["col_end"], move["color"])
            move["taken"] = self.board[move["enpassant"]]

        if move["squares"][1] in self.board:
            move["taken"] = self.board[move["squares"][1]]

        move["short"] = get_short_move(notation, move)
        move["sf_move"] = notation_to_sf_move(notation, move["color"])
        return move


class Game(object):
    """Holds the complete game"""
    # (too many public methods) pylint: disable=R0904

    def __init__(self):
        self.setup()

    def setup(self):
        """Reset the game"""
        self.history = {}
        self.moves = {}
        self.info = collections.defaultdict(dict)
        self.position = Position(config.START)
        self.set_position()

    def clicks_to_notation(self, clicks):
        """call self.position"""
        return self.position.clicks_to_notation(clicks)

    def notation_to_move(self, notation):
        """call self.position"""
        return self.position.notation_to_move(notation)

    def check_move(self, move):
        """call self.position"""
        return self.position.check_move(move)

    def get(self, key):
        """Get property from the current position"""
        return (self.position.board if key == "board" else
                self.position.halfmove if key == "halfmove" else
                self.position.props[key])

    def set_position(self, position=None):
        """Set the position and fill history"""
        if position is not None:
            self.position = position

        halfmove = self.position.halfmove
        self.history[halfmove] = copy.deepcopy(self.position)
        self.moves[halfmove] = self.get("sf_move")

#         if halfmove in self.history:
#             orig_style12 = self.history[halfmove].get_style12()
#             new_style12 = self.position.get_style12()
#             if orig_style12 != new_style12:
#                 logger.error(
#                     "Style12\nnew: {new}\norig: {orig}\n".format(
#                         orig=orig_style12, new=new_style12))

        # Delete previous history
        for prev_halfmove in list(self.history.keys()):
            if prev_halfmove > halfmove:
                del self.history[prev_halfmove]
                del self.moves[prev_halfmove]

    def make_move(self, move):
        """Make a move"""
        logger.debug("make_move: {0}".format(move["notation"]))
        self.position.make_move(move)
        self.set_position()

    def get_history(self, halfmove):
        """Return a previous position"""
        return copy.deepcopy(self.history[halfmove])

    def get_halfmoves(self):
        """Return all the moves in the history"""
        return sorted(self.history.keys())

    def update_info(self, info):
        """New stockfish info received
            update previous scores and add prev_pscore"""

        halfmove = info["halfmove"]
        if "time" not in info:
            logger.debug("No time available in sf_info: {0}".format(info))
            # not a pv result
            return
        if ("time" in self.info[halfmove] and
                self.info[halfmove]["time"] > info["time"]):
            return
        self.info[halfmove].update(info)

        # setting pscore_prev from previous move (so we can color it)
        if "pscore" in self.info[halfmove - 1]:
            self.info[halfmove]["pscore_prev"] = \
                self.info[halfmove - 1]["pscore"]

        # setting pscore_prev for next move (so we can color it)
        self.info[halfmove + 1]["pscore_prev"] = info["pscore"]
#         if "pscore" in self.info[halfmove + 1]:
#             yield self.info[halfmove + 1]
        return halfmove
