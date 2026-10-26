import argparse
import sys

import matplotlib

# Pipeline plots go to files; the GUI embeds its own matplotlib canvases
matplotlib.use("Agg")

from PyQt6.QtWidgets import QApplication  # noqa: E402
import pyqtgraph as pg  # noqa: E402

from . import DEFAULT_CONFIG  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m polstudio", description="Offline ToF analysis GUI")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="pipeline config.yaml")
    parser.add_argument("--data", help="data folder to scan on start-up")
    parser.add_argument("--session", help="session folder to open on start-up")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("PolStudio")
    pg.setConfigOptions(background="w", foreground="k", antialias=False)

    from .main_window import MainWindow
    from .session import AnalysisSession
    from .workers import installLogStreams

    out, err = installLogStreams()
    window = MainWindow(AnalysisSession(args.config))
    out.text.connect(window.appendLog)
    err.text.connect(window.appendLog)
    window.show()
    if args.session:
        window.openSession(args.session)
    elif args.data:
        window.openFolder(args.data)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
