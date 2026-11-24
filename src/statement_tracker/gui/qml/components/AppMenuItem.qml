import QtQuick
import QtQuick.Controls.Basic

// One choice in an AppMenu: an icon and a label. `danger` for a choice that removes something; `radio`
// for one of several choices, with a round mark instead of the icon, filled when it is the one `chosen`.
MenuItem {
    id: item
    property string iconName: ""
    property bool danger: false
    property bool radio: false
    property bool chosen: false

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
        Rectangle {
            visible: item.radio
            anchors.verticalCenter: parent.verticalCenter
            width: 16
            height: 16
            radius: 8
            color: "transparent"
            border.width: 1.5
            border.color: item.chosen ? Theme.accent : Theme.borderStrong
            Rectangle {
                visible: item.chosen
                anchors.centerIn: parent
                width: 8
                height: 8
                radius: 4
                color: Theme.accent
            }
        }
        Icon {
            visible: !item.radio
            anchors.verticalCenter: parent.verticalCenter
            name: item.iconName
            size: 16
            color: item.danger ? Theme.errInk : Theme.muted
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: item.text
            color: item.danger ? Theme.errInk : Theme.text
            font.pixelSize: item.font.pixelSize
            font.weight: item.radio && item.chosen ? Font.DemiBold : Font.Normal
        }
    }

    background: Rectangle {
        radius: 6
        color: !item.highlighted || !item.enabled ? "transparent" : item.danger ? Theme.errBg : Theme.subtle
    }
}
