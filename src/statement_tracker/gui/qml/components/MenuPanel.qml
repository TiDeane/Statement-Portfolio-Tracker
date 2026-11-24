import QtQuick
import QtQuick.Controls.Basic

// A panel that opens under its button, drawn like AppMenu, for choices made several at a time: it stays
// open while they are made, and closes with Esc, a click elsewhere or its button again.
Popup {
    padding: 8
    margins: 8  // never past the window's edge
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
    focus: true  // Tab moves through its choices; Esc closes it

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 110; easing.type: Easing.OutCubic }
    }

    background: MenuBackground {}
}
