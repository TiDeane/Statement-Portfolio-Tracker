import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "columns.js" as Columns

// One row of the investments list: an investment, or the Total ("total"). It shows the name, then the
// columns listed in `columns` (keys of settings.TABLE_COLUMNS, in that order), as wide as columns.js says.
Rectangle {
    id: row
    property string mode: "holding"
    property var columns: []
    property string name: ""
    property string detail: ""
    property string shares: ""
    property string averageCost: ""
    property string price: ""
    property string invested: ""
    property string worth: ""
    property string worthNote: ""
    property string share: ""
    property real shareFraction: 0
    property string investedShare: ""
    property string gain: ""
    property bool gainUp: true
    property string realized: ""
    property string realizedTone: ""
    property string dividends: ""
    property string status: "priced"
    property string editName: ""
    signal doubleClicked()
    signal renamed(string name)

    readonly property bool loading: status === "loading"
    readonly property bool missing: status === "missing"
    readonly property bool total: mode === "total"
    readonly property int weight: total ? Font.Bold : Font.Normal

    objectName: "investmentRow"
    implicitHeight: total ? 56 : 64
    color: total || missing ? Theme.subtle : Theme.surface

    MouseArea {  // double-clicking a row whose value is not today's from Yahoo lets the user enter it
        anchors.fill: parent
        enabled: row.mode === "holding" && !row.loading
        onDoubleClicked: row.doubleClicked()
    }

    Rectangle {  // the line above each row
        width: parent.width
        height: 1
        color: row.total ? Theme.borderStrong : Theme.border
    }

    // A number that needs no more than its text: right-aligned, in tabular figures.
    component Amount: Text {
        property string key
        property var shownColumns: []
        property bool waiting: false  // its value is on its way: a placeholder instead

        visible: shownColumns.indexOf(key) >= 0
        color: Theme.text
        font.pixelSize: 14
        font.features: { "tnum": 1 }
        horizontalAlignment: Text.AlignRight
        elide: Text.ElideRight
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        Layout.minimumWidth: Columns.minimum[key]
        Layout.horizontalStretchFactor: Columns.stretch[key]

        Skeleton {
            visible: parent.waiting
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            implicitWidth: 64
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Columns.margin
        anchors.rightMargin: Columns.margin
        spacing: Columns.spacing

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
            Layout.minimumWidth: Columns.minimum.name
            Layout.horizontalStretchFactor: Columns.stretch.name

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
                    color: Theme.text
                    font.pixelSize: 14
                    font.weight: row.total ? Font.Bold : Font.DemiBold
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

        Amount {
            key: "shares"
            shownColumns: row.columns
            text: row.shares
            font.weight: row.weight
        }
        Amount {
            key: "average_cost"
            shownColumns: row.columns
            text: row.averageCost
            font.weight: row.weight
        }
        Amount {
            key: "price"
            shownColumns: row.columns
            text: row.loading ? "" : row.price
            waiting: row.loading
            font.weight: row.weight
        }
        Amount {
            key: "invested"
            shownColumns: row.columns
            text: row.invested
            font.weight: row.weight
        }

        Item {
            visible: row.columns.indexOf("worth") >= 0
            implicitHeight: worthColumn.implicitHeight
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.minimumWidth: Columns.minimum.worth
            Layout.horizontalStretchFactor: Columns.stretch.worth
            ColumnLayout {
                id: worthColumn
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    visible: !row.loading && row.worth !== ""
                    text: row.worth
                    color: Theme.text
                    font.pixelSize: 14
                    font.weight: row.total ? Font.Bold : Font.DemiBold
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
            visible: row.columns.indexOf("share") >= 0
            spacing: 10
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.minimumWidth: Columns.minimum.share
            Layout.horizontalStretchFactor: Columns.stretch.share
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
                color: Theme.muted
                font.pixelSize: 14
                font.weight: row.total ? Font.DemiBold : Font.Normal
                font.features: { "tnum": 1 }
            }
            Item { Layout.fillWidth: true }
        }

        Amount {
            key: "invested_share"
            shownColumns: row.columns
            text: row.investedShare
            color: Theme.muted
            font.weight: row.total ? Font.DemiBold : Font.Normal
        }

        Item {
            visible: row.columns.indexOf("gain") >= 0
            implicitHeight: gainText.implicitHeight
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.minimumWidth: Columns.minimum.gain
            Layout.horizontalStretchFactor: Columns.stretch.gain
            Text {
                id: gainText
                visible: !row.loading
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: row.gain
                color: row.gainUp ? Theme.gain : Theme.loss
                font.pixelSize: 14
                font.weight: row.total ? Font.Bold : Font.DemiBold
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

        Amount {
            key: "realized"
            shownColumns: row.columns
            text: row.realized
            color: row.realizedTone === "up" ? Theme.gain : row.realizedTone === "down" ? Theme.loss : Theme.text
            font.weight: row.weight
        }
        Amount {
            key: "dividends"
            shownColumns: row.columns
            text: row.dividends
            font.weight: row.weight
        }
    }
}
