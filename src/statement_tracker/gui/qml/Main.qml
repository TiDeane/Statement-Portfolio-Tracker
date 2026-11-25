import QtQuick
import QtQuick.Controls.Basic
import "dialogs"
import "pages"

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
    onActiveChanged: if (active) session.activated()  // back from moving files or changing startup apps elsewhere
    onClosing: {
        session.stopRun()  // closing stops a fetch: nothing of it is saved
        dialogs.cancel()
    }

    readonly property bool dragging: dropArea.containsDrag
    property var dragKinds: []  // what the files dragged over the window would be used as: "statement", "spreadsheet"

    // Files dropped on the window, as local file URLs; the session decides what each is for.
    function dropFiles(urls) {
        session.dropFiles(Array.from(urls, (url) => url.toString()))
    }

    // The page shown (Spec F11). Settings goes over Home, which stays as it was under it; first launch replaces
    // everything. The new page fades in as it rises a little, the one left fades out.
    StackView {
        id: pageStack
        objectName: "pages"
        anchors.fill: parent

        readonly property var pageComponents: ({ "welcome": welcomePage, "home": homePage, "settings": settingsPage })

        function show(name) {
            if (currentItem && currentItem.objectName === "page-" + name)
                return
            if (depth > 1 && get(depth - 2).objectName === "page-" + name)
                pop()
            else if (name === "settings")
                push(pageComponents[name])
            else
                replace(null, pageComponents[name])  // the whole stack
        }

        initialItem: pageComponents[session.page]
        Connections {
            target: session
            function onPageChanged() { pageStack.show(session.page) }
        }

        component Arrive: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 180; easing.type: Easing.OutCubic }
            NumberAnimation { property: "y"; from: 8; to: 0; duration: 180; easing.type: Easing.OutCubic }
        }
        component Leave: Transition {
            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120; easing.type: Easing.OutCubic }
        }
        pushEnter: Arrive {}
        pushExit: Leave {}
        popEnter: Arrive {}
        popExit: Leave {}
        replaceEnter: Arrive {}
        replaceExit: Leave {}
    }
    Component {
        id: welcomePage
        WelcomePage { objectName: "page-welcome" }
    }
    Component {
        id: homePage
        HomePage { objectName: "page-home" }
    }
    Component {
        id: settingsPage
        SettingsPage { objectName: "page-settings" }
    }

    DropArea {
        id: dropArea
        anchors.fill: parent
        onEntered: (drag) => { root.dragKinds = session.dropKinds(Array.from(drag.urls, (url) => url.toString())) }
        onExited: root.dragKinds = []
        onDropped: (drop) => {
            root.dragKinds = []
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
