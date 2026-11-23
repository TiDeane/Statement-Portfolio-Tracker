import QtQuick
import QtQuick.Layouts
import "../components"

// Where the values come from: the statement, its latest transaction, and a newer one (mockup: Home).
Card {
    id: card
    readonly property var home: session.home

    padding: 20
    spacing: 16

    RowLayout {
        spacing: 16
        Layout.fillWidth: true
        Rectangle {
            implicitWidth: 44
            implicitHeight: 44
            radius: 10
            color: Theme.subtle
            Icon {
                anchors.centerIn: parent
                name: "file"
                size: 22
                color: Theme.text
            }
        }
        ColumnLayout {
            spacing: 2
            Layout.fillWidth: true
            Text {
                text: "Your statement"
                color: Theme.text
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
            Text {
                text: card.home.statementLine
                color: Theme.muted
                font.pixelSize: 13
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }
    }

    Item { Layout.fillHeight: true }

    Flow {
        spacing: 12
        Layout.fillWidth: true
        SecondaryButton {
            text: "Use a newer statement…"
            iconName: "upload"
            implicitHeight: 44
            onClicked: card.home.chooseStatement()
        }
        Text {
            height: 44
            verticalAlignment: Text.AlignVCenter
            text: "or drop it on this window"
            color: Theme.muted
            font.pixelSize: 13
        }
    }
}
