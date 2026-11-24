import QtQuick
import QtQuick.Controls.Basic

// The app's pop-up menu: a rounded card in the window's colours, with a soft shadow below it.
// Its choices are AppMenuItem, grouped with AppMenuSeparator.
Menu {
    id: menu
    padding: 6
    margins: 8  // never past the window's edge

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 110; easing.type: Easing.OutCubic }
    }

    background: Rectangle {
        implicitWidth: 260
        radius: 10
        color: Theme.surface
        border.width: 1
        border.color: Theme.dark ? Theme.borderStrong : Theme.border

        Repeater {  // the shadow: faint layers, each a little wider, a little lower than the card
            model: 4
            Rectangle {
                required property int index
                z: -1
                anchors.fill: parent
                anchors.margins: -(index + 1)
                anchors.topMargin: 1 - index
                anchors.bottomMargin: -(index + 4)
                radius: 11 + index
                color: Qt.rgba(0, 0, 0, Theme.dark ? 0.16 : 0.035)
            }
        }
    }
}
