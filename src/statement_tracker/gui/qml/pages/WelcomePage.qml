import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes
import "../components"

// First launch, shown until a statement is kept (mockups: Welcome, Welcome-Chosen, Welcome-Spreadsheet).
// Each step shows what was picked and moves on only with its button.
Item {
    id: page
    readonly property var welcome: session.welcome
    readonly property bool onStatement: welcome.step === "statement"
    readonly property bool chosen: welcome.statementChosen
    readonly property bool dragging: ApplicationWindow.window ? ApplicationWindow.window.dragging : false

    ScrollView {
        id: scroll
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            width: Math.min(scroll.availableWidth - 48, 920)
            x: (scroll.availableWidth - width) / 2
            spacing: 28

            Item { Layout.preferredHeight: 4 }

            RowLayout {
                spacing: 10
                Layout.fillWidth: true
                AppLogo { size: 28 }
                Text {
                    text: "Statement Portfolio Tracker"
                    color: Theme.text
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: page.onStatement ? "Step 1 of 2" : "Step 2 of 2"
                    color: Theme.muted
                    font.pixelSize: 13
                }
                Row {
                    spacing: 6
                    Rectangle { width: 24; height: 6; radius: 3; color: Theme.accent }
                    Rectangle { width: 24; height: 6; radius: 3; color: page.onStatement ? Theme.borderStrong : Theme.accent }
                }
            }

            // Step 1: the statement.
            ColumnLayout {
                visible: page.onStatement
                spacing: 28
                Layout.fillWidth: true

                ColumnLayout {
                    spacing: 8
                    Layout.fillWidth: true
                    Text {
                        text: "Let's see how your investments are doing"
                        color: Theme.text
                        font.pixelSize: 30
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                    Text {
                        text: "Start with your stock statement from Revolut. The app reads what you bought and sold, then looks up today's prices."
                        color: Theme.muted
                        font.pixelSize: 15
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                        Layout.maximumWidth: 640
                    }
                }

                GridLayout {
                    columns: page.width > 780 ? 2 : 1
                    columnSpacing: 16
                    rowSpacing: 16
                    Layout.fillWidth: true

                    // Where the statement goes: dashed until one is read, then green with what it holds.
                    Rectangle {
                        id: dropCard
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 540
                        Layout.minimumHeight: 300
                        implicitHeight: dropColumn.implicitHeight + 72
                        radius: 14
                        color: page.chosen || page.dragging ? Theme.okBg : Theme.surface
                        border.width: page.chosen || page.dragging ? 2 : 0
                        border.color: Theme.accent

                        Shape {
                            anchors.fill: parent
                            visible: !page.chosen && !page.dragging
                            preferredRendererType: Shape.CurveRenderer
                            ShapePath {
                                strokeColor: Theme.borderStrong
                                strokeWidth: 2
                                strokeStyle: ShapePath.DashLine
                                dashPattern: [4, 3]
                                fillColor: "transparent"
                                PathRectangle {
                                    x: 1
                                    y: 1
                                    width: dropCard.width - 2
                                    height: dropCard.height - 2
                                    radius: 13
                                }
                            }
                        }

                        ColumnLayout {
                            id: dropColumn
                            anchors.centerIn: parent
                            width: parent.width - 48
                            spacing: 12

                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                implicitWidth: 56
                                implicitHeight: 56
                                radius: 28
                                color: Theme.accentSoft
                                Icon {
                                    anchors.centerIn: parent
                                    name: page.chosen ? "check" : "upload"
                                    size: 26
                                    color: Theme.accentInk
                                }
                            }
                            Text {
                                visible: !page.chosen
                                text: "Drop your Revolut statement here"
                                color: Theme.text
                                font.pixelSize: 18
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                            Text {
                                visible: !page.chosen
                                text: "A CSV file from the Revolut app"
                                color: Theme.muted
                                font.pixelSize: 14
                                horizontalAlignment: Text.AlignHCenter
                                Layout.fillWidth: true
                            }
                            Text {
                                visible: !page.chosen
                                text: "or"
                                color: Theme.muted
                                font.pixelSize: 13
                                horizontalAlignment: Text.AlignHCenter
                                Layout.fillWidth: true
                            }
                            SecondaryButton {
                                visible: !page.chosen
                                text: "Choose statement file…"
                                Layout.alignment: Qt.AlignHCenter
                                onClicked: welcome.chooseStatement()
                            }
                            Text {
                                visible: page.chosen
                                text: welcome.statementName
                                color: Theme.text
                                font.pixelSize: 18
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }
                            Repeater {
                                model: page.chosen ? welcome.statementFacts : []
                                Text {
                                    required property string modelData
                                    text: modelData
                                    color: Theme.text
                                    font.pixelSize: 14
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }
                            }
                            SecondaryButton {
                                visible: page.chosen
                                text: "Choose another file…"
                                Layout.alignment: Qt.AlignHCenter
                                onClicked: welcome.chooseStatement()
                            }
                            Text {
                                visible: page.chosen
                                text: "or drop another one here"
                                color: Theme.muted
                                font.pixelSize: 13
                                horizontalAlignment: Text.AlignHCenter
                                Layout.fillWidth: true
                            }
                        }
                    }

                    Card {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 360
                        radius: 14
                        spacing: 14

                        Text {
                            text: "Where do I get it?"
                            color: Theme.text
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }
                        Repeater {
                            model: welcome.revolutSteps
                            RowLayout {
                                required property string modelData
                                required property int index
                                spacing: 10
                                Layout.fillWidth: true
                                Rectangle {
                                    Layout.alignment: Qt.AlignTop
                                    implicitWidth: 22
                                    implicitHeight: 22
                                    radius: 11
                                    color: Theme.subtle
                                    Text {
                                        anchors.centerIn: parent
                                        text: index + 1
                                        color: Theme.text
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                    }
                                }
                                Text {
                                    text: modelData
                                    color: Theme.text
                                    font.pixelSize: 14
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                            }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: note.implicitHeight + 20
                            radius: 8
                            color: Theme.warnBg
                            Text {
                                id: note
                                anchors.fill: parent
                                anchors.margins: 10
                                text: welcome.allTimeNote
                                color: Theme.warnInk
                                font.pixelSize: 13
                                wrapMode: Text.Wrap
                            }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: Theme.border
            }

            RowLayout {
                spacing: 12
                Layout.fillWidth: true

                RowLayout {
                    visible: page.onStatement
                    spacing: 8
                    Layout.fillWidth: true
                    Icon {
                        name: "lock"
                        size: 15
                        color: Theme.muted
                    }
                    Text {
                        text: "Everything stays on this computer. Only fund codes and dates go to Yahoo Finance."
                        color: Theme.muted
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                    TextButton {
                        text: "About and privacy"
                        onClicked: session.goTo("settings")
                    }
                }
                Item {
                    visible: !page.onStatement
                    Layout.fillWidth: true
                }
                PrimaryButton {
                    text: page.onStatement ? "Continue" : "Show my investments"
                    iconName: "arrowRight"
                    enabled: welcome.canContinue
                    onClicked: welcome.next()
                }
            }

            Item { Layout.preferredHeight: 8 }
        }
    }
}
