"""Peak finding on the preprocessed data: parameters, per-detector traces with peaks, results table."""
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
                             QSpinBox, QSplitter, QVBoxLayout, QWidget)

from .pandas_model import PandasModel, makeTableView
from .params import ParamForm
from .plot_grid import TOL, PlotGrid

PEAK_TOOLTIPS = {
    "threshold": "Cut-off in units of the noise amplitude (absolute if noiseRegion is empty)",
    "peakNo": "Highest peak index to find (0 = one peak per trace)",
    "roi": "[start, stop] sample range searched for peaks (drag the blue region)",
    "distanceFactor": "Region around a found peak (in widths) excluded from the next search",
    "widthFraction": "Fraction of the height where the width is measured (0.5 = FWHM)",
    "symmetric": "Use symmetric widths",
    "minWidth": "Minimum width (False = off)",
    "slopeLength": "Samples over which the baseline slope is evaluated (False = no baseline)",
    "maxSlope": "Maximum slope accepted as baseline",
    "noiseRegion": "[start, stop] sample range used for the noise amplitude (drag the red region)",
}


class PeaksTab(QWidget):
    findRequested = pyqtSignal(dict)

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._regions = {"roi": [], "noiseRegion": []}
        self._syncing = False

        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        side = QWidget()
        sideLayout = QVBoxLayout(side)
        params = QGroupBox("PeakFinder.process")
        paramLayout = QVBoxLayout(params)
        self.form = ParamForm(dict(self.session.state["peaks"]), tooltips=PEAK_TOOLTIPS)
        self.form.changed.connect(self._formChanged)
        paramLayout.addWidget(self.form)
        self.findButton = QPushButton("Find peaks")
        self.findButton.clicked.connect(lambda: self.findRequested.emit(self.params()))
        paramLayout.addWidget(self.findButton)
        self.summaryLabel = QLabel("")
        self.summaryLabel.setWordWrap(True)
        paramLayout.addWidget(self.summaryLabel)
        sideLayout.addWidget(params)

        view = QGroupBox("View")
        viewLayout = QFormLayout(view)
        self.pulseSpin = QSpinBox()
        self.pulseSpin.valueChanged.connect(self.redraw)
        viewLayout.addRow("pulse index", self.pulseSpin)
        self.pulseLabel = QLabel("–")
        viewLayout.addRow("trainId / pulseId", self.pulseLabel)
        self.axisCombo = QComboBox()
        self.axisCombo.addItems(["Sample", "Time (ns)", "Energy (eV)"])
        self.axisCombo.currentIndexChanged.connect(self._updateAxes)
        viewLayout.addRow("x axis labels", self.axisCombo)
        self.showRegions = QCheckBox("show ROI / noise regions")
        self.showRegions.setChecked(True)
        self.showRegions.toggled.connect(self.redraw)
        viewLayout.addRow(self.showRegions)
        self.histDetector = QComboBox()
        self.histDetector.currentIndexChanged.connect(self._drawHistogram)
        viewLayout.addRow("histogram detector", self.histDetector)
        sideLayout.addWidget(view)
        sideLayout.addStretch(1)
        splitter.addWidget(side)

        right = QSplitter(Qt.Orientation.Vertical)
        self.grid = PlotGrid()
        right.addWidget(self.grid)
        bottom = QSplitter(Qt.Orientation.Horizontal)
        self.model = PandasModel()
        self.table = makeTableView(self.model)
        bottom.addWidget(self.table)
        self.histPlot = pg.PlotWidget(title="Peak positions")
        self.histPlot.setLabel("bottom", "pos (sample)")
        self.histPlot.addLegend()
        bottom.addWidget(self.histPlot)
        bottom.setSizes([700, 400])
        right.addWidget(bottom)
        right.setSizes([600, 300])
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1000])

    # ------------------------------------------------------------------
    def params(self):
        params = self.form.params()
        self.session.state["peaks"] = params
        return params

    def _formChanged(self):
        self.params()
        self._placeRegions()

    def onProcessedChanged(self):
        data = self.session.processed
        n = data.sizes["pulse"] if data is not None else 0
        self.pulseSpin.setMaximum(max(n - 1, 0))
        if data is not None:
            dets = [int(d) for d in data["detector"].values]
            self.histDetector.blockSignals(True)
            self.histDetector.clear()
            for d in dets:
                self.histDetector.addItem(f"ToF {d}", d)
            self.histDetector.blockSignals(False)
        self.redraw()

    def onResultsChanged(self):
        results = self.session.results
        self.model.setDataFrame(results)
        if results is not None and len(results):
            nPulses = results.groupby(["trainId", "pulseId"]).ngroups
            self.summaryLabel.setText(f"{len(results)} peaks in {nPulses} pulses "
                                      f"({results['detector'].nunique()} detectors)")
        else:
            self.summaryLabel.setText("No peaks found" if results is not None else "")
        self.redraw()
        self._drawHistogram()

    def _range(self, key):
        value = self.session.state["peaks"].get(key)
        data = self.session.processed
        if data is None:
            return None
        samples = data["sample"].values
        if not value or len(value) != 2:
            return None if key == "noiseRegion" else (samples[0], samples[-1])
        lo = samples[0] if value[0] is None else value[0]
        hi = samples[-1] if value[1] is None else value[1]
        return (lo, hi)

    def redraw(self):
        data = self.session.processed
        self.grid.clear()
        if data is None or data.sizes["pulse"] == 0:
            return
        self.grid.setDetectors(data["detector"].values)
        self._updateAxes()
        i = min(self.pulseSpin.value(), data.sizes["pulse"] - 1)
        tid, pid = data["pulse"].to_index()[i]
        self.pulseLabel.setText(f"{tid} / {pid}")
        x = data["sample"].values
        results = self.session.results
        if results is not None and len(results):
            peaks = results[(results["trainId"] == tid) & (results["pulseId"] == pid)]
        else:
            peaks = None
        widthFraction = self.session.state["peaks"].get("widthFraction") or 0.5
        self._regions = {"roi": [], "noiseRegion": []}
        for det, plot in self.grid.plots.items():
            y = data.sel(detector=det).isel(pulse=i).values
            plot.plot(x, y, pen=pg.mkPen(TOL["blue"], width=1))
            if peaks is not None:
                p = peaks[peaks["detector"] == det]
                if len(p):
                    # pos is a positional index into the trace (see PeakFinder.process)
                    plot.plot(x[np.clip(p["pos"].values, 0, len(x) - 1)], p["height"].values, pen=None,
                              symbol="o", symbolSize=7, symbolBrush=TOL["purple"], symbolPen=None)
                    for _, row in p.iterrows():
                        x0 = x[0] + row["pos"] + row["width left"]
                        x1 = x[0] + row["pos"] + row["width right"]
                        h = row["height"] * widthFraction
                        plot.plot([x0, x1], [h, h], pen=pg.mkPen(TOL["purple"], width=2))
                        if np.isfinite(row.get("baseline left", np.nan)) and row.get("baseline left", 0) != 0:
                            bl = int(row["pos"] + row["baseline left"])
                            br = int(row["pos"] + row["baseline right"])
                            if 0 <= bl < len(y) and 0 <= br < len(y):
                                plot.plot([x[bl], x[br]], [y[bl], y[br]],
                                          pen=pg.mkPen(TOL["green"], width=1, style=Qt.PenStyle.DashLine))
            if self.showRegions.isChecked():
                self._addRegions(plot)
        self._placeRegions()

    def _addRegions(self, plot):
        for key, color in (("roi", (68, 119, 170, 30)), ("noiseRegion", (238, 102, 119, 40))):
            region = pg.LinearRegionItem(brush=pg.mkBrush(*color), movable=True)
            region.setZValue(-10)
            region.sigRegionChangeFinished.connect(lambda r, k=key: self._regionMoved(k, r))
            plot.addItem(region)
            self._regions[key].append(region)

    def _placeRegions(self):
        self._syncing = True
        for key, regions in self._regions.items():
            rng = self._range(key)
            for region in regions:
                region.setVisible(rng is not None)
                if rng is not None:
                    region.setRegion(rng)
        self._syncing = False

    def _regionMoved(self, key, region):
        if self._syncing:
            return
        lo, hi = (int(round(v)) for v in region.getRegion())
        self.form.setValue(key, [lo, hi])
        self.params()
        self._placeRegions()

    def _updateAxes(self):
        mode = self.axisCombo.currentIndex()
        if mode == 0:
            self.grid.setAxisMapper(None)
        elif mode == 1:
            rate = self.session.sampleRate
            self.grid.setAxisMapper(lambda det: (lambda s: s / rate * 1e9), "ns", "{:.0f}")
        else:
            self.grid.setAxisMapper(lambda det: (lambda s, d=det: self.session.energyOf(d, s)), "eV", "{:.1f}")

    def _drawHistogram(self):
        self.histPlot.clear()
        results = self.session.results
        det = self.histDetector.currentData()
        if results is None or not len(results) or det is None:
            return
        sel = results[results["detector"] == det]
        colors = [TOL["blue"], TOL["red"], TOL["green"], TOL["yellow"], TOL["cyan"]]
        for k, (peakNo, group) in enumerate(sel.groupby("peakNo")):
            counts, edges = np.histogram(group["pos"].values, bins=max(10, min(200, len(group) // 5)))
            self.histPlot.plot(edges, counts, stepMode="center", fillLevel=0, name=f"peak {peakNo}",
                               pen=pg.mkPen(colors[k % len(colors)]),
                               brush=pg.mkBrush(colors[k % len(colors)] + "55"))
