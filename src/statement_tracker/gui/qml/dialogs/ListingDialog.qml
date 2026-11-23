import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// Which listing an investment is, when the app cannot tell (mockup: Confirm-Listing).
Popup {
    id: dialog
    property var question: ({ "options": [] })
    property int chosen: 0
    property bool answered: false
    readonly property bool hasOptions: (question.options || []).length > 0

    function show(data) {
        question = data
        chosen = 0
        field.text = ""
        always.checked = false
        answered = false
        open()
    }
    function finish(use) {
        answered = true
        close()
        if (!use) {
            dialogs.cancel()
            return
        }
        var typed = field.text.trim()
        var symbol = typed !== "" ? typed : (hasOptions ? question.options[chosen].symbol : "")
        dialogs.answer({ "symbol": symbol, "always": always.checked })
    }

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(600, (parent ? parent.width : 640) - 32)
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
            text: dialog.question.title || ""
            color: Theme.text
            font.pixelSize: 19
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        Text {
            text: dialog.question.intro || ""
            color: Theme.muted
            font.pixelSize: 14
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }

        ColumnLayout {
            visible: dialog.hasOptions
            spacing: 8
            Layout.fillWidth: true
            Repeater {
                model: dialog.question.options || []
                AbstractButton {
                    id: option
                    required property var modelData
                    required property int index
                    readonly property bool isChosen: dialog.chosen === index
                    Accessible.name: modelData.name + ", " + modelData.detail
                    Accessible.role: Accessible.RadioButton
                    Layout.fillWidth: true
                    implicitHeight: optionRow.implicitHeight + 24
                    hoverEnabled: true
                    onClicked: dialog.chosen = index
                    background: Rectangle {
                        radius: 10
                        color: option.isChosen ? Theme.okBg : Theme.surface
                        border.width: option.isChosen || option.visualFocus ? 2 : 1
                        border.color: option.isChosen ? Theme.accent : option.visualFocus ? Theme.text : Theme.border
                    }
                    contentItem: Item {}
                    RowLayout {
                        id: optionRow
                        anchors.fill: parent
                        anchors.margins: 12
                        anchors.leftMargin: 14
                        spacing: 12
                        Rectangle {  // the radio mark
                            implicitWidth: 18
                            implicitHeight: 18
                            radius: 9
                            color: Theme.surface
                            border.width: option.isChosen ? 5 : 1.5
                            border.color: option.isChosen ? Theme.accent : Theme.borderStrong
                        }
                        ColumnLayout {
                            spacing: 1
                            Layout.fillWidth: true
                            Text {
                                text: option.modelData.name
                                color: Theme.text
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                text: option.modelData.detail
                                color: Theme.muted
                                font.pixelSize: 13
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                        Chip {
                            visible: option.modelData.match
                            text: "Matches your purchases"
                            tone: "ok"
                        }
                    }
                }
            }
        }

        ColumnLayout {
            spacing: 6
            Layout.fillWidth: true
            Label {
                text: dialog.question.fieldLabel || ""
                color: Theme.text
                font.pixelSize: 13
                font.weight: Font.DemiBold
                MouseArea {
                    anchors.fill: parent
                    onClicked: field.forceActiveFocus()
                }
            }
            TextField {
                id: field
                Accessible.name: dialog.question.fieldLabel || ""
                placeholderText: "For example ABCD.AS"
                color: Theme.text
                font.pixelSize: 14
                Layout.fillWidth: true
                implicitHeight: 40
                background: Rectangle {
                    radius: 8
                    color: Theme.surface
                    border.width: field.activeFocus ? 2 : 1
                    border.color: field.activeFocus ? Theme.accent : Theme.borderStrong
                }
                onAccepted: if (dialog.hasOptions || text.trim() !== "") dialog.finish(true)
            }
        }

        CheckBox {
            id: always
            visible: dialog.hasOptions
            text: "From now on, take the first listing without asking. The best match always comes first."
            font.pixelSize: 13
            Layout.fillWidth: true
            contentItem: Text {
                text: always.text
                font: always.font
                color: Theme.text
                wrapMode: Text.Wrap
                leftPadding: always.indicator.width + always.spacing
                verticalAlignment: Text.AlignVCenter
            }
        }

        RowLayout {
            spacing: 8
            Layout.fillWidth: true
            Layout.topMargin: 4
            TextButton {
                text: "Skip this investment"
                onClicked: dialog.finish(false)
            }
            Item { Layout.fillWidth: true }
            PrimaryButton {
                text: dialog.question.useLabel || "Use this listing"
                enabled: dialog.hasOptions || field.text.trim() !== ""
                onClicked: dialog.finish(true)
            }
        }
    }
}
