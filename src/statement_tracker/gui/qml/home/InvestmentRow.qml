import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// One row of the investments list: an investment, the headings ("header") or the Total ("total").
// Columns: Investment, Invested, Worth now, Share of total, Gain or loss.
Rectangle {
    id: row
    property string mode: "holding"
    property string name: ""
    property string detail: ""
    property string invested: ""
    property string worth: ""
    property string worthNote: ""
    property string share: ""
    property real shareFraction: 0
    property string gain: ""
    property bool gainUp: true
    property string status: "priced"
    property string editName: ""
    signal doubleClicked()
    signal renamed(string name)

    readonly property bool loading: status === "loading"
    readonly property bool missing: status === "missing"
    readonly property bool header: mode === "header"
    readonly property bool total: mode === "total"
    readonly property int weight: total ? Font.Bold : Font.Normal

    objectName: header ? "investmentHeader" : "investmentRow"
    implicitHeight: header ? 38 : total ? 56 : 64
    color: header || total || missing ? Theme.subtle : Theme.surface

    MouseArea {  // double-clicking a row whose value is not today's from Yahoo lets the user enter it
        anchors.fill: parent
        enabled: row.mode === "holding" && !row.loading
        onDoubleClicked: row.doubleClicked()
    }

    Rectangle {  // the line above each row
        visible: !row.header
        width: parent.width
        height: 1
        color: row.total ? Theme.borderStrong : Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        spacing: 16

        // The name: double-click it, or press F2 (Return on a Mac) on it, to type a new one.
        FocusScope {
            id: nameCell
            property bool editing: false
            readonly property bool editable: row.mode === "holding" && !row.loading

            implicitHeight: nameColumn.implicitHeight
            activeFocusOnTab: editable
            Accessible.name: row.name
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.horizontalStretchFactor: 20

            function startEditing() {
                if (!editable)
                    return
                editor.text = row.editName
                editing = true
                editor.forceActiveFocus()
                editor.selectAll()
            }

            Keys.onPressed: (event) => {
                var mac = Qt.platform.os === "osx"
                var renameKey = event.key === Qt.Key_F2 || (mac && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter))
                if (renameKey && !editing) {
                    startEditing()
                    event.accepted = true
                }
            }

            Rectangle {  // where the keyboard is
                anchors.fill: parent
                anchors.margins: -4
                radius: 6
                color: "transparent"
                border.width: 2
                border.color: Theme.text
                visible: nameCell.activeFocus && !nameCell.editing
            }
            MouseArea {
                anchors.fill: parent
                enabled: nameCell.editable && !nameCell.editing
                onClicked: nameCell.forceActiveFocus()
                onDoubleClicked: nameCell.startEditing()
            }
            ColumnLayout {
                id: nameColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 1
                Text {
                    visible: !nameCell.editing
                    text: row.name
                    color: row.header ? Theme.muted : Theme.text
                    font.pixelSize: row.header ? 13 : 14
                    font.weight: row.header ? Font.DemiBold : row.total ? Font.Bold : Font.DemiBold
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                TextField {
                    id: editor
                    objectName: "nameEditor"
                    visible: nameCell.editing
                    Accessible.name: "New name for " + row.name
                    color: Theme.text
                    font.pixelSize: 14
                    implicitHeight: 30
                    leftPadding: 6
                    Layout.fillWidth: true
                    background: Rectangle {
                        radius: 6
                        color: Theme.surface
                        border.width: 2
                        border.color: Theme.accent
                    }
                    onAccepted: {
                        nameCell.editing = false
                        row.renamed(text)
                    }
                    Keys.onEscapePressed: nameCell.editing = false
                    onActiveFocusChanged: if (!activeFocus) nameCell.editing = false
                }
                Text {
                    visible: row.detail !== ""
                    text: row.detail
                    color: Theme.muted
                    font.pixelSize: 13
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
        }

        Text {
            text: row.invested
            color: row.header ? Theme.muted : Theme.text
            font.pixelSize: row.header ? 13 : 14
            font.weight: row.header ? Font.DemiBold : row.weight
            font.features: { "tnum": 1 }
            horizontalAlignment: Text.AlignRight
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.horizontalStretchFactor: 11
        }

        Item {
            implicitHeight: worthColumn.implicitHeight
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.horizontalStretchFactor: 12
            ColumnLayout {
                id: worthColumn
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    visible: !row.loading && row.worth !== ""
                    text: row.worth
                    color: row.header ? Theme.muted : Theme.text
                    font.pixelSize: row.header ? 13 : 14
                    font.weight: row.header || row.total ? (row.header ? Font.DemiBold : Font.Bold) : Font.DemiBold
                    font.features: { "tnum": 1 }
                    Layout.alignment: Qt.AlignRight
                }
                Text {
                    visible: row.worthNote !== ""
                    text: row.worthNote
                    color: Theme.warnInk
                    font.pixelSize: 12
                    Layout.alignment: Qt.AlignRight
                }
                Skeleton {
                    visible: row.loading
                    Layout.alignment: Qt.AlignRight
                }
                Chip {
                    visible: row.missing
                    text: "No price today"
                    tone: "warn"
                    Layout.alignment: Qt.AlignRight
                }
            }
        }

        RowLayout {
            spacing: 10
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.horizontalStretchFactor: 13
            ProgressLine {
                visible: row.mode === "holding" && !row.loading && row.share !== ""
                fraction: row.shareFraction
                Layout.preferredWidth: 56
            }
            Skeleton {
                visible: row.loading
                implicitWidth: 56
                implicitHeight: 6
            }
            Text {
                visible: row.missing
                text: "Not in the total"
                color: Theme.muted
                font.pixelSize: 13
            }
            Text {
                visible: !row.loading && !row.missing
                text: row.share
                color: row.header ? Theme.muted : row.total ? Theme.muted : Theme.muted
                font.pixelSize: row.header ? 13 : 14
                font.weight: row.header ? Font.DemiBold : row.total ? Font.DemiBold : Font.Normal
                font.features: { "tnum": 1 }
            }
            Item { Layout.fillWidth: true }
        }

        Item {
            implicitHeight: gainText.implicitHeight
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.horizontalStretchFactor: 14
            Text {
                id: gainText
                visible: !row.loading
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: row.gain
                color: row.header ? Theme.muted : row.gainUp ? Theme.gain : Theme.loss
                font.pixelSize: row.header ? 13 : 14
                font.weight: row.header ? Font.DemiBold : row.total ? Font.Bold : Font.DemiBold
                font.features: { "tnum": 1 }
            }
            Skeleton {
                visible: row.loading
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 120
            }
            SecondaryButton {
                visible: row.missing
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                implicitHeight: 36
                text: "Enter its value…"
                onClicked: row.doubleClicked()
            }
        }
    }
}
