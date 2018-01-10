#!/usr/bin/env python
# -*-coding: utf-8-*-

"""Main pyfics module"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

import os
import configobj
import sys  # pylint: disable=W0611

from . import tools

ROOT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_DIR = os.path.join(ROOT, "config")
ICON = os.path.join(DATA_DIR, "icons", "pyfics.svg")

LOCAL_DIR = os.path.expanduser("~/.config/pyfics")
if not os.path.exists(LOCAL_DIR):
    os.makedirs(LOCAL_DIR)

SETTINGS = configobj.ConfigObj(
    os.path.join(LOCAL_DIR, "settings.ini"),
    configspec=os.path.join(CONFIG_DIR, "pyfics.spec"))
tools.cobj_check(SETTINGS)
SETTINGS["rgb_"] = {}
for key, values in SETTINGS["rgb"].items():
    SETTINGS["rgb_"][key] = [val / 255 for val in values]

INFO_WIDTH = 150
PROMOTION = "Q"
SPEED = 1
THREADS = 1
MAX_DIF = 2  # the maximum drop in score
LOST = 3  # a score at which position is lost

INFO = ["info", "depth", "seldepth", "time", "nodes", "pv", "multipv", "score",
        "currmove", "currmovenumber", "hashfull", "nps", "tbhits", "cpuload",
        "string", "refutation", "currline"]
OPTION = ["option", "name", "type", "default", "min", "max"]

START = (
    "<12> rnbqkbnr pppppppp -------- --------" +
    " -------- -------- PPPPPPPP RNBQKBNR" +
    " W -1 1 1 1 1 0 51 WHITE BLACK 2 0 0 39 39 0 0 1 none (0:00) none 0 0 0")

STYLE12 = ["style12"] + list(range(8, 0, -1)) \
    + ["next_color", "double_pawn_move", "white_castle_short",
       "white_castle_long", "black_castle_short", "black_castle_long",
       "moves_irreversible", "game_number", "white_name",
       "black_name", "relation", "initial_time", "increment",
       "white_material", "black_material", "white_time", "black_time",
       "next_move_number", "notation", "move_time", "last_move_short",
       "orientation", "extra1", "extra2"]
PIECE_VALUE = {"Q": 9, "P": 1, "N": 3, "B": 3, "R": 5, "K": 0}
