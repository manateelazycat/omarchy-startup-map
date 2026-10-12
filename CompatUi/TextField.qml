// SPDX-License-Identifier: MIT
// Copyright (c) David Heinemeier Hansson
// See OMARCHY-LICENSE for the upstream permission notice.
// Adapted from Omarchy shell/Ui/TextField.qml (Omarchy 4.0.4).
// Qualify Commons.Color for Qt 6.12 compatibility.
import QtQuick
import QtQuick.Controls as Controls
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
