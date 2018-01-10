#!/usr/bin/env python3
"""PyFics"""

import signal
from gi.repository import Gtk
import logging

import pyfics

signal.signal(signal.SIGINT, signal.SIG_DFL) # listen for ctrl-c
logging.basicConfig(level=getattr(logging, "DEBUG"))

pyfics.Player()
Gtk.main()
