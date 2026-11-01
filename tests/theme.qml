import QtQuick
import QtTest
import Quickshell
import qs.Commons as Commons
import "Plugin" as Plugin
import "Plugin/CompatUi" as StartupUi

ShellRoot {
    id: test
    Plugin.Service { id: service; launchStarted: true }
    StartupUi.Button { id: button; text: "保存" }
    StartupUi.TextField { id: field; text: "应用" }
    StartupUi.PanelActionButton { id: action; iconText: "+" }
    StartupUi.ConfirmDialog { id: confirmation; message: "确认" }
    TestCase { id: checks; when: false }
    function check(value, message) { if (!value) throw new Error(message); }
    function checkPalette() {
        check(button.foreground === Commons.Color.foreground, "Button foreground");
        check(button.accent === Commons.Color.accent, "Button accent");
        check(button.tooltipBackground === Commons.Color.tooltip.background, "Button tooltip");
        check(field.foreground === Commons.Color.foreground, "Input foreground");
        check(field.accent === Commons.Color.accent, "Input accent");
        check(action.foreground === Commons.Color.foreground, "Action foreground");
        check(confirmation.background === Commons.Color.background, "Confirmation background");
        check(confirmation.foreground === Commons.Color.foreground, "Confirmation foreground");
        check(confirmation.selectedText === Commons.Color.accent, "Confirmation accent");
    }
    Timer {
        interval: 250; running: true
        onTriggered: {
            try {
                checkPalette();
                var screen = Quickshell.screens[0];
                service.dialogScreenName = screen.name;
                service.selectedMonitorName = screen.name;
                service.dialogCenterX = screen.width / 2;
                service.dialogCenterY = screen.height / 2;
                service.displays = [{name: screen.name, width: screen.width, height: screen.height, x: 0, y: 0}];
                service.draftEntries = [{id: "test", name: "测试", command: "/bin/true", monitor: screen.name, position: 1}];
                service.opened = true;
                checks.wait(100);
                var overlay = service.testWindows.instances[0];
                var loader = checks.findChild(overlay.contentItem, "searchFieldLoader");
                var nameField = checks.findChild(overlay.contentItem, "nameField");
                check(loader !== null && nameField !== null, "Dialog controls exist");
                check(loader.item === null, "Search field absent before picker opens");
                check(!nameField.readOnly, "Visible dialog allows editing");
                Commons.Color.background = "#060b1e";
                Commons.Color.foreground = "#ffcead";
                Commons.Color.accent = "#7d82d9";
                checks.wait(100);
                checkPalette();
                service.searchingRowId = "test";
                checks.wait(100);
                check(loader.item !== null, "Search field created when picker opens");
                check(nameField.readOnly, "Covered dialog is read-only");
                check(loader.item.foreground === Commons.Color.foreground, "Search field theme");
                service.searchingRowId = "";
                checks.wait(50);
                check(loader.item === null, "Search field destroyed when picker closes");
                service.confirmationKind = "discard";
                checks.wait(100);
                checkPalette();
                check(nameField.readOnly, "Confirmation makes dialog read-only");
                Commons.Color.background = "#fafafa";
                Commons.Color.foreground = "#202020";
                Commons.Color.accent = "#0055aa";
                checks.wait(100);
                checkPalette();
                service.close();
                checks.wait(50);
                check(nameField.readOnly, "Hidden dialog is read-only");
                service.draftEntries = [{id: "catalog-test", name: "Test", command: "/bin/true",
                    desktopId: "test.desktop", monitor: screen.name, position: 1, delaySeconds: 17}];
                service.openPicker("catalog-test");
                checks.tryVerify(function() { return service.lazycatEntries.length === 1; }, 3000);
                service.searchQuery = "网盘";
                checks.wait(50);
                check(service.pickerRows.length === 1, "Chinese alias finds cloud app");
                service.chooseApp(0);
                check(service.draftEntries[0].lazycatAppId === "test.files", "Cloud identity selected");
                check(service.draftEntries[0].desktopId === "", "Cloud app never uses gtk-launch desktop ID");
                check(service.draftEntries[0].delaySeconds === 17, "Selection preserves launch delay");
                service.draftEntries[0].delaySeconds = -1;
                service.save();
                check(!service.saving && service.errorMessage.indexOf("延时") >= 0, "Invalid delay rejected before writing");
                service.draftEntries[0].delaySeconds = 17;
                service.save();
                checks.tryVerify(function() { return !service.saving && service.savedEntries.length === 1
                    && service.savedEntries[0].lazycatAppId === "test.files"; }, 3000);
                check(service.savedEntries[0].delaySeconds === 17, "Saved cloud app retains its delay");
                service.searchingRowId = "catalog-test";
                service.lazycatEntries = [];
                service.searchQuery = "";
                // Also exercise selection back to a native DesktopEntry.
                if (service.pickerRows.length) {
                    service.chooseApp(0);
                    check(service.draftEntries[0].lazycatAppId === "", "Native selection clears cloud identity");
                    check(service.draftEntries[0].delaySeconds === 17, "Native selection preserves delay");
                }
                console.log("STARTUP_MAP_THEME_PASS");
            } catch (error) { console.log("STARTUP_MAP_THEME_FAIL", String(error)); }
            Qt.quit();
        }
    }
}
