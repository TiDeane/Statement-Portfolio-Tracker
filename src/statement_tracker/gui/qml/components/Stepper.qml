import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// A whole number between `from` and `to`, changed with − and + (each says what it does).
Rectangle {
    id: stepper
    property int value: 0
    property int from: 0
    property int to: 99
    signal changedTo(int value)

    implicitWidth: row.implicitWidth + 2
    implicitHeight: 40
    radius: 8
    color: Theme.surface
    border.color: Theme.borderStrong

    component StepButton: AbstractButton {
        id: step
        property string sign: ""
        implicitWidth: 40
        implicitHeight: 38
        focusPolicy: Qt.StrongFocus
        Accessible.name: text
        contentItem: Text {
            text: step.sign
            color: step.enabled ? Theme.text : Theme.muted
            font.pixelSize: 18
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: step.down || step.hovered ? Theme.border : Theme.subtle
            border.width: step.visualFocus ? 2 : 0
            border.color: Theme.text
        }
    }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 0
        StepButton {
            text: "One fewer"
            sign: "−"
            enabled: stepper.value > stepper.from
            onClicked: stepper.changedTo(stepper.value - 1)
        }
        Text {
            text: stepper.value
            color: Theme.text
            font.pixelSize: 14
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            Layout.preferredWidth: 48
        }
        StepButton {
            text: "One more"
            sign: "+"
            enabled: stepper.value < stepper.to
            onClicked: stepper.changedTo(stepper.value + 1)
        }
    }
}
