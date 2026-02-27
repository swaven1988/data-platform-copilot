from collections import defaultdict
from threading import Lock

class MetricsRegistry:
    def __init__(self):
        self._lock = Lock()
        self._counters = defaultdict(int)

    def increment(self, key: str):
        with self._lock:
            self._counters[key] += 1

    def snapshot(self):
        with self._lock:
            return dict(self._counters)

metrics_registry = MetricsRegistry()