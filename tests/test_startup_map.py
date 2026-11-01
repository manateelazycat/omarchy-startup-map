import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import startup_map as sm


class StartupMapTests(unittest.TestCase):
    def setUp(self):
        self.monitors = [
            {"id": 1, "name": "DP-1", "x": 100, "y": 0, "activeWorkspace": {"id": 1}},
            {"id": 2, "name": "DP-2", "x": 0, "y": 0, "activeWorkspace": {"id": 4}},
        ]
        self.rules = [
            {"workspaceString": str(i), "monitor": "DP-1"} for i in (1, 2, 3)
        ] + [
            {"workspaceString": str(i), "monitor": "DP-2"} for i in (4, 5, 6)
        ]

    def test_same_local_position_maps_to_different_global_ids(self):
        entries = [
            {"id": "a", "name": "A", "command": "/bin/true", "monitor": "DP-1", "position": 1},
            {"id": "b", "name": "B", "command": "/bin/true", "monitor": "DP-2", "position": 1},
            {"id": "c", "name": "C", "command": "/bin/true", "monitor": "DP-2", "position": 2},
            {"id": "d", "name": "D", "command": "/bin/true", "monitor": "DP-2", "position": 1},
        ]
        planned = sm.plan(entries, self.monitors, [], self.rules)
        self.assertEqual([item["workspaceId"] for item in planned["entries"]], [1, 4, 5, 4])

    def test_new_positions_get_unique_ids_after_existing_workspaces(self):
        entries = [
            {"name": "A", "command": "/bin/true", "monitor": "DP-1", "position": 4},
            {"name": "B", "command": "/bin/true", "monitor": "DP-2", "position": 4},
        ]
        planned = sm.plan(entries, self.monitors, [], self.rules)
        # The displays are processed in physical order: DP-2 is left of DP-1.
        self.assertEqual([item["workspaceId"] for item in planned["entries"]], [8, 7])
        self.assertEqual(planned["newSlots"], [
            {"monitor": "DP-2", "position": 4, "workspaceId": 7},
            {"monitor": "DP-1", "position": 4, "workspaceId": 8},
        ])

    def test_disconnected_monitor_is_skipped(self):
        entries = [{"name": "A", "command": "/bin/true", "monitor": "HDMI-A-1", "position": 1}]
        self.assertEqual(sm.plan(entries, self.monitors, [], self.rules),
                         {"entries": [], "newSlots": []})

    def test_empty_prior_positions_are_provisioned(self):
        monitors = [{"id": 1, "name": "DP-1", "x": 0, "y": 0,
                     "activeWorkspace": {"id": 1}}]
        entries = [{"name": "A", "command": "/bin/true", "monitor": "DP-1", "position": 3}]
        planned = sm.plan(entries, monitors, [{"id": 1, "monitor": "DP-1"}], [])
        self.assertEqual(planned["entries"][0]["workspaceId"], 3)
        self.assertEqual(planned["newSlots"], [
            {"monitor": "DP-1", "position": 2, "workspaceId": 2},
            {"monitor": "DP-1", "position": 3, "workspaceId": 3},
        ])

    def test_new_slot_uses_free_id_when_highest_id_is_100(self):
        monitors = [{"id": 1, "name": "DP-1", "x": 0, "y": 0,
                     "activeWorkspace": {"id": 100}}]
        entries = [{"name": "A", "command": "/bin/true", "monitor": "DP-1", "position": 2}]
        planned = sm.plan(entries, monitors, [], [])
        self.assertEqual(planned["entries"][0]["workspaceId"], 1)

    def test_desktop_exec_codes_are_removed_for_manual_commands(self):
        self.assertEqual(sm.desktop_exec_to_command('env FOO=bar /usr/bin/example --name %c %U', 'My App'),
                         "env FOO=bar /usr/bin/example --name 'My App'")
        self.assertEqual(sm.desktop_exec_to_command('Exec=/usr/bin/example %f'), '/usr/bin/example')

    def test_unquoted_absolute_path_with_spaces_is_accepted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / 'My Program'
            executable.write_text('')
            self.assertEqual(sm.desktop_exec_to_command(str(executable)),
                             "'" + str(executable) + "'")

    def test_selected_desktop_uses_gtk_launch(self):
        entry = {"command": "/usr/bin/example %U", "desktopId": "org.example.App", "name": "App"}
        self.assertIn("gtk-launch org.example.App.desktop", sm.launch_command(entry, "token"))

    def test_direct_command_keeps_launch_token_without_gtk_launch(self):
        entry = {"command": "/usr/bin/example", "desktopId": "", "name": "App"}
        command = sm.launch_command(entry, "token")
        self.assertIn("OMARCHY_STARTUP_MAP_TOKEN=token", command)
        self.assertIn("sh -c /usr/bin/example", command)
        self.assertNotIn("gtk-launch", command)

    def test_watcher_places_only_main_window_when_process_opens_multiple(self):
        entry = {"name": "懒猫微服", "monitor": "DP-2", "workspaceId": 4}
        child = {"address": "0x1", "pid": 123, "initialTitle": "懒猫清单-user",
                 "workspace": {"id": 8}, "monitor": 0}
        main = {"address": "0x2", "pid": 123, "initialTitle": "懒猫微服-user",
                "workspace": {"id": 8}, "monitor": 0}
        now = [0.0]

        def advance(seconds):
            now[0] += seconds

        with mock.patch.object(sm.time, "monotonic", side_effect=lambda: now[0]), \
                mock.patch.object(sm.time, "sleep", side_effect=advance), \
                mock.patch.object(sm, "hypr_json", return_value=[child, main]), \
                mock.patch.object(sm, "proc_token", return_value="token"), \
                mock.patch.object(sm, "place_window") as place:
            sm.watch_new_windows({"token": entry}, set(), {"DP-2": 3})

        place.assert_called_once_with("0x2", entry)

    def test_watcher_uses_first_window_when_title_does_not_match(self):
        entry = {"name": "Browser", "monitor": "DP-2", "workspaceId": 4}
        window = {"address": "0x3", "pid": 456, "initialTitle": "New Tab",
                  "workspace": {"id": 8}, "monitor": 0}
        now = [0.0]

        def advance(seconds):
            now[0] += seconds

        with mock.patch.object(sm.time, "monotonic", side_effect=lambda: now[0]), \
                mock.patch.object(sm.time, "sleep", side_effect=advance), \
                mock.patch.object(sm, "hypr_json", return_value=[window]), \
                mock.patch.object(sm, "proc_token", return_value="token"), \
                mock.patch.object(sm, "place_window") as place:
            sm.watch_new_windows({"token": entry}, set(), {"DP-2": 3})

        place.assert_called_once_with("0x3", entry)
        self.assertGreaterEqual(now[0], 1)

    def test_invalid_position_is_rejected(self):
        with self.assertRaises(ValueError):
            sm.validate_entries({"version": 1, "entries": [
                {"name": "A", "command": "/bin/true", "monitor": "DP-1", "position": 0}
            ]})

    def test_old_config_defaults_to_immediate_launch_and_invalid_delays_fail(self):
        row = {"name": "App", "command": "/bin/true", "monitor": "DP-1", "position": 1}
        self.assertEqual(sm.validate_entries({"version": 1, "entries": [row]})[0]['delaySeconds'], 0)
        for delay in [-1, 3601, True, 1.5, "10", None]:
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                sm.validate_entries({"version": 1, "entries": [{**row, "delaySeconds": delay}]})

    def test_lazycat_launch_uses_app_id_instead_of_desktop_or_editable_command(self):
        entry = {"name": "LightOS", "command": "/bin/wrong", "desktopId": "wrong",
                 "lazycatAppId": "cloud.lazycat.lightos.entry"}
        command = sm.launch_command(entry, "test")
        self.assertIn('lzc://client/app/open?appId=cloud.lazycat.lightos.entry', command)
        self.assertNotIn('/bin/wrong', command)
        self.assertNotIn('gtk-launch', command)

    def scheduler(self, entries, *, lazycat=False, ready=True, ambiguous=False):
        now = [0.0]
        launched = []
        windows = []
        existing = {"address": "0x99", "pid": 5, "class": "lzc-client-desktop",
                    "initialTitle": "Already open", "workspace": {"id": 8}, "monitor": 0}

        def launch(entry, token):
            launched.append((entry['name'], now[0]))
            if lazycat and entry.get('lazycatAppId'):
                title = 'LCMD WebShell-user' if entry['name'] == 'LightOS' else '懒猫网盘-user'
                windows.append({"address": '0x' + str(len(windows) + 1), "pid": 5,
                                "class": "lzc-client-desktop", "initialTitle": title,
                                "workspace": {"id": entry['workspaceId']}, "monitor": 3})
                if ambiguous:
                    windows[-1]['initialTitle'] = 'Unknown'
                    windows.append({**windows[-1], 'address': '0xa'})
            else:
                windows.append({"address": '0x' + str(len(windows) + 1), "pid": token,
                                "initialTitle": entry['name'], "workspace": {"id": 8}, "monitor": 0})

        with mock.patch.object(sm.time, 'monotonic', side_effect=lambda: now[0]), \
                mock.patch.object(sm.time, 'sleep', side_effect=lambda seconds: now.__setitem__(0, now[0] + seconds)), \
                mock.patch.object(sm, 'hypr_json', side_effect=lambda _: [existing, *windows]), \
                mock.patch.object(sm, 'proc_token', side_effect=lambda pid: pid), \
                mock.patch.object(sm, 'launch_entry', side_effect=launch), \
                mock.patch.object(sm, 'clear_lazycat_placement'), \
                mock.patch.object(sm.lazycat_apps, 'Client') as client, \
                mock.patch.object(sm.subprocess, 'Popen') as bootstrap, \
                mock.patch.object(sm, 'place_window') as place:
            if ready:
                client.return_value.box.return_value = {'boxId': 'box-1'}
            else:
                client.return_value.box.side_effect = OSError('not ready')
            sm.watch_new_windows({}, {'0x99'}, {'DP-2': 3}, scheduled=entries)
        return launched, place.call_args_list, bootstrap.call_count

    def test_delays_are_independent_and_windows_are_watched_between_launches(self):
        entries = [{"name": name, "monitor": "DP-2", "workspaceId": 4, "delaySeconds": delay}
                   for name, delay in [('Late', 10), ('First', 0), ('Middle', 5)]]
        launched, placed, _ = self.scheduler(entries)
        self.assertEqual([name for name, _ in launched], ['First', 'Middle', 'Late'])
        for (_, actual), expected in zip(launched, [0, 5, 10]):
            self.assertGreaterEqual(actual, expected)
            self.assertLess(actual, expected + 0.5)
        self.assertEqual([call.args[1]['name'] for call in placed], ['First', 'Middle', 'Late'])

    def test_shared_pid_lazycat_windows_use_aliases_and_preserve_existing_windows(self):
        entries = [dict(name=name, monitor='DP-2', workspaceId=4, delaySeconds=0,
                        lazycatAppId=appid, lazycatBoxId='box-1', lazycatWindowTitles=[title])
                   for name, appid, title in [('Files', 'cloud.lazycat.shell.files', '懒猫网盘'),
                                              ('LightOS', 'cloud.lazycat.lightos.entry', 'LCMD WebShell')]]
        launched, placed, _ = self.scheduler(entries, lazycat=True)
        self.assertEqual([name for name, _ in launched], ['Files', 'LightOS'])
        self.assertEqual(placed, [])  # Both windows were already mapped at the destination.

    def test_unready_lazycat_does_not_delay_native_apps_and_bootstraps_only_once(self):
        entries = [dict(name='Cloud', lazycatAppId='test.app', lazycatBoxId='box-1', delaySeconds=0),
                   dict(name='Native', monitor='DP-2', workspaceId=4, delaySeconds=2)]
        launched, _, bootstraps = self.scheduler(entries, ready=False)
        self.assertEqual(len(launched), 1)
        self.assertEqual(launched[0][0], 'Native')
        self.assertLess(launched[0][1], 2.5)
        self.assertEqual(bootstraps, 1)

    def test_ambiguous_shared_pid_windows_are_not_moved(self):
        entries = [dict(name='Files', monitor='DP-2', workspaceId=4, delaySeconds=0,
                        lazycatAppId='test.files', lazycatBoxId='box-1')]
        _, placed, _ = self.scheduler(entries, lazycat=True, ambiguous=True)
        self.assertEqual(placed, [])

    def test_another_selected_server_is_not_used_for_saved_app(self):
        entries = [dict(name='Files', lazycatAppId='test.files', lazycatBoxId='different-box', delaySeconds=0)]
        launched, placed, _ = self.scheduler(entries, lazycat=True)
        self.assertEqual(launched, [])
        self.assertEqual(placed, [])

    def test_lazycat_mapping_is_armed_before_the_launcher_is_requested(self):
        entry = dict(name='LightOS', command='ignored', lazycatAppId='cloud.lazycat.lightos.entry',
                     monitor='DP-2', workspaceId=4, lazycatWindowTitles=['LCMD WebShell'])
        with mock.patch.object(sm, 'eval_lua') as evaluate:
            sm.launch_entry(entry, 'token')
        code = evaluate.call_args.args[0]
        self.assertLess(code.index('.arm('), code.index('hl.exec_cmd('))
        self.assertIn('StartupPlacement.lua', code)
        self.assertIn('LCMD WebShell', code)
        self.assertNotIn('hl.dsp.window.move', code)
        self.assertNotIn('hl.dsp.workspace.move', code)

    def test_native_fallback_never_moves_an_entire_workspace(self):
        with mock.patch.object(sm, 'eval_lua') as evaluate:
            sm.place_window('0x123', {'workspaceId': 4, 'monitor': 'DP-2'})
        code = evaluate.call_args.args[0]
        self.assertIn('hl.dsp.window.move', code)
        self.assertNotIn('hl.dsp.workspace.move', code)

    def test_remote_wechat_completion_waits_for_cde_instead_of_relay(self):
        entry = dict(name='远程微信', lazycatAppId='cloud.lazycat.catlink.wechat')
        relay = {'class': 'lzc-client-desktop', 'initialTitle': '远程微信-user'}
        actual = {'class': 'wechat', 'initialTitle': '微信 on cloud.lazycat.catlink.wechat-cde'}
        self.assertIsNone(sm.primary_window([relay], entry))
        self.assertIs(sm.primary_window([relay, actual], entry), actual)

    def test_re2_literal_escapes_title_operators_without_changing_spaces(self):
        import re
        title = 'My App [test] (v2)+.?'
        pattern = '^' + sm.regex_literal(title) + '$'
        self.assertIsNotNone(re.fullmatch(pattern, title))
        self.assertIsNone(re.fullmatch(pattern, 'My App test v2'))


if __name__ == "__main__":
    unittest.main()
