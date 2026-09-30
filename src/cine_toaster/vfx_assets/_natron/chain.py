"""Runs inside NatronRenderer: a chain of OpenFX plugins over a PNG sequence (CT-0047).

    CINE_TOASTER_OFX_SPEC=spec.json NatronRenderer -w Out 1-<frames> chain.py

The spec gives the input and output sequences (`####` for the frame
number) and the plugins in order, each with its OFX id and the parameter
values to set (by the plugin's own parameter names; others are ignored).
The writer is named `Out`; NatronRenderer renders it over the given range.
"""

import json
import os

spec = json.loads(open(os.environ["CINE_TOASTER_OFX_SPEC"], encoding="utf-8").read())
app = app1  # noqa: F821 - NatronRenderer's instance

# The project's format is the picture's: headless, a writer falls back to it, not to its input.
width, height = int(spec["width"]), int(spec["height"])
app.addFormat("CineToaster %dx%d 1" % (width, height))  # name, WxH, pixel aspect
formats = app.getProjectParam("outputFormat")
options = [formats.getOption(index) for index in range(formats.getNumOptions())]
formats.setValue(next(index for index, name in enumerate(options) if name.startswith("CineToaster")))
reader = app.createReader(spec["input"])
for name, value in (("firstFrame", 1), ("lastFrame", int(spec["frames"]))):
    param = reader.getParam(name)
    if param is not None:
        param.setValue(value)
last = reader
for step in spec["effects"]:
    node = app.createNode(step["plugin"])
    if node is None:
        raise SystemExit("Natron has no OpenFX plugin %r" % step["plugin"])
    node.connectInput(0, last)
    for name, value in (step.get("params") or {}).items():
        param = node.getParam(name)
        if param is None:
            continue  # the item's own parameters (strength, x...) are not the plugin's
        if isinstance(value, (list, tuple)):
            # A 2D or 3D parameter: set() takes every dimension; setValue(v, d) takes one.
            param.set(*[float(item) for item in value])
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            param.setValue(value)
        else:
            try:
                param.setValue(value)
            except TypeError:
                param.setValue(float(value))
    last = node

writer = app.createWriter(spec["output"])
writer.setScriptName("Out")
writer.connectInput(0, last)
