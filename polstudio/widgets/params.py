"""Generic form for pipeline keyword arguments: bools as check boxes, everything else as YAML text."""
import yaml
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QFormLayout, QHBoxLayout, QLineEdit, QWidget


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


class ToggleEdit(QWidget):
    """Check box plus value: checked -> the typed value, unchecked -> ``off`` (e.g. False or None)."""
    changed = pyqtSignal()

    def __init__(self, value, default, off, parent=None):
        super().__init__(parent)
        self.off = off
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.check = QCheckBox()
        self.edit = QLineEdit()
        layout.addWidget(self.check)
        layout.addWidget(self.edit, stretch=1)
        self.check.toggled.connect(self.edit.setEnabled)
        self.check.toggled.connect(self.changed)
        self.edit.editingFinished.connect(self.changed)
        self.default = default
        self.setValue(value)

    def setValue(self, value):
        enabled = value is not self.off and value is not None and value is not False
        self.check.setChecked(enabled)
        self.edit.setEnabled(enabled)
        # Keep the last typed number visible while switched off
        if enabled or not self.edit.text():
            self.edit.setText(toText(value if enabled else self.default))

    def value(self):
        if not self.check.isChecked():
            return self.off
        value = fromText(self.edit.text())
        return self.default if value is None else value

    def setToolTip(self, text):
        super().setToolTip(text)
        self.check.setToolTip(text)
        self.edit.setToolTip(text)


class ParamForm(QWidget):
    """
    Edit a flat dict. Empty text means None (the pipeline then uses its default).

    toggles : dict key -> (default value, off value) for arguments that are switched off by a
        sentinel (``slopeLength=False``) and take a value when on.
    """
    changed = pyqtSignal()

    def __init__(self, params=None, tooltips=None, toggles=None, parent=None):
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._editors = {}
        self.tooltips = tooltips or {}
        self.toggles = toggles or {}
        if params is not None:
            self.setParams(params)

    def setParams(self, params):
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._editors = {}
        for key, value in params.items():
            if key in self.toggles:
                default, off = self.toggles[key]
                editor = ToggleEdit(value, default, off)
                editor.changed.connect(self.changed)
            elif isinstance(value, bool):
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
        if isinstance(editor, ToggleEdit):
            editor.setValue(value)
        elif isinstance(editor, QCheckBox):
            editor.setChecked(bool(value))
        else:
            editor.setText(toText(value))

    def params(self):
        out = {}
        for key, editor in self._editors.items():
            if isinstance(editor, ToggleEdit):
                out[key] = editor.value()
            elif isinstance(editor, QCheckBox):
                out[key] = editor.isChecked()
            else:
                out[key] = fromText(editor.text())
        return out
