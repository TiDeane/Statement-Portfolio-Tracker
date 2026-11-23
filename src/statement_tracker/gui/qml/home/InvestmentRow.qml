import QtQuick
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

    readonly property bool loading: status === "loading"
    readonly property bool header: mode === "header"
    readonly property bool total: mode === "total"
    readonly property int weight: total ? Font.Bold : Font.Normal

    objectName: header ? "investmentHeader" : "investmentRow"
    implicitHeight: header ? 38 : total ? 56 : 64
    color: header || total ? Theme.subtle : Theme.surface

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

        ColumnLayout {
            spacing: 1
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.horizontalStretchFactor: 22
            Text {
                text: row.name
                color: row.header ? Theme.muted : Theme.text
                font.pixelSize: row.header ? 13 : 14
                font.weight: row.header ? Font.DemiBold : row.total ? Font.Bold : Font.DemiBold
                elide: Text.ElideRight
                Layout.fillWidth: true
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
            }
        }

        RowLayout {
            spacing: 10
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.horizontalStretchFactor: 11
            ProgressLine {
                visible: row.mode === "holding" && !row.loading && row.share !== ""
                fraction: row.shareFraction
                Layout.preferredWidth: 72
            }
            Skeleton {
                visible: row.loading
                implicitWidth: 72
                implicitHeight: 6
            }
            Text {
                visible: !row.loading
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
        }
    }
}
