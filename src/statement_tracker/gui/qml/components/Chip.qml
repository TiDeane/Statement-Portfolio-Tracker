import QtQuick

// A small rounded label: "neutral", "warn" (amber) or "ok" (green).
Rectangle {
    id: chip
    property alias text: label.text
    property string tone: "neutral"

    radius: height / 2
    implicitHeight: 24
    implicitWidth: label.implicitWidth + 20
    color: tone === "warn" ? Theme.warnBg : tone === "ok" ? Theme.accentSoft : Theme.subtle

    Text {
        id: label
        anchors.centerIn: parent
        font.pixelSize: 13
        font.weight: Font.DemiBold
        color: chip.tone === "warn" ? Theme.warnInk : chip.tone === "ok" ? Theme.accentInk : Theme.text
    }
}
