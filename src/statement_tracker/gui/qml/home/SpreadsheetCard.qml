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

    // With a spreadsheet: its name, its folder and when it last changed on one line, and the update
    // (mockup: Space-Joined).
    RowLayout {
        visible: card.home.hasSpreadsheet
        spacing: 16
        Layout.fillWidth: true
        Rectangle {
            Layout.alignment: Qt.AlignTop
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
                text: "Your spreadsheet"
                color: Theme.text
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
            Text {
                text: card.home.sheetName
                color: Theme.text
                font.pixelSize: 14
                font.weight: Font.Medium
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere  // the whole name, however long
                Layout.fillWidth: true
                Layout.topMargin: 4
            }
            Text {
                text: card.home.sheetPlace
                color: Theme.muted
                font.pixelSize: 13
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere  // the whole path, however long
                Layout.fillWidth: true
            }
            Text {
                visible: text !== ""
                text: card.home.sheetNote
                color: Theme.warnInk
                font.pixelSize: 13
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }
    }

    ProgressLine {
        visible: card.home.writing
        indeterminate: true
        Layout.fillWidth: true
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
            enabled: !card.home.writing
            onClicked: card.home.openFolder()
        }
        // Another spreadsheet: one the user has, or a new one; or one dropped on the window (Spec F7).
        TextButton {
            id: another
            text: "Use another…"
            iconName: "swap"
            opensMenu: true
            implicitHeight: 44
            enabled: !card.home.writing
            onClicked: anotherMenu.popup(another, another.width - anotherMenu.width, another.height + 4)

            // Each asks for a file once the menu has closed: the file chooser waits for its answer, and the
            // menu would stay open behind it.
            AppMenu {
                id: anotherMenu
                AppMenuItem {
                    text: "Use an existing spreadsheet…"
                    iconName: "folder"
                    onTriggered: Qt.callLater(card.home.chooseSpreadsheet)
                }
                AppMenuItem {
                    text: "Create a new one…"
                    iconName: "plusFile"
                    onTriggered: Qt.callLater(card.home.createSpreadsheet)
                }
                AppMenuSeparator {}
                Text {
                    text: "Or drop an Excel file on this window."
                    color: Theme.muted
                    font.pixelSize: 12
                    leftPadding: 12
                    rightPadding: 12
                    topPadding: 2
                    bottomPadding: 4
                }
            }
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
