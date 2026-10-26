import numpy as np
import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableView


class PandasModel(QAbstractTableModel):
    """Read-only (optionally editable per column) view of a DataFrame."""

    def __init__(self, df=None, editableColumns=(), parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()
        self.editableColumns = set(editableColumns)

    def setDataFrame(self, df):
        self.beginResetModel()
        self._df = df if df is not None else pd.DataFrame()
        self.endResetModel()

    def dataFrame(self):
        return self._df

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self._df.iat[index.row(), index.column()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if isinstance(value, (float, np.floating)):
                return "" if np.isnan(value) else f"{value:.6g}"
            return str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and isinstance(value, (int, float, np.number)):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole:
            return False
        try:
            value = float(value) if str(value).strip() != "" else np.nan
        except ValueError:
            return False
        self._df.iat[index.row(), index.column()] = value
        self.dataChanged.emit(index, index)
        return True

    def flags(self, index):
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._df.columns[index.column()] in self.editableColumns:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return str(section)


def makeTableView(model):
    view = QTableView()
    view.setModel(model)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    view.verticalHeader().setDefaultSectionSize(20)
    return view
