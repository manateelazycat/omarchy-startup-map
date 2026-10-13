import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtTest
import Quickshell
import "Plugin/CompatUi" as StartupUi

ShellRoot {
    Window {
        id: window
        width: 400; height: 200; visible: true
        StartupUi.TextField {
            id: field
            width: 350; height: 40
            property int edits: 0
            onTextEdited: edits++
        }
        TestCase {
            id: checks
            name: "BoundedClipboard"
            when: false
            function expect(value) { if (!value) throw new Error("Assertion failed"); }
            function expectEqualNow(actual, expected) {
                if (actual !== expected) throw new Error("Expected " + expected + ", got " + actual);
            }
            function expectEqual(object, property, expected) {
                expectEventually(function() { return object[property] === expected; });
            }
            function expectEventually(predicate) {
                for (var i = 0; i < 150 && !predicate(); i++) wait(10);
                expect(predicate());
            }
            function init() {
                field.visible = true;
                field.editingEnabled = true;
                field.text = "abc";
                field.cursorPosition = 3;
                field.forceActiveFocus();
                field.edits = 0;
                expectEqual(field, "activeFocus", true);
            }
            function test_keyboardPaste() {
                keyClick(Qt.Key_V, Qt.ControlModifier);
                expectEqual(field, "text", "abc应用");
                expectEqualNow(field.edits, 1);
            }
            function test_shiftInsertReplacesSelection() {
                field.select(0, 3);
                keyClick(Qt.Key_Insert, Qt.ShiftModifier);
                expectEqual(field, "text", "应用");
                expectEqualNow(field.edits, 2);
            }
            function test_primarySelection() {
                mouseClick(field, 10, 20, Qt.MiddleButton);
                expectEventually(function() { return field.text.indexOf("primary") >= 0; });
                expectEqualNow(field.edits, 1);
            }
            function test_contextMenuPaste() {
                var menu = field.ContextMenu.menu;
                menu.itemAt(2).triggered();
                expectEqual(field, "text", "abc应用");
            }
            function test_disabledAndHidden() {
                field.editingEnabled = false;
                expect(field.readOnly);
                field.pasteBounded(false);
                wait(100);
                expectEqualNow(field.text, "abc");
                field.editingEnabled = true;
                field.visible = false;
                expect(field.readOnly);
                field.pasteBounded(false);
                wait(100);
                expectEqualNow(field.text, "abc");
            }
            function test_editWhilePending() {
                field.pasteBounded(false);
                field.text = "changed";
                wait(500);
                expectEqualNow(field.text, "changed");
            }
            function test_hideWhilePending() {
                field.pasteBounded(false);
                field.visible = false;
                wait(500);
                expectEqualNow(field.text, "abc");
            }
            function test_typingStillWorks() {
                keyClick(Qt.Key_D);
                expectEqualNow(field.text, "abcd");
                keyClick(Qt.Key_Backspace);
                expectEqualNow(field.text, "abc");
            }
        }
        Timer {
            interval: 100; running: true
            onTriggered: {
                try {
                    var tests = ["keyboardPaste", "shiftInsertReplacesSelection", "primarySelection",
                                 "contextMenuPaste", "disabledAndHidden", "editWhilePending",
                                 "hideWhilePending", "typingStillWorks"];
                    for (var name of tests) {
                        console.log("Checking", name);
                        checks.init();
                        checks["test_" + name]();
                    }
                    console.log("STARTUP_MAP_CLIPBOARD_PASS");
                } catch (error) { console.log("STARTUP_MAP_CLIPBOARD_FAIL", String(error)); }
                Qt.quit();
            }
        }
    }
}
