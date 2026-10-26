"""Generic form for pipeline keyword arguments: bools as check boxes, everything else as YAML text."""
import yaml
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QFormLayout, QLineEdit, QWidget


def toText(value):
    if value is None:
        return ""
    text = yaml.safe_dump(value, default_flow_style=True).strip()
    return text[:-4].strip() if text.endswith("...") else text


def fromText(text):
    text = text.strip()
    if text == "":
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return text


class ParamForm(QWidget):
    """Edit a flat dict. Empty text means None (the pipeline then uses its default)."""
    changed = pyqtSignal()

    def __init__(self, params=None, tooltips=None, parent=None):
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._editors = {}
        self.tooltips = tooltips or {}
        if params is not None:
            self.setParams(params)

    def setParams(self, params):
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._editors = {}
        for key, value in params.items():
            if isinstance(value, bool):
                editor = QCheckBox()
                editor.setChecked(value)
                editor.toggled.connect(self.changed)
            else:
                editor = QLineEdit(toText(value))
                editor.setPlaceholderText("default")
                editor.editingFinished.connect(self.changed)
            if key in self.tooltips:
                editor.setToolTip(self.tooltips[key])
            self._editors[key] = editor
            self._layout.addRow(key, editor)

    def setValue(self, key, value):
        editor = self._editors[key]
        if isinstance(editor, QCheckBox):
            editor.setChecked(bool(value))
        else:
            editor.setText(toText(value))

    def params(self):
        out = {}
        for key, editor in self._editors.items():
            out[key] = editor.isChecked() if isinstance(editor, QCheckBox) else fromText(editor.text())
        return out
