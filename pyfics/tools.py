#!/usr/bin/env python3
# -*-coding: utf-8-*-

"""Tools"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

# tools: *.py

# pylint: disable=C0302

import six
import chardet
import validate
import configobj
import numpy


def to_unicode(output):
    """Autodetect unicode"""
    if isinstance(output, six.text_type):
        # already unicode
        return output
    elif output is None or len(output) == 0:
        return ""
    elif isinstance(output, (six.string_types, six.binary_type)):
        detect = chardet.detect(output)
        return output.decode(detect["encoding"])
    else:
        return "{0}".format(output)


def cobj_check(settings, exception=None, copy=False):
    """Check for errors in config file"""

    if not exception:
        exception = Exception

    validator = validate.Validator()

    def numpy_array(val):
        """Define float list"""
        float_list = validator.functions["float_list"](val)
        return numpy.array(float_list)
    validator.functions["numpy_array"] = numpy_array

    results = settings.validate(validator, copy=copy, preserve_errors=True)
    if results is not True:
        output = "{0}: \n".format(
            settings.filename if settings.filename is not None else
            "configobj")
        for (section_list, key, error) in configobj.flatten_errors(
                settings, results):
            if key is not None:
                val = settings
                for section in section_list:
                    val = val[section]
                val = val[key] if key in val else "<EMPTY>"
                output += "   [{sections}], {key}='{val}' ({error})\n".format(
                    sections=', '.join(section_list),
                    key=key,
                    val=val,
                    error=error)
            else:
                output += "Missing section: {0}\n".format(
                    ", ".join(section_list))
        raise exception(output)


class Cache(object):
    """Class which save output when called"""
    # (too few public methods) pylint: disable=R0903

    def __init__(self):
        self.output = None

    def __call__(self, output):
        self.output = output
        return output
