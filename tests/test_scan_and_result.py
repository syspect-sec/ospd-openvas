# Copyright (C) 2015-2019 Greenbone Networks GmbH
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.

# pylint: disable=too-many-lines

""" Test module for scan runs
"""

import time
import unittest

from unittest.mock import patch, MagicMock

import xml.etree.ElementTree as ET
import defusedxml.lxml as secET

from defusedxml.common import EntitiesForbidden

from .helper import DummyWrapper, assert_called


class FakeStartProcess:
    def __init__(self):
        self.run_mock = MagicMock()
        self.call_mock = MagicMock()

        self.func = None
        self.args = None
        self.kwargs = None

    def __call__(self, func, *, args=None, kwargs=None):
        self.func = func
        self.args = args or []
        self.kwargs = kwargs or {}
        return self.call_mock

    def run(self):
        self.func(*self.args, **self.kwargs)
        return self.run_mock

    def __repr__(self):
        return "<FakeProcess func={} args={} kwargs={}>".format(
            self.func, self.args, self.kwargs
        )


class Result(object):
    def __init__(self, type_, **kwargs):
        self.result_type = type_
        self.host = ''
        self.hostname = ''
        self.name = ''
        self.value = ''
        self.port = ''
        self.test_id = ''
        self.severity = ''
        self.qod = ''
        for name, value in kwargs.items():
            setattr(self, name, value)


