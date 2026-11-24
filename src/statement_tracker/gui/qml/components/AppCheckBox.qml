import QtQuick
import QtQuick.Controls.Basic

// A tick box in the app's colours: a rounded square that turns green with a white tick when ticked.
// The label wraps beside it, the box level with its first line.
CheckBox {
    id: box
    spacing: 12
    font.pixelSize: 13
    hoverEnabled: true

    indicator: Rectangle {
        implicitWidth: 20
        implicitHeight: 20
        x: box.leftPadding
        y: box.topPadding
        radius: 5
        color: box.checked ? Theme.accent : Theme.surface
        border.width: box.checked ? 0 : 1.5
        border.color: box.hovered || box.down ? Theme.accent : Theme.borderStrong

        Icon {
            anchors.centerIn: parent
            visible: box.checked
            name: "tick"
            size: 14
            strokeWidth: 2.6
            color: Theme.accentText
        }
        Rectangle {  // the keyboard focus ring, a little outside the box
            visible: box.visualFocus
            anchors.fill: parent
            anchors.margins: -3
            radius: 7
            color: "transparent"
            border.width: 2
            border.color: Theme.text
        }
    }

    contentItem: Text {
        text: box.text
        font: box.font
        color: Theme.text
        wrapMode: Text.Wrap
        leftPadding: box.indicator.width + box.spacing
        topPadding: Math.max(0, (box.indicator.height - firstLine.height) / 2)
        verticalAlignment: Text.AlignTop
        FontMetrics { id: firstLine; font: box.font }
    }
}
