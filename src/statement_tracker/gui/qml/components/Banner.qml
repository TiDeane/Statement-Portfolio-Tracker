import QtQuick
import QtQuick.Layouts

// A coloured message inside a card: "ok" (green), "warn" (amber) or "error" (red), with an icon,
// a title, a text and, on the right, any buttons given as children.
Rectangle {
    id: banner
    property string tone: "warn"
    property string title: ""
    property string text: ""
    property string iconName: tone === "ok" ? "check" : tone === "error" ? "alert" : "info"
    default property alias actions: actionRow.data
    readonly property color ink: tone === "ok" ? Theme.okInk : tone === "error" ? Theme.errInk : Theme.warnInk

    radius: 10
    color: tone === "ok" ? Theme.okBg : tone === "error" ? Theme.errBg : Theme.warnBg
    border.color: tone === "ok" ? Theme.okBorder : tone === "error" ? Theme.errBorder : Theme.warnBorder
    border.width: 1
    implicitHeight: row.implicitHeight + 28

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        Icon {
            name: banner.iconName
            size: 20
            color: banner.ink
            Layout.alignment: Qt.AlignTop
        }
        ColumnLayout {
            spacing: 4
            Layout.fillWidth: true
            Text {
                visible: banner.title !== ""
                text: banner.title
                color: banner.ink
                font.pixelSize: 14
                font.weight: Font.DemiBold
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Text {
                visible: banner.text !== ""
                text: banner.text
                color: banner.tone === "warn" && banner.title === "" ? banner.ink : Theme.text
                font.pixelSize: 13
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }
        RowLayout {
            id: actionRow
            spacing: 8
        }
    }
}
