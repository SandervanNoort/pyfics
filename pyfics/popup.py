#!/usr/bin/env python
# -*-coding: utf-8-*-

"""A button with a dropdown menu"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

from gi.repository import Gtk
from gi.repository import GObject
import logging

from . import tools

logger = logging.getLogger(__name__)

class PopupButton(Gtk.ToggleButton):
    # pylint: disable=R0904
    # R0904 = Too many public methods (Gtk.Widget)
    """A normal toggle button with popup menu"""
    def __init__(self, menu, label=""):
        GObject.GObject.__init__(self)
        self.menu = menu
        self._menu_selection_done_id = self.menu.connect(
            "selection-done", self._on_menu_selection_done)
        self.connect('toggled', self._on_toggled)
        self.orientation = "top"
        if label != "":
            self.set_label(label)
        self.menu.show_all()

    def set_menu(self, menu):
        """Set the menu for the toggle button"""
        if getattr(self, '_menu_selection_done_id', None):
            self.menu.disconnect(self._menu_selection_done_id)
        self.menu = menu
        self._menu_selection_done_id = self.menu.connect(
            "selection-done", self._on_menu_selection_done)
        self.menu.show_all()

    def set_orientation(self, orientation):
        """Set whether the menu goes up or down"""
        if orientation not in ("top", "bottom"):
            logger.error("Unknown orientation: {0}".format(orientation))
            orientation = "top"
        self.orientation = orientation

    def _get_text(self):
        """Return the label"""
        return tools.to_unicode(self.get_label())

    def _set_text(self, value):
        """Set the label"""
        self.set_label(value)
        # text = property(_get_text, _set_text)

    def _calculate_popup_pos(self, menu, _data):
        """Calculate the location of the menu when expanded"""
        window_xy = self.get_window().get_origin()
        widget_alloc = self.get_allocation()

        xval = widget_alloc.x + window_xy[1]
        yval = widget_alloc.y + window_xy[2]

        if self.orientation == "top":
            button_height = self.size_request().height
            yval += button_height
        elif self.orientation == "bottom":
            menu_height = menu.size_request().height
            yval -= menu_height
        return (xval, yval, True)

    def popdown(self):
        """Collapse the menu"""
        self.menu.popdown()
        return True

    def popup(self):
        """Expand the menu"""
        self.menu.popup(None, None, self._calculate_popup_pos, 0, 0, 0)

    def _on_menu_selection_done(self, _menu):
        """Return button to normal when menu is collapsed"""
        self.set_active(False)

    def _on_toggled(self, togglebutton):
        """The button toggled"""
        assert self is togglebutton

        if self.get_active():
            self.popup()
        else:
            self.popdown()
