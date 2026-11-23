import QtQuick
import QtQuick.Shapes

// A line icon from the mockups, drawn by the app (no image files): 24-unit paths, scaled to `size`.
Shape {
    id: icon
    property string name: ""
    property int size: 18
    property color color: Theme.text
    property real strokeWidth: 2

    readonly property var paths: ({
        "settings": "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z M15 12a3 3 0 1 1-6 0a3 3 0 1 1 6 0",
        "help": "M22 12a10 10 0 1 1-20 0a10 10 0 1 1 20 0 M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3 M12 17h.01",
        "refresh": "M21 12a9 9 0 1 1-2.64-6.36 M21 3v6h-6",
        "file": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8",
        "plusFile": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M12 12v6 M9 15h6",
        "sheet": "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M3 9h18 M3 15h18 M9 3v18",
        "folder": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
        "check": "M22 12a10 10 0 1 1-20 0a10 10 0 1 1 20 0 M9 12l2 2 4-4",
        "alert": "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
        "clock": "M22 12a10 10 0 1 1-20 0a10 10 0 1 1 20 0 M12 6v6l4 2",
        "info": "M22 12a10 10 0 1 1-20 0a10 10 0 1 1 20 0 M12 16v-4 M12 8h.01",
        "wifiOff": "M2 2l20 20 M8.5 16.5a5 5 0 0 1 7 0 M5 12.9a10 10 0 0 1 5.17-2.69 M19 12.9a10 10 0 0 0-2.3-1.7 M2 8.8a15 15 0 0 1 4.2-2.7 M22 8.8a15 15 0 0 0-11.3-3.7 M12 20h.01",
        "upload": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12",
        "pencil": "M12 20h9 M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
        "more": "M5 12h.01 M12 12h.01 M19 12h.01",
        "arrowLeft": "M19 12H5 M12 19l-7-7 7-7",
        "arrowRight": "M5 12h14 M12 5l7 7-7 7",
        "close": "M18 6 6 18 M6 6l12 12",
        "copy": "M11 9h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2z M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1",
        "lock": "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z M7 11V7a5 5 0 0 1 10 0v4",
        "shield": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
        "trend": "M3 17l6-6 4 4 8-8 M14 7h7v7",
        "contrast": "M22 12a10 10 0 1 1-20 0a10 10 0 1 1 20 0 M12 2v20 M12 7h5 M12 12h7.5 M12 17h5",
        "trash": "M3 6h18 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"
    })

    implicitWidth: size
    implicitHeight: size
    visible: name !== ""
    preferredRendererType: Shape.CurveRenderer

    ShapePath {
        strokeColor: icon.color
        strokeWidth: icon.name === "more" ? icon.strokeWidth * 1.6 : icon.strokeWidth
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.RoundJoin
        scale: Qt.size(icon.size / 24, icon.size / 24)
        PathSvg { path: icon.paths[icon.name] || "" }
    }
}
