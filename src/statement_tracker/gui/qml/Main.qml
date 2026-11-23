import QtQuick
import QtQuick.Controls

// The window. For now a stand-in that proves the foundation: a heading, a button and dropping files.
ApplicationWindow {
    id: root
    width: 1040
    height: 760
    minimumWidth: 720
    minimumHeight: 560
    title: "Statement Portfolio Tracker"
    color: Theme.bg

    // Called by the drop area below for files dropped on the window.
    function dropFiles(urls) {
        if (urls.length > 0)
            heading.text = decodeURIComponent(urls[0].toString().split("/").pop())
    }

    Column {
        anchors.centerIn: parent
        spacing: 16

        Label {
            id: heading
            text: "Your portfolio"
            color: Theme.text
            font.pixelSize: 20
        }

        Button {
            text: "Try me"
            onClicked: heading.text = "Clicked"
        }
    }

    DropArea {
        anchors.fill: parent
        onDropped: (drop) => {
            root.dropFiles(drop.urls)
            drop.accept(Qt.CopyAction)
        }
    }
}