class ScanTestCase(unittest.TestCase):
    def test_get_default_scanner_params(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(
            daemon.handle_command('<get_scanner_details />')
        )

        # The status of the response must be success (i.e. 200)
        self.assertEqual(response.get('status'), '200')
        # The response root element must have the correct name
        self.assertEqual(response.tag, 'get_scanner_details_response')
        # The response must contain a 'scanner_params' element
        self.assertIsNotNone(response.find('scanner_params'))

    def test_get_default_help(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(daemon.handle_command('<help />'))

        self.assertEqual(response.get('status'), '200')

        response = secET.fromstring(
            daemon.handle_command('<help format="xml" />')
        )

        self.assertEqual(response.get('status'), '200')
        self.assertEqual(response.tag, 'help_response')

    def test_get_default_scanner_version(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(daemon.handle_command('<get_version />'))

        self.assertEqual(response.get('status'), '200')
        self.assertIsNotNone(response.find('protocol'))

    def test_get_vts_no_vt(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(daemon.handle_command('<get_vts />'))

        self.assertEqual(response.get('status'), '200')
        self.assertIsNotNone(response.find('vts'))

    def test_get_vts_single_vt(self):
        daemon = DummyWrapper([])
        daemon.add_vt('1.2.3.4', 'A vulnerability test')
        response = secET.fromstring(daemon.handle_command('<get_vts />'))

        self.assertEqual(response.get('status'), '200')

        vts = response.find('vts')
        self.assertIsNotNone(vts.find('vt'))

        vt = vts.find('vt')
        self.assertEqual(vt.get('id'), '1.2.3.4')

    def test_get_vts_filter_positive(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            vt_modification_time='19000202',
        )

        response = secET.fromstring(
            daemon.handle_command(
                '<get_vts filter="modification_time&gt;19000201"></get_vts>'
            )
        )

        self.assertEqual(response.get('status'), '200')
        vts = response.find('vts')

        vt = vts.find('vt')
        self.assertIsNotNone(vt)
        self.assertEqual(vt.get('id'), '1.2.3.4')

        modification_time = response.findall('vts/vt/modification_time')
        self.assertEqual(
            '<modification_time>19000202</modification_time>',
            ET.tostring(modification_time[0]).decode('utf-8'),
        )

    def test_get_vts_filter_negative(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            vt_modification_time='19000202',
        )

        response = secET.fromstring(
            daemon.handle_command(
                '<get_vts filter="modification_time&lt;19000203"></get_vts>'
            )
        )
        self.assertEqual(response.get('status'), '200')

        vts = response.find('vts')

        vt = vts.find('vt')
        self.assertIsNotNone(vt)
        self.assertEqual(vt.get('id'), '1.2.3.4')

        modification_time = response.findall('vts/vt/modification_time')
        self.assertEqual(
            '<modification_time>19000202</modification_time>',
            ET.tostring(modification_time[0]).decode('utf-8'),
        )

    def test_get_vtss_multiple_vts(self):
        daemon = DummyWrapper([])
        daemon.add_vt('1.2.3.4', 'A vulnerability test')
        daemon.add_vt('1.2.3.5', 'Another vulnerability test')
        daemon.add_vt('123456789', 'Yet another vulnerability test')

        response = secET.fromstring(daemon.handle_command('<get_vts />'))

        self.assertEqual(response.get('status'), '200')

        vts = response.find('vts')
        self.assertIsNotNone(vts.find('vt'))

    def test_get_vts_multiple_vts_with_custom(self):
        daemon = DummyWrapper([])
        daemon.add_vt('1.2.3.4', 'A vulnerability test', custom='b')
        daemon.add_vt(
            '4.3.2.1', 'Another vulnerability test with custom info', custom='b'
        )
        daemon.add_vt('123456789', 'Yet another vulnerability test', custom='b')

        response = secET.fromstring(daemon.handle_command('<get_vts />'))
        custom = response.findall('vts/vt/custom')

        self.assertEqual(3, len(custom))

    def test_get_vts_vts_with_params(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4', 'A vulnerability test', vt_params="a", custom="b"
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )
        # The status of the response must be success (i.e. 200)
        self.assertEqual(response.get('status'), '200')

        # The response root element must have the correct name
        self.assertEqual(response.tag, 'get_vts_response')
        # The response must contain a 'scanner_params' element
        self.assertIsNotNone(response.find('vts'))

        vt_params = response[0][0].findall('params')
        self.assertEqual(1, len(vt_params))

        custom = response[0][0].findall('custom')
        self.assertEqual(1, len(custom))

        params = response.findall('vts/vt/params/param')
        self.assertEqual(2, len(params))

    def test_get_vts_vts_with_refs(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            vt_refs="c",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )
        # The status of the response must be success (i.e. 200)
        self.assertEqual(response.get('status'), '200')

        # The response root element must have the correct name
        self.assertEqual(response.tag, 'get_vts_response')

        # The response must contain a 'vts' element
        self.assertIsNotNone(response.find('vts'))

        vt_params = response[0][0].findall('params')
        self.assertEqual(1, len(vt_params))

        custom = response[0][0].findall('custom')
        self.assertEqual(1, len(custom))

        refs = response.findall('vts/vt/refs/ref')
        self.assertEqual(2, len(refs))

    def test_get_vts_vts_with_dependencies(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            vt_dependencies="c",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        deps = response.findall('vts/vt/dependencies/dependency')
        self.assertEqual(2, len(deps))

    def test_get_vts_vts_with_severities(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            severities="c",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        severity = response.findall('vts/vt/severities/severity')
        self.assertEqual(1, len(severity))

    def test_get_vts_vts_with_detection_qodt(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            detection="c",
            qod_t="d",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        detection = response.findall('vts/vt/detection')
        self.assertEqual(1, len(detection))

    def test_get_vts_vts_with_detection_qodv(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            detection="c",
            qod_v="d",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        detection = response.findall('vts/vt/detection')
        self.assertEqual(1, len(detection))

    def test_get_vts_vts_with_summary(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            summary="c",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        summary = response.findall('vts/vt/summary')
        self.assertEqual(1, len(summary))

    def test_get_vts_vts_with_impact(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            impact="c",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        impact = response.findall('vts/vt/impact')
        self.assertEqual(1, len(impact))

    def test_get_vts_vts_with_affected(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            affected="c",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        affect = response.findall('vts/vt/affected')
        self.assertEqual(1, len(affect))

    def test_get_vts_vts_with_insight(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            insight="c",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        insight = response.findall('vts/vt/insight')
        self.assertEqual(1, len(insight))

    def test_get_vts_vts_with_solution(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            custom="b",
            solution="c",
            solution_t="d",
            solution_m="e",
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        solution = response.findall('vts/vt/solution')
        self.assertEqual(1, len(solution))

    def test_get_vts_vts_with_ctime(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            vt_creation_time='01-01-1900',
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        creation_time = response.findall('vts/vt/creation_time')
        self.assertEqual(
            '<creation_time>01-01-1900</creation_time>',
            ET.tostring(creation_time[0]).decode('utf-8'),
        )

    def test_get_vts_vts_with_mtime(self):
        daemon = DummyWrapper([])
        daemon.add_vt(
            '1.2.3.4',
            'A vulnerability test',
            vt_params="a",
            vt_modification_time='02-01-1900',
        )

        response = secET.fromstring(
            daemon.handle_command('<get_vts vt_id="1.2.3.4"></get_vts>')
        )

        modification_time = response.findall('vts/vt/modification_time')
        self.assertEqual(
            '<modification_time>02-01-1900</modification_time>',
            ET.tostring(modification_time[0]).decode('utf-8'),
        )

    def test_clean_forgotten_scans(self):
        daemon = DummyWrapper([])

        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan target="localhost" ports="80, '
                '443"><scanner_params /></start_scan>'
            )
        )
        scan_id = response.findtext('id')

        finished = False
        while not finished:
            response = secET.fromstring(
                daemon.handle_command(
                    '<get_scans scan_id="%s" details="1"/>' % scan_id
                )
            )
            scans = response.findall('scan')
            self.assertEqual(1, len(scans))

            scan = scans[0]
            status = scan.get('status')

            if status == "init" or status == "running":
                self.assertEqual('0', scan.get('end_time'))
                time.sleep(0.010)
            else:
                finished = True

        response = secET.fromstring(
            daemon.handle_command(
                '<get_scans scan_id="%s" details="1"/>' % scan_id
            )
        )
        self.assertEqual(len(list(daemon.scan_collection.ids_iterator())), 1)

        # Set an old end_time
        daemon.scan_collection.scans_table[scan_id]['end_time'] = 123456
        # Run the check
        daemon.clean_forgotten_scans()
        # Not removed
        self.assertEqual(len(list(daemon.scan_collection.ids_iterator())), 1)

        # Set the max time and run again
        daemon.scaninfo_store_time = 1
        daemon.clean_forgotten_scans()
        # Now is removed
        self.assertEqual(len(list(daemon.scan_collection.ids_iterator())), 0)

    def test_scan_with_error(self):
        daemon = DummyWrapper([Result('error', value='something went wrong')])

        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan target="localhost" ports="80, '
                '443"><scanner_params /></start_scan>'
            )
        )
        scan_id = response.findtext('id')

        finished = False
        while not finished:
            response = secET.fromstring(
                daemon.handle_command(
                    '<get_scans scan_id="%s" details="1"/>' % scan_id
                )
            )
            scans = response.findall('scan')
            self.assertEqual(1, len(scans))

            scan = scans[0]
            status = scan.get('status')

            if status == "init" or status == "running":
                self.assertEqual('0', scan.get('end_time'))
                time.sleep(0.010)
            else:
                finished = True

        response = secET.fromstring(
            daemon.handle_command(
                '<get_scans scan_id="%s" details="1"/>' % scan_id
            )
        )

        self.assertEqual(
            response.findtext('scan/results/result'), 'something went wrong'
        )

        response = secET.fromstring(
            daemon.handle_command('<delete_scan scan_id="%s" />' % scan_id)
        )

        self.assertEqual(response.get('status'), '200')

    def test_get_scan_pop(self):
        daemon = DummyWrapper([Result('host-detail', value='Some Host Detail')])

        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan target="localhost" ports="80, 443">'
                '<scanner_params /></start_scan>'
            )
        )

        scan_id = response.findtext('id')
        time.sleep(1)

        response = secET.fromstring(
            daemon.handle_command('<get_scans scan_id="%s"/>' % scan_id)
        )
        self.assertEqual(
            response.findtext('scan/results/result'), 'Some Host Detail'
        )

        response = secET.fromstring(
            daemon.handle_command(
                '<get_scans scan_id="%s" pop_results="1"/>' % scan_id
            )
        )
        self.assertEqual(
            response.findtext('scan/results/result'), 'Some Host Detail'
        )

        response = secET.fromstring(
            daemon.handle_command('<get_scans details="0" pop_results="1"/>')
        )
        self.assertEqual(response.findtext('scan/results/result'), None)

    def test_get_scan_pop_max_res(self):
        daemon = DummyWrapper(
            [
                Result('host-detail', value='Some Host Detail'),
                Result('host-detail', value='Some Host Detail1'),
                Result('host-detail', value='Some Host Detail2'),
            ]
        )

        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan target="localhost" ports="80, 443">'
                '<scanner_params /></start_scan>'
            )
        )

        scan_id = response.findtext('id')
        time.sleep(1)

        response = secET.fromstring(
            daemon.handle_command(
                '<get_scans scan_id="%s" pop_results="1" max_results="1"/>'
                % scan_id
            )
        )
        self.assertEqual(len(response.findall('scan/results/result')), 1)

        response = secET.fromstring(
            daemon.handle_command(
                '<get_scans scan_id="%s" pop_results="1"/>' % scan_id
            )
        )
        self.assertEqual(len(response.findall('scan/results/result')), 2)

    def test_billon_laughs(self):
        # pylint: disable=line-too-long
        daemon = DummyWrapper([])
        lol = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE lolz ['
            ' <!ENTITY lol "lol">'
            ' <!ELEMENT lolz (#PCDATA)>'
            ' <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
            ' <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">'
            ' <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
            ' <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">'
            ' <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">'
            ' <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">'
            ' <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">'
            ' <!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">'
            ' <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">'
            ']>'
        )
        self.assertRaises(EntitiesForbidden, daemon.handle_command, lol)

    def test_scan_multi_target(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan>'
                '<scanner_params /><vts><vt id="1.2.3.4" />'
                '</vts>'
                '<targets><target>'
                '<hosts>localhosts</hosts>'
                '<ports>80,443</ports>'
                '<alive_test>0</alive_test>'
                '</target>'
                '<target><hosts>192.168.0.0/24</hosts>'
                '<ports>22</ports></target></targets>'
                '</start_scan>'
            )
        )
        self.assertEqual(response.get('status'), '200')

    def test_multi_target_with_credentials(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan>'
                '<scanner_params /><vts><vt id="1.2.3.4" />'
                '</vts>'
                '<targets><target><hosts>localhosts</hosts>'
                '<ports>80,443</ports></target><target>'
                '<hosts>192.168.0.0/24</hosts><ports>22'
                '</ports><credentials>'
                '<credential type="up" service="ssh" port="22">'
                '<username>scanuser</username>'
                '<password>mypass</password>'
                '</credential><credential type="up" service="smb">'
                '<username>smbuser</username>'
                '<password>mypass</password></credential>'
                '</credentials>'
                '</target></targets>'
                '</start_scan>'
            )
        )

        self.assertEqual(response.get('status'), '200')

        cred_dict = {
            'ssh': {
                'type': 'up',
                'password': 'mypass',
                'port': '22',
                'username': 'scanuser',
            },
            'smb': {'type': 'up', 'password': 'mypass', 'username': 'smbuser'},
        }
        scan_id = response.findtext('id')
        response = daemon.get_scan_credentials(scan_id, "192.168.0.0/24")
        self.assertEqual(response, cred_dict)

    def test_scan_get_target(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan>'
                '<scanner_params /><vts><vt id="1.2.3.4" />'
                '</vts>'
                '<targets><target>'
                '<hosts>localhosts</hosts>'
                '<ports>80,443</ports>'
                '</target>'
                '<target><hosts>192.168.0.0/24</hosts>'
                '<ports>22</ports></target></targets>'
                '</start_scan>'
            )
        )
        scan_id = response.findtext('id')
        response = secET.fromstring(
            daemon.handle_command('<get_scans scan_id="%s"/>' % scan_id)
        )
        scan_res = response.find('scan')
        self.assertEqual(scan_res.get('target'), 'localhosts,192.168.0.0/24')

    def test_scan_get_target_options(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan>'
                '<scanner_params /><vts><vt id="1.2.3.4" />'
                '</vts>'
                '<targets>'
                '<target><hosts>192.168.0.1</hosts>'
                '<ports>22</ports><alive_test>0</alive_test></target>'
                '</targets>'
                '</start_scan>'
            )
        )
        scan_id = response.findtext('id')
        time.sleep(1)
        target_options = daemon.get_scan_target_options(scan_id, '192.168.0.1')
        self.assertEqual(target_options, {'alive_test': '0'})

    def test_scan_get_finished_hosts(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan>'
                '<scanner_params /><vts><vt id="1.2.3.4" />'
                '</vts>'
                '<targets><target>'
                '<hosts>192.168.10.20-25</hosts>'
                '<ports>80,443</ports>'
                '<finished_hosts>192.168.10.23-24'
                '</finished_hosts>'
                '</target>'
                '<target><hosts>192.168.0.0/24</hosts>'
                '<ports>22</ports></target>'
                '</targets>'
                '</start_scan>'
            )
        )
        scan_id = response.findtext('id')
        time.sleep(1)
        finished = daemon.get_scan_finished_hosts(scan_id)
        self.assertEqual(finished, ['192.168.10.23', '192.168.10.24'])

    def test_progress(self):
        daemon = DummyWrapper([])

        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan parallel="2">'
                '<scanner_params />'
                '<targets><target>'
                '<hosts>localhost1</hosts>'
                '<ports>22</ports>'
                '</target><target>'
                '<hosts>localhost2</hosts>'
                '<ports>22</ports>'
                '</target></targets>'
                '</start_scan>'
            )
        )

        scan_id = response.findtext('id')

        daemon.set_scan_host_progress(scan_id, 'localhost1', 'localhost1', 75)
        daemon.set_scan_host_progress(scan_id, 'localhost2', 'localhost2', 25)

        self.assertEqual(daemon.calculate_progress(scan_id), 50)

    def test_set_get_vts_version(self):
        daemon = DummyWrapper([])
        daemon.set_vts_version('1234')

        version = daemon.get_vts_version()
        self.assertEqual('1234', version)

    def test_set_get_vts_version_error(self):
        daemon = DummyWrapper([])
        self.assertRaises(TypeError, daemon.set_vts_version)

    @patch("ospd.ospd.os")
    @patch("ospd.command.command.create_process")
    def test_resume_task(self, mock_create_process, _mock_os):
        daemon = DummyWrapper(
            [
                Result(
                    'host-detail', host='localhost', value='Some Host Detail'
                ),
                Result(
                    'host-detail', host='localhost', value='Some Host Detail2'
                ),
            ]
        )

        fp = FakeStartProcess()
        mock_create_process.side_effect = fp
        mock_process = fp.call_mock
        mock_process.start.side_effect = fp.run
        mock_process.is_alive.return_value = True
        mock_process.pid = "main-scan-process"

        response = ET.fromstring(
            daemon.handle_command(
                '<start_scan>'
                '<scanner_params />'
                '<targets><target>'
                '<hosts>localhost</hosts>'
                '<ports>22</ports>'
                '</target></targets>'
                '</start_scan>'
            )
        )
        scan_id = response.findtext('id')

        self.assertIsNotNone(scan_id)

        assert_called(mock_create_process)
        assert_called(mock_process.start)

        daemon.handle_command('<stop_scan scan_id="%s" />' % scan_id)

        response = ET.fromstring(
            daemon.handle_command(
                '<get_scans scan_id="%s" details="1"/>' % scan_id
            )
        )

        result = response.findall('scan/results/result')
        self.assertEqual(len(result), 2)

        # Resume the task
        cmd = (
            '<start_scan scan_id="{}" target="localhost" ports="80, 443">'
            '<scanner_params />'
            '</start_scan>'.format(scan_id)
        )
        response = ET.fromstring(daemon.handle_command(cmd))

        # Check unfinished host
        self.assertEqual(response.findtext('id'), scan_id)
        self.assertEqual(
            daemon.get_scan_unfinished_hosts(scan_id), ['localhost']
        )

        # Finished the host and check unfinished again.
        daemon.set_scan_host_finished(scan_id, "localhost", "localhost")
        self.assertEqual(len(daemon.get_scan_unfinished_hosts(scan_id)), 0)

        # Check finished hosts
        self.assertEqual(
            daemon.scan_collection.get_hosts_finished(scan_id), ['localhost']
        )

        # Check if the result was removed.
        response = ET.fromstring(
            daemon.handle_command(
                '<get_scans scan_id="%s" details="1"/>' % scan_id
            )
        )
        result = response.findall('scan/results/result')

        # current the response still contains the results
        # self.assertEqual(len(result), 0)

    def test_result_order(self):
        daemon = DummyWrapper([])
        response = secET.fromstring(
            daemon.handle_command(
                '<start_scan parallel="1">'
                '<scanner_params />'
                '<targets><target>'
                '<hosts>a</hosts>'
                '<ports>22</ports>'
                '</target></targets>'
                '</start_scan>'
            )
        )

        scan_id = response.findtext('id')

        daemon.add_scan_log(scan_id, host='a', name='a')
        daemon.add_scan_log(scan_id, host='c', name='c')
        daemon.add_scan_log(scan_id, host='b', name='b')
        hosts = ['a', 'c', 'b']
        response = secET.fromstring(
            daemon.handle_command('<get_scans details="1"/>')
        )
        results = response.findall("scan/results/")

        for idx, res in enumerate(results):
            att_dict = res.attrib
            self.assertEqual(hosts[idx], att_dict['name'])
