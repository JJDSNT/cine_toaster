"""The suite, whole or in part, by one rule: a test marked `heavy` needs what is costly to run -- Blender, a
model's inference, a long render -- and nothing else is left out.

    python tests/run.py            every test (what `make test` runs: the final authority)
    python tests/run.py fast       every test not marked heavy (`make test-fast`)
    python tests/run.py heavy      only the tests marked heavy (`make test-heavy`)
    python tests/run.py --times    every test, then the slowest modules, to see what deserves the mark
    python tests/run.py -j 1       one process, as before (and with --times, the slowest classes)

By default the modules run in parallel, one fresh process each -- as isolated as a module run alone -- as many at
once as the machine has cores, the slowest first (their last times are kept in a disposable cache). The
summary is unittest's, so `OK` or `FAILED` ends it either way.

`fast` is not a lighter check: contracts, invalidation, composition and compatibility all run in it, on
synthetic or recorded data. Only the cost of making the data again is left to `heavy`.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import unittest
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
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


TIMES = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "cine-toaster" / "test-times.json"


def _module(task: tuple[str, str, int]) -> dict:
    """One module's chosen tests, run in this (fresh) process; what came of them."""

    name, mode, threads = task
    # Each module's numerical libraries get their share of the cores, not all of them each: eight modules each
    # spreading over eight cores were four times slower than alone (CT-0096). Set before they are imported.
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(variable, str(threads))
    sys.path.insert(0, str(HERE))
    started = time.monotonic()
    stream = io.StringIO()
    try:
        loaded = unittest.defaultTestLoader.loadTestsFromName(name)
        chosen = [test for test in _flatten(loaded) if mode == "all" or (is_heavy(test) == (mode == "heavy"))]
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(unittest.TestSuite(chosen))
        failures = [(str(test), text) for test, text in result.failures + result.errors]
        return {"module": name, "ran": result.testsRun, "failures": len(result.failures),
                "errors": len(result.errors), "skipped": len(result.skipped), "details": failures,
                "seconds": time.monotonic() - started}
    except Exception as error:  # a module that cannot even load is an error of the run, said
        return {"module": name, "ran": 0, "failures": 0, "errors": 1, "skipped": 0,
                "details": [(name, f"{type(error).__name__}: {error}")], "seconds": time.monotonic() - started}


#: A module that took longer than this last time is run class by class, so one long module is not the whole run.
SPLIT_SECONDS = 60.0


def _classes(module: str) -> list[str]:
    import ast

    tree = ast.parse((HERE / f"{module}.py").read_text(encoding="utf-8"))
    return [f"{module}.{node.name}" for node in tree.body
            if isinstance(node, ast.ClassDef) and any(isinstance(base, ast.Attribute) and base.attr == "TestCase"
                                                      or isinstance(base, ast.Name) and base.id.endswith("Case")
                                                      for base in node.bases)]


def parallel(mode: str, jobs: int, timed: bool) -> int:
    try:
        last = json.loads(TIMES.read_text())
    except (OSError, ValueError):
        last = {}
    modules = []
    for name in sorted(path.stem for path in HERE.glob("test_*.py")):
        classes = _classes(name) if float(last.get(name, 0.0)) > SPLIT_SECONDS else []
        modules += classes if len(classes) > 1 else [name]
    modules.sort(key=lambda name: -float(last.get(name, 1e9)))  # the unknown and the slowest first
    started = time.monotonic()
    totals = {"ran": 0, "failures": 0, "errors": 0, "skipped": 0}
    details, seconds = [], {}
    print(f"{mode}: {len(modules)} modules, {jobs} at once", file=sys.stderr)
    with ProcessPoolExecutor(max_workers=jobs, mp_context=get_context("spawn"), max_tasks_per_child=1) as pool:
        threads = max(1, (os.cpu_count() or 1) // jobs)
        for done in as_completed(pool.submit(_module, (name, mode, threads)) for name in modules):
            outcome = done.result()
            for key in totals:
                totals[key] += outcome[key]
            details += outcome["details"]
            seconds[outcome["module"]] = outcome["seconds"]
            mark = "ok" if not outcome["failures"] and not outcome["errors"] else "FAIL"
            print(f"{mark:4} {outcome['module']:40} {outcome['ran']:4} tests {outcome['seconds']:7.1f} s",
                  file=sys.stderr)
    # A module's time is kept whole too (its classes summed), so it is split again next time.
    whole = defaultdict(float)
    for name, value in seconds.items():
        whole[name.split(".")[0]] += value
    try:
        TIMES.parent.mkdir(parents=True, exist_ok=True)
        TIMES.write_text(json.dumps({**last, **{name: round(value, 1) for name, value in {**whole, **seconds}.items()}}))
    except OSError:
        pass
    for test, text in details:
        print("=" * 70, f"FAIL: {test}", "-" * 70, text, sep="\n", file=sys.stderr)
    if timed:
        for name, value in sorted(seconds.items(), key=lambda item: -item[1])[:25]:
            print(f"{value:8.1f} s  {name}", file=sys.stderr)
    print("-" * 70, f"Ran {totals['ran']} tests in {time.monotonic() - started:.3f}s", "", sep="\n", file=sys.stderr)
    if totals["failures"] or totals["errors"]:
        print(f"FAILED (failures={totals['failures']}, errors={totals['errors']})", file=sys.stderr)
        return 1
    print("OK" + (f" (skipped={totals['skipped']})" if totals["skipped"] else ""), file=sys.stderr)
    return 0


def main(argv: list[str]) -> int:
    mode = next((arg for arg in argv if arg in ("fast", "heavy")), "all")
    jobs = os.cpu_count() or 1
    for index, arg in enumerate(argv):
        if arg in ("-j", "--jobs") and index + 1 < len(argv):
            jobs = max(1, int(argv[index + 1]))
    if jobs > 1:
        return parallel(mode, jobs, "--times" in argv)
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
