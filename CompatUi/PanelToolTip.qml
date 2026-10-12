// SPDX-License-Identifier: MIT
// Copyright (c) David Heinemeier Hansson
// See OMARCHY-LICENSE for the upstream permission notice.
// Adapted from Omarchy shell/Ui/PanelToolTip.qml (Omarchy 4.0.4).
// Qualify Commons.Color for Qt 6.12 compatibility.
import QtQuick
import QtQuick.Controls
import qs.Commons as Commons
import qs.Ui as ShellUi

// Styled wrapper around Qt Quick Controls ToolTip. Drop-in: declare inside
// the hovered item and bind `visible` to the hover state, e.g.
//   PanelToolTip {
//     visible: mouse.containsMouse
//     text: "Forget network"
//   }
//
// Defaults pull from [tooltip] in shell.toml via Commons.Color.tooltip.*. Override
// the panel* properties per-instance only when you need a tooltip that
// intentionally diverges from the theme.
//
// Property names are prefixed `panel*` to avoid clashing with ToolTip's
// built-in `background`/`font` properties.
ToolTip {
  id: root

  property color panelForeground: Commons.Color.tooltip.text
  property color panelBackground: Commons.Color.tooltip.background
  property color panelBorder: Commons.Color.tooltip.border
  property string fontFamily: Commons.Style.font.family
  property real fontSize: Commons.Style.font.bodySmall

  readonly property var panelBorderSpec: Commons.Border.flat(panelBorder, Commons.Style.normalBorderWidth)

  delay: 400
  padding: 0

  background: ShellUi.BorderSurface {
    color: root.panelBackground
    borderSpec: root.panelBorderSpec
    radius: Commons.Style.cornerRadius
  }

  contentItem: Text {
    textFormat: Text.PlainText
    text: root.text
    color: root.panelForeground
    font.family: root.fontFamily
    font.pixelSize: root.fontSize
    leftPadding: Commons.Border.left(root.panelBorderSpec) + Commons.Style.spacing.controlPaddingX
    rightPadding: Commons.Border.right(root.panelBorderSpec) + Commons.Style.spacing.controlPaddingX
    topPadding: Commons.Border.top(root.panelBorderSpec) + Commons.Style.spacing.controlPaddingY
    bottomPadding: Commons.Border.bottom(root.panelBorderSpec) + Commons.Style.spacing.controlPaddingY
  }
}
