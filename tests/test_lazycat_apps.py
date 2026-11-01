import json
from pathlib import Path
import struct
import ssl
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lazycat_apps as lc


def string_field(number, text):
    value = text.encode()
    assert len(value) < 128
    return bytes([number * 8 + 2, len(value)]) + value


def frame(payload, flags=0):
    return bytes([flags]) + struct.pack('>I', len(payload)) + payload


class LazycatCatalogTests(unittest.TestCase):
    def test_grpc_metadata_decodes_unicode_names_and_skips_unknown_fields(self):
        app = string_field(1, 'cloud.lazycat.shell.files') + bytes([16, 4])
        app += string_field(4, '懒猫网盘') + string_field(6, '//box.heiyu.space/icon.png')
        app += bytes([0x98, 0x01, 1])  # resourceOnly, field 19
        response = frame(bytes([10, len(app)]) + app)
        response += frame(b'grpc-status: 0\r\n', 128)
        row = lc.decode_apps(response)[0]
        self.assertEqual(row['name'], '懒猫网盘')
        self.assertEqual(row['appId'], 'cloud.lazycat.shell.files')
        self.assertEqual(row['resourceOnly'], 1)

    def test_malformed_or_failed_grpc_response_is_rejected(self):
        for data in [b'\0', frame(b'grpc-status: 16\r\n', 128),
                     frame(b'\x0a\xff'), frame(b'', 1),
                     b'\0\0\0\0\x0a', frame(b'\0')]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                lc.decode_apps(data)

    def test_hidden_resource_and_uninstalled_apps_are_not_offered(self):
        apps = [
            {'appId': 'cloud.lazycat.shell.files', 'name': 'Cloud Drive', 'status': 4},
            {'appId': 'cloud.lazycat.shell.home', 'status': 4},
            {'appId': 'test.hidden', 'status': 4, 'hiddenFromLauncher': 1},
            {'appId': 'test.resource', 'status': 4, 'resourceOnly': 1},
            {'appId': 'test.installing', 'status': 3},
            {'appId': "evil; touch /tmp/bad", 'status': 4},
        ]
        box = {'boxId': 'box-1', 'boxName': 'My Box'}
        entries = lc.catalog_entries(apps, box)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['lazycatBoxId'], 'box-1')
        self.assertIn('懒猫网盘', entries[0]['keywords'])
        self.assertIn('懒猫网盘', entries[0]['lazycatWindowTitles'])
        self.assertEqual(entries[0]['execString'],
                         'xdg-open lzc://client/app/open?appId=cloud.lazycat.shell.files')

    def test_offline_uses_cached_metadata_without_leaking_error_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'catalog.json').write_text(json.dumps({'entries': [{'name': 'Cached'}]}))
            with mock.patch.object(lc, 'cache_root', return_value=root), \
                    mock.patch.object(lc, 'load_catalog', side_effect=OSError('SECRET_TOKEN')):
                result = lc.catalog()
            self.assertEqual(result['entries'][0]['name'], 'Cached')
            self.assertIn('缓存', result['warning'])
            self.assertNotIn('SECRET_TOKEN', json.dumps(result))

    def test_redirects_do_not_forward_session_headers(self):
        self.assertIsNone(lc.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere/'))

    def test_bad_app_id_cannot_become_a_launch_command(self):
        with self.assertRaises(ValueError):
            lc.launch_uri('app; rm -rf /')

    def test_private_overlay_certificate_policy_does_not_disable_public_tls(self):
        client = object.__new__(lc.Client)
        box = {'boxDomain': 'box.heiyu.space'}
        cookies = {'cookies': [{'name': 'Lzc-Auth-Token', 'value': 'test-session'}]}
        for address, verify in [('fc03::1234', ssl.CERT_NONE), ('203.0.113.1', ssl.CERT_REQUIRED)]:
            with self.subTest(address=address), mock.patch.object(client, 'local', return_value=cookies), \
                    mock.patch.object(lc.socket, 'getaddrinfo', return_value=[(0, 0, 0, '', (address, 443))]):
                _, _, context = client.session(box)
                self.assertEqual(context.verify_mode, verify)


if __name__ == '__main__':
    unittest.main()
