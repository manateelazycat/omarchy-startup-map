import QtQuick
import QtTest
import Quickshell
import "Plugin" as Plugin

ShellRoot {
    id: test
    Plugin.Service { id: service; launchStarted: true }
    TestCase { id: checks; when: false }
    function check(value, message) { if (!value) throw new Error(message); }
    function waitUntil(predicate, message) {
        for (var i = 0; i < 100 && !predicate(); i++) checks.wait(10);
        check(predicate(), message);
    }
    Timer {
        interval: 200; running: true
        onTriggered: {
            try {
                waitUntil(function() { return service.savedEntries.length === 1; }, "Initial file loaded");
                var screen = Quickshell.screens[0];
                service.dialogScreenName = screen.name;
                service.selectedMonitorName = "TEST";
                service.dialogCenterX = screen.width / 2;
                service.dialogCenterY = screen.height / 2;
                service.displays = [{name: "TEST", width: screen.width, height: screen.height, x: 0, y: 0}];
                service.draftEntries = service.cloneRows(service.savedEntries);
                service.opened = true;
                checks.wait(100);
                var overlay = service.testWindows.instances[0];
                var field = checks.findChild(overlay.contentItem, "delayField");
                var button = checks.findChild(overlay.contentItem, "saveButton");
                var closeButton = checks.findChild(overlay.contentItem, "closeButton");
                check(field !== null && button !== null && closeButton !== null, "Save and close controls exist");
                field.forceActiveFocus();
                checks.keyClick(Qt.Key_A, Qt.ControlModifier);
                checks.keyClick(Qt.Key_1);
                checks.keyClick(Qt.Key_0);
                check(field.text === "10", "Delay input has 10");
                check(Number(service.draftEntries[0].delaySeconds) === 10, "Draft has 10");
                checks.mouseClick(button);
                waitUntil(function() { return !service.saving; }, "First save must complete immediately");
                check(service.opened, "Successful save keeps dialog open");
                check(!service.dirty, "Successful save clears unsaved changes");
                check(service.draftEntries[0].delaySeconds === 10, "Draft is normalized after saving");
                check(service.savedEntries[0].delaySeconds === 10, "Saved delay is 10");
                checks.wait(100);
                checks.mouseClick(button);
                waitUntil(function() { return !service.saving; }, "Unchanged save must complete immediately");
                check(service.opened, "Unchanged save keeps dialog open");
                checks.mouseClick(closeButton);
                check(!service.opened, "Close button closes saved dialog");
                service.opened = true;
                checks.wait(50);
                field = checks.findChild(overlay.contentItem, "delayField");
                field.forceActiveFocus();
                checks.keyClick(Qt.Key_A, Qt.ControlModifier);
                checks.keyClick(Qt.Key_1);
                checks.keyClick(Qt.Key_1);
                checks.mouseClick(closeButton);
                check(service.opened && service.confirmationKind === "discard", "Close confirms unsaved changes");
                service.confirmAction();
                check(!service.opened, "Confirmed discard closes dialog");
                check(service.savedEntries[0].delaySeconds === 10, "Discard preserves saved delay");
                console.log("STARTUP_MAP_SAVE_PASS");
            } catch (error) { console.log("STARTUP_MAP_SAVE_FAIL", String(error)); }
            Qt.quit();
        }
    }
}
