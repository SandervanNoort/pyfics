#!/usr/bin/env python3
# -*-coding: utf-8-*-

"""queueing output"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

import sys
import subprocess
import threading
import time
import os
import signal

from six.moves import queue  # pylint: disable=F0401


def parse(proc):
    """put output in queue"""
    line = ""
    while proc.poll() is None:
        char = proc.stdout.read(1)
        if char == "\n":
            print(line)
            line = ""
        else:
            line += char

def main():
    """main loop"""
    proc = subprocess.Popen(
        ["stockfish"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE,
        bufsize=1,
        close_fds="posix" in sys.builtin_module_names,
        universal_newlines=True)
    thread = threading.Thread(target=parse, args=(proc,))
    thread.daemon = True  # thread dies with the program
    thread.start()

    proc.stdin.write("position startpos\n")
    proc.stdin.write("go infinite\n")
    running = True
    while True:
        time.sleep(5)
        os.kill(proc.pid, signal.SIGSTOP if running else signal.SIGCONT)
        running = not running
        print("running" if running else "stopped")
    print("end")

if __name__ == "__main__":
    main()
