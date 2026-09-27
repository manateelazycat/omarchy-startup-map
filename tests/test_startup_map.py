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


if __name__ == "__main__":
    unittest.main()
