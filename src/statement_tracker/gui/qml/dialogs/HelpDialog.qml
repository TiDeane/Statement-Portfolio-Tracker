import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// Help: where the statement comes from, privacy, and the version.
Popup {
    id: dialog
    property var help: ({ "steps": [] })
    property bool closedByButton: false

    function show(data) {
        help = data
        open()
    }

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(560, (parent ? parent.width : 600) - 32)
    height: Math.min(implicitHeight, (parent ? parent.height : 700) - 48)
    padding: 24
    closePolicy: Popup.CloseOnEscape
    onClosed: dialogs.answer({})

    Overlay.modal: Rectangle { color: Theme.dark ? "#8C000000" : "#6B101216" }
    background: Rectangle {
        radius: 14
        color: Theme.surface
        border.color: Theme.border
    }

    contentItem: ColumnLayout {
        spacing: 16
        ScrollView {
            id: scroll
            contentWidth: availableWidth
            clip: true
            Layout.fillWidth: true
            Layout.fillHeight: true
            implicitHeight: content.implicitHeight
            ColumnLayout {
                id: content
                width: scroll.availableWidth
                spacing: 12
                Text {
                    text: "Where do I get my statement?"
                    color: Theme.text
                    font.pixelSize: 19
                    font.weight: Font.DemiBold
                }
                Repeater {
                    model: dialog.help.steps || []
                    Text {
                        required property string modelData
                        required property int index
                        text: (index + 1) + ".  " + modelData
                        color: Theme.text
                        font.pixelSize: 14
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
                Text {
                    text: dialog.help.allTime || ""
                    color: Theme.warnInk
                    font.pixelSize: 13
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Text {
                    text: "Privacy"
                    color: Theme.text
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                    Layout.topMargin: 8
                }
                Text {
                    text: dialog.help.privacy || ""
                    color: Theme.text
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Text {
                    text: dialog.help.version || ""
                    color: Theme.muted
                    font.pixelSize: 13
                    Layout.topMargin: 8
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            TextButton {
                text: "New versions"
                onClicked: Qt.openUrlExternally(dialog.help.releases)
            }
            Item { Layout.fillWidth: true }
            PrimaryButton {
                text: "Close"
                onClicked: dialog.close()
            }
        }
    }
}
