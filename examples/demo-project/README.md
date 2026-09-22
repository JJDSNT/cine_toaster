# The Last Signal

A small demo production. Every file here is read directly by Cine Toaster;
nothing is generated or imported.

Scene SC-030 has three shots with real take files under `work/`, a measured
geography, and a declared line of action, so `toast check` and the comparison
room both have something true to work with.

```bash
toast serve .
toast check .
toast shots . --scene SC-030
```

## Production-specific tooling

This production intentionally has no executable local extension. That is a
valid project shape: a film does not need a counterpart for every tool another
film has.

If Echo Chamber used a shared grading or focus operation, the cold receiver
palette and the exact focus timing would remain explicit inputs owned here by
The Last Signal. They would not become Cine Toaster defaults merely because the
application supplied the LUT or focus mechanism.

This is the parameterized-mechanism side of the boundary described in
[`docs/production-tooling.md`](../../docs/production-tooling.md).
