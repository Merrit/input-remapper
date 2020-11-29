#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


import sys
import time
import os
import unittest
import evdev
from unittest.mock import patch
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

import gi
import shutil
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from keymapper.state import custom_mapping, system_mapping
from keymapper.paths import CONFIG
from keymapper.config import config

from test import tmp, pending_events, Event, uinput_write_history_pipe, \
    clear_write_history


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()


def launch(argv=None, bin_path='/bin/key-mapper-gtk'):
    """Start key-mapper-gtk with the command line argument array argv."""
    if not argv:
        argv = ['-d']

    with patch.object(sys, 'argv', [''] + [str(arg) for arg in argv]):
        loader = SourceFileLoader('__main__', bin_path)
        spec = spec_from_loader('__main__', loader)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

    gtk_iteration()

    return module.window


class FakeDropdown(Gtk.ComboBoxText):
    def __init__(self, name):
        self.name = name

    def get_active_text(self):
        return self.name

    def get_active_id(self):
        return self.name


class Integration(unittest.TestCase):
    """For tests that use the window.

    Try to modify the configuration only by calling functions of the window.
    """
    @classmethod
    def setUpClass(cls):
        # iterate a few times when Gtk.main() is called, but don't block
        # there and just continue to the tests while the UI becomes
        # unresponsive
        Gtk.main = gtk_iteration

        # doesn't do much except avoid some Gtk assertion error, whatever:
        Gtk.main_quit = lambda: None

    def setUp(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)
        custom_mapping.empty()
        self.window = launch()

    def tearDown(self):
        self.window.on_apply_system_layout_clicked(None)
        gtk_iteration()
        self.window.on_close()
        self.window.window.destroy()
        gtk_iteration()
        shutil.rmtree('/tmp/key-mapper-test')
        clear_write_history()

    def get_rows(self):
        return self.window.get('key_list').get_children()

    def test_autoload(self):
        self.window.on_preset_autoload_switch_activate(None, False)
        self.assertFalse(config.is_autoloaded(
            self.window.selected_device,
            self.window.selected_preset
        ))

        # select a preset for the first device
        self.window.on_select_device(FakeDropdown('device 1'))
        self.window.on_preset_autoload_switch_activate(None, True)
        self.assertTrue(config.is_autoloaded('device 1', 'new preset'))
        self.assertFalse(config.is_autoloaded('device 2', 'new preset'))
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [('device 1', 'new preset')]
        )

        # select a preset for the second device
        self.window.on_select_device(FakeDropdown('device 2'))
        self.window.on_preset_autoload_switch_activate(None, True)
        self.assertTrue(config.is_autoloaded('device 1', 'new preset'))
        self.assertTrue(config.is_autoloaded('device 2', 'new preset'))
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [('device 1', 'new preset'), ('device 2', 'new preset')]
        )

        # disable autoloading for the second device
        self.window.on_preset_autoload_switch_activate(None, False)
        self.assertTrue(config.is_autoloaded('device 1', 'new preset'))
        self.assertFalse(config.is_autoloaded('device 2', 'new preset'))
        self.assertListEqual(
            list(config.iterate_autoload_presets()),
            [('device 1', 'new preset')]
        )

    def test_can_start(self):
        self.assertIsNotNone(self.window)
        self.assertTrue(self.window.window.get_visible())

    def test_adds_empty_rows(self):
        rows = len(self.window.get('key_list').get_children())
        self.assertEqual(rows, 1)

        custom_mapping.change(13, 'a', None)
        time.sleep(0.2)
        gtk_iteration()

        rows = len(self.window.get('key_list').get_children())
        self.assertEqual(rows, 2)

    def change_empty_row(self, keycode, character):
        """Modify the one empty row that always exists."""
        # wait for the window to create a new empty row if needed
        time.sleep(0.2)
        gtk_iteration()

        # find the empty row
        rows = self.get_rows()
        row = rows[-1]
        self.assertNotIn('changed', row.get_style_context().list_classes())
        self.assertIsNone(row.keycode.get_label())
        self.assertEqual(row.character_input.get_text(), '')

        self.window.window.set_focus(row.keycode)

        pending_events[self.window.selected_device] = [
            Event(evdev.events.EV_KEY, keycode - 8, 1)
        ]

        self.window.on_window_event(None, None)

        self.assertEqual(int(row.keycode.get_label()), keycode)

        # set the character to make the new row complete
        row.character_input.set_text(character)

        self.assertIn('changed', row.get_style_context().list_classes())

        return row

    def test_rows(self):
        """Comprehensive test for rows."""

        # add two rows by modifiying the one empty row that exists
        self.change_empty_row(10, 'a')
        self.change_empty_row(11, 'b')

        # one empty row added automatically again
        time.sleep(0.2)
        gtk_iteration()
        # sleep one more time because it's funny to watch the ui
        # during the test, how rows turn blue and stuff
        time.sleep(0.2)
        self.assertEqual(len(self.get_rows()), 3)

        self.assertEqual(custom_mapping.get_character(10), 'a')
        self.assertEqual(custom_mapping.get_character(11), 'b')
        self.assertTrue(custom_mapping.changed)

        self.window.on_save_preset_clicked(None)
        for row in self.get_rows():
            self.assertNotIn(
                'changed',
                row.get_style_context().list_classes()
            )
        self.assertFalse(custom_mapping.changed)

        # now change the first row and it should turn blue,
        # but the other should remain unhighlighted
        row = self.get_rows()[0]
        row.character_input.set_text('c')
        self.assertIn('changed', row.get_style_context().list_classes())
        for row in self.get_rows()[1:]:
            self.assertNotIn(
                'changed',
                row.get_style_context().list_classes()
            )

        self.assertEqual(custom_mapping.get_character(10), 'c')
        self.assertEqual(custom_mapping.get_character(11), 'b')
        self.assertTrue(custom_mapping.changed)

    def test_rename_and_save(self):
        custom_mapping.change(14, 'a', None)
        self.assertEqual(self.window.selected_preset, 'new preset')
        self.window.on_save_preset_clicked(None)
        self.assertEqual(custom_mapping.get_character(14), 'a')

        custom_mapping.change(14, 'b', None)
        self.window.get('preset_name_input').set_text('asdf')
        self.window.on_save_preset_clicked(None)
        self.assertEqual(self.window.selected_preset, 'asdf')
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/asdf.json'))
        self.assertEqual(custom_mapping.get_character(14), 'b')

    def test_select_device_and_preset(self):
        # created on start because the first device is selected and some empty
        # preset prepared.
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset.json'))
        self.assertEqual(self.window.selected_device, 'device 1')
        self.assertEqual(self.window.selected_preset, 'new preset')

        # create another one
        self.window.on_create_preset_clicked(None)
        gtk_iteration()
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset.json'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset 2.json'))
        self.assertEqual(self.window.selected_preset, 'new preset 2')

        self.window.on_select_preset(FakeDropdown('new preset'))
        gtk_iteration()
        self.assertEqual(self.window.selected_preset, 'new preset')

        self.assertListEqual(
            sorted(os.listdir(f'{CONFIG}/device 1')),
            sorted(['new preset.json', 'new preset 2.json'])
        )

        # now try to change the name
        self.window.get('preset_name_input').set_text('abc 123')
        gtk_iteration()
        self.assertEqual(self.window.selected_preset, 'new preset')
        self.assertFalse(os.path.exists(f'{CONFIG}/device 1/abc 123.json'))
        custom_mapping.change(10, '1', None)
        self.window.on_save_preset_clicked(None)
        gtk_iteration()
        self.assertEqual(self.window.selected_preset, 'abc 123')
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/abc 123.json'))
        self.assertListEqual(
            sorted(os.listdir(CONFIG)),
            sorted(['device 1'])
        )
        self.assertListEqual(
            sorted(os.listdir(f'{CONFIG}/device 1')),
            sorted(['abc 123.json', 'new preset 2.json'])
        )

    def test_start_injecting(self):
        keycode_from = 9
        keycode_to = 200

        self.change_empty_row(keycode_from, 'a')
        system_mapping.empty()
        system_mapping.change(keycode_to, 'a')

        pending_events['device 2'] = [
            Event(evdev.events.EV_KEY, keycode_from - 8, 1),
            Event(evdev.events.EV_KEY, keycode_from - 8, 0)
        ]

        custom_mapping.save('device 2', 'foo preset')

        self.window.selected_device = 'device 2'
        self.window.selected_preset = 'foo preset'
        self.window.on_apply_preset_clicked(None)

        # the integration tests will cause the injection to be started as
        # processes, as intended. Luckily, recv will block until the events
        # are handled and pushed.

        # Note, that pushing events to pending_events won't work anymore
        # from here on because the injector processes memory cannot be
        # modified from here.

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, evdev.events.EV_KEY)
        self.assertEqual(event.code, keycode_to - 8)
        self.assertEqual(event.value, 1)

        event = uinput_write_history_pipe[0].recv()
        self.assertEqual(event.type, evdev.events.EV_KEY)
        self.assertEqual(event.code, keycode_to - 8)
        self.assertEqual(event.value, 0)

    def test_stop_injecting(self):
        keycode_from = 16
        keycode_to = 90

        self.change_empty_row(keycode_from, 't')
        system_mapping.empty()
        system_mapping.change(keycode_to, 't')

        # not all of those events should be processed, since that takes some
        # time due to time.sleep in the fakes and the injection is stopped.
        pending_events['device 2'] = [Event(1, keycode_from - 8, 1)] * 100

        custom_mapping.save('device 2', 'foo preset')

        self.window.selected_device = 'device 2'
        self.window.selected_preset = 'foo preset'
        self.window.on_apply_preset_clicked(None)

        pipe = uinput_write_history_pipe[0]
        # block until the first event is available, indicating that
        # the injector is ready
        write_history = [pipe.recv()]

        # stop
        self.window.on_apply_system_layout_clicked(None)

        # try to receive a few of the events
        time.sleep(0.2)
        while pipe.poll():
            write_history.append(pipe.recv())

        len_before = len(write_history)
        self.assertLess(len(write_history), 50)

        # since the injector should not be running anymore, no more events
        # should be received after waiting even more time
        time.sleep(0.2)
        while pipe.poll():
            write_history.append(pipe.recv())
        self.assertEqual(len(write_history), len_before)


if __name__ == "__main__":
    unittest.main()
