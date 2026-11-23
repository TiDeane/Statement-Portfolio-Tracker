import QtQuick
import QtQuick.Layouts
import "../components"

// The investments held, one row each, and the Total (mockup: Home).
Rectangle {
    id: card
    readonly property var home: session.home

    radius: 12
    color: Theme.surface
    border.color: Theme.border
    clip: true
    implicitHeight: column.implicitHeight + 2

    ColumnLayout {
        id: column
        x: 1
        y: 1
        width: parent.width - 2
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 16
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            Text {
                text: "Your investments"
                color: Theme.text
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
            Item { Layout.fillWidth: true }
        }

        InvestmentRow {
            mode: "header"
            name: "Investment"
            invested: "Invested"
            worth: "Worth now"
            share: "Share of total"
            gain: "Gain or loss"
            Layout.fillWidth: true
        }

        Repeater {
            model: card.home.holdings
            InvestmentRow {
                required property var model
                required property int index
                onDoubleClicked: card.home.enterValue(index)
                name: model.name
                detail: model.detail
                invested: model.invested
                worth: model.worth
                worthNote: model.worthNote
                share: model.share
                shareFraction: model.shareFraction
                gain: model.gain
                gainUp: model.gainUp
                status: model.status
                Layout.fillWidth: true
            }
        }

        InvestmentRow {
            visible: card.home.totalRow.length > 0
            mode: "total"
            name: "Total"
            invested: card.home.totalRow.length ? card.home.totalRow[1] : ""
            worth: card.home.totalRow.length ? card.home.totalRow[2] : ""
            share: card.home.totalRow.length ? card.home.totalRow[3] : ""
            gain: card.home.totalRow.length ? card.home.totalRow[4] : ""
            gainUp: card.home.gainUp
            Layout.fillWidth: true
        }
    }
}
