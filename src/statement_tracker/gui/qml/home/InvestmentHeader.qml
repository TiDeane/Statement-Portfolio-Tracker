import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "columns.js" as Columns

// The headings of the investments list: the name's, then one per column shown, laid out as the rows are.
// Each is a button that sorts by its column; an arrow marks the one sorted by, and which way.
Rectangle {
    id: header
    property var columns: []
    property var headings: ({})
    property string sortColumn: ""
    property bool sortDescending: true
    signal sortClicked(string column)

    objectName: "investmentHeader"
    implicitHeight: Math.max(38, cells.implicitHeight + 16)
    color: Theme.subtle

    RowLayout {
        id: cells
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: Columns.margin
        anchors.rightMargin: Columns.margin
        anchors.verticalCenter: parent.verticalCenter
        spacing: Columns.spacing

        Repeater {
            model: ["name"].concat(header.columns)
            AbstractButton {
                id: heading
                required property string modelData
                readonly property bool sorted: header.sortColumn === modelData
                readonly property bool startsLeft: Columns.leftAligned(modelData)

                text: header.headings[modelData] || ""
                Accessible.name: "Sort by " + text
                focusPolicy: Qt.TabFocus
                hoverEnabled: true
                implicitHeight: label.implicitHeight
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.minimumWidth: Columns.minimum[modelData]
                Layout.horizontalStretchFactor: Columns.stretch[modelData]
                onClicked: header.sortClicked(modelData)

                contentItem: Item {  // the heading on its column's side, the arrow after it
                    implicitHeight: label.implicitHeight
                    Text {
                        id: label
                        width: parent.width - (heading.sorted ? 17 : 0)
                        text: heading.text
                        color: heading.sorted || heading.hovered ? Theme.text : Theme.muted
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                        horizontalAlignment: heading.startsLeft ? Text.AlignLeft : Text.AlignRight
                    }
                    Icon {
                        visible: heading.sorted
                        x: heading.startsLeft ? Math.min(label.contentWidth, label.width) + 4 : parent.width - 13
                        anchors.verticalCenter: label.verticalCenter
                        name: header.sortDescending ? "arrowDown" : "arrowUp"
                        size: 13
                        strokeWidth: 2.4
                        color: Theme.text
                    }
                }

                background: Rectangle {  // where the keyboard is
                    visible: heading.visualFocus
                    anchors.fill: parent
                    anchors.margins: -4
                    radius: 6
                    color: "transparent"
                    border.width: 2
                    border.color: Theme.text
                }
            }
        }
    }
}
