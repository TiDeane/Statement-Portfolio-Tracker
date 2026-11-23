import QtQuick

// A thin progress bar: `fraction` from 0 to 1.
Rectangle {
    id: track
    property real fraction: 0

    implicitHeight: 6
    radius: 3
    color: Theme.subtle

    Rectangle {
        width: track.width * Math.max(0, Math.min(1, track.fraction))
        height: track.height
        radius: 3
        color: Theme.accent
        Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
    }
}
