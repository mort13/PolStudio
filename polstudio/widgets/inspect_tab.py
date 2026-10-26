"""Inspect raw train traces, tune the pulse split and look at the per-pulse GMD energy."""
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
                             QSlider, QSpinBox, QVBoxLayout, QWidget)

from .plot_grid import CYCLE, TOL


class InspectTab(QWidget):
    recutRequested = pyqtSignal()
    trainChanged = pyqtSignal(int)   # trainId

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._trace = None
        self._regions = []

        layout = QHBoxLayout(self)
        side = QVBoxLayout()
        layout.addLayout(side, stretch=0)

        nav = QGroupBox("Train")
        navLayout = QFormLayout(nav)
        self.trainSlider = QSlider(Qt.Orientation.Horizontal)
        self.trainSpin = QSpinBox()
        self.trainSlider.valueChanged.connect(self.trainSpin.setValue)
        self.trainSpin.valueChanged.connect(self.trainSlider.setValue)
        self.trainSpin.valueChanged.connect(self._trainIndexChanged)
        navLayout.addRow("index", self.trainSpin)
        navLayout.addRow(self.trainSlider)
        self.trainLabel = QLabel("–")
        navLayout.addRow("trainId", self.trainLabel)
        self.detectorCombo = QComboBox()
        self.detectorCombo.currentIndexChanged.connect(self.redraw)
        navLayout.addRow("detector", self.detectorCombo)
        side.addWidget(nav)

        split = QGroupBox("Pulse split")
        splitLayout = QFormLayout(split)
        cfg = self.session.loaderConfig
        self.offsetSpin = QDoubleSpinBox(decimals=2, maximum=1e6, singleStep=1.0)
        self.offsetSpin.setValue(float(cfg.get("pulseOffset", 0.0)))
        self.periodSpin = QDoubleSpinBox(decimals=3, maximum=1e6, singleStep=0.1)
        self.periodSpin.setValue(float(cfg.get("pulsePeriod", 1000.0)))
        self.nPulsesSpin = QSpinBox(minimum=1, maximum=1000)
        self.nPulsesSpin.setValue(int(cfg.get("nPulses", 1)))
        self.windowSpin = QSpinBox(minimum=1, maximum=1_000_000)
        self.windowSpin.setValue(int(cfg.get("pulseWindow", 1000)))
        for label, spin in (("first pulse offset", self.offsetSpin), ("period (samples)", self.periodSpin),
                            ("number of pulses", self.nPulsesSpin), ("window (samples)", self.windowSpin)):
            splitLayout.addRow(label, spin)
            spin.valueChanged.connect(self._splitChanged)
        self.startsLabel = QLabel("")
        self.startsLabel.setWordWrap(True)
        self.startsLabel.setTextFormat(Qt.TextFormat.RichText)
        splitLayout.addRow(self.startsLabel)
        self.recutButton = QPushButton("Apply split (re-cut pulses)")
        self.recutButton.setToolTip("Re-cuts all loaded trains with these settings. "
                                    "Preprocessing and peaks have to be redone afterwards.")
        self.recutButton.clicked.connect(self.recutRequested)
        splitLayout.addRow(self.recutButton)
        side.addWidget(split)
        side.addStretch(1)

        self.view = pg.GraphicsLayoutWidget()
        layout.addWidget(self.view, stretch=1)
        self.trainPlot = self.view.addPlot(row=0, col=0, title="Raw train trace (ADC counts)")
        self.trainPlot.setLabel("bottom", "sample")
        self.trainPlot.showGrid(x=True, y=True, alpha=0.3)
        self.overlayPlot = self.view.addPlot(row=1, col=0, title="Pulse windows overlaid (baseline subtracted)")
        self.overlayPlot.setLabel("bottom", "sample within pulse window")
        self.overlayPlot.showGrid(x=True, y=True, alpha=0.3)
        self.overlayPlot.addLegend(offset=(-10, 10))
        self.gmdPlot = self.view.addPlot(row=2, col=0, title="GMD pulse energy")
        self.gmdPlot.setLabel("bottom", "pulseId")
        self.view.ci.layout.setRowStretchFactor(0, 3)
        self.view.ci.layout.setRowStretchFactor(1, 3)
        self.view.ci.layout.setRowStretchFactor(2, 1)
        self._updateStartsLabel()

    # ------------------------------------------------------------------
    def splitSettings(self):
        return {"pulseOffset": self.offsetSpin.value(), "pulsePeriod": self.periodSpin.value(),
                "nPulses": self.nPulsesSpin.value(), "pulseWindow": self.windowSpin.value()}

    def applySettingsToConfig(self):
        self.session.loaderConfig.update(self.splitSettings())

    def onDataLoaded(self):
        tids = self.session.trainIds()
        self.trainSpin.setMaximum(max(len(tids) - 1, 0))
        self.trainSlider.setMaximum(max(len(tids) - 1, 0))
        self.detectorCombo.blockSignals(True)
        current = self.detectorCombo.currentData()
        self.detectorCombo.clear()
        self.detectorCombo.addItem("sum of all", None)
        for det in self.session.loader.trainTraces["detector"].values:
            self.detectorCombo.addItem(f"ToF {det}", int(det))
        idx = self.detectorCombo.findData(current)
        self.detectorCombo.setCurrentIndex(idx if idx >= 0 else 0)
        self.detectorCombo.blockSignals(False)
        self._trainIndexChanged(self.trainSpin.value())

    def currentTrainId(self):
        tids = self.session.trainIds()
        if not len(tids):
            return None
        return int(tids[min(self.trainSpin.value(), len(tids) - 1)])

    def _trainIndexChanged(self, index):
        tid = self.currentTrainId()
        if tid is None:
            return
        self.trainLabel.setText(f"{tid}  (run {self.session.runOfTrain(tid)})")
        self._trace = self.session.trainTrace(tid)
        self.redraw()
        self.trainChanged.emit(tid)

    def _splitChanged(self, *args):
        self._updateStartsLabel()
        self.redraw()

    def _starts(self):
        s = self.splitSettings()
        nSamples = self._trace.sizes["sample"] if self._trace is not None else 16000
        starts = np.round(s["pulseOffset"] + np.arange(s["nPulses"]) * s["pulsePeriod"]).astype(int)
        valid = (starts >= 0) & (starts + s["pulseWindow"] <= nSamples)
        return starts, valid, s["pulseWindow"]

    def _updateStartsLabel(self):
        starts, valid, _ = self._starts()
        text = ", ".join(str(s) if v else f"<s>{s}</s>" for s, v in zip(starts, valid))
        self.startsLabel.setText(f"starts: {text}" + ("" if valid.all() else "<br>struck-out windows do not fit"))

    def redraw(self):
        self.trainPlot.clear()
        self.overlayPlot.clear()
        self.gmdPlot.clear()
        if self._trace is None:
            return
        det = self.detectorCombo.currentData()
        trace = self._trace
        x = trace["sample"].values
        if det is None:
            y = trace.values.astype(float)
            y = (y - np.median(y[:, :200], axis=1, keepdims=True)).sum(axis=0)
        else:
            y = trace.sel(detector=det).values.astype(float)
        self.trainPlot.plot(x, y, pen=pg.mkPen(TOL["blue"], width=1))

        starts, valid, window = self._starts()
        for k, (s, v) in enumerate(zip(starts, valid)):
            color = pg.mkColor(CYCLE[k % len(CYCLE)]) if v else pg.mkColor("#999999")
            color.setAlpha(40)
            region = pg.LinearRegionItem(values=(s, s + window), movable=False, brush=color)
            self.trainPlot.addItem(region)
            label = pg.TextItem(str(k), color=CYCLE[k % len(CYCLE)] if v else "#999999", anchor=(0, 0))
            label.setPos(s, float(np.nanmax(y)))
            self.trainPlot.addItem(label)

        base = np.median(y[:200])
        for k, (s, v) in enumerate(zip(starts, valid)):
            if not v:
                continue
            seg = y[s:s + window] - base
            self.overlayPlot.plot(np.arange(len(seg)), seg, pen=pg.mkPen(CYCLE[k % len(CYCLE)], width=1),
                                  name=f"pulse {k}")

        gmd = self.session.gmdOfTrain(self.currentTrainId())
        if gmd is not None and len(gmd):
            bars = pg.BarGraphItem(x=gmd["pulseId"].values, height=np.nan_to_num(gmd["Pulse Energy"].values),
                                   width=0.7, brush=TOL["green"])
            self.gmdPlot.addItem(bars)
