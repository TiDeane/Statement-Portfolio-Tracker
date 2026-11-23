import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// What an investment Yahoo has no price for is worth now, typed in by the user (mockup: Enter-Value).
// The text typed goes back as it is: Python reads it, and asks again with an error when it is not an amount.
Popup {
    id: dialog
    property var question: ({})
    property bool answered: false

    function show(data) {
        question = data
        field.text = ""
        answered = false
        open()
        field.forceActiveFocus()
    }
    function finish(yes) {
        answered = true
        close()
        if (yes)
            dialogs.answer({ "text": field.text })
        else
            dialogs.cancel()
    }

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(520, (parent ? parent.width : 560) - 32)
    padding: 24
    closePolicy: Popup.CloseOnEscape
    onClosed: if (!answered) dialogs.cancel()

    Overlay.modal: Rectangle { color: Theme.dark ? "#8C000000" : "#6B101216" }
    background: Rectangle {
        radius: 14
        color: Theme.surface
        border.color: Theme.border
    }

    contentItem: ColumnLayout {
        spacing: 18

        RowLayout {
            spacing: 12
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text {
                    text: dialog.question.title || ""
                    color: Theme.text
                    font.pixelSize: 19
                    font.weight: Font.DemiBold
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Text {
                    text: dialog.question.subtitle || ""
                    color: Theme.muted
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }

        ColumnLayout {
            spacing: 6
            Layout.fillWidth: true
            Label {
                text: "Its whole value today"
                color: Theme.text
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 48
                radius: 8
                color: Theme.surface
                border.width: 2
                border.color: dialog.question.error ? Theme.errInk : Theme.accent
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 8
                    TextField {
                        id: field
                        Accessible.name: "Its whole value today"
                        placeholderText: "0.00"
                        inputMethodHints: Qt.ImhFormattedNumbersOnly
                        color: Theme.text
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                        font.features: { "tnum": 1 }
                        background: Item {}
                        Layout.fillWidth: true
                        onAccepted: dialog.finish(true)
                    }
                    Text {
                        text: dialog.question.currency || ""
                        color: Theme.muted
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }
                }
            }
            Text {
                visible: !!dialog.question.error
                text: dialog.question.error || ""
                color: Theme.errInk
                font.pixelSize: 13
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Text {
                text: dialog.question.hint || ""
                color: Theme.muted
                font.pixelSize: 13
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: noteRow.implicitHeight + 20
            radius: 8
            color: Theme.subtle
            RowLayout {
                id: noteRow
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10
                Icon {
                    name: "info"
                    size: 16
                    color: Theme.muted
                    Layout.alignment: Qt.AlignTop
                }
                Text {
                    text: dialog.question.note || ""
                    color: Theme.text
                    font.pixelSize: 13
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }

        RowLayout {
            spacing: 8
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            SecondaryButton {
                text: "Cancel"
                onClicked: dialog.finish(false)
            }
            PrimaryButton {
                text: "Use this value"
                onClicked: dialog.finish(true)
            }
        }
    }
}
