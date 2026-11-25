import QtQuick
import QtQuick.Controls.Basic

// An on/off switch with its label on the left, in the app's colours. It shows `on` (what was saved); a click
// says `switched(value)`, and the switch then shows `on` again, whatever the click did: what could not be
// saved, or was changed again by something else later, shows as it is.
Switch {
    id: control
    property bool on: false
    signal switched(bool value)

    checked: on
    onToggled: {
        switched(checked)
        checked = Qt.binding(() => control.on)
    }
    font.pixelSize: 14
    font.weight: Font.DemiBold
    spacing: 16

    indicator: Rectangle {
        x: control.width - width - control.rightPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        implicitWidth: 44
        implicitHeight: 24
        radius: 12
        color: control.checked ? Theme.accent : Theme.surface
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? Theme.text : control.checked ? Theme.accent : Theme.muted
        Rectangle {
            x: control.checked ? parent.width - width - 4 : 4
            anchors.verticalCenter: parent.verticalCenter
            width: 16
            height: 16
            radius: 8
            color: control.checked ? Theme.accentText : Theme.muted
            Behavior on x { NumberAnimation { duration: 120 } }
        }
    }
    contentItem: Text {
        text: control.text
        font: control.font
        color: Theme.text
        wrapMode: Text.Wrap
        rightPadding: control.indicator.width + control.spacing
        verticalAlignment: Text.AlignVCenter
    }
}
