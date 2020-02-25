# -*- coding: utf-8 -*-
# Copyright (C) 2018-2019 Greenbone Networks GmbH
#
# SPDX-License-Identifier: GPL-2.0-or-later
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

# pylint: disable=unused-argument

""" Unit Test for ospd-openvas """

import logging

from unittest import TestCase
from unittest.mock import patch, MagicMock

from redis.exceptions import ConnectionError as RCE

from ospd.errors import RequiredArgument
from ospd_openvas.db import OpenvasDB, MainDB, ScanDB, DBINDEX_NAME, time
from ospd_openvas.errors import OspdOpenvasError

from tests.helper import assert_called


@patch('ospd_openvas.db.redis.Redis')
class TestOpenvasDB(TestCase):
    @patch('ospd_openvas.db.Openvas')
    def test_get_db_connection(
        self, mock_openvas: MagicMock, mock_redis: MagicMock
    ):
        OpenvasDB._db_address = None  # pylint: disable=protected-access
        mock_settings = mock_openvas.get_settings.return_value
        mock_settings.get.return_value = None

        self.assertIsNone(OpenvasDB.get_database_address())

        # set the first time
        mock_openvas.get_settings.return_value = {'db_address': '/foo/bar'}

        self.assertEqual(OpenvasDB.get_database_address(), "/foo/bar")

        self.assertEqual(mock_openvas.get_settings.call_count, 2)

        # should cache address
        self.assertEqual(OpenvasDB.get_database_address(), "/foo/bar")
        self.assertEqual(mock_openvas.get_settings.call_count, 2)

    def test_create_context_fail(self, mock_redis):
        mock_redis.side_effect = RCE

        logging.Logger.error = MagicMock()

        with patch.object(time, 'sleep', return_value=None):
            with self.assertRaises(SystemExit):
                OpenvasDB.create_context()

        logging.Logger.error.assert_called_with(  # pylint: disable=no-member
            'Redis Error: Not possible to connect to the kb.'
        )

    def test_create_context_success(self, mock_redis):
        ctx = mock_redis.return_value
        ret = OpenvasDB.create_context()
        self.assertIs(ret, ctx)

    def test_select_database_error(self, mock_redis):
        with self.assertRaises(RequiredArgument):
            OpenvasDB.select_database(None, 1)

        with self.assertRaises(RequiredArgument):
            OpenvasDB.select_database(mock_redis, None)

    def test_select_database(self, mock_redis):
        mock_redis.execute_command.return_value = mock_redis

        OpenvasDB.select_database(mock_redis, 1)

        mock_redis.execute_command.assert_called_with('SELECT 1')

    def test_get_list_item_error(self, mock_redis):
        ctx = mock_redis.return_value

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_list_item(None, 'foo')

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_list_item(ctx, None)

    def test_get_list_item(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.lrange.return_value = ['1234']

        ret = OpenvasDB.get_list_item(ctx, 'name')

        self.assertEqual(ret, ['1234'])
        assert_called(ctx.lrange)

    def test_get_last_list_item(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.rpop.return_value = 'foo'

        ret = OpenvasDB.get_last_list_item(ctx, 'name')

        self.assertEqual(ret, 'foo')
        ctx.rpop.assert_called_with('name')

    def test_get_last_list_item_error(self, mock_redis):
        ctx = mock_redis.return_value

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_last_list_item(ctx, None)

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_last_list_item(None, 'name')

    def test_remove_list_item(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.lrem.return_value = 1

        OpenvasDB.remove_list_item(ctx, 'name', '1234')

        ctx.lrem.assert_called_once_with('name', count=0, value='1234')

    def test_remove_list_item_error(self, mock_redis):
        ctx = mock_redis.return_value

        with self.assertRaises(RequiredArgument):
            OpenvasDB.remove_list_item(None, '1', 'bar')

        with self.assertRaises(RequiredArgument):
            OpenvasDB.remove_list_item(ctx, None, 'bar')

        with self.assertRaises(RequiredArgument):
            OpenvasDB.remove_list_item(ctx, '1', None)

    def test_get_single_item_error(self, mock_redis):
        ctx = mock_redis.return_value

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_single_item(None, 'foo')

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_single_item(ctx, None)

    def test_get_single_item(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.lindex.return_value = 'a'

        value = OpenvasDB.get_single_item(ctx, 'a')

        self.assertEqual(value, 'a')
        ctx.lindex.assert_called_once_with('a', 0)

    def test_add_single_item(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.rpush.return_value = 1

        OpenvasDB.add_single_item(ctx, 'a', ['12'])

        ctx.rpush.assert_called_once_with('a', '12')

    def test_add_single_item_error(self, mock_redis):
        ctx = mock_redis.return_value

        with self.assertRaises(RequiredArgument):
            OpenvasDB.add_single_item(None, '1', ['12'])

        with self.assertRaises(RequiredArgument):
            OpenvasDB.add_single_item(ctx, None, ['12'])

        with self.assertRaises(RequiredArgument):
            OpenvasDB.add_single_item(ctx, '1', None)

    def test_set_single_item_error(self, mock_redis):
        ctx = mock_redis.return_value

        with self.assertRaises(RequiredArgument):
            OpenvasDB.set_single_item(None, '1', ['12'])

        with self.assertRaises(RequiredArgument):
            OpenvasDB.set_single_item(ctx, None, ['12'])

        with self.assertRaises(RequiredArgument):
            OpenvasDB.set_single_item(ctx, '1', None)

    def test_set_single_item(self, mock_redis):
        ctx = mock_redis.return_value
        pipeline = ctx.pipeline.return_value
        pipeline.delete.return_value = None
        pipeline.rpush.return_value = None
        pipeline.execute.return_value = None

        OpenvasDB.set_single_item(ctx, 'foo', ['bar'])

        pipeline.delete.assert_called_once_with('foo')
        pipeline.rpush.assert_called_once_with('foo', 'bar')
        assert_called(pipeline.execute)

    def test_get_pattern(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.keys.return_value = ['a', 'b']
        ctx.lrange.return_value = [1, 2, 3]

        ret = OpenvasDB.get_pattern(ctx, 'a')

        self.assertEqual(ret, [['a', [1, 2, 3]], ['b', [1, 2, 3]]])

    def test_get_pattern_error(self, mock_redis):
        ctx = mock_redis.return_value

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_pattern(None, 'a')

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_pattern(ctx, None)

    def test_get_elem_pattern_by_index_error(self, mock_redis):
        ctx = mock_redis.return_value

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_elem_pattern_by_index(None, 'a')

        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_elem_pattern_by_index(ctx, None)

    def test_get_elem_pattern_by_index(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.keys.return_value = ['aa', 'ab']
        ctx.lindex.side_effect = [1, 2]

        ret = OpenvasDB.get_elem_pattern_by_index(ctx, 'a')

        self.assertEqual(list(ret), [('aa', 1), ('ab', 2)])

    def test_get_key_count(self, mock_redis):
        ctx = mock_redis.return_value

        ctx.keys.return_value = ['aa', 'ab']

        ret = OpenvasDB.get_key_count(ctx, "foo")

        self.assertEqual(ret, 2)
        ctx.keys.assert_called_with('foo')

    def test_get_key_count_with_default_pattern(self, mock_redis):
        ctx = mock_redis.return_value

        ctx.keys.return_value = ['aa', 'ab']

        ret = OpenvasDB.get_key_count(ctx)

        self.assertEqual(ret, 2)
        ctx.keys.assert_called_with('*')

    def test_get_key_count_error(self, mock_redis):
        with self.assertRaises(RequiredArgument):
            OpenvasDB.get_key_count(None)

    def test_find_database_by_pattern_none(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.keys.return_value = None

        new_ctx, index = OpenvasDB.find_database_by_pattern('foo*', 123)

        self.assertIsNone(new_ctx)
        self.assertIsNone(index)

    def test_find_database_by_pattern(self, mock_redis):
        ctx = mock_redis.return_value

        # keys is called twice per iteration
        ctx.keys.side_effect = [None, None, None, None, True, True]

        new_ctx, index = OpenvasDB.find_database_by_pattern('foo*', 123)

        self.assertEqual(new_ctx, ctx)
        self.assertEqual(index, 2)


@patch('ospd_openvas.db.OpenvasDB')
class ScanDBTestCase(TestCase):
    @patch('ospd_openvas.db.redis.Redis')
    def setUp(self, mock_redis):  # pylint: disable=arguments-differ
        self.ctx = mock_redis.return_value
        self.db = ScanDB(10, self.ctx)

    def test_get_result(self, mock_openvas_db):
        mock_openvas_db.get_last_list_item.return_value = 'some result'

        ret = self.db.get_result()

        self.assertEqual(ret, 'some result')
        mock_openvas_db.get_last_list_item.assert_called_with(
            self.ctx, 'internal/results'
        )

    def test_get_status(self, mock_openvas_db):
        mock_openvas_db.get_single_item.return_value = 'some status'

        ret = self.db.get_status('foo')

        self.assertEqual(ret, 'some status')
        mock_openvas_db.get_single_item.assert_called_with(
            self.ctx, 'internal/foo'
        )

    def test_select(self, mock_openvas_db):
        ret = self.db.select(11)

        self.assertIs(ret, self.db)
        self.assertEqual(self.db.index, 11)

        mock_openvas_db.select_database.assert_called_with(self.ctx, 11)

    def test_get_host_scan_start_time(self, mock_openvas_db):
        mock_openvas_db.get_last_list_item.return_value = 'some start time'

        ret = self.db.get_host_scan_start_time()

        self.assertEqual(ret, 'some start time')
        mock_openvas_db.get_last_list_item.assert_called_with(
            self.ctx, 'internal/start_time'
        )

    def test_get_host_scan_end_time(self, mock_openvas_db):
        mock_openvas_db.get_last_list_item.return_value = 'some end time'

        ret = self.db.get_host_scan_end_time()

        self.assertEqual(ret, 'some end time')
        mock_openvas_db.get_last_list_item.assert_called_with(
            self.ctx, 'internal/end_time'
        )

    def test_get_host_ip(self, mock_openvas_db):
        mock_openvas_db.get_single_item.return_value = '192.168.0.1'

        ret = self.db.get_host_ip()

        self.assertEqual(ret, '192.168.0.1')
        mock_openvas_db.get_single_item.assert_called_with(
            self.ctx, 'internal/ip'
        )


@patch('ospd_openvas.db.redis.Redis')
class MainDBTestCase(TestCase):
    def test_max_database_index_fail(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.config_get.return_value = {}

        maindb = MainDB(ctx)

        with self.assertRaises(OspdOpenvasError):
            max_db = (  # pylint: disable=unused-variable
                maindb.max_database_index
            )

        ctx.config_get.assert_called_with('databases')

    def test_max_database_index(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.config_get.return_value = {'databases': '123'}

        maindb = MainDB(ctx)

        max_db = maindb.max_database_index

        self.assertEqual(max_db, 123)
        ctx.config_get.assert_called_with('databases')

    def test_try_database_success(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.hsetnx.return_value = 1

        maindb = MainDB(ctx)

        ret = maindb.try_database(1)

        self.assertEqual(ret, True)
        ctx.hsetnx.assert_called_with(DBINDEX_NAME, 1, 1)

    def test_try_database_false(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.hsetnx.return_value = 0

        maindb = MainDB(ctx)

        ret = maindb.try_database(1)

        self.assertEqual(ret, False)
        ctx.hsetnx.assert_called_with(DBINDEX_NAME, 1, 1)

    def test_try_db_index_error(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.hsetnx.side_effect = Exception

        maindb = MainDB(ctx)

        with self.assertRaises(OspdOpenvasError):
            maindb.try_database(1)

    def test_release_database_by_index(self, mock_redis):
        ctx = mock_redis.return_value
        ctx.hdel.return_value = 1

        maindb = MainDB(ctx)

        maindb.release_database_by_index(3)

        ctx.hdel.assert_called_once_with(DBINDEX_NAME, 3)
