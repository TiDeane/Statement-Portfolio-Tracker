import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// The app's button. `kind`: "primary" (the one green action of an area), "secondary" (outlined),
// "text" (minor actions) or "danger" (forgetting things). Outlined in the text colour only when
// reached with the keyboard.
Button {
    id: control
    property string kind: "secondary"
    property string iconName: ""
    readonly property color ink: kind === "primary" ? Theme.accentText
                                : kind === "text" ? Theme.accentInk
                                : kind === "danger" ? Theme.errInk
                                : Theme.text

    implicitHeight: kind === "primary" ? 44 : 40
    leftPadding: kind === "text" ? 10 : 16
    rightPadding: leftPadding
    hoverEnabled: true
    font.pixelSize: 14
    font.weight: kind === "secondary" ? Font.Medium : Font.DemiBold

    contentItem: RowLayout {
        spacing: 8
        Icon {
            name: control.iconName
            size: 16
            color: control.ink
        }
        Text {
            text: control.text
            font: control.font
            color: control.ink
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            Layout.fillWidth: true
        }
    }

    background: Rectangle {
        radius: 8
        opacity: control.enabled ? 1 : 0.5
        color: control.kind === "primary"
               ? (control.down ? Qt.darker(Theme.accent, 1.12) : control.hovered ? Qt.darker(Theme.accent, 1.06) : Theme.accent)
               : control.kind === "text" ? (control.down || control.hovered ? Theme.subtle : "transparent")
               : (control.down || control.hovered ? Theme.subtle : Theme.surface)
        border.width: control.visualFocus ? 2 : (control.kind === "primary" || control.kind === "text" ? 0 : 1)
        border.color: control.visualFocus ? Theme.text : control.kind === "danger" ? Theme.errBorder : Theme.borderStrong
    }
}
