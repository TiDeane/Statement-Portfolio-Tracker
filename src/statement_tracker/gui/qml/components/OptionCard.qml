import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// One of several options shown as cards, one chosen at a time (outlined in green). Its title is
// its text; a file chosen for it shows inside, with "Choose another…".
AbstractButton {
    id: card
    property string iconName: ""
    property bool neutralIcon: false
    property string description: ""
    property string fileName: ""
    property string fileFolder: ""
    signal chooseAnother()

    checkable: false
    hoverEnabled: true
    implicitWidth: 260
    implicitHeight: column.implicitHeight + 40
    focusPolicy: Qt.StrongFocus

    background: Rectangle {
        radius: 14
        color: card.checked ? Theme.okBg : Theme.surface
        border.width: card.checked || card.visualFocus ? 2 : 1
        border.color: card.checked ? Theme.accent : card.visualFocus ? Theme.text : card.hovered ? Theme.borderStrong : Theme.border
    }

    contentItem: Item {}

    ColumnLayout {
        id: column
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 20
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Rectangle {
                implicitWidth: 40
                implicitHeight: 40
                radius: 10
                color: card.neutralIcon ? Theme.subtle : Theme.accentSoft
                Icon {
                    anchors.centerIn: parent
                    name: card.iconName
                    size: 20
                    color: card.neutralIcon ? Theme.muted : Theme.accentInk
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {  // the radio mark
                implicitWidth: 18
                implicitHeight: 18
                radius: 9
                color: Theme.surface
                border.width: card.checked ? 5 : 1.5
                border.color: card.checked ? Theme.accent : Theme.borderStrong
            }
        }
        Text {
            text: card.text
            color: Theme.text
            font.pixelSize: 16
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        Text {
            text: card.description
            color: Theme.muted
            font.pixelSize: 14
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        Rectangle {
            visible: card.fileName !== ""
            Layout.fillWidth: true
            implicitHeight: fileColumn.implicitHeight + 16
            radius: 8
            color: Theme.surface
            border.color: Theme.okBorder
            ColumnLayout {
                id: fileColumn
                anchors.fill: parent
                anchors.margins: 8
                anchors.leftMargin: 12
                spacing: 2
                Text {
                    text: card.fileName
                    color: Theme.text
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }
                Text {
                    text: card.fileFolder
                    color: Theme.muted
                    font.pixelSize: 13
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }
                TextButton {
                    text: "Choose another…"
                    Layout.leftMargin: -10
                    implicitHeight: 32
                    onClicked: card.chooseAnother()
                }
            }
        }
    }
}
