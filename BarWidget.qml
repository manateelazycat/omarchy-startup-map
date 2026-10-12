import "CompatUi" as ThemeUi
import QtQuick
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.manateelazycat.startup-map"
  readonly property var startupService: bar?.shell?.serviceFor(root.moduleName)

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  ThemeUi.BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    iconComponent: Component {
      RocketIcon {
        color: button.active && button.useActiveColor ? button.activeColor : button.foreground
      }
    }
    active: root.startupService ? root.startupService.opened : false
    tooltipText: "登录启动应用"
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.LeftButton && root.startupService)
        root.startupService.toggle()
    }
  }
}
