"""Bounded single-worker sliding windows, as specified by Feature 007."""
from collections import deque
import time


class SlidingWindowRateLimiter:
    def __init__(self, clock=time.monotonic, max_keys=10000):
        self.clock, self.max_keys = clock, max_keys
        self._windows, self._warnings = {}, {}

    def check(self, key, limit):
        now = self.clock()
        for old_key, values in list(self._windows.items()):
            if not values or values[-1] <= now - 60:
                self._windows.pop(old_key, None)
                self._warnings.pop(old_key, None)
        if key not in self._windows:
            if len(self._windows) >= self.max_keys:
                return False, False
            self._windows[key] = deque()
        values = self._windows[key]
        while values and values[0] <= now - 60:
            values.popleft()
        if len(values) >= limit:
            warn = self._warnings.get(key, -float("inf")) <= now - 60
            if warn:
                self._warnings[key] = now
            return False, warn
        values.append(now)
        return True, False
