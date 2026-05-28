"""Log and file history table models for PyQt5."""

from PyQt5.QtCore import QAbstractTableModel, Qt, pyqtSignal, pyqtSlot


class LogModel(QAbstractTableModel):
    """Table model for connection log. Columns: Time, Client IP, Event."""

    _headers = ["时间", "客户端", "事件"]
    MAX_ROWS = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[tuple[str, str, str]] = []

    def rowCount(self, parent=None):
        return len(self._rows)

    def columnCount(self, parent=None):
        return 3

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        return self._rows[index.row()][index.column()]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None

    @pyqtSlot(str, str, str)
    def add_entry(self, time: str, client: str, event: str):
        """Add a log entry. Thread-safe: callable from any thread via signal."""
        idx = len(self._rows)
        self.beginInsertRows(self.index(idx, 0), idx, idx)
        self._rows.append((time, client, event))
        if len(self._rows) > self.MAX_ROWS:
            # Ring buffer: remove oldest
            self.beginRemoveRows(self.index(0, 0), 0, 0)
            del self._rows[0]
            self.endRemoveRows()
        self.endInsertRows()

    def clear(self):
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()


class FileHistoryModel(QAbstractTableModel):
    """Table model for received files. Columns: Filename, Size, Type, Status."""

    _headers = ["文件名", "大小", "类型", "状态"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    def rowCount(self, parent=None):
        return len(self._rows)

    def columnCount(self, parent=None):
        return 4

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        row = self._rows[index.row()]
        return [row["filename"], row["size"], row["type"], row["status"]][index.column()]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None

    @pyqtSlot(str, str, str, str)
    def add_file(self, filename: str, size: str, filetype: str, filepath: str):
        idx = len(self._rows)
        self.beginInsertRows(self.index(idx, 0), idx, idx)
        self._rows.append({
            "filename": filename, "size": size,
            "type": filetype, "status": "等待打印",
            "path": filepath,
        })
        self.endInsertRows()

    @pyqtSlot(str, bool)
    def update_status(self, filename: str, success: bool):
        for i, row in enumerate(self._rows):
            if row["filename"] == filename:
                row["status"] = "打印完成" if success else "打印失败"
                self.dataChanged.emit(
                    self.index(i, 3), self.index(i, 3), [Qt.DisplayRole]
                )
                break

    def clear(self):
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()
