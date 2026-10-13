// SPDX-License-Identifier: MIT
// Copyright (c) David Heinemeier Hansson
// See OMARCHY-LICENSE for the upstream permission notice.
// Adapted from Omarchy shell/Ui/TextField.qml (Omarchy 4.0.4).
// Qualify Commons.Color for Qt 6.12 compatibility.
import QtQuick
import QtQuick.Controls as Controls
import Quickshell.Io
import qs.Commons as Commons
import qs.Ui as ShellUi

// Single-line text input with the kit's focus + selection styling. Inherits
// from Qt Quick Controls TextField so the underlying type's API (text,
// placeholderText, accepted, editingFinished, validator, ...) is available
// to callers without re-exposing each property.
//
// Defaults bind to qs.Commons.Color so a caller with no theme overrides
// just works; foreground / accent / selectionTint can be overridden per
// instance. activeFocus and mouse hover / panel cursor use the same
// hover-cursor defaults, so text inputs match Button, Toggle, and Dropdown.
//
// Sizing is driven by font.pixelSize + verticalPadding. The default 30px
// implicitHeight fits dialog forms; inline callers (wifi's row-embedded
// passphrase prompt) drop verticalPadding to match a 22-26px row.
Controls.TextField {
  id: root

  property color foreground: Commons.Color.foreground
  property color accent: Commons.Color.accent
  property color selectionTint: Commons.Style.selectionFillFor(foreground, accent)
  property bool password: false
  property real horizontalPadding: Commons.Style.spacing.controlPaddingX
  property real verticalPadding: Commons.Style.spacing.inputPaddingY

  // Panel-cursor flag. When true (and the field isn't already focused),
  // the background paints the shared hover/cursor state.
  // For mouse-enter/leave the consumer reads QQC TextField's inherited
  // `hovered` property (via onHoveredChanged) — we don't add a sibling
  // signal because the inherited property would shadow it.
  property bool hasCursor: false

  // Qt's native paste reads an entire foreign offer synchronously. Never
  // route paste gestures or the context menu through that implementation.
  property bool editingEnabled: true
  readOnly: !editingEnabled || !visible || !enabled
  property string pasteError: ""
  property string _pasteText: ""
  property int _pasteStart: 0
  property int _pasteEnd: 0
  readonly property string _clipboardHelper: decodeURIComponent(
    String(Qt.resolvedUrl("../clipboard_read.py")).replace(/^file:\/\//, ""))

  function pasteBounded(primary) {
    if (readOnly || !activeFocus || clipboardProcess.running) return
    pasteError = ""
    _pasteText = text
    _pasteStart = selectionStart
    _pasteEnd = selectionEnd
    clipboardProcess.command = ["python3", _clipboardHelper].concat(primary ? ["--primary"] : [])
    clipboardProcess.running = true
  }

  onActiveFocusChanged: { if (!activeFocus) clipboardProcess.running = false }
  onReadOnlyChanged: { if (readOnly) clipboardProcess.running = false }

  Keys.onShortcutOverride: event => {
    if (event.matches(StandardKey.Paste)) event.accepted = true
  }
  Keys.onPressed: event => {
    if (event.matches(StandardKey.Paste)) {
      event.accepted = true
      pasteBounded(false)
    }
  }

  MouseArea {
    anchors.fill: parent
    acceptedButtons: Qt.MiddleButton
    onPressed: mouse => {
      if (root.readOnly) return
      root.forceActiveFocus()
      root.cursorPosition = root.positionAt(mouse.x, mouse.y)
      root.pasteBounded(true)
    }
  }

  Controls.ContextMenu.menu: Controls.Menu {
    Controls.MenuItem { text: qsTr("Cut"); enabled: !root.readOnly && root.selectedText.length > 0; onTriggered: root.cut() }
    Controls.MenuItem { text: qsTr("Copy"); enabled: root.selectedText.length > 0; onTriggered: root.copy() }
    Controls.MenuItem { text: qsTr("Paste"); enabled: !root.readOnly; onTriggered: { root.forceActiveFocus(); root.pasteBounded(false) } }
    Controls.MenuItem { text: qsTr("Select All"); onTriggered: root.selectAll() }
  }

  PanelToolTip {
    visible: root.pasteError.length > 0 && root.activeFocus
    text: qsTr("无法粘贴：") + root.pasteError
    delay: 0
    timeout: 4000
  }

  Process {
    id: clipboardProcess
    stdout: StdioCollector {
      onStreamFinished: {
        if (root.readOnly || !root.activeFocus || root.text !== root._pasteText
            || root.selectionStart !== root._pasteStart || root.selectionEnd !== root._pasteEnd) return
        try {
          const result = JSON.parse(text)
          if (!result.ok) { root.pasteError = result.error; return }
          // A single-line input follows Qt's usual newline handling.
          const pasted = result.text.replace(/[\r\n]/g, " ")
          if (root._pasteEnd > root._pasteStart) root.remove(root._pasteStart, root._pasteEnd)
          root.insert(root._pasteStart, pasted)
        } catch (error) { root.pasteError = "Clipboard text unavailable" }
      }
    }
  }

  readonly property bool _focused: activeFocus
  readonly property bool _hot: hovered || hasCursor
  readonly property var _borderSpec: Commons.Border.controlSpec(_focused ? "focus" : (_hot ? "hover-cursor" : "normal"), root.foreground, root.accent)

  echoMode: password ? TextInput.Password : TextInput.Normal
  font.family: Commons.Style.font.family
  font.pixelSize: Commons.Style.font.body
  color: foreground
  selectionColor: selectionTint
  selectedTextColor: foreground
  placeholderTextColor: Qt.darker(foreground, 1.6)

  leftPadding: horizontalPadding + Commons.Border.left(_borderSpec)
  rightPadding: horizontalPadding + Commons.Border.right(_borderSpec)
  topPadding: verticalPadding + Commons.Border.top(_borderSpec)
  bottomPadding: verticalPadding + Commons.Border.bottom(_borderSpec)

  background: ShellUi.BorderSurface {
    color: Commons.Style.controlFill(root._focused, root._hot, root.foreground, root.accent)
    borderSpec: root._borderSpec
    radius: Commons.Style.cornerRadius
  }
}
