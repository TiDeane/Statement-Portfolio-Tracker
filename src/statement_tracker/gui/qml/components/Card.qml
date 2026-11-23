import QtQuick
import QtQuick.Layouts

// A white (or, in dark mode, raised) area with rounded corners, holding a column of content.
Rectangle {
    id: card
    default property alias content: column.data
    property int padding: 24
    property int spacing: 16

    radius: 12
    color: Theme.surface
    border.color: Theme.border
    border.width: 1
    implicitWidth: column.implicitWidth + 2 * padding
    implicitHeight: column.implicitHeight + 2 * padding

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: card.padding
        spacing: card.spacing
    }
}
