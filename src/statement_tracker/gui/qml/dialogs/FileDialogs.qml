import QtQuick
import QtQuick.Dialogs

// The system's own file dialogs (native on Windows and macOS), for opening and for saving a file.
Item {
    function openFile(data) {
        openDialog.title = data.title
        openDialog.nameFilters = data.nameFilters
        openDialog.currentFolder = data.folder
        openDialog.open()
    }
    function saveFile(data) {
        saveDialog.title = data.title
        saveDialog.nameFilters = data.nameFilters
        saveDialog.currentFolder = data.folder
        saveDialog.selectedFile = data.file
        saveDialog.open()
    }

    FileDialog {
        id: openDialog
        fileMode: FileDialog.OpenFile
        onAccepted: dialogs.answer({ "file": selectedFile.toString() })
        onRejected: dialogs.cancel()
    }
    FileDialog {
        id: saveDialog
        fileMode: FileDialog.SaveFile
        onAccepted: dialogs.answer({ "file": selectedFile.toString() })
        onRejected: dialogs.cancel()
    }
}
