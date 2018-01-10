#!/usr/bin/env python
# -*-coding: utf-8-*-

"""PyFics window"""

from __future__ import (division, absolute_import, unicode_literals,
                        print_function)

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
import sys  # pylint: disable=W0611
import os
import logging

from . import popup, config

logger = logging.getLogger(__name__)


class Interface(Gtk.Window):
    """The interface of the program, where all elements are combined"""
    # (too many public methods) pylint: disable=R0904

    def __init__(self, board, movestab):
        super(Interface, self).__init__()

        css_provider = Gtk.CssProvider()
        screen = Gdk.Screen.get_default()
        css_provider.load_from_path(
            os.path.join(config.CONFIG_DIR, "settings.css"))
        context = Gtk.StyleContext()
        context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        if "." in config.ICON:
            self.set_icon_from_file(config.ICON)
        else:
            self.set_icon_name(config.ICON)
        self.set_default_size(config.SETTINGS["window"]["width"],
                              config.SETTINGS["window"]["height"])

        # fics tab
        fics_tab = Gtk.VBox()
        fics_terminal, self.fics_buffer = self.get_terminal()
        vadj = fics_terminal.get_vadjustment()
        vadj.autoscroll = True
        vadj.connect("changed", self.on_changed)
        vadj.connect("value-changed", self.on_value_changed)
        self.entry = Gtk.Entry()
        self.entry.connect("activate", self.on_entry)
        fics_tab.pack_start(fics_terminal, True, True, 0)
        fics_tab.pack_start(self.entry, False, True, 0)

        # right panel
        right_panel = Gtk.Notebook()
        right_panel.append_page(fics_tab, Gtk.Label("Fics"))
        right_panel.append_page(movestab, Gtk.Label("Moves"))

        # board panel
        board_panel = Gtk.VBox()
        self.button_panel = Gtk.HBox()
        self.promotion_button = self.get_promotion_button()
        board_panel.pack_start(self.button_panel, False, True, 0)
        board_panel.pack_start(board, True, True, 0)

        # join board and right panel
        self.hpane = Gtk.HPaned()
        self.hpane.add(board_panel)
        self.hpane.add(right_panel)
        self.hpane.set_position(config.SETTINGS["window"]["pane"])

        # add a top menu
        menu_box = Gtk.VBox(False, 0)
        menubar = self.get_menubar()
        menu_box.pack_start(menubar, False, False, 0)
        menu_box.pack_end(self.hpane, True, True, 0)

        self.show_move_buttons()

        self.add(menu_box)
        self.show_all()

        right_panel.set_current_page(0)
        self.entry.grab_focus()
        self.connect("size-allocate", self.on_size_allocate)

    def on_size_allocate(self, _widget, cairo):
        """New height/width in settings"""
        config.SETTINGS["window"]["width"] = cairo.width
        config.SETTINGS["window"]["height"] = cairo.height

    def show_game_buttons(self):
        """Buttons during a fics game"""

        for child in self.button_panel.get_children():
            child.destroy()
        for action in ["Draw", "Resign", "Flag", "Takeback",
                       "Adjourn", "Abort"]:
            button = Gtk.Button(action)
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.connect("clicked", self.on_ficsbutton, action)
            self.button_panel.pack_start(button, True, True, 0)
        self.button_panel.pack_start(self.promotion_button, False, True, 0)
        self.button_panel.show_all()

    def on_ficsbutton(self, _widget, cmd):
        """A fics cmd button was clicked"""
        self.emit("command", cmd)

    def on_entry(self, entry):
        """A console command was entered"""
        self.emit("command", entry.get_text())
        entry.set_text("")
        entry.grab_focus()

    def on_step(self, _widget, stepsize):
        """A move button is clicked"""
        self.emit("step", stepsize)

    def show_move_buttons(self):
        """Button after a game"""

        for child in self.button_panel.get_children():
            child.destroy()
        for icon, stepsize in [("<<", "start"), ("<", "back"),
                               (">", "forward"), (">>", "end")]:
            button = Gtk.Button(icon)
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.connect("clicked", self.on_step, stepsize)
            self.button_panel.pack_start(button, True, True, 0)
        self.button_panel.pack_start(self.promotion_button, False, True, 0)
        self.button_panel.show_all()

    def on_login_dialog(self, _widget):
        """Show a dialog for fics login/passwor"""

        dialog = Gtk.Dialog("Login")
        action_area = dialog.get_action_area()
        content_area = dialog.get_content_area()

        cancel_button = Gtk.Button("Cancel")
        action_area.add(cancel_button)
        login_button = Gtk.Button("Login")
        action_area.pack_start(login_button, True, True, 0)

        table = Gtk.Table(rows=2, columns=2)
        table.attach(Gtk.Label("Login"), 0, 1, 0, 1)
        table.attach(Gtk.Label("Password"), 0, 1, 1, 2)
        login_entry = Gtk.Entry()
        login_entry.set_text(config.SETTINGS["fics"]["user"])
        password_entry = Gtk.Entry()
        password_entry.set_text(config.SETTINGS["fics"]["password"])
        table.attach(login_entry, 1, 2, 0, 1)
        table.attach(password_entry, 1, 2, 1, 2)

        content_area.pack_start(table, True, True, 0)

        login_button.connect("clicked", self.on_login,
                             (dialog, login_entry, password_entry))
        cancel_button.connect("clicked", lambda w: dialog.destroy())
        dialog.show_all()

    def on_login(self, _widget, data):
        """Connect to fics in a thread"""

        dialog, login_entry, password_entry = data
        login = login_entry.get_text()
        password = password_entry.get_text()
        config.SETTINGS["fics"]["user"] = login
        config.SETTINGS["fics"]["password"] = password
        dialog.destroy()
        self.emit("login", None)

    @staticmethod
    def get_terminal():
        """Return a scrollable textview"""
        terminal = Gtk.ScrolledWindow()
        terminal.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        textview = Gtk.TextView()
        textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        terminal.add(textview)
        return terminal, textview.get_buffer()

    def get_promotion_button(self):
        """Get a dropdown button for the promotion piece"""

        menu = Gtk.Menu()
        for promotion in ["Q", "R", "N", "B"]:
            item = Gtk.ImageMenuItem(label="")
            image = Gtk.Image()
            filename = os.path.join(config.DATA_DIR, "pieces",
                                    "w{0}.svg".format(promotion.lower()))
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename, 15, 15)
            image.set_from_pixbuf(pixbuf)
            item.set_image(image)
            item.set_always_show_image(True)
            item.set_reserve_indicator(False)
            menu.add(item)
            item.connect("activate", self.on_promotion, promotion)

        button = popup.PopupButton(menu)
        button.set_relief(Gtk.ReliefStyle.NONE)
        image = Gtk.Image()
        filename = os.path.join(
            config.DATA_DIR, "pieces",
            "w{0}.svg".format(config.PROMOTION.lower()))
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename, 15, 15)
        image.set_from_pixbuf(pixbuf)
        button.add(image)
        return button

    def on_promotion(self, _widget, promotion):
        """Set the promotion piece"""

        filename = os.path.join(
            config.DATA_DIR, "pieces", "w{0}.svg".format(promotion.lower()))
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(filename, 15, 15)
        self.promotion_button.get_child().set_from_pixbuf(pixbuf)
        config.PROMOTION = promotion

    def get_menubar(self):
        """Return the menu bar"""
        menubar = Gtk.MenuBar()

        item = Gtk.MenuItem("Pyfics")
        submenu = Gtk.Menu()
        subitem = Gtk.MenuItem("Connect to FICS")
        subitem.connect("activate", self.on_login_dialog)
        submenu.append(subitem)

        subitem = Gtk.MenuItem("Exit")
        subitem.connect("activate", Gtk.main_quit)
        submenu.append(subitem)

        item.set_submenu(submenu)
        menubar.append(item)

        for (name, actions) in config.SETTINGS["menu"].items():
            item = Gtk.MenuItem(name)
            submenu = Gtk.Menu()
            for action in actions:
                subitem = Gtk.MenuItem(action)
                subitem.connect("activate", self.on_ficsbutton, action)
                submenu.append(subitem)
            item.set_submenu(submenu)
            menubar.append(item)

        return menubar

    def on_changed(self, adj):
        """The fics terminal has new input, scroll if at bottom"""
        if adj.autoscroll:
            adj.set_value(adj.get_upper() - adj.get_page_size())

    def on_value_changed(self, adj):
        """The fics terminal was scrolled manually"""
        if adj.get_upper() - adj.get_page_size() != adj.get_value():
            adj.autoscroll = False
        else:
            adj.autoscroll = True

GObject.signal_new("step", Interface, GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, (GObject.TYPE_PYOBJECT,))
GObject.signal_new("command", Interface, GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, (GObject.TYPE_PYOBJECT,))
GObject.signal_new("login", Interface, GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, (GObject.TYPE_PYOBJECT,))
