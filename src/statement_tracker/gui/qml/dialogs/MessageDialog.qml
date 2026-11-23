import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// A message or a yes-or-no question: a title, what to do, and Copy details when there are details.
Popup {
    id: dialog
    property string heading: ""
    property string message: ""
    property string details: ""
    property string confirmText: "OK"
    property string cancelText: ""
    property bool answered: false

    function show(data) {
        heading = data.title
        message = data.text
        details = data.details || ""
        confirmText = data.confirm
        cancelText = data.cancel
        answered = false
        open()
    }
    function finish(yes) {
        answered = true
        close()
        if (yes)
            dialogs.answer({})
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
        spacing: 16
        Text {
            text: dialog.heading
            color: Theme.text
            font.pixelSize: 19
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        Text {
            visible: dialog.message !== ""
            text: dialog.message
            color: Theme.muted
            font.pixelSize: 14
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        RowLayout {
            spacing: 8
            Layout.fillWidth: true
            Layout.topMargin: 4
            TextButton {
                visible: dialog.details !== ""
                iconName: "copy"
                text: "Copy details"
                onClicked: session.copyText(dialog.details)
            }
            Item { Layout.fillWidth: true }
            SecondaryButton {
                visible: dialog.cancelText !== ""
                text: dialog.cancelText
                onClicked: dialog.finish(false)
            }
            PrimaryButton {
                text: dialog.confirmText
                focus: true
                onClicked: dialog.finish(true)
            }
        }
    }
}
