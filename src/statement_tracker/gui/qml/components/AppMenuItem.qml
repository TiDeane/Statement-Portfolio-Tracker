import QtQuick
import QtQuick.Controls.Basic

// One choice in an AppMenu: an icon and a label. `danger` for a choice that removes something.
MenuItem {
    id: item
    property string iconName: ""
    property bool danger: false

    implicitHeight: 38
    leftPadding: 12
    rightPadding: 16
    spacing: 12
    font.pixelSize: 14
    arrow: null
    indicator: null

    contentItem: Row {
        spacing: item.spacing
        opacity: item.enabled ? 1 : 0.55
        Icon {
            anchors.verticalCenter: parent.verticalCenter
            name: item.iconName
            size: 16
            color: item.danger ? Theme.errInk : Theme.muted
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: item.text
            color: item.danger ? Theme.errInk : Theme.text
            font: item.font
        }
    }

    background: Rectangle {
        radius: 6
        color: !item.highlighted || !item.enabled ? "transparent" : item.danger ? Theme.errBg : Theme.subtle
    }
}
