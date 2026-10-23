"""Fresh GPAS demo session rotation after an uncertain or failed operation.

A failing wager is never retried. Subsequent *different* declared operations
are verified in a new isolated demo so one failure does not hide the rest.
"""
from pathlib import Path


class GPASDemoSessions:
    def __init__(self, factory, code, directory, timeout_s, stop_event):
        self.factory = factory
        self.code = code
        self.directory = Path(directory)
        self.timeout_s = timeout_s
        self.stop_event = stop_event
        self.session = None
        self._context = None
        self.restarts = 0

    def _start(self, directory):
        if self.stop_event.is_set():
            raise InterruptedError("DETENIDO")
        context = self.factory(self.code, Path(directory), self.timeout_s, self.stop_event)
        try:
            session = context.__enter__()
        except BaseException:
            # Implementations clean up bootstrap failures in __enter__.
            self.session = None
            self._context = None
            raise
        self._context = context
        self.session = session
        return session

    def __enter__(self):
        self._start(self.directory)
        return self

    def close(self, exc_type=None, exc=None, tb=None):
        context = self._context
        self._context = None
        self.session = None
        if context is not None:
            return context.__exit__(exc_type, exc, tb)
        return None

    def reopen(self, directory):
        # Always close the poisoned socket/session before starting another.
        self.close()
        self.restarts += 1
        return self._start(directory)

    def __exit__(self, exc_type, exc, tb):
        return self.close(exc_type, exc, tb)
