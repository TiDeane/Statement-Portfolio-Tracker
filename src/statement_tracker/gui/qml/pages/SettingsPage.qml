import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

// Settings, one page with sections (mockup: Settings). Every change is saved at once.
Item {
    id: page
    readonly property var settings: session.settingsPage

    // The page's frame: centred, at most 992 wide. The title and the chapter menu stay in place;
    // only the chapters themselves scroll.
    readonly property real frameWidth: Math.min(width - 48, 992)
    readonly property real frameX: (width - frameWidth) / 2
    readonly property bool withMenu: width > 760
    readonly property var chapterCards: [investmentsCard, statementCard, sheetCard, openingCard, appearanceCard, aboutCard]
    readonly property var chapterNames: [
        "Your investments", "Your statement", "Your spreadsheet", "Opening the app", "Appearance", "About and privacy"
    ]
    readonly property var chapterIcons: ["trend", "file", "sheet", "power", "contrast", "info"]

    property int chosenChapter: -1  // clicked in the menu: marked until the page is scrolled by hand
    readonly property int currentChapter: {
        if (chosenChapter >= 0)
            return chosenChapter
        var flick = scroll.contentItem
        if (flick.contentY >= flick.contentHeight - flick.height - 2)
            return chapterCards.length - 1  // at the end, the last chapter is the one being read
        var found = 0
        for (var i = 0; i < chapterCards.length; i++)
            if (chapterCards[i].y <= flick.contentY + 24)
                found = i
        return found
    }

    function scrollTo(index) {
        var flick = scroll.contentItem
        chosenChapter = index
        glide.to = Math.max(0, Math.min(chapterCards[index].y, flick.contentHeight - flick.height))
        glide.restart()
    }

    NumberAnimation {
        id: glide
        target: scroll.contentItem
        property: "contentY"
        duration: 220
        easing.type: Easing.OutCubic
    }
    Connections {
        target: scroll.contentItem
        function onContentYChanged() { if (!glide.running) page.chosenChapter = -1 }
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

    ColumnLayout {  // the title, fixed
        id: header
        x: page.frameX
        width: page.frameWidth
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
        Item { Layout.preferredHeight: 12 }
    }

    Column {  // the chapters, fixed beside the page
        id: menu
        visible: page.withMenu
        x: page.frameX
        y: header.y + header.height
        width: 200
        spacing: 2
        Accessible.role: Accessible.PageTabList
        Repeater {
            model: page.chapterNames.length
            AbstractButton {
                id: chapter
                required property int index
                objectName: "chapter"
                readonly property bool current: page.currentChapter === index
                text: page.chapterNames[index]
                width: menu.width
                implicitHeight: 40
                focusPolicy: Qt.StrongFocus
                hoverEnabled: true
                Accessible.role: Accessible.PageTab
                Accessible.selected: current
                onClicked: page.scrollTo(index)
                background: Rectangle {
                    radius: 8
                    color: chapter.current ? Theme.accentSoft : chapter.hovered ? Theme.subtle : "transparent"
                    border.width: chapter.visualFocus ? 2 : 0
                    border.color: Theme.text
                    Rectangle {  // the mark beside the chapter being read
                        visible: chapter.current
                        width: 3
                        height: 18
                        radius: 1.5
                        x: 0
                        anchors.verticalCenter: parent.verticalCenter
                        color: Theme.accent
                    }
                }
                contentItem: Item {}
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 14
                    spacing: 12
                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: page.chapterIcons[chapter.index]
                        color: chapter.current ? Theme.accentInk : Theme.muted
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: chapter.text
                        color: chapter.current ? Theme.accentInk : Theme.text
                        font.pixelSize: 14
                        font.weight: chapter.current ? Font.DemiBold : Font.Normal
                    }
                }
            }
        }
    }

    ScrollView {  // the chapters' content, which scrolls; its scroll bar at the window's edge
        id: scroll
        x: page.withMenu ? page.frameX + 224 : page.frameX
        y: header.y + header.height
        width: page.width - x
        height: page.height - y
        contentWidth: availableWidth
        clip: true  // what scrolls up goes under the title, not over it

        ColumnLayout {
            width: Math.min(scroll.availableWidth - 24, page.frameWidth - (page.withMenu ? 224 : 0))
            spacing: 8

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
                                        onClicked: menu.popup(more, more.width - menu.width, more.height + 4)  // under it, right edges lined up
                                    }
                                }
                                AppMenu {
                                    id: menu
                                    AppMenuItem {
                                        text: "Rename"
                                        iconName: "pencil"
                                        onTriggered: {
                                            editor.text = investment.editName
                                            investment.editing = true
                                            editor.forceActiveFocus()
                                            editor.selectAll()
                                        }
                                    }
                                    AppMenuItem {
                                        text: "Choose the listing next time"
                                        iconName: "refresh"
                                        enabled: !investment.status.startsWith("Asks") && !investment.status.startsWith("Not matched")
                                        onTriggered: page.settings.chooseAgain(investment.ticker)
                                    }
                                    AppMenuSeparator {}
                                    AppMenuItem {
                                        text: "Forget…"
                                        iconName: "trash"
                                        danger: true
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
                                    visible: text !== ""
                                    text: page.settings.statementName
                                    color: Theme.text
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    Layout.fillWidth: true
                                }
                                Muted {
                                    visible: text !== ""
                                    text: page.settings.statementFolder
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                }
                                Text {
                                    visible: text !== ""
                                    text: page.settings.statementNote
                                    color: Theme.warnInk
                                    font.pixelSize: 13
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: page.settings.statementLine
                                    color: page.settings.hasStatement ? Theme.muted : Theme.text
                                    font.pixelSize: page.settings.hasStatement ? 13 : 14
                                    font.weight: page.settings.hasStatement ? Font.Normal : Font.DemiBold
                                    Layout.topMargin: page.settings.hasStatement ? 4 : 0
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
                        Rectangle { visible: page.settings.hasSpreadsheet; Layout.fillWidth: true; implicitHeight: 1; color: Theme.border }
                        ColumnLayout {
                            visible: page.settings.hasSpreadsheet
                            spacing: 2
                            Layout.fillWidth: true
                            AppSwitch {
                                text: "Update it by itself"
                                checked: page.settings.autoUpdate
                                padding: 0  // in line with the backup copies' title and stepper above
                                onToggled: page.settings.setAutoUpdate(checked)
                                Layout.fillWidth: true
                            }
                            Muted { text: "As soon as today's prices are in: when the app opens, after Refresh prices and with a new statement." }
                        }
                    }

                    Card {  // opening when the user signs in (Spec F12)
                        id: openingCard
                        spacing: 14
                        Layout.fillWidth: true
                        SectionTitle { text: "Opening the app" }
                        ColumnLayout {
                            spacing: 2
                            Layout.fillWidth: true
                            AppSwitch {
                                text: page.settings.loginStartLabel
                                checked: page.settings.loginStartOn
                                enabled: page.settings.canStartAtLogin
                                padding: 0
                                // What the system's entry is, whatever the click did: one that could not be
                                // written leaves it as it was.
                                onToggled: {
                                    page.settings.setLoginStart(checked)
                                    checked = Qt.binding(() => page.settings.loginStartOn)
                                }
                                Layout.fillWidth: true
                            }
                            Muted { text: page.settings.loginStartHelp }
                            Muted {
                                visible: text !== ""
                                text: page.settings.loginStartNote
                                color: Theme.warnInk
                            }
                        }
                    }

                    Card {
                        id: appearanceCard
                        spacing: 14
                        Layout.fillWidth: true
                        SectionTitle { text: "Appearance" }
                        Flow {
                            spacing: 8
                            Layout.fillWidth: true
                            Repeater {
                                model: [["system", "Use device theme"], ["light", "Light"], ["dark", "Dark"]]
                                AbstractButton {
                                    id: look
                                    required property var modelData
                                    text: modelData[1]
                                    checked: page.settings.appearance === modelData[0]
                                    focusPolicy: Qt.StrongFocus
                                    hoverEnabled: true
                                    implicitHeight: 44
                                    implicitWidth: lookRow.implicitWidth + 32
                                    onClicked: page.settings.setAppearance(modelData[0])
                                    background: Rectangle {
                                        radius: 10
                                        color: look.checked ? Theme.okBg : Theme.surface
                                        border.width: look.checked || look.visualFocus ? 2 : 1
                                        border.color: look.checked ? Theme.accent : look.visualFocus ? Theme.text : Theme.border
                                    }
                                    contentItem: Item {}
                                    Row {
                                        id: lookRow
                                        anchors.centerIn: parent
                                        spacing: 10
                                        Rectangle {  // the radio mark
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: 18
                                            height: 18
                                            radius: 9
                                            color: Theme.surface
                                            border.width: look.checked ? 5 : 1.5
                                            border.color: look.checked ? Theme.accent : Theme.borderStrong
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: look.text
                                            color: Theme.text
                                            font.pixelSize: 14
                                            font.weight: Font.Medium
                                        }
                                    }
                                }
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
