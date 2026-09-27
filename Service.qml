import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "Layout.js" as DisplayLayout
import "AppCatalog.js" as AppCatalog

Item {
  id: root

  property var shell: null
  property bool opened: false
  property bool launchStarted: false
  property var savedEntries: []
  property var draftEntries: []
  property var pendingEntries: []
  property bool dirty: false
  property bool saving: false
  property var displays: []
  property string dialogScreenName: ""
  property string selectedMonitorName: ""
  property real dialogCenterX: 0
  property real dialogCenterY: 0
  property string errorMessage: ""
  property string searchingRowId: ""
  property string searchQuery: ""
  property int pickerIndex: 0
  property int catalogRevision: 0
  property string confirmationKind: ""
  property string confirmationRowId: ""
  property string confirmationRowName: ""
  property string newlyAddedId: ""

  readonly property string configPath: (Quickshell.env("XDG_CONFIG_HOME")
    || (Quickshell.env("HOME") + "/.config")) + "/omarchy/startup-map.json"
  readonly property string helperPath: {
    var url = String(Qt.resolvedUrl("startup_map.py"))
    try { return decodeURIComponent(url.replace(/^file:\/\//, "")) }
    catch (error) { return url.replace(/^file:\/\//, "") }
  }
  readonly property var mapBounds: DisplayLayout.bounds(root.displays)
  readonly property var visibleEntries: root.draftEntries.filter(function(entry) {
    return entry.monitor === root.selectedMonitorName
  }).sort(function(a, b) {
    return (Number(a.position) || 0) - (Number(b.position) || 0)
  })
  readonly property var pickerRows: {
    var serial = root.catalogRevision
    void serial
    return AppCatalog.filtered(DesktopEntries.applications.values || [], root.searchQuery)
  }

  function cloneRows(rows) { return JSON.parse(JSON.stringify(rows || [])) }

  function loadConfig(raw) {
    try {
      var parsed = JSON.parse(String(raw || ""))
      if (parsed.version !== 1 || !Array.isArray(parsed.entries))
        throw new Error("配置格式不正确")
      root.savedEntries = root.cloneRows(parsed.entries)
      if (!root.opened) root.draftEntries = root.cloneRows(root.savedEntries)
      root.errorMessage = ""
    } catch (error) {
      root.savedEntries = []
      if (!root.opened) root.draftEntries = []
      if (String(raw || "").trim().length > 0)
        root.errorMessage = "无法读取配置：" + error
    }
    if (!root.launchStarted) {
      root.launchStarted = true
      startupProcess.running = true
    }
  }

  function open() {
    if (root.opened) return
    root.draftEntries = root.cloneRows(root.savedEntries)
    root.dirty = false
    root.errorMessage = ""
    root.searchingRowId = ""
    root.opened = true
    snapshotProcess.running = true
  }

  function close() {
    root.opened = false
    root.searchingRowId = ""
    root.confirmationKind = ""
  }

  function requestClose() {
    if (root.saving) return
    if (root.searchingRowId) { root.searchingRowId = ""; return }
    if (root.dirty) { root.confirmationKind = "discard"; return }
    root.close()
  }

  function toggle() {
    if (root.opened) root.requestClose()
    else root.open()
  }

  function applySnapshot(raw) {
    var parsed = JSON.parse(raw)
    root.displays = DisplayLayout.normalize(parsed.monitors || [], Quickshell.screens)
    if (!root.displays.length) throw new Error("没有可用的显示器")
    var active = parsed.activeWindow || {}
    var display = root.displays.find(function(item) { return item.id === active.monitor })
      || root.displays.find(function(item) { return item.focused }) || root.displays[0]
    root.dialogScreenName = display.name
    root.selectedMonitorName = display.name
    var at = active.at || []
    var size = active.size || []
    if (active.monitor === display.id && at.length === 2 && size.length === 2) {
      root.dialogCenterX = Number(at[0]) - display.x + Number(size[0]) / 2
      root.dialogCenterY = Number(at[1]) - display.y + Number(size[1]) / 2
    } else {
      root.dialogCenterX = display.width / 2
      root.dialogCenterY = display.height / 2
    }
  }

  function countForMonitor(name) {
    return root.draftEntries.filter(function(entry) { return entry.monitor === name }).length
  }

  function addRow() {
    if (!root.selectedMonitorName) return
    var maximum = 0
    for (var entry of root.visibleEntries) maximum = Math.max(maximum, Number(entry.position) || 0)
    var position = Math.min(100, maximum + 1)
    var id = String(Date.now()) + "-" + String(Math.random()).slice(2)
    root.newlyAddedId = id
    root.draftEntries = root.draftEntries.concat([{ id: id, name: "", command: "",
      desktopId: "", monitor: root.selectedMonitorName, position: position }])
    root.dirty = true
    root.errorMessage = ""
  }

  function askDelete(row) {
    if (!String(row.name || "").trim() && !String(row.command || "").trim()
        && !String(row.desktopId || "").trim()) {
      root.removeRow(row.id)
      return
    }
    root.confirmationRowId = row.id
    root.confirmationRowName = row.name || "这条应用"
    root.confirmationKind = "delete"
  }

  function removeRow(id) {
    root.draftEntries = root.draftEntries.filter(function(entry) { return entry.id !== id })
    root.dirty = JSON.stringify(root.draftEntries) !== JSON.stringify(root.savedEntries)
    root.errorMessage = ""
  }

  function confirmAction() {
    if (root.confirmationKind === "delete") {
      root.removeRow(root.confirmationRowId)
    } else if (root.confirmationKind === "discard") {
      root.close()
    }
    root.confirmationKind = ""
    root.errorMessage = ""
  }

  function openPicker(id) {
    root.searchingRowId = id
    root.searchQuery = ""
    root.pickerIndex = 0
  }

  function chooseApp(index) {
    var selected = root.pickerRows[index]
    if (!selected) return
    var entry = selected.entry
    var updated = root.draftEntries.map(function(row) {
      if (row.id !== root.searchingRowId) return row
      return Object.assign({}, row, { name: String(entry.name || ""),
        command: String(entry.execString || ""), desktopId: String(entry.id || "") })
    })
    root.draftEntries = updated
    root.dirty = true
    root.searchingRowId = ""
    root.errorMessage = ""
  }

  function save() {
    if (root.saving) return
    var clean = []
    for (var i = 0; i < root.draftEntries.length; i++) {
      var entry = root.draftEntries[i]
      var name = String(entry.name || "").trim()
      var command = String(entry.command || "").trim()
      var position = Number(entry.position)
      if (!name || !command || !Number.isInteger(position) || position < 1 || position > 100) {
        root.errorMessage = "请填写每条应用的名称、启动命令和 1–100 的工作区位置"
        return
      }
      clean.push({ id: String(entry.id), name: name, command: command,
        desktopId: String(entry.desktopId || ""), monitor: String(entry.monitor),
        position: position })
    }
    root.pendingEntries = clean
    root.saving = true
    configFile.setText(JSON.stringify({ version: 1, entries: clean }, null, 2) + "\n")
  }

  function iconFor(name) {
    var result = Quickshell.iconPath(String(name || "application-x-executable"), true)
    return result || Quickshell.iconPath("application-x-executable", true)
  }

  FileView {
    id: configFile
    path: root.configPath
    watchChanges: true
    atomicWrites: true
    printErrors: false
    onLoaded: root.loadConfig(text())
    onLoadFailed: root.loadConfig("")
    onFileChanged: reload()
    onSaved: {
      if (!root.saving) return
      root.savedEntries = root.cloneRows(root.pendingEntries)
      root.dirty = false
      root.saving = false
      root.close()
    }
    onSaveFailed: {
      root.saving = false
      root.errorMessage = "保存失败，请检查配置文件权限"
    }
  }

  Process {
    id: startupProcess
    command: ["python3", root.helperPath, "launch"]
    stderr: StdioCollector { id: startupError; waitForEnd: true }
    onExited: function(code) {
      var warning = String(startupError.text || "").trim()
      if (warning || code !== 0)
        console.warn("[Startup Map] " + (warning || "启动失败"))
    }
  }

  Process {
    id: snapshotProcess
    command: ["python3", root.helperPath, "snapshot"]
    stdout: StdioCollector { id: snapshotOutput; waitForEnd: true }
    stderr: StdioCollector { id: snapshotError; waitForEnd: true }
    onExited: function(code) {
      if (!root.opened) return
      try {
        if (code !== 0) throw new Error(String(snapshotError.text || "无法读取窗口信息").trim())
        root.applySnapshot(String(snapshotOutput.text || "{}"))
      } catch (error) {
        root.errorMessage = String(error)
        var screen = Quickshell.screens[0]
        if (screen) {
          root.dialogScreenName = screen.name
          root.selectedMonitorName = screen.name
          root.dialogCenterX = screen.width / 2
          root.dialogCenterY = screen.height / 2
          root.displays = [{ name: screen.name, model: "", id: -1,
            x: 0, y: 0, width: screen.width, height: screen.height, focused: true }]
        }
      }
    }
  }

  Connections {
    target: DesktopEntries.applications
    function onValuesChanged() { root.catalogRevision++ }
  }

  IpcHandler {
    target: "io.github.manateelazycat.startup-map"
    function show(): void { root.open() }
    function hide(): void { root.requestClose() }
    function toggle(): void { root.toggle() }
  }

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: overlay
      required property ShellScreen modelData
      screen: modelData
      visible: root.opened && root.dialogScreenName === modelData.name
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.namespace: "omarchy-startup-map"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
      anchors { top: true; bottom: true; left: true; right: true }

      Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.44)
        MouseArea { anchors.fill: parent; onClicked: root.requestClose() }
      }

      Item {
        anchors.fill: parent
        focus: overlay.visible
        Keys.onEscapePressed: root.requestClose()

        Rectangle {
          id: card
          width: Math.min(760, parent.width - 28)
          height: Math.min(720, parent.height - 28,
            (root.displays.length > 1 ? 470 : 315)
              + Math.max(0, Math.min(3, root.visibleEntries.length) * 154 - 100))
          x: Math.max(14, Math.min(parent.width - width - 14, root.dialogCenterX - width / 2))
          y: Math.max(14, Math.min(parent.height - height - 14, root.dialogCenterY - height / 2))
          color: Color.background
          border.color: Color.accent
          border.width: 1
          radius: 0

          MouseArea { anchors.fill: parent; onClicked: {} }

          Text {
            id: heading
            x: 24; y: 20
            text: "登录启动应用"
            color: Color.foreground
            font.family: Style.font.family
            font.pixelSize: 23
            font.bold: true
          }

          Text {
            x: 24; y: 57
            width: parent.width - 48
            text: root.errorMessage || "选择应用启动后所在的显示器与工作区；更改将在下次登录时生效"
            color: root.errorMessage ? Color.urgent : Color.foreground
            opacity: root.errorMessage ? 1 : 0.65
            font.family: Style.font.family
            font.pixelSize: 13
            elide: Text.ElideRight
          }

          Rectangle {
            id: mapCanvas
            x: 24; y: 88
            width: parent.width - 48
            height: root.displays.length > 1 ? 145 : 0
            visible: root.displays.length > 1
            color: Qt.rgba(0.5, 0.5, 0.5, 0.08)
            border.color: Qt.rgba(0.5, 0.5, 0.5, 0.22)
            border.width: 1

            Repeater {
              model: root.displays
              delegate: Rectangle {
                required property var modelData
                readonly property var geometry: DisplayLayout.rect(modelData, root.mapBounds,
                  mapCanvas.width, mapCanvas.height, 12)
                readonly property bool selected: root.selectedMonitorName === modelData.name
                x: geometry.x; y: geometry.y
                width: geometry.width; height: geometry.height
                color: selected ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.28)
                  : Qt.rgba(0.5, 0.5, 0.5, 0.12)
                border.color: selected ? Color.accent : Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.5)
                border.width: selected ? 2 : 1

                Text {
                  anchors.centerIn: parent
                  width: parent.width - 8
                  text: modelData.name + "\n" + root.countForMonitor(modelData.name) + " 个应用"
                  textFormat: Text.PlainText
                  color: Color.foreground
                  horizontalAlignment: Text.AlignHCenter
                  verticalAlignment: Text.AlignVCenter
                  font.family: Style.font.family
                  font.pixelSize: 13
                  font.bold: selected
                  elide: Text.ElideRight
                  maximumLineCount: 2
                }

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.selectedMonitorName = modelData.name
                }
              }
            }
          }

          Item {
            id: listHeader
            x: 24
            y: root.displays.length > 1 ? 248 : 88
            width: parent.width - 48
            height: 39

            Text {
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              text: root.selectedMonitorName + " 的启动应用"
              color: Color.foreground
              font.family: Style.font.family
              font.pixelSize: 16
              font.bold: true
            }

            Button {
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: "＋ 添加"
              focusable: true
              onClicked: root.addRow()
            }
          }

          Flickable {
            id: listView
            x: 24
            y: listHeader.y + listHeader.height + 8
            width: parent.width - 48
            height: Math.max(0, footer.y - y - 12)
            clip: true
            contentWidth: width
            contentHeight: rowColumn.height
            boundsBehavior: Flickable.StopAtBounds

            Column {
              id: rowColumn
              width: listView.width
              spacing: 10

              Repeater {
                model: root.visibleEntries
                delegate: Rectangle {
                  required property var modelData
                  property var row: modelData
                  width: rowColumn.width
                  height: 144
                  color: Qt.rgba(0.5, 0.5, 0.5, 0.07)
                  border.color: Qt.rgba(0.5, 0.5, 0.5, 0.22)
                  border.width: 1

                  Component.onCompleted: {
                    if (row.id === root.newlyAddedId) {
                      root.newlyAddedId = ""
                      Qt.callLater(function() { nameField.forceActiveFocus() })
                    }
                  }

                  Text {
                    x: 12
                    anchors.verticalCenter: nameField.verticalCenter
                    text: "名称"
                    color: Color.foreground
                    font.family: Style.font.family
                    font.pixelSize: 13
                  }

                  TextField {
                    id: nameField
                    x: 82; y: 10
                    width: parent.width - x - 48
                    placeholderText: "名称"
                    text: row.name
                    onTextEdited: { row.name = text; root.dirty = true; root.errorMessage = "" }
                  }

                  Text {
                    x: 12
                    anchors.verticalCenter: commandField.verticalCenter
                    text: "启动路径"
                    color: Color.foreground
                    font.family: Style.font.family
                    font.pixelSize: 13
                  }

                  PanelActionButton {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: nameField.verticalCenter
                    iconText: "✕"
                    tooltipText: "删除"
                    hoverColor: Color.urgent
                    onClicked: root.askDelete(row)
                  }

                  TextField {
                    id: commandField
                    x: 82; y: 53
                    width: nameField.width
                    rightPadding: horizontalPadding + 38
                    placeholderText: "绝对路径或 .desktop Exec 命令"
                    text: row.command
                    onTextEdited: {
                      row.command = text
                      row.desktopId = ""
                      root.dirty = true
                      root.errorMessage = ""
                    }

                    PanelActionButton {
                      anchors.right: parent.right
                      anchors.rightMargin: 5
                      anchors.verticalCenter: parent.verticalCenter
                      iconText: "󰍉"
                      tooltipText: "搜索应用"
                      onClicked: root.openPicker(row.id)
                    }
                  }

                  Text {
                    x: 12
                    anchors.verticalCenter: workspaceField.verticalCenter
                    text: "工作区"
                    color: Color.foreground
                    font.family: Style.font.family
                    font.pixelSize: 13
                  }

                  TextField {
                    id: workspaceField
                    x: 82; y: 96
                    width: 92
                    horizontalAlignment: TextInput.AlignHCenter
                    text: String(row.position)
                    onTextEdited: { row.position = text; root.dirty = true; root.errorMessage = "" }
                    onEditingFinished: root.draftEntries = root.draftEntries.slice()
                  }
                }
              }
            }
          }

          Text {
            anchors.centerIn: listView
            visible: root.visibleEntries.length === 0
            text: "这里还没有启动应用"
            color: Color.foreground
            opacity: 0.6
            font.family: Style.font.family
            font.pixelSize: 14
          }

          Item {
            id: footer
            x: 24
            y: card.height - 66
            width: card.width - 48
            height: 45

            Row {
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: 8
              Button { text: "取消"; focusable: true; onClicked: root.requestClose() }
              Button {
                text: root.saving ? "保存中…" : "保存"
                focusable: true
                selected: true
                enabled: !root.saving
                onClicked: root.save()
              }
            }
          }

          Rectangle {
            id: pickerOverlay
            anchors.fill: parent
            visible: root.searchingRowId !== ""
            z: 10
            color: Qt.rgba(0, 0, 0, 0.55)
            MouseArea { anchors.fill: parent; onClicked: root.searchingRowId = "" }

            Rectangle {
              width: Math.min(560, parent.width - 32)
              height: Math.min(460, parent.height - 32)
              anchors.centerIn: parent
              color: Color.background
              border.color: Color.accent
              border.width: 1
              MouseArea { anchors.fill: parent; onClicked: {} }

              Text {
                x: 18; y: 16
                text: "选择应用"
                color: Color.foreground
                font.family: Style.font.family
                font.pixelSize: 18
                font.bold: true
              }

              TextField {
                id: searchField
                x: 18; y: 52
                width: parent.width - 36
                placeholderText: "搜索应用名称…"
                text: root.searchQuery
                onTextEdited: { root.searchQuery = text; root.pickerIndex = 0 }
                Keys.onDownPressed: root.pickerIndex = Math.min(root.pickerRows.length - 1, root.pickerIndex + 1)
                Keys.onUpPressed: root.pickerIndex = Math.max(0, root.pickerIndex - 1)
                Keys.onReturnPressed: root.chooseApp(root.pickerIndex)
                Keys.onEnterPressed: root.chooseApp(root.pickerIndex)
                Keys.onEscapePressed: root.searchingRowId = ""
              }

              Connections {
                target: root
                function onSearchingRowIdChanged() {
                  if (root.searchingRowId)
                    Qt.callLater(function() { searchField.forceActiveFocus() })
                }
              }

              Flickable {
                x: 18; y: 96
                width: parent.width - 36
                height: parent.height - 114
                clip: true
                contentWidth: width
                contentHeight: searchColumn.height

                Column {
                  id: searchColumn
                  width: parent.width
                  spacing: 2

                  Repeater {
                    model: root.pickerRows
                    delegate: Rectangle {
                      required property var modelData
                      required property int index
                      readonly property var app: modelData.entry
                      width: searchColumn.width
                      height: 44
                      color: index === root.pickerIndex
                        ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.18) : "transparent"

                      Image {
                        x: 7; y: 9; width: 26; height: 26
                        source: root.iconFor(app.icon)
                        fillMode: Image.PreserveAspectFit
                      }
                      Text {
                        x: 42; y: 5; width: parent.width - 48
                        text: app.name
                        textFormat: Text.PlainText
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: 14
                        elide: Text.ElideRight
                      }
                      Text {
                        x: 42; y: 25; width: parent.width - 48
                        text: app.execString
                        textFormat: Text.PlainText
                        color: Color.foreground
                        opacity: 0.55
                        font.family: Style.font.family
                        font.pixelSize: 11
                        elide: Text.ElideRight
                      }
                      MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: root.pickerIndex = index
                        onClicked: root.chooseApp(index)
                      }
                    }
                  }
                }
              }
            }
          }

          ConfirmDialog {
            anchors.fill: parent
            z: 20
            opened: root.confirmationKind !== ""
            message: root.confirmationKind === "delete"
              ? "删除「" + root.confirmationRowName + "」的启动配置？" : "放弃未保存的更改？"
            cancelText: "取消"
            confirmText: root.confirmationKind === "delete" ? "删除" : "放弃"
            selectedIndex: 0
            onCanceled: root.confirmationKind = ""
            onConfirmed: root.confirmAction()
          }
        }
      }
    }
  }
}
