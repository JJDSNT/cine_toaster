"""The suite, whole or in part, by one rule: a test marked `heavy` needs what is costly to run -- Blender, a
model's inference, a long render -- and nothing else is left out.

    python tests/run.py            every test (what `make test` runs: the final authority)
    python tests/run.py fast       every test not marked heavy (`make test-fast`)
    python tests/run.py heavy      only the tests marked heavy (`make test-heavy`)
    python tests/run.py --times    every test, then the slowest classes, to see what deserves the mark

`fast` is not a lighter check: contracts, invalidation, composition and compatibility all run in it, on
synthetic or recorded data. Only the cost of making the data again is left to `heavy`.
"""

from __future__ import annotations

import sys
import time
import unittest
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from heavy import is_heavy  # noqa: E402


def _flatten(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


class _Timed(unittest.TextTestResult):
    times: dict[str, float] = defaultdict(float)

    last = None

    def startTest(self, test):  # noqa: N802 -- unittest's name
        now = time.monotonic()
        # The time since the last test ended went to this class's setUpClass (a render, a model's run).
        if _Timed.last is not None:
            self.times[f"{type(test).__module__}.{type(test).__name__}"] += now - _Timed.last
        self._started = now
        super().startTest(test)

    def stopTest(self, test):  # noqa: N802
        super().stopTest(test)
        _Timed.last = time.monotonic()
        self.times[f"{type(test).__module__}.{type(test).__name__}"] += _Timed.last - self._started


def main(argv: list[str]) -> int:
    mode = next((arg for arg in argv if arg in ("fast", "heavy")), "all")
    loaded = unittest.defaultTestLoader.discover(str(HERE), top_level_dir=str(HERE))
    chosen = [test for test in _flatten(loaded)
              if mode == "all" or (is_heavy(test) == (mode == "heavy"))]
    runner = unittest.TextTestRunner(verbosity=1, resultclass=_Timed if "--times" in argv else unittest.TextTestResult)
    print(f"{mode}: {len(chosen)} tests", file=sys.stderr)
    result = runner.run(unittest.TestSuite(chosen))
    if "--times" in argv:
        for name, seconds in sorted(_Timed.times.items(), key=lambda item: -item[1])[:40]:
            print(f"{seconds:8.1f} s  {name}{'  [heavy]' if name in _heavy_names(chosen) else ''}", file=sys.stderr)
    return 0 if result.wasSuccessful() else 1


def _heavy_names(tests) -> set[str]:
    return {f"{type(test).__module__}.{type(test).__name__}" for test in tests if is_heavy(test)}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
