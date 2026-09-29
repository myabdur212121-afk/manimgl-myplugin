# manimgl_myplugin

Helpers for [ManimGL](https://github.com/3b1b/manim) — the pieces I kept
rewriting, packaged once and documented properly.

```python
from manimlib import *
from manimgl_myplugin import OBJMobject

class Demo(ThreeDScene):
    def construct(self):
        self.camera.frame.reorient(0, 70, 0)
        self.add(OBJMobject("chair.obj", height=4))
        self.wait(2)
```

---

## Why

ManimGL is very good at what it was built for — equations, graphs, shapes
that move with intent. It is deliberately thin everywhere else. Bringing in
a real 3D model, a mesh from a scanner, a dataset with its own geometry:
each of those is a few hundred lines of plumbing before anything appears on
screen, and the plumbing is the same every time.

This is where that plumbing lives. Each helper is a subpackage, self
contained, with its own reference, its own notes and its own tests.

**Goal:** make ManimGL usable for explaining things that already exist in
three dimensions — buildings, terrain, scans, planets — without every
project starting from the same blank file.

**Not the goal:** photorealism or simulation. See
[what this cannot do](#what-this-cannot-do).

---

## Helpers

| helper | what it gives you | status | docs |
| --- | --- | --- | --- |
| **`obj`** | Wavefront `.obj` models as native mobjects — loading, axis conversion, materials, per-pixel texturing, decimate / subdivide / displace, wireframes, point clouds, build-up animation | working, 21 tests | [reference](docs/obj/reference.md) · [notes](docs/obj/notes.md) · [guide (বাংলা)](docs/obj/guide_bn.md) |

Nothing else is written yet. [`docs/adding-a-helper.md`](docs/adding-a-helper.md)
is the shape the next one should take.

```python
import manimgl_myplugin as P
P.helpers()        # {'obj': (...the names it exports...)}
```

---

## Install

```bash
git clone https://github.com/myabdur212121-afk/manimgl-myplugin.git
cd manimgl-myplugin
pip install -e .
pip install git+https://github.com/3b1b/manim.git     # ManimGL itself
```

**ManimGL only — not Manim Community Edition.** The mobject side subclasses
ManimGL's `Surface` and writes its wgsl shader buffers directly; CE's
renderer is a different thing, so a port would mean a second backend rather
than a patch.

The mesh side has no such tie. `loader.py` imports only numpy, scipy,
trimesh and Pillow, and the package imports it lazily, so this works with
no manim installed at all:

```python
from manimgl_myplugin import load_mesh
mesh = load_mesh("earth.obj").subdivide(2).decimate(20_000)
```

---

## Layout

```
manimgl_myplugin/
├── __init__.py            re-exports every helper's public names
└── obj/                   helper: Wavefront .obj
    ├── loader.py          mesh reading, repair, reshaping — no manim
    └── mobject.py         OBJMobject, OBJTextured, BuildMesh

docs/
├── adding-a-helper.md     the shape a new helper should take
└── obj/
    ├── reference.md       every parameter and method of the obj helper
    ├── notes.md           bugs hit, causes, dead ends, expected numbers
    └── guide_bn.md        the long guide, in Bengali

examples/                  runnable scenes, one folder per helper
tests/                     python tests/test_obj.py  →  21 checks, ~9 s
```

---

## Running the tests

```bash
python tests/test_obj.py        # ~9 seconds
```

Every check corresponds to something that was once broken, so a failure
points at a specific entry in that helper's `notes.md`. Worth running
before a long render — the big example scene takes thirteen minutes.

---

## What this cannot do

Limits of the renderer, not missing features:

- **No shadows.** One light, diffuse plus specular. Nothing casts a shadow.
- **One light source**, no HDRI, no ambient occlusion, no global illumination.
- **No PBR**, no normal or specular maps.
- **No physics, no rigging** — no rigid bodies, cloth, fluids or characters.

**This is a 3D illustration toolkit, not a renderer.** It exists to explain
things with models — exploded views, labelled parts, cutaways, build-up
animations. For photoreal images or simulation, model in Blender, export
`.obj` or `.glb`, and bring the result here for the explanatory part.

Each helper's `notes.md` lists its own limits in detail.

---

## Contributing a helper

Read [`docs/adding-a-helper.md`](docs/adding-a-helper.md). In short: a
subpackage under `manimgl_myplugin/`, a row in the table above, a
`reference.md` and a `notes.md` under `docs/<helper>/`, examples under
`examples/<helper>/`, and tests that would have caught the bugs you hit.

## Licence

MIT.
