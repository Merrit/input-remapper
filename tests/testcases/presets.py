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


import os
import unittest
import shutil
import time

from keymapper.presets import find_newest_preset, rename_preset, \
    get_any_preset, delete_preset, get_available_preset_name, get_presets
from keymapper.paths import CONFIG
from keymapper.state import custom_mapping

from test import tmp


def create_preset(device, name='new preset'):
    name = get_available_preset_name(device, name)
    custom_mapping.empty()
    custom_mapping.save(device, name)


class TestCreatePreset(unittest.TestCase):
    def setUp(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

    def test_create_preset_1(self):
        self.assertEqual(get_any_preset(), ('device 1', None))
        create_preset('device 1')
        self.assertEqual(get_any_preset(), ('device 1', 'new preset'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset.json'))

    def test_create_preset_2(self):
        create_preset('device 1')
        create_preset('device 1')
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset.json'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset 2.json'))

    def test_create_preset_3(self):
        create_preset('device 1', 'pre set')
        create_preset('device 1', 'pre set')
        create_preset('device 1', 'pre set')
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/pre set.json'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/pre set 2.json'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/pre set 3.json'))


class TestDeletePreset(unittest.TestCase):
    def setUp(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

    def test_delete_preset(self):
        create_preset('device 1')
        create_preset('device 1')
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/new preset.json'))
        delete_preset('device 1', 'new preset')
        self.assertFalse(os.path.exists(f'{CONFIG}/device 1/new preset.json'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1'))
        delete_preset('device 1', 'new preset 2')
        self.assertFalse(os.path.exists(f'{CONFIG}/device 1/new preset.json'))
        self.assertFalse(os.path.exists(f'{CONFIG}/device 1/new preset 2.json'))
        # if no preset in the directory, remove the directory
        self.assertFalse(os.path.exists(f'{CONFIG}/device 1'))


class TestRenamePreset(unittest.TestCase):
    def setUp(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

    def test_rename_preset(self):
        create_preset('device 1', 'preset 1')
        create_preset('device 1', 'preset 2')
        create_preset('device 1', 'foobar')
        rename_preset('device 1', 'preset 1', 'foobar')
        rename_preset('device 1', 'preset 2', 'foobar')
        self.assertFalse(os.path.exists(f'{CONFIG}/device 1/preset 1.json'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/foobar.json'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/foobar 2.json'))
        self.assertTrue(os.path.exists(f'{CONFIG}/device 1/foobar 3.json'))


class TestFindPresets(unittest.TestCase):
    def setUp(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

    def test_get_presets(self):
        os.makedirs(os.path.join(CONFIG, '1234'))

        os.mknod(os.path.join(CONFIG, '1234', 'picture.png'))
        self.assertEqual(len(get_presets('1234')), 0)

        os.mknod(os.path.join(CONFIG, '1234', 'foo bar 1.json'))
        time.sleep(0.01)
        os.mknod(os.path.join(CONFIG, '1234', 'foo bar 2.json'))
        # the newest to the front
        self.assertListEqual(get_presets('1234'), ['foo bar 2', 'foo bar 1'])

    def test_find_newest_preset_1(self):
        create_preset('device 1', 'preset 1')
        time.sleep(0.01)
        create_preset('device 2', 'preset 2')

        # not a preset, ignore
        time.sleep(0.01)
        os.mknod(os.path.join(CONFIG, 'device 2', 'picture.png'))

        self.assertEqual(find_newest_preset(), ('device 2', 'preset 2'))

    def test_find_newest_preset_2(self):
        os.makedirs(f'{CONFIG}/device 1')
        time.sleep(0.01)
        os.makedirs(f'{CONFIG}/device_2')
        # takes the first one that the test-fake returns
        self.assertEqual(find_newest_preset(), ('device 1', None))

    def test_find_newest_preset_3(self):
        os.makedirs(f'{CONFIG}/device 1')
        self.assertEqual(find_newest_preset(), ('device 1', None))

    def test_find_newest_preset_4(self):
        create_preset('device 1', 'preset 1')
        self.assertEqual(find_newest_preset(), ('device 1', 'preset 1'))

    def test_find_newest_preset_5(self):
        create_preset('device 1', 'preset 1')
        time.sleep(0.01)
        create_preset('unknown device 3', 'preset 3')
        self.assertEqual(find_newest_preset(), ('device 1', 'preset 1'))

    def test_find_newest_preset_6(self):
        # takes the first one that the test-fake returns
        self.assertEqual(find_newest_preset(), ('device 1', None))

    def test_find_newest_preset_7(self):
        self.assertEqual(find_newest_preset('device 1'), ('device 1', None))

    def test_find_newest_preset_8(self):
        create_preset('device 1', 'preset 1')
        time.sleep(0.01)
        create_preset('device 1', 'preset 3')
        time.sleep(0.01)
        create_preset('device 2', 'preset 2')
        self.assertEqual(
            find_newest_preset('device 1'),
            ('device 1', 'preset 3')
        )


if __name__ == "__main__":
    unittest.main()
