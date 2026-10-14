+++
id = "a-composite-is-a-checked-graph"
title = "A shot's composite is a typed graph, checked before anything renders"
domain = "compositing"
status = "convention"
enforced_by = ["composite_cycle", "composite_input_missing", "composite_param_missing", "composite_type_mismatch", "composite_unknown_op", "composite_unknown_param", "layers_and_composite", "layers_invalid"]
evidence = ["SPEC-0012", "ADR 0022"]
+++

A shot whose picture is more than its take -- a window replaced, a person
keyed over a plate, a picture flown over another -- says how in its
breakdown, as a graph of operations: sources, signals, mattes, warps, merges.
Every edge carries a typed value, and a graph that connects a signal where a
matte belongs, asks for an operation nobody declares, leaves a port empty or
names a take the shot does not have is refused when the scene loads, not
discovered halfway through a render.

A shot may be written as **layers** instead -- each a source placed over the
ones below, with what of it is seen, how it meets them, a border and a
shadow, any of it moving over time. The layers become the same graph and are
checked the same way; a shot gives layers or a graph, not both.

The graph is a record of the production, like a take's selection: it can be
read, compared between versions, and changed by a person or an agent through
the same files.
