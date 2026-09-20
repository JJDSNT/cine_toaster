# The Last Signal

A small demo production. Every file here is read directly by Cine Toaster;
nothing is generated or imported.

Scene SC-030 has three shots with real take files under `trabalho/`, a measured
geography, and a declared line of action, so `toast check` and the comparison
room both have something true to work with.

```bash
toast serve .
toast check .
toast shots . --scene SC-030
```
