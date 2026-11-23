import QtQuick
import QtQuick.Controls.Basic
import "dialogs"

// The window: one page at a time (first launch, Home or Settings), files dropped anywhere on it,
// and the dialogs the session opens.
ApplicationWindow {
    id: root
    width: 1040
    height: 760
    minimumWidth: 720
    minimumHeight: 560
    title: "Statement Portfolio Tracker"
    color: Theme.bg
    onClosing: dialogs.cancel()

    readonly property var pages: ({ "welcome": "WelcomePage", "home": "HomePage", "settings": "SettingsPage" })

    // Files dropped on the window, as local file URLs; the session decides what each is for.
    function dropFiles(urls) {
        session.dropFiles(Array.from(urls, (url) => url.toString()))
    }

    Loader {
        anchors.fill: parent
        source: "pages/" + root.pages[session.page] + ".qml"
    }

    DropArea {
        anchors.fill: parent
        onDropped: (drop) => {
            root.dropFiles(drop.urls)
            drop.accept(Qt.CopyAction)
        }
    }

    MessageDialog { id: messageDialog }
    FileDialogs { id: fileDialogs }

    Connections {
        target: dialogs
        function onOpened(kind, data) {
            if (kind === "message")
                messageDialog.show(data)
            else if (kind === "openFile")
                fileDialogs.openFile(data)
            else if (kind === "saveFile")
                fileDialogs.saveFile(data)
        }
    }
}
