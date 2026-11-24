import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../home"

// Home: the investments with today's prices (mockups: Home and its states). The page scrolls.
Item {
    id: page
    // What files dragged over the window would be used as: the card each would go to says so (Spec F6, F7).
    readonly property var dragKinds: ApplicationWindow.window ? ApplicationWindow.window.dragKinds : []

    ScrollView {
        id: scroll
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            id: column
            width: Math.min(scroll.availableWidth - 48, 992)
            x: (scroll.availableWidth - width) / 2
            spacing: 16

            Item { Layout.preferredHeight: 4 }

            RowLayout {
                spacing: 12
                Layout.fillWidth: true
                AppLogo { size: 32 }
                Text {
                    text: "Your portfolio"
                    color: Theme.text
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }
                IconButton {
                    text: "Help"
                    iconName: "help"
                    onClicked: session.showHelp()
                }
                SecondaryButton {
                    text: "Settings"
                    iconName: "settings"
                    enabled: !session.busy && !session.home.writing  // a fetch and the spreadsheet use the same settings
                    onClicked: session.goTo("settings")
                }
            }

            TotalsCard { Layout.fillWidth: true }

            // What goes in (the statement) and what comes out (the spreadsheet), side by side.
            GridLayout {
                id: sources
                readonly property bool sideBySide: page.width > 820
                readonly property real shared: column.width - columnSpacing  // set by the page, never by the cards
                columns: sideBySide ? 2 : 1
                columnSpacing: 16
                rowSpacing: 16
                Layout.fillWidth: true
                StatementCard {
                    id: statementCard
                    objectName: "statementCard"
                    dropping: page.dragKinds.indexOf("statement") >= 0
                    faded: page.dragKinds.length > 0 && !dropping
                    dropTitle: "Drop it to use this statement"
                    dropText: "Today's values are worked out again from it."
                    // Side by side, the width that makes both cards about as tall (see RowBalancer).
                    Layout.fillWidth: !sources.sideBySide
                    Layout.fillHeight: true
                    Layout.preferredWidth: !sources.sideBySide ? -1 : balancer.firstWidth > 0 ? balancer.firstWidth : sources.shared * 0.4
                }
                SpreadsheetCard {
                    id: spreadsheetCard
                    objectName: "spreadsheetCard"
                    dropping: page.dragKinds.indexOf("spreadsheet") >= 0
                    faded: page.dragKinds.length > 0 && !dropping
                    dropTitle: "Drop it to use this spreadsheet"
                    dropText: session.home.dropSheetLine
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                }
            }
            RowBalancer {
                id: balancer
                first: statementCard
                second: spreadsheetCard
                available: sources.sideBySide ? sources.shared : 0
            }
            Connections {
                target: session.home
                function onChanged() { balancer.refresh() }  // new texts in either card
            }
            InvestmentsCard { Layout.fillWidth: true }

            Item { Layout.preferredHeight: 16 }
        }
    }
}
