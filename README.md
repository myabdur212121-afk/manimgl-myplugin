# manim_obj

Load Wavefront `.obj` models and use them as native **ManimGL** mobjects.

```python
from manimlib import *
from manim_obj import OBJMobject

class Demo(ThreeDScene):
    def construct(self):
        self.camera.frame.reorient(0, 70, 0)
        self.add(OBJMobject("chair.obj", height=4))
        self.wait(2)
```

That is the whole setup. No conversion step, no axis wrangling, no material
file to hand-edit.

---

## Install

```bash
git clone https://github.com/<you>/manim-obj.git
cd manim-obj
pip install -e .
```

Requires **ManimGL 1.7.2** (see *Not ManimCE* below), `numpy`, `scipy`,
`trimesh`, `Pillow`, and `fast-simplification` for `decimate()`.

---

## Not ManimCE — ManimGL only

This is a ManimGL extension and will not work with Manim Community Edition.
`OBJMobject` subclasses ManimGL's `Surface` and leans on things that only
exist there:

| what it uses | why |
| --- | --- |
| `Surface` with `resolution=(0, 0)` | tells the wgsl shader the points are a plain triangle list, not a parametric grid |
| `TexturedSurface` + `textured_surface.wgsl` | real per-pixel texture lookup |
| `self.data.being_written()` | writing per-vertex colour data |
| `self.camera.light_source` | the moving light |

ManimCE's renderer is a different thing entirely, so a port would mean a
second backend rather than a patch.

**But half of it is renderer-agnostic.** `loader.py` (876 of 2,308 lines)
imports only numpy, scipy, trimesh and Pillow — no manim at all. Everything
about reading, repairing and reshaping a mesh lives there and could be
reused by any renderer:

```python
from manim_obj.loader import load_mesh
mesh = load_mesh("earth.obj").subdivide(2).displace("bump.jpg").decimate(20000)
```

---

## What it does

### Loading

```python
OBJMobject("building.obj")                      # from ~/models
OBJMobject("/path/to/model.obj")
OBJMobject("https://example.com/teapot.obj")    # downloaded once, cached
OBJMobject(mesh)                                # a MeshData you already have
OBJMobject("v 0 0 0\nv 1 0 0\n...")             # raw OBJ text
```

`.stl`, `.ply` and `.glb` load too, through trimesh.

| parameter | what it is for |
| --- | --- |
| `height` / `width` / `depth` / `scale` | size in manim units — **`height` is the z extent** |
| `up_axis` | `"y"` (OBJ convention, default), `"z"` (most CAD exports), `"x"`, `"auto"`, `None` |
| `dedupe` | drop coincident duplicate faces — on by default, see below |
| `decimate` | fewer triangles, same shape |
| `subdivide` / `smooth_subdivide` | more triangles, and genuinely rounder |
| `displace` / `displace_strength` | a height map becomes real geometry |
| `color`, `color_by`, `palette`, `gradient`, `use_mtl` | colour |
| `smooth`, `shading`, `flip_faces`, `depth_test` | shading |
| `face_filter`, `vertex_func` | arbitrary culling and deformation |

### Colour

```python
model.set_color_by("material")          # one palette colour per material
model.set_color_by("group")             # ...or per group / object
model.set_color_by("z", gradient=[...]) # a gradient up any axis
model.set_color_by("normal")            # colour from facing direction
model.set_color_by("mtl")               # Kd / d from the .mtl
model.set_color_by(lambda c, n, i: ...) # your own function per triangle
model.set_part_color("glass", "#8FE8FF", opacity=0.75)
model.set_face_colors(rgb_array)        # an (F, 3) numpy array
model.legend()                          # a colour key that cannot drift out of step
```

### Texture

```python
earth = OBJMobject("earth.obj", height=4).textured()
```

`.textured()` reads `map_Kd` from the .mtl, finds the image next to the
.obj, and hands it to the GPU for a real per-pixel lookup. If the .mtl also
names `map_Ke` it is used as the dark-side texture, so a globe lights up
with city lights at night.

`set_texture_colors()` is the cheaper fallback: it samples the image per
vertex and lets the GPU interpolate. Softer, no extra draw cost.

### Reshaping

```python
mesh.decimate(1500)                 # or decimate(0.25) to keep a quarter
mesh.subdivide(2, smooth=True)      # Loop subdivision — the outline rounds too
mesh.displace("bump.jpg", strength=0.04)
mesh.slice("z", low=0, high=2)
mesh.select_named("wall*")
model.split_by("group")             # an OBJGroup you can explode
model.filter_faces(lambda c, n, i: c[2] > 0)
```

### Other mobjects out of the same model

```python
model.wireframe(feature_angle=30)   # one VMobject, crease edges only
model.point_cloud(6000)             # a DotCloud sampled over the surface
model.bounding_box_mobject()
```

### Animation

```python
self.play(BuildMesh(model, order="radial", spread=0.8, run_time=4))
```

Assembles the model out of its own triangles. `order` can be an axis,
`"radial"`, `"random"`, or an array you supply.

---

## Fixing files that are wrong

Real exports are messy. Three problems came up often enough to handle
automatically.

### Coincident duplicate faces (z-fighting)

