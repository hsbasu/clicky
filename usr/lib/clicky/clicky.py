#!/usr/bin/python3
import gettext
import gi
import locale
import os
import setproctitle
import subprocess
import warnings
import sys
import traceback

# Suppress GTK deprecation warnings
warnings.filterwarnings("ignore")

gi.require_version("Gtk", "3.0")
gi.require_version('XApp', '1.0')
from gi.repository import Gtk, Gdk, Gio, XApp

from common import *

setproctitle.setproctitle("clicky")

# i18n
APP = 'clicky'
LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain(APP, LOCALE_DIR)
gettext.bindtextdomain(APP, LOCALE_DIR)
gettext.textdomain(APP)
_ = gettext.gettext


class MyApplication(Gtk.Application):

    def __init__(self, application_id, flags):
        Gtk.Application.__init__(self, application_id=application_id, flags=flags)
        self.connect("activate", self.activate)

    def activate(self, application):
        windows = self.get_windows()
        if (len(windows) > 0):
            window = windows[0]
            window.present()
            window.show()
        else:
            window = MainWindow(self)
            self.add_window(window.window)
            window.window.show()

class MainWindow():

    def __init__(self, application):

        self.application = application
        self.settings = Gio.Settings(schema_id="org.x.clicky")

        # Main UI
        gladefile = "/usr/share/clicky/clicky.ui"
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP)
        self.builder.add_from_file(gladefile)
        self.window = self.builder.get_object("main_window")
        self.window.set_title(_("Screenshot"))
        self.window.set_icon_name("clicky")
        self.window.set_resizable(False)
        self.stack = self.builder.get_object("stack")

        # CSS
        provider = Gtk.CssProvider()
        provider.load_from_path("/usr/share/clicky/clicky.css")
        screen = Gdk.Display.get_default_screen(Gdk.Display.get_default())
        Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Widget signals
        self.window.connect("key-press-event",self.on_key_press_event)

        #dark mode
        prefer_dark_mode = self.settings.get_boolean("prefer-dark-mode")
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", prefer_dark_mode)
        self.builder.get_object("darkmode_switch").set_active(prefer_dark_mode)
        self.builder.get_object("darkmode_switch").connect("notify::active", self.on_darkmode_switch_toggled)

        # Menubar
        accel_group = Gtk.AccelGroup()
        self.window.add_accel_group(accel_group)
        menu = self.builder.get_object("main_menu")
        item = Gtk.ImageMenuItem()
        item.set_image(Gtk.Image.new_from_icon_name("preferences-desktop-keyboard-shortcuts-symbolic", Gtk.IconSize.MENU))
        item.set_label(_("Preferences"))
        item.connect("activate", self.open_preferences)
        menu.append(item)
        item = Gtk.ImageMenuItem()
        item.set_image(Gtk.Image.new_from_icon_name("preferences-desktop-keyboard-shortcuts-symbolic", Gtk.IconSize.MENU))
        item.set_label(_("Keyboard Shortcuts"))
        item.connect("activate", self.open_keyboard_shortcuts)
        key, mod = Gtk.accelerator_parse("<Control>K")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        item = Gtk.ImageMenuItem()
        item.set_image(Gtk.Image.new_from_icon_name("help-about-symbolic", Gtk.IconSize.MENU))
        item.set_label(_("About"))
        item.connect("activate", self.open_about)
        key, mod = Gtk.accelerator_parse("F1")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        item = Gtk.ImageMenuItem(label=_("Quit"))
        image = Gtk.Image.new_from_icon_name("application-exit-symbolic", Gtk.IconSize.MENU)
        item.set_image(image)
        item.connect('activate', self.on_menu_quit)
        key, mod = Gtk.accelerator_parse("<Control>Q")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>W")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        menu.show_all()

        self.window.show()

        self.builder.get_object("go_back_button").hide()
        self.builder.get_object("go_back_button").connect("clicked", self.go_back)

        self.builder.get_object("button_take_screenshot").connect("clicked", self.start_screenshot)

    def start_screenshot(self, widget):
        self.hide_window()
        GObject.timeout_add(200, self.take_screenshot)

    def hide_window(self):
        self.window.hide()
        self.window.set_opacity(0)
        self.window.set_skip_pager_hint(True)
        self.window.set_skip_taskbar_hint(True)

    def show_window(self):
        self.window.show()
        self.window.set_opacity(1)
        self.window.set_skip_pager_hint(False)
        self.window.set_skip_taskbar_hint(False)

    def take_screenshot(self):
        import utils
        if self.builder.get_object("radio_window").get_active():
            mode = SCREENSHOT_MODE_WINDOW
        elif self.builder.get_object("radio_area").get_active():
            mode = SCREENSHOT_MODE_AREA
        else:
            mode = SCREENSHOT_MODE_DESKTOP
        include_frame = self.builder.get_object("checkbox_border").get_active()
        include_cursor = self.builder.get_object("checkbox_cursor").get_active()
        pixbuf = utils.get_pixbuf(mode, include_frame, include_cursor)
        self.builder.get_object("screenshot_image").set_from_pixbuf(pixbuf)
        self.builder.get_object("screenshot_image").show()
        self.navigate_to("screenshot_page")
        self.show_window()

    @idle_function
    def navigate_to(self, page, name=""):
        if page == "main_page":
            self.builder.get_object("go_back_button").hide()
        else:
            self.builder.get_object("go_back_button").show()
        self.stack.set_visible_child_name(page)

    def open_preferences(self, widget):
        self.navigate_to("preferences_page")

    def go_back(self, widget):
        self.navigate_to("main_page")

    def open_about(self, widget):
        dlg = Gtk.AboutDialog()
        dlg.set_transient_for(self.window)
        dlg.set_title(_("About"))
        dlg.set_program_name(_("Screenshot"))
        dlg.set_comments(_("Save images of your screen or individual windows"))
        try:
            h = open('/usr/share/common-licenses/GPL', encoding="utf-8")
            s = h.readlines()
            gpl = ""
            for line in s:
                gpl += line
            h.close()
            dlg.set_license(gpl)
        except Exception as e:
            print (e)

        dlg.set_version("__DEB_VERSION__")
        dlg.set_icon_name("clicky")
        dlg.set_logo_icon_name("clicky")
        dlg.set_website("https://www.github.com/linuxmint/clicky")
        def close(w, res):
            if res == Gtk.ResponseType.CANCEL or res == Gtk.ResponseType.DELETE_EVENT:
                w.destroy()
        dlg.connect("response", close)
        dlg.show()

    def open_keyboard_shortcuts(self, widget):
        gladefile = "/usr/share/clicky/shortcuts.ui"
        builder = Gtk.Builder()
        builder.set_translation_domain(APP)
        builder.add_from_file(gladefile)
        window = builder.get_object("shortcuts")
        window.set_title(_("Screenshot"))
        window.show()

    def on_darkmode_switch_toggled(self, widget, key):
        prefer_dark_mode = widget.get_active()
        self.settings.set_boolean("prefer-dark-mode", prefer_dark_mode)
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", prefer_dark_mode)

    def on_menu_quit(self, widget):
        self.application.quit()

    def on_key_press_event(self, widget, event):
        persistant_modifiers = Gtk.accelerator_get_default_mod_mask()
        modifier = event.get_state() & persistant_modifiers
        ctrl = modifier == Gdk.ModifierType.CONTROL_MASK
        shift = modifier == Gdk.ModifierType.SHIFT_MASK

        if ctrl and event.keyval == Gdk.KEY_r:
            # Ctrl + R
            pass
        elif ctrl and event.keyval == Gdk.KEY_f:
            # Ctrl + F
            pass
        elif event.keyval == Gdk.KEY_F11:
             # F11..
             pass

if __name__ == "__main__":
    application = MyApplication("org.x.clicky", Gio.ApplicationFlags.FLAGS_NONE)
    application.run()
