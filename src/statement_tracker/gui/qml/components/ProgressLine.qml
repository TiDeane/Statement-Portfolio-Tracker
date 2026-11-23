import QtQuick

// A thin progress bar: `fraction` from 0 to 1, or, with `indeterminate`, a segment moving back and forth
// for work whose length is not known.
Rectangle {
    id: track
    property real fraction: 0
    property bool indeterminate: false

    implicitHeight: 6
    radius: 3
    color: Theme.subtle
    clip: true

    Rectangle {
        visible: !track.indeterminate
        width: track.width * Math.max(0, Math.min(1, track.fraction))
        height: track.height
        radius: 3
        color: Theme.accent
        Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
    }

    Rectangle {
        id: moving
        visible: track.indeterminate
        width: track.width * 0.3
        height: track.height
        radius: 3
        color: Theme.accent
        SequentialAnimation on x {
            running: track.indeterminate && track.visible
            loops: Animation.Infinite
            NumberAnimation { from: -moving.width; to: track.width; duration: 1100; easing.type: Easing.InOutQuad }
        }
    }
}
