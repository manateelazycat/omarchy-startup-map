import QtQuick
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.manateelazycat.startup-map"
  readonly property var startupService: bar?.shell?.serviceFor(root.moduleName)

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰐖"
    active: root.startupService ? root.startupService.opened : false
    tooltipText: "登录启动应用"
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.LeftButton && root.startupService)
        root.startupService.toggle()
    }
  }
}
