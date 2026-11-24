import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes

// A white (or, in dark mode, raised) area with rounded corners, holding a column of content.
// While files are dragged over the window, a card they would go to says so over its content (`dropping`,
// with `dropTitle` and `dropText`), and one they would not go to fades (`faded`).
Rectangle {
    id: card
    default property alias content: column.data
    readonly property Item body: column  // what the card holds, without what is drawn over it
    property int padding: 24
    property int spacing: 16
    property bool dropping: false
    property bool faded: false
    property string dropTitle: ""
    property string dropText: ""

    radius: 12
    color: Theme.surface
    border.color: Theme.border
    border.width: 1
    implicitWidth: column.implicitWidth + 2 * padding
    implicitHeight: column.implicitHeight + 2 * padding
    opacity: faded ? 0.45 : 1

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: card.padding
        spacing: card.spacing
    }

    // Over the content, not in its column: the card keeps its height, and the row its balance.
    Rectangle {
        visible: card.dropping
        anchors.fill: parent
        z: 1
        radius: card.radius
        color: Theme.accentSoft

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Theme.accent
                strokeWidth: 2
                strokeStyle: ShapePath.DashLine
                dashPattern: [3, 2]
                fillColor: "transparent"
                PathRectangle {
                    x: 1
                    y: 1
                    width: card.width - 2
                    height: card.height - 2
                    radius: card.radius - 1
                }
            }
        }

        ColumnLayout {
            anchors.centerIn: parent
            width: parent.width - 32
            spacing: 8
            Icon {
                name: "download"
                size: 28
                color: Theme.accentInk
                Layout.alignment: Qt.AlignHCenter
            }
            Text {
                text: card.dropTitle
                color: Theme.accentInk
                font.pixelSize: 16
                font.weight: Font.Bold
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Text {
                visible: text !== ""
                text: card.dropText
                color: Theme.text
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere  // a long file name
                Layout.fillWidth: true
            }
        }
    }
}
