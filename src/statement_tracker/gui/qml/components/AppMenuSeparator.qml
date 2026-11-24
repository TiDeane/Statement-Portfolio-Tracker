import QtQuick
import QtQuick.Controls.Basic

// A thin line between groups of choices in an AppMenu.
MenuSeparator {
    topPadding: 5
    bottomPadding: 5
    leftPadding: 6
    rightPadding: 6
    contentItem: Rectangle {
        implicitHeight: 1
        color: Theme.border
    }
}
