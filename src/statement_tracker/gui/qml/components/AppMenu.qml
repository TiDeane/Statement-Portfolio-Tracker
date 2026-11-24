import QtQuick
import QtQuick.Controls.Basic

// The app's pop-up menu: a rounded card in the window's colours, with a soft shadow below it.
// Its choices are AppMenuItem, grouped with AppMenuSeparator.
Menu {
    id: menu
    padding: 6
    margins: 8  // never past the window's edge

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 110; easing.type: Easing.OutCubic }
    }

    background: MenuBackground {}
}
