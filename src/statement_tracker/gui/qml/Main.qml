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

    // Qt's own parts (scroll bars, selected text, anything the app does not draw itself) take these
    // colours rather than the computer's: the app can be light on a computer in dark mode, and the other way round.
    palette.window: Theme.bg
    palette.windowText: Theme.text
    palette.base: Theme.surface
    palette.alternateBase: Theme.subtle
    palette.text: Theme.text
    palette.button: Theme.surface
    palette.buttonText: Theme.text
    palette.light: Theme.subtle
    palette.midlight: Theme.border
    palette.mid: Theme.borderStrong
    palette.dark: Theme.muted
    palette.shadow: Theme.borderStrong
    palette.highlight: Theme.accent
    palette.highlightedText: Theme.accentText
    palette.placeholderText: Theme.muted
    palette.toolTipBase: Theme.surface
    palette.toolTipText: Theme.text
    onClosing: {
        session.stopRun()  // closing stops a fetch: nothing of it is saved
        dialogs.cancel()
    }

    readonly property var pages: ({ "welcome": "WelcomePage", "home": "HomePage", "settings": "SettingsPage" })
    readonly property bool dragging: dropArea.containsDrag

    // Files dropped on the window, as local file URLs; the session decides what each is for.
    function dropFiles(urls) {
        session.dropFiles(Array.from(urls, (url) => url.toString()))
    }

    Loader {
        anchors.fill: parent
        source: "pages/" + root.pages[session.page] + ".qml"
    }

    DropArea {
        id: dropArea
        anchors.fill: parent
        onDropped: (drop) => {
            root.dropFiles(drop.urls)
            drop.accept(Qt.CopyAction)
        }
    }

    // Ctrl+Z and Ctrl+Y: changes to investments, on Home and in Settings, never during a fetch.
    Shortcut {
        sequences: [StandardKey.Undo]
        enabled: session.page !== "welcome" && !session.busy
        onActivated: session.undo()
    }
    Shortcut {
        // Ctrl+Y everywhere, as well as the system's own Redo (which may be Ctrl+Y already: then the two
        // are "ambiguous" to Qt, and redo is still what is meant).
        sequences: [StandardKey.Redo, "Ctrl+Y"]
        enabled: session.page !== "welcome" && !session.busy
        onActivated: session.redo()
        onActivatedAmbiguously: session.redo()
    }

    MessageDialog { id: messageDialog }
    ValueDialog { id: valueDialog }
    ListingDialog { id: listingDialog }
    HelpDialog { id: helpDialog }
    FileDialogs { id: fileDialogs }

    Connections {
        target: dialogs
        // A question settled by the app itself (or the window closing) takes its dialog off the screen.
        function onOpenChanged() {
            if (!dialogs.isOpen) {
                messageDialog.close()
                valueDialog.close()
                listingDialog.close()
                helpDialog.close()
            }
        }
        function onOpened(kind, data) {
            if (kind === "message")
                messageDialog.show(data)
            else if (kind === "value")
                valueDialog.show(data)
            else if (kind === "listing")
                listingDialog.show(data)
            else if (kind === "help")
                helpDialog.show(data)
            else if (kind === "openFile")
                fileDialogs.openFile(data)
            else if (kind === "saveFile")
                fileDialogs.saveFile(data)
        }
    }
}
