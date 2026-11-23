import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// Settings, one page with sections (mockup: Settings). Every change is saved at once.
Item {
    id: page
    readonly property var settings: session.settingsPage

    function scrollTo(section) {
        var flick = scroll.contentItem
        flick.contentY = Math.max(0, Math.min(section.y, flick.contentHeight - flick.height))
    }

    component SectionTitle: Text {
        color: Theme.text
        font.pixelSize: 17
        font.weight: Font.DemiBold
    }
    component Muted: Text {
        color: Theme.muted
        font.pixelSize: 13
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }

    ScrollView {
        id: scroll
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            width: Math.min(scroll.availableWidth - 48, 992)
            x: (scroll.availableWidth - width) / 2
            spacing: 8

            Item { Layout.preferredHeight: 4 }
            TextButton {
                text: "Your portfolio"
                iconName: "arrowLeft"
                Layout.leftMargin: -10
                onClicked: page.settings.back()
            }
            Text {
                text: "Settings"
                color: Theme.text
                font.pixelSize: 26
                font.weight: Font.DemiBold
            }

            RowLayout {
                spacing: 24
                Layout.fillWidth: true
                Layout.topMargin: 12

                ColumnLayout {  // the side menu
                    visible: page.width > 760
                    spacing: 2
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredWidth: 200
                    Repeater {
                        model: [["Investments", investmentsCard], ["Statement", statementCard], ["Spreadsheet", sheetCard], ["About", aboutCard]]
                        TextButton {
                            required property var modelData
                            text: modelData[0]
                            Layout.alignment: Qt.AlignLeft
                            onClicked: page.scrollTo(modelData[1])
                        }
                    }
                }

                ColumnLayout {
                    id: sections
                    spacing: 20
                    Layout.fillWidth: true

                    Card {
                        id: investmentsCard
                        spacing: 0
                        padding: 0
                        Layout.fillWidth: true

                        ColumnLayout {
                            spacing: 4
                            Layout.margins: 24
                            Layout.bottomMargin: 12
                            SectionTitle { text: "Your investments" }
                            Muted { text: "The stock exchange listing used for each one, and the name shown for it here and in your spreadsheet." }
                        }
                        Text {
                            visible: !page.settings.hasInvestments
                            text: page.settings.nothingRemembered
                            color: Theme.muted
                            font.pixelSize: 14
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                            Layout.margins: 24
                            Layout.topMargin: 8
                        }
                        Repeater {
                            model: page.settings.investments
                            Rectangle {
                                id: investment
                                required property string ticker
                                required property string name
                                required property string detail
                                required property string status
                                required property string editName
                                property bool editing: false
                                Layout.fillWidth: true
                                implicitHeight: investmentRow.implicitHeight + 24
                                color: Theme.surface
                                Rectangle { width: parent.width; height: 1; color: Theme.border }
                                RowLayout {
                                    id: investmentRow
                                    anchors.fill: parent
                                    anchors.leftMargin: 24
                                    anchors.rightMargin: 24
                                    spacing: 16
                                    ColumnLayout {
                                        spacing: 1
                                        Layout.fillWidth: true
                                        Text {
                                            visible: !investment.editing
                                            text: investment.name
                                            color: Theme.text
                                            font.pixelSize: 14
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                        TextField {
                                            id: editor
                                            objectName: "nameEditor"
                                            visible: investment.editing
                                            Accessible.name: "New name for " + investment.name
                                            color: Theme.text
                                            font.pixelSize: 14
                                            implicitHeight: 30
                                            Layout.fillWidth: true
                                            background: Rectangle {
                                                radius: 6
                                                color: Theme.surface
                                                border.width: 2
                                                border.color: Theme.accent
                                            }
                                            onAccepted: {
                                                investment.editing = false
                                                page.settings.rename(investment.ticker, text)
                                            }
                                            Keys.onEscapePressed: investment.editing = false
                                            onActiveFocusChanged: if (!activeFocus) investment.editing = false
                                        }
                                        Text {
                                            text: investment.detail
                                            color: Theme.muted
                                            font.pixelSize: 13
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }
                                    Chip {
                                        text: investment.status
                                        tone: investment.status.startsWith("Asks") ? "warn" : "neutral"
                                    }
                                    IconButton {
                                        id: more
                                        text: "More for " + investment.name
                                        iconName: "more"
                                        onClicked: menu.popup(more, 0, more.height)
                                    }
                                }
                                Menu {
                                    id: menu
                                    MenuItem {
                                        text: "Rename"
                                        onTriggered: {
                                            editor.text = investment.editName
                                            investment.editing = true
                                            editor.forceActiveFocus()
                                            editor.selectAll()
                                        }
                                    }
                                    MenuItem {
                                        text: "Choose the listing next time"
                                        enabled: !investment.status.startsWith("Asks") && !investment.status.startsWith("Not matched")
                                        onTriggered: page.settings.chooseAgain(investment.ticker)
                                    }
                                    MenuItem {
                                        text: "Forget…"
                                        onTriggered: page.settings.forget(investment.ticker)
                                    }
                                }
                            }
                        }
                        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.border }
                        AppSwitch {
                            text: "Take the first listing without asking"
                            checked: page.settings.alwaysFirst
                            onToggled: page.settings.setAlwaysFirst(checked)
                            Layout.fillWidth: true
                            Layout.leftMargin: 24
                            Layout.rightMargin: 24
                            Layout.topMargin: 14
                        }
                        Muted {
                            text: "When a fund is on several stock exchanges. The listing that best matches your purchases always comes first."
                            Layout.leftMargin: 24
                            Layout.rightMargin: 84
                        }
                        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.border; Layout.topMargin: 14 }
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.margins: 24
                            Layout.topMargin: 12
                            Layout.bottomMargin: 16
                            Muted { text: "Ctrl+Z takes back the last change." }
                            DangerButton {
                                text: "Forget all investments…"
                                enabled: page.settings.hasInvestments
                                onClicked: page.settings.forgetAll()
                            }
                        }
                    }

                    Card {
                        id: statementCard
                        spacing: 14
                        Layout.fillWidth: true
                        SectionTitle { text: "Your statement" }
                        RowLayout {
                            spacing: 16
                            Layout.fillWidth: true
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text {
                                    text: page.settings.statementLine
                                    color: Theme.text
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                }
                                Muted {
                                    visible: page.settings.hasStatement
                                    text: "A copy is kept in the app's own folder, so prices can be looked up without a new statement."
                                }
                            }
                            SecondaryButton {
                                text: "Use a newer one…"
                                onClicked: page.settings.useNewerStatement()
                            }
                            DangerButton {
                                visible: page.settings.hasStatement
                                text: "Forget it…"
                                onClicked: page.settings.forgetStatement()
                            }
                        }
                    }

                    Card {
                        id: sheetCard
                        spacing: 14
                        Layout.fillWidth: true
                        SectionTitle { text: "Your spreadsheet" }
                        RowLayout {
                            visible: page.settings.hasSpreadsheet
                            spacing: 16
                            Layout.fillWidth: true
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text {
                                    text: page.settings.spreadsheetName
                                    color: Theme.text
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                Muted {
                                    text: page.settings.spreadsheetFolder
                                    elide: Text.ElideMiddle
                                    wrapMode: Text.NoWrap
                                }
                            }
                            SecondaryButton {
                                text: "Open folder"
                                onClicked: page.settings.openFolder()
                            }
                            SecondaryButton {
                                text: "Choose another…"
                                onClicked: page.settings.chooseSpreadsheet()
                            }
                            TextButton {
                                text: "Stop using it"
                                onClicked: page.settings.stopUsingSpreadsheet()
                            }
                        }
                        RowLayout {
                            visible: !page.settings.hasSpreadsheet
                            spacing: 8
                            Layout.fillWidth: true
                            Muted { text: "No spreadsheet is updated." }
                            SecondaryButton {
                                text: "Choose spreadsheet…"
                                onClicked: page.settings.chooseSpreadsheet()
                            }
                            SecondaryButton {
                                text: "Create a new one…"
                                onClicked: page.settings.createSpreadsheet()
                            }
                        }
                        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.border }
                        RowLayout {
                            spacing: 16
                            Layout.fillWidth: true
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Text {
                                    text: "Backup copies to keep"
                                    color: Theme.text
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                }
                                Muted { text: page.settings.backupsHelp }
                            }
                            Stepper {
                                value: page.settings.backupsKept
                                to: page.settings.maxBackups
                                onChangedTo: (value) => page.settings.setBackupsKept(value)
                            }
                        }
                    }

                    Card {
                        id: aboutCard
                        spacing: 12
                        Layout.fillWidth: true
                        SectionTitle { text: "About and privacy" }
                        RowLayout {
                            spacing: 12
                            AppLogo { size: 36 }
                            ColumnLayout {
                                spacing: 0
                                Text {
                                    text: "Statement Portfolio Tracker"
                                    color: Theme.text
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    text: page.settings.version
                                    color: Theme.muted
                                    font.pixelSize: 13
                                }
                            }
                            Item { Layout.fillWidth: true }
                            TextButton {
                                text: "New versions"
                                onClicked: Qt.openUrlExternally(page.settings.releasesUrl)
                            }
                        }
                        Text {
                            text: page.settings.privacyText
                            color: Theme.text
                            font.pixelSize: 14
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                        Muted { text: page.settings.disclaimer }
                    }

                    Item { Layout.preferredHeight: 16 }
                }
            }
        }
    }
}
