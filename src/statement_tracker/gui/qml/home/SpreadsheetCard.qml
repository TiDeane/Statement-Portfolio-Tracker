import QtQuick
import QtQuick.Layouts
import "../components"

// What comes out: the spreadsheet, its one green button, and what the last update did
// (mockups: Home, Home-Updated, Home-Error).
Card {
    id: card
    readonly property var home: session.home

    padding: 20
    spacing: 16

    // With a spreadsheet: its name, when it last changed, and the update.
    RowLayout {
        visible: card.home.hasSpreadsheet
        spacing: 16
        Layout.fillWidth: true
        Rectangle {
            implicitWidth: 44
            implicitHeight: 44
            radius: 10
            color: Theme.accentSoft
            Icon {
                anchors.centerIn: parent
                name: "sheet"
                size: 22
                color: Theme.accentInk
            }
        }
        ColumnLayout {
            spacing: 2
            Layout.fillWidth: true
            Text {
                text: card.home.sheetName
                color: Theme.text
                font.pixelSize: 15
                font.weight: Font.DemiBold
                elide: Text.ElideMiddle
                Layout.fillWidth: true
            }
            Text {
                text: card.home.sheetLine
                color: Theme.muted
                font.pixelSize: 13
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }
    }

    Text {
        visible: card.home.backupsOff !== ""
        text: card.home.backupsOff
        color: Theme.errInk
        font.pixelSize: 13
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }

    Item {
        visible: card.home.hasSpreadsheet
        Layout.fillHeight: true
    }

    Flow {
        visible: card.home.hasSpreadsheet
        spacing: 8
        layoutDirection: Qt.RightToLeft
        Layout.fillWidth: true
        PrimaryButton {
            text: card.home.sheetButton
            enabled: card.home.canUpdate
            onClicked: card.home.updateSpreadsheet()
        }
        SecondaryButton {
            text: "Open folder"
            iconName: "folder"
            implicitHeight: 44
            onClicked: card.home.openFolder()
        }
    }

    Text {
        visible: card.home.hasSpreadsheet && card.home.offlineSheetNote !== ""
        text: card.home.offlineSheetNote
        color: Theme.muted
        font.pixelSize: 13
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }

    Banner {
        visible: card.home.sheetResult !== ""
        tone: card.home.sheetResult === "ok" ? "ok" : "error"
        title: card.home.sheetResultTitle
        text: card.home.sheetResultLines.join("\n")
        Layout.fillWidth: true
        TextButton {
            visible: card.home.sheetHasDetails
            text: "Copy details"
            iconName: "copy"
            onClicked: card.home.copyDetails()
        }
    }

    // Without one: the choice first launch offers.
    ColumnLayout {
        visible: !card.home.hasSpreadsheet
        spacing: 4
        Layout.fillWidth: true
        Text {
            text: "Keep a spreadsheet up to date?"
            color: Theme.text
            font.pixelSize: 15
            font.weight: Font.DemiBold
        }
        Text {
            text: "The app can write your investments and a row of history into an Excel file each time you update it."
            color: Theme.muted
            font.pixelSize: 13
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
    }
    Flow {
        visible: !card.home.hasSpreadsheet
        spacing: 8
        Layout.fillWidth: true
        SecondaryButton {
            text: "Choose spreadsheet…"
            iconName: "folder"
            onClicked: card.home.chooseSpreadsheet()
        }
        SecondaryButton {
            text: "Create a new one…"
            iconName: "plusFile"
            onClicked: card.home.createSpreadsheet()
        }
    }
}
