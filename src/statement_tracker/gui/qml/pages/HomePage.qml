import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../home"

// Home: the investments with today's prices (mockups: Home and its states). The page scrolls.
Item {
    id: page

    ScrollView {
        id: scroll
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
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
                columns: sideBySide ? 2 : 1
                columnSpacing: 16
                rowSpacing: 16
                Layout.fillWidth: true
                StatementCard {
                    // A third of the row: the spreadsheet's longer texts must not squeeze it.
                    Layout.fillWidth: !sources.sideBySide
                    Layout.fillHeight: true
                    Layout.preferredWidth: sources.sideBySide ? Math.max(300, (sources.width - 16) * 0.36) : -1
                }
                SpreadsheetCard {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                }
            }
            InvestmentsCard { Layout.fillWidth: true }

            Item { Layout.preferredHeight: 16 }
        }
    }
}
