import QtQuick
import QtQuick.Layouts
import "../components"

// What it is all worth, the gain or loss, and where the prices come from (mockups: Home, Home-Loading).
Card {
    id: card
    readonly property var home: session.home
    readonly property bool waiting: home.busy

    spacing: 20

    RowLayout {
        spacing: 24
        Layout.fillWidth: true

        ColumnLayout {
            spacing: 6
            Layout.fillWidth: true
            Text {
                text: "Worth now"
                color: Theme.muted
                font.pixelSize: 13
                font.weight: Font.Medium
            }
            Skeleton {
                visible: card.waiting
                implicitWidth: 280
                implicitHeight: 48
                radius: 8
            }
            Skeleton {
                visible: card.waiting
                implicitWidth: 220
                implicitHeight: 20
            }
            RowLayout {
                visible: !card.waiting
                spacing: 8
                Text {
                    text: card.home.worthNow
                    color: Theme.text
                    font.pixelSize: 44
                    font.weight: Font.DemiBold
                    font.features: { "tnum": 1 }
                }
                Text {
                    text: card.home.currency
                    color: Theme.muted
                    font.pixelSize: 20
                    font.weight: Font.Medium
                    Layout.alignment: Qt.AlignBaseline
                }
            }
            RowLayout {
                visible: !card.waiting && card.home.gainText !== ""
                spacing: 6
                Text {
                    text: card.home.gainText
                    color: card.home.gainUp ? Theme.gain : Theme.loss
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    font.features: { "tnum": 1 }
                }
                Text {
                    text: "since you bought"
                    color: Theme.muted
                    font.pixelSize: 15
                }
            }
        }

        GridLayout {
            columns: 2
            columnSpacing: 40
            rowSpacing: 2
            Layout.alignment: Qt.AlignBottom
            Text { text: "Invested"; color: Theme.muted; font.pixelSize: 13 }
            Text { text: "Investments"; color: Theme.muted; font.pixelSize: 13 }
            Text {
                text: card.home.invested === "" ? "" : card.home.invested + " " + card.home.currency
                color: Theme.text
                font.pixelSize: 17
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
            }
            Text {
                text: card.home.count
                color: Theme.text
                font.pixelSize: 17
                font.weight: Font.DemiBold
            }
        }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: Theme.border
    }

    // While prices come in: what is being done, and how far along.
    ColumnLayout {
        visible: card.waiting
        spacing: 8
        Layout.fillWidth: true
        Text {
            text: card.home.progressText
            color: Theme.muted
            font.pixelSize: 13
        }
        ProgressLine {
            fraction: card.home.progressFraction
            Layout.fillWidth: true
        }
    }

    // Then: where the prices come from, and what the totals leave out.
    RowLayout {
        visible: !card.waiting && card.home.hasReport
        spacing: 12
        Layout.fillWidth: true
        ColumnLayout {
            spacing: 2
            Layout.fillWidth: true
            RowLayout {
                spacing: 8
                Rectangle { implicitWidth: 8; implicitHeight: 8; radius: 4; color: Theme.gain }
                Text {
                    text: card.home.pricesLine
                    color: Theme.muted
                    font.pixelSize: 13
                }
            }
            Text {
                visible: card.home.leftOutLine !== ""
                text: card.home.leftOutLine
                color: Theme.warnInk
                font.pixelSize: 13
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }
        TextButton {
            text: "Refresh prices"
            iconName: "refresh"
            onClicked: card.home.refresh()
        }
    }
}
