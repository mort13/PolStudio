"""Background execution of long pipeline calls and capture of the pipeline's print() output."""
import sys
import threading
import traceback

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal


class TaskSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


class Task(QRunnable):
    """Run ``fn(*args, **kwargs)`` in the thread pool; result/exception arrive as signals."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = TaskSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # reported in the GUI, never raised into Qt
            traceback.print_exc()
            self.signals.error.emit(f"{type(e).__name__}: {e}")
        else:
            self.signals.finished.emit(result)


class LogStream(QObject):
    """Replacement for sys.stdout/stderr that forwards text to the log dock (thread safe via signal)."""
    text = pyqtSignal(str)

    def __init__(self, original):
        super().__init__()
        self.original = original
        self._lock = threading.Lock()

    def write(self, s):
        with self._lock:
            if self.original is not None:
                try:
                    self.original.write(s)
                except Exception:
                    pass
            if s:
                self.text.emit(s)

    def flush(self):
        if self.original is not None:
            try:
                self.original.flush()
            except Exception:
                pass

    def isatty(self):
        return False


def installLogStreams():
    out, err = LogStream(sys.stdout), LogStream(sys.stderr)
    sys.stdout, sys.stderr = out, err
    return out, err