CAD exporters routinely write the same wall twice on two layers, at exactly
the same coordinates. Both get drawn, the depth test cannot choose, and the
wall comes out speckled with two colours fighting pixel by pixel.

In the Engel House test model, **7,086 of 15,024 triangles (47%)** were
duplicates. `dedupe="auto"` removes them:

- different materials → the rarer, more specific one survives
- same material → the larger face survives, and between equals the one
  facing outwards, so the wall keeps its lit side

Detection is a geometric coplanar-overlap test (plane bucket → per-plane 2D
grid → four sample points per triangle), about one second on 15k faces.
A vertex weld does **not** work: the twins are usually triangulated along
opposite diagonals, so the triangles never match exactly.

### Backslash line continuations

Some exporters wrap long `f` lines with `\`. Splitting on newlines silently
drops faces — 11,346 instead of 15,024 in our case. The parser joins
logical lines first.

### Axis conventions

`.obj` says Y is up; Rhino, Revit and SketchUp export Z-up. `up_axis="auto"`
guesses from the smallest extent, which is right for buildings and terrain.

---

## Tested on

Eight models, four exporters, none edited by hand:

| model | source | triangles | exporter |
| --- | --- | --- | --- |
| `building.obj` | ladybug-tools/3d-models | 15,024 → 7,938 | Rhino, Z-up |
| `earth.obj` | AudranDoublet/opr | 3,968 | 3ds Max, + texture |
| `chair.obj` | cnr-isti-vclab/meshlab | 6,893 → 6,716 | LightWave, no `vt`/`vn` |
| `mountain.obj` | ZeusYang/TinySoftRenderer | 6,962 | Y-up terrain |
| `terrain.obj` | ericstoneking/42 | 3,042 | Z-up terrain |
| `armchair.obj` | code-iai/iai_maps | 2,832 | collision mesh |
| `house.obj` | RobLoach/node-raylib | 1,792 | — |
| `tree_a` / `tree_b` / `palm` | various | 876 / 760 / 1,246 | — |

Also exercised: 5-sided n-gons, negative face indices (`f -3 -2 -1`), and
`.stl` / `.ply` / `.glb` through the trimesh path.

---

## What does **not** work

Being clear about this matters more than the feature list.

### Limits inherited from ManimGL

| | |
| --- | --- |
| **No shadows** | the shader does diffuse + specular from one light. Nothing casts a shadow on anything. |
| **One light source** | `self.camera.light_source` is a single `Point`. No area lights, no HDRI, no ambient occlusion, no global illumination. |
| **No PBR** | `shading=(reflectiveness, gloss, shadow)` is a toy model. No roughness/metalness workflow. |
| **No normal or specular maps** | only a diffuse texture and an optional dark one. `displace()` fakes relief with real geometry instead. |
| **Flat shading with `textured()`** | the textured shader takes colour from the image, so `shade_smooth()` has nothing to bake into. Pass `shading=(0,0,0)` for even lighting. |
| **No transparency sorting** | overlapping translucent surfaces can draw in the wrong order. |

### Limits of this library

- `decimate()` **damages UVs and material boundaries.** Attributes are
  transferred from the nearest original vertex/face, which is an
  approximation — a texture will slide slightly.
- `subdivide(smooth=True)` **rounds off sharp corners.** Right for a sphere
  or a scanned figure, wrong for architecture. Use `smooth=False` there.
- `displace()` needs vertices to move, so it must follow `subdivide()`.
- **No automated test suite yet.** Everything here was verified by rendering
  and looking, which is how two real bugs survived until a viewer spotted
  them.
- Not published to PyPI.

### Not what this is for at all

No physics, no rigid bodies, cloth, fluids or particle collision. No
rigging or skinning, so no character animation. No ray tracing, no
photorealism.

**This is a 3D *illustration* tool, not a 3D *rendering* tool.** It exists
to explain things with models — exploded views, labelled parts, cutaways,
build-up animations, a real building standing next to the equation that
describes it. For photoreal images or simulation, model in Blender, export
`.obj` or `.glb`, and bring the result here for the explanatory part.

### Performance

Measured in a 2-CPU / 2 GB sandbox with a software GPU:

| scene | resolution | triangles | time | peak memory |
| --- | --- | --- | --- | --- |
| one building | 1280×720 | 7,938 | 2.5 min / 48 s of video | 1,132 MB |
| eight models | 2560×1440 | ~70,000 | 13 min / 90 s of video | **1,804 MB of 1,984** |

QHD was the ceiling on that machine. A real GPU changes the time but not
the feature limits above.

---

## Examples

| file | what it shows |
| --- | --- |
| `examples/01_minimal.py` | four scenes, two lines each |
| `examples/02_building.py` | one building, nine beats |
| `examples/03_earth_chair.py` | two downloaded models, texture, materials |
| `examples/04_resolution.py` | `decimate` / `subdivide` / `displace` side by side |
| `examples/05_landscape.py` | six models, a moving camera and a moving light |
| `examples/06_highland.py` | eight models, QHD, placement on a mountain |

```bash
manimgl examples/01_minimal.py Simplest -w -l -c "#070B14" --video_dir /tmp/out
```

A longer guide, in Bengali, is at `docs/guide_bn.md`.

---

## Licence

MIT.
