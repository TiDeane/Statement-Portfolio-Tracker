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
                SecondaryButton {
                    text: "Settings"
                    iconName: "settings"
                    onClicked: session.goTo("settings")
                }
            }

            TotalsCard { Layout.fillWidth: true }

            // What goes in (the statement) and what comes out (the spreadsheet), side by side.
            GridLayout {
                columns: page.width > 820 ? 2 : 1
                columnSpacing: 16
                rowSpacing: 16
                Layout.fillWidth: true
                StatementCard {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    Layout.horizontalStretchFactor: 1
                }
            }
            InvestmentsCard { Layout.fillWidth: true }

            Item { Layout.preferredHeight: 16 }
        }
    }
}
