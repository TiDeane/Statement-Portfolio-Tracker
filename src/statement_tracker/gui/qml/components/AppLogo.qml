import QtQuick
import QtQuick.Shapes

// The app's icon, drawn: a green tile with a rising line and arrow (as packaging/make_icon.py draws it).
Rectangle {
    id: logo
    property int size: 28

    implicitWidth: size
    implicitHeight: size
    radius: size / 4
    color: Theme.dark ? "#21A366" : "#107C41"

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: "#FFFFFF"
            strokeWidth: 2.4
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            scale: Qt.size(logo.size / 28, logo.size / 28)
            PathSvg { path: "M6 19l5-5 4 3 7-8 M17 9h5v5" }
        }
    }
}
