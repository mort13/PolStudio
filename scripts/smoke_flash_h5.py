"""
Headless smoke test of the offline FLASH HDF5 path through ToFPipeline.

    python scripts/smoke_flash_h5.py ../2024_hdf5
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ToFPipeline"))

from ToFPipeline import (GlobalConfig, FlashH5Loader, PeakFinder,  # noqa: E402
                         saveCalibration, loadCalibration)


def main(dataDir):
    GlobalConfig.load(ROOT / "ToFPipeline" / "config.yaml")

    overview = FlashH5Loader.scan(dataDir)
    print(overview[["run", "nTrains", "trainId min", "trainId max", "wavelength"]].to_string(index=False))
    assert len(overview) > 0, "no files found"

    first = overview.iloc[0]
    loader = FlashH5Loader([first["file"]]).load(trainStart=0, trainStop=20)
    nPulses = len(loader.pulseStarts)
    print("pulse starts:", loader.pulseStarts.tolist())
    print("data:", dict(loader.data.sizes))
    assert loader.data.dims == ("detector", "pulse", "sample")
    assert loader.data.sizes["pulse"] == 20 * nPulses
    assert loader.pulseEnergy is not None and len(loader.pulseEnergy) == 20 * nPulses
    print("photon energy:", loader.photonEnergy["Photon Energy"].unique())

    loader.defaultPreprocessing()
    pf = PeakFinder(loader.data.copy(), config={"stackTrains": True, "stackPulses": False})
    pf.smooth(5).stack(trainStackSize=20).process(threshold=0.2, peakNo=0, noiseRegion=[0, 100])
    print(pf.results.head().to_string())
    assert isinstance(pf.results, pd.DataFrame) and len(pf.results) > 0

    energy = pd.DataFrame({"detector": [0, 1], "peakNo": [0, 0], "p0": [1.0, 2.0], "p1": [3.0, np.nan],
                           "p2": [0.1, 0.2], "p3": [0.0, 0.0], "p4": [1.0, 1.0],
                           "pos_min": [10.0, 12.0], "pos_max": [900.0, 950.0]})
    with tempfile.TemporaryDirectory() as tmp:
        path = saveCalibration(Path(tmp) / "calib.json", energyParam=energy, meta={"runs": [int(first["run"])]})
        loaded = loadCalibration(path)
    pd.testing.assert_frame_equal(loaded["energy"], energy, check_dtype=False)
    print("calibration round trip OK")
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "2024_hdf5")
