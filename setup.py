#!/usr/bin/env python

"""Install script for pyfics"""

import sys
import os
import re

from distutils.core import setup
import distutils.command.build_py


def substitute(fname, values):
    """Substitute the variable declarations"""
    with open(os.path.join(fname), "r") as fobj:
        contents = fobj.read()
        for key, value in values.items():
            contents = re.sub("{0} *=.*".format(key),
                              "{0} = \"{1}\"".format(key, value),
                              contents)
    with open(os.path.join(fname), "w") as fobj:
        fobj.write(contents)


def data_include(install_root, local_root):
    """Include all files from a subdirectory"""
    data_files = []
    for dirpath, _dirnames, fnames in os.walk(local_root):
        install_dir = os.path.join(install_root,
                                   os.path.relpath(dirpath, local_root))
        files = [os.path.join(dirpath, fname) for fname in fnames]
        data_files.append((install_dir, files))
    return data_files


class build_py(distutils.command.build_py.build_py):
    "build python modules"

    # pylint: disable=R0904,C0103
    def run(self):
        distutils.command.build_py.build_py.run(self)
        substitute(os.path.join(self.build_lib, "pyfics/__init__.py"),
                   {"CONFIG_DIR": "/etc/pyfics",
                    "DATA_DIR": os.path.join(sys.prefix, "share", "pyfics"),
                    "ICON": "pyfics"})


setup(name="pyfics",
      cmdclass={"build_py": build_py},
      version="0.1",
      description="Play Chess on Freechess.org (FICS)",
      author="Sander van Noort",
      author_email="Sander.van.Noort@gmail.com",
      url="http://www.vnoort.info/",
      packages=["pyfics"],
      scripts=["bin/pyfics"],
      data_files=(data_include("/etc/pyfics", "config") +
                  data_include("share/pyfics", "data") +
                  [("share/applications", ["pyfics.desktop"]),
                   ("share/icons/hicolor/scalable/apps",
                    ["icons/pyfics.svg"])]))
