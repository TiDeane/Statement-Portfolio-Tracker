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
            InvestmentsCard { Layout.fillWidth: true }

            Item { Layout.preferredHeight: 16 }
        }
    }
}
