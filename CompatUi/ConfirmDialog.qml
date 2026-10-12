// SPDX-License-Identifier: MIT
// Copyright (c) David Heinemeier Hansson
// See OMARCHY-LICENSE for the upstream permission notice.
// Adapted from Omarchy shell/Ui/ConfirmDialog.qml (Omarchy 4.0.4).
// Qualify Commons.Color for Qt 6.12 compatibility.
import QtQuick
import qs.Commons as Commons
import qs.Ui as ShellUi

Item {
  id: root

  property bool opened: false
  property string message: ""
  property string cancelText: "Cancel"
  property string confirmText: "Confirm"
  property int selectedIndex: 1
  property color background: Commons.Color.background
  property color foreground: Commons.Color.foreground
  property color scrim: Commons.Util.alpha(Commons.Color.background, 0.7)
  property color selectedBackground: Commons.Util.alpha(Commons.Color.foreground, 0.08)
  property color selectedText: Commons.Color.accent
  property string fontFamily: Commons.Style.font.family
  property int cornerRadius: Commons.Style.cornerRadius

  signal canceled()
  signal confirmed()

  function handleKey(event) {
    if (!root.opened) return false

    if (event.key === Qt.Key_Escape) {
      root.canceled()
      return true
    } else if (event.key === Qt.Key_Left || event.key === Qt.Key_Right || event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
      root.selectedIndex = root.selectedIndex === 0 ? 1 : 0
      return true
    } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
      if (root.selectedIndex === 0) root.canceled()
      else root.confirmed()
      return true
    }

    return false
  }

  visible: opened

  Rectangle {
    anchors.fill: parent
    color: root.scrim

    MouseArea { anchors.fill: parent; onClicked: root.canceled() }

    ShellUi.BorderSurface {
      id: card
      width: Math.min(parent.width - Commons.Style.space(32), Commons.Style.space(370))
      // Grows with the wrapped message so narrow hosts (like the menu card)
      // don't squeeze the text into the buttons.
      height: card.contentTopInset + card.contentBottomInset + messageText.implicitHeight + Commons.Style.space(20) + Commons.Style.space(34)
      anchors.centerIn: parent
      color: root.background
      borderSpec: Commons.Border.flat(root.selectedText, Commons.Style.normalBorderWidth)
      padding: Commons.Style.space(18)
      radius: root.cornerRadius

      MouseArea { anchors.fill: parent; onClicked: {} }

      Item {
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset

        Text {
          id: messageText
          textFormat: Text.PlainText
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          text: root.message
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Commons.Style.font.title
          wrapMode: Text.WordWrap
        }

        Row {
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          spacing: Commons.Style.space(10)

          Repeater {
            model: [root.cancelText, root.confirmText]

            ShellUi.BorderSurface {
              required property int index
              required property string modelData

              readonly property bool selected: root.selectedIndex === index
              readonly property bool destructive: index === 1

              width: Commons.Style.space(88)
              height: Commons.Style.space(34)
              color: selected
                ? (destructive ? Commons.Util.alpha(Commons.Color.urgent, 0.22) : root.selectedBackground)
                : "transparent"
              borderSpec: Commons.Border.flat(destructive
                ? (selected ? Commons.Color.urgent : Commons.Util.alpha(Commons.Color.urgent, 0.56))
                : (selected ? root.selectedText : Commons.Util.alpha(root.foreground, 0.38)), Commons.Style.normalBorderWidth)
              radius: 0

              Text {
                textFormat: Text.PlainText
                anchors.centerIn: parent
                text: modelData
                color: destructive ? (selected ? Commons.Color.urgent : root.foreground) : (selected ? root.selectedText : root.foreground)
                font.family: root.fontFamily
                font.pixelSize: Commons.Style.font.caption
              }

              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onEntered: root.selectedIndex = index
                onClicked: {
                  if (index === 0) root.canceled()
                  else root.confirmed()
                }
              }
            }
          }
        }
      }
    }
  }
}
