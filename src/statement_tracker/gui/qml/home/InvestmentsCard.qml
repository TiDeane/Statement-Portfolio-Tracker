import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "columns.js" as Columns

// The investments held, one row each, and the Total (mockups: Home, A1-A4). The columns shown are the
// user's choice; when they do not fit the card, the list scrolls sideways inside it.
Rectangle {
    id: card
    readonly property var home: session.home

    objectName: "investmentsCard"

    radius: 12
    color: Theme.surface
    border.color: Theme.border
    clip: true
    implicitHeight: column.implicitHeight + 2

    // Each column's least width: never narrower than its longest text, laid out as the table draws it
    // (bold, as the Total is, with figures of equal width), so that amounts fit whatever font the
    // computer draws them in. Worked out when Home changes, not in a binding: measuring changes `measure`.
    Text {
        id: measure
        visible: false
        font.pixelSize: 14
        font.weight: Font.Bold
        font.features: { "tnum": 1 }
    }
    property var widths: ({})
    function measureColumns() {
        widths = Columns.minimums(card.home.columns, card.home.widest, function (text) {
            measure.text = text
            return measure.implicitWidth
        })
    }
    Component.onCompleted: measureColumns()
    Connections {
        target: card.home
        function onChanged() { card.measureColumns() }
    }

    // Open the Columns panel clear of its button: the page first scrolls the toolbar towards the top, then
    // the panel opens below the button, or above it when there is more room there.
    function openColumns() {
        var page = card.parent
        while (page && page.contentY === undefined)
            page = page.parent
        if (page) {
            var top = card.mapToItem(page.contentItem, 0, 0).y
            page.contentY = Math.max(0, Math.min(top - 16, page.contentHeight - page.height))
        }
        var height = columnsPanel.implicitHeight
        var buttonTop = columnsButton.mapToItem(null, 0, 0).y
        var below = card.Window.height - buttonTop - columnsButton.height - 12
        columnsPanel.y = below >= height + 4 || buttonTop < below ? columnsButton.height + 4 : -height - 4
        columnsPanel.open()
    }

    ColumnLayout {
        id: column
        x: 1
        y: 1
        width: parent.width - 2
        spacing: 0

        // The title, then the search box and the buttons: beside it, or under it on a narrow window.
        GridLayout {
            id: top
            readonly property bool stacked: width < 380 + tools.implicitWidth
            columns: stacked ? 1 : 2
            rowSpacing: 12
            columnSpacing: 12
            Layout.fillWidth: true
            Layout.margins: 16
            Layout.leftMargin: 20
            Layout.rightMargin: 20

            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true
                Text {
                    text: "Your investments"
                    color: Theme.text
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                }
                Text {
                    text: "Double-click a name to rename it. Click a heading to sort by it."
                    color: Theme.muted
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }

            RowLayout {
                id: tools
                spacing: 8
                Layout.fillWidth: top.stacked
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter

                TextField {
                    objectName: "tableSearch"
                    placeholderText: "Search by name or ticker"
                    Accessible.name: "Search your investments"
                    text: card.home.search
                    onTextEdited: card.home.setSearch(text)
                    implicitWidth: 220
                    implicitHeight: 36
                    leftPadding: 34
                    color: Theme.text
                    placeholderTextColor: Theme.muted
                    font.pixelSize: 14
                    Layout.fillWidth: top.stacked
                    background: Rectangle {
                        radius: 8
                        color: Theme.surface
                        border.width: parent.activeFocus ? 2 : 1
                        border.color: parent.activeFocus ? Theme.accent : Theme.borderStrong
                    }
                    Icon {
                        x: 11
                        anchors.verticalCenter: parent.verticalCenter
                        name: "search"
                        size: 15
                        color: Theme.muted
                    }
                }

                SecondaryButton {
                    id: showButton
                    text: card.home.showLabel
                    iconName: "filter"
                    lit: card.home.show !== "all"
                    implicitHeight: 36
                    onClicked: showMenu.popup(showButton, showButton.width - showMenu.width, showButton.height + 4)

                    AppMenu {
                        id: showMenu
                        AppMenuItem {
                            text: "All investments"
                            radio: true
                            chosen: card.home.show === "all"
                            onTriggered: card.home.setShow("all")
                        }
                        AppMenuItem {
                            text: "Gaining"
                            radio: true
                            chosen: card.home.show === "gaining"
                            onTriggered: card.home.setShow("gaining")
                        }
                        AppMenuItem {
                            text: "Losing"
                            radio: true
                            chosen: card.home.show === "losing"
                            onTriggered: card.home.setShow("losing")
                        }
                    }
                }

                SecondaryButton {
                    id: columnsButton
                    text: "Columns"
                    iconName: "columns"
                    implicitHeight: 36
                    onClicked: columnsPanel.visible ? columnsPanel.close() : card.openColumns()

                    MenuPanel {
                        id: columnsPanel
                        x: columnsButton.width - width

                        ColumnLayout {
                            spacing: 0
                            Text {
                                text: "Columns shown"
                                color: Theme.muted
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                Layout.leftMargin: 4
                                Layout.bottomMargin: 4
                            }
                            GridLayout {  // two columns, in the table's order down each: short enough to open clear of its button
                                flow: GridLayout.TopToBottom
                                rows: Math.ceil(card.home.columnKeys.length / 2)
                                rowSpacing: 0
                                columnSpacing: 12
                                Repeater {
                                    model: card.home.columnKeys  // fixed: a tick box keeps the keyboard when ticked
                                    RowLayout {
                                        required property string modelData
                                        spacing: 8
                                        Layout.fillWidth: true
                                        AppCheckBox {
                                            objectName: "columnChoice"
                                            text: card.home.headings[modelData]
                                            checked: modelData === "name" || card.home.columns.indexOf(modelData) >= 0
                                            enabled: modelData !== "name"
                                            implicitHeight: 32
                                            Layout.fillWidth: true
                                            onToggled: card.home.setColumnShown(modelData, checked)
                                        }
                                        Text {
                                            visible: modelData === "name"
                                            text: "always shown"
                                            color: Theme.muted
                                            font.pixelSize: 12
                                            Layout.rightMargin: 4
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                implicitHeight: 1
                                color: Theme.border
                                Layout.fillWidth: true
                                Layout.topMargin: 6
                                Layout.bottomMargin: 6
                            }
                            TextButton {
                                text: "Reset columns"
                                iconName: "refresh"
                                implicitHeight: 34
                                onClicked: card.home.resetColumns()
                            }
                        }
                    }
                }
            }
        }

        // Some investments are hidden: which ones are shown, and a way back to all of them.
        Rectangle {
            visible: card.home.filterLine !== ""
            color: Theme.subtle
            implicitHeight: filterRow.implicitHeight + 16
            Layout.fillWidth: true
            Rectangle {
                width: parent.width
                height: 1
                color: Theme.border
            }
            RowLayout {
                id: filterRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 20
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Icon {
                    name: "filter"
                    size: 15
                    color: Theme.muted
                }
                Text {
                    text: card.home.filterLine
                    color: Theme.text
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                TextButton {
                    text: "Show all"
                    implicitHeight: 32
                    onClicked: card.home.showAll()
                }
            }
        }

        Flickable {
            id: table
            readonly property bool scrolls: contentWidth > width + 0.5

            contentWidth: Math.max(width, Columns.needed(card.home.columns, card.widths))
            contentHeight: rows.implicitHeight
            implicitHeight: rows.implicitHeight + (scrolls ? sideways.height : 0)
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            interactive: scrolls
            clip: true
            Layout.fillWidth: true

            ScrollBar.horizontal: ScrollBar {
                id: sideways
                policy: table.scrolls ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            }

            ColumnLayout {
                id: rows
                width: table.contentWidth
                spacing: 0

                InvestmentHeader {
                    columns: card.home.columns
                    widths: card.widths
                    headings: card.home.headings
                    sortColumn: card.home.sortColumn
                    sortDescending: card.home.sortDescending
                    onSortClicked: (column) => card.home.sortBy(column)
                    Layout.fillWidth: true
                }

                Repeater {
                    model: card.home.holdings
                    InvestmentRow {
                        required property var model
                        onDoubleClicked: card.home.enterValue(model.ticker)
                        columns: card.home.columns
                        widths: card.widths
                        name: model.name
                        detail: model.detail
                        shares: model.shares
                        averageCost: model.averageCost
                        price: model.price
                        invested: model.invested
                        worth: model.worth
                        worthNote: model.worthNote
                        share: model.share
                        shareFraction: model.shareFraction
                        investedShare: model.investedShare
                        gain: model.gain
                        gainUp: model.gainUp
                        realized: model.realized
                        realizedTone: model.realizedTone
                        dividends: model.dividends
                        status: model.status
                        editName: model.editName
                        Layout.fillWidth: true
                        onRenamed: (name) => card.home.rename(model.ticker, name)
                    }
                }

                InvestmentRow {
                    readonly property var cells: card.home.totalCells
                    visible: cells.name !== undefined
                    mode: "total"
                    columns: card.home.columns
                    widths: card.widths
                    name: cells.name || ""
                    invested: cells.invested || ""
                    worth: cells.worth || ""
                    share: cells.share || ""
                    investedShare: cells.invested_share || ""
                    gain: cells.gain || ""
                    gainUp: cells.gain_up !== false
                    realized: cells.realized || ""
                    realizedTone: cells.realized_tone || ""
                    dividends: cells.dividends || ""
                    Layout.fillWidth: true
                }
            }
        }
    }
}
