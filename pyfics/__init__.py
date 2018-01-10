#!/usr/bin/env python
# -*-coding: utf-8-*-

"""Main pyfics module"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

from gi.repository import GObject

from .board import Board, Clock
from .interface import Interface
from .moves import MovesTab
from .game import Game, Position
from .player import Player
from .stockfish import Stockfish
from .fics import Fics
from . import config

VERSION = "0.1"
DESCRIPTION = "Play Chess on Freechess.org (FICS)"
AUTHOR = "Sander van Noort"
EMAIL = "Sander.van.Noort@gmail.com"

# GObject.threads_init()
