import QtQuick
import QtQuick.Controls.Basic

// A button showing only an icon. Its `text` is what it is called (read out by screen readers), not shown.
AbstractButton {
    id: control
    property string iconName: ""
    property color iconColor: Theme.muted

    implicitWidth: 40
    implicitHeight: 40
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: text

    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: control.iconName
            size: 18
            color: control.iconColor
        }
    }
    background: Rectangle {
        radius: 8
        color: control.down || control.hovered ? Theme.subtle : "transparent"
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.text
    }
}
