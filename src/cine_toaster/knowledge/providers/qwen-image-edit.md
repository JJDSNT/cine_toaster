+++
id = "qwen-image-edit"
title = "Qwen Image Edit (RunPod serverless)"
kind = "image-edit"
version = "endpoint qwen-image-edit, image wlsdml1114-qwen-image-edit, 2026"
measured_with = "SINGULAR master pictures, 19–29 Sep 2026 (ferramentas/cena.py, singular/docs/SINGULAR-PROXIMOS-PASSOS.md)"

[[claims]]
id = "recomposes-without-geometry-clauses"
claim = "Asked to turn a 3D render into a photograph, the editor recomposes the frame unless told that image 1 alone decides geometry, to repaint surfaces only, and to self-check for double edges; the bellows moved in the first 1-02A batch without them."
status = "measured"
measured_on = "2026-09-20"
evidence = ["singular 1-02A/ltx/teste-controle (edge scores 20.3–20.6 with the clauses)"]
impact = "high"
workaround = "providers/qwen_edit.py always adds GEOMETRY, IDENTITY and SELF_CHECK."

[[claims]]
id = "majority-aspect"
claim = "The output follows the proportion of most input images: two square cast sheets against one 16:9 render made it recompose."
status = "measured"
measured_on = "2026-09-20"
evidence = ["SINGULAR 1-02A: the bellows ended up on Claire's side"]
impact = "high"
workaround = "References are padded with neutral grey to the frame's proportion."

[[claims]]
id = "size-follows-source"
claim = "Asking for a size in another proportion than the source (1344×768 from a 704×384 render) was enough to make it recompose."
status = "measured"
measured_on = "2026-09-20"
evidence = ["ferramentas/cena.py medida_como"]
impact = "medium"
workaround = "The size is the source's proportion, in multiples of 32, 1024–1408 wide."

[[claims]]
id = "one-edit-loses-small-details"
claim = "Asking for the set and the people in one edit loses small details: Claire's nasal cannula vanished."
status = "measured"
measured_on = "2026-09-19"
evidence = ["singular 1-02A decupagem: IMAGENS-MESTRE EM DUAS ETAPAS"]
impact = "medium"
workaround = "Two stages: the empty room from the render first, approved once; the people painted into that plate."

[[claims]]
id = "hair-redrawn-as-scribble"
claim = "Allowed to redraw hair in a face edit, it draws it as a scribble."
status = "measured"
measured_on = "2026-09-21"
evidence = ["SINGULAR 3-01 first face test"]
impact = "medium"
workaround = "A face edit names only the facial features and keeps the hair pixel for pixel."

[[claims]]
id = "edge-score-misses-a-moved-subject"
claim = "The edge score (PSNR of edges against the source) catches a recomposed frame but not a subject that moved: on 1-02A mA both SINGULAR's approved picture (22.2) and a new edit (21.0) moved Claire's head from the render's left towards the centre or right."
status = "measured"
measured_on = "2026-09-29"
evidence = ["singular copy, cenas/1-02A/ltx/trabalho/pmA-1.png against blockout/A-final.png"]
impact = "high"
workaround = "A master picture is approved by a person before it is animated (plan step 10)."

[[claims]]
id = "cheap-when-warm"
claim = "A warm 1280×704 edit ran 33 s after 21 s in the queue: about US$ 0.02."
status = "measured"
measured_on = "2026-09-29"
evidence = ["pmA-1.png.job.json"]
impact = "low"
+++

Master pictures are made in SINGULAR by repainting a render of the 3D set
with the cast's faces, not by generating a picture from words: the render
decides where everything is, the sheets decide who. These are the editor's
habits that method depends on.
