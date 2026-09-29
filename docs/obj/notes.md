> Part of [manimgl_myplugin](../../README.md).

# The `obj` helper — working notes

Read this before changing anything. It is the short version of everything
that went wrong while building this, what the cause turned out to be, and
which directions are already known to be dead ends.

---

## 1. What this is

A ManimGL extension that loads Wavefront `.obj` models and exposes them as
native mobjects, so a real 3D model can be dropped into an explainer scene:

```python
self.add(OBJMobject("chair.obj", height=4))
```

Two files do the work. `obj/loader.py` reads, repairs and reshapes meshes and
imports no manim at all. `obj/mobject.py` turns a mesh into a ManimGL
`Surface`, and is the only part tied to the renderer.

---

## 2. Problems faced, and what fixed them

Each of these was found by rendering something and looking at it. The
symptom is what you would actually see.

### 2.1 A quarter of the model silently missing

| | |
| --- | --- |
| **Symptom** | 11,346 triangles loaded from a file that should give 15,024. No error, no warning. Parts of the building simply absent. |
| **Cause** | The exporter wrapped long `f` lines with a trailing backslash. `text.splitlines()` treats each physical line as a face and throws away the continuation. |
| **Fix** | `_logical_lines()` joins continued lines before parsing. |
| **Guard** | `test_backslash_continuations_keep_every_face` |

Never go back to `splitlines()` in the parser.

### 2.2 Walls speckled with two colours (z-fighting, different materials)

| | |
| --- | --- |
| **Symptom** | Zig-zag dithering across flat walls, two colours fighting pixel by pixel; worse as the camera moves. |
| **Cause** | The CAD export writes the same wall **twice**, on two material layers, at the same coordinates — 6,417 cross-material pairs, at most 0.0049 units apart on a 44.65-unit model. The depth test cannot choose between them. |
| **Fix** | `dedupe="auto"`, on by default. A geometric coplanar-overlap test: bucket faces by plane, then a 2D grid within each plane, then four sample points per triangle. ~1 s on 15k faces. |
| **Guard** | `test_dedupe_removes_the_twins_and_leaves_none` |

### 2.3 Roofs still speckled after that

| | |
| --- | --- |
| **Symptom** | Fainter checkerboard left on roof slabs and slab edges after 2.2 was fixed. |
| **Cause** | Same-material twins, which had been deliberately left alone on the reasoning that identical colours cannot fight. They can: the twins are usually wound in opposite directions, so one is lit and one is in shadow. Same colour, different **brightness**. |
| **Fix** | `dedupe` handles same-material pairs too. The larger face wins (so a small detail lying flush on a wall can never punch a hole in it); between equals the outward-facing one wins, keeping the lit side. |
| **Result** | 15,024 → 7,938 triangles. Total surface area halves exactly, because every surface really was drawn twice. Residual coincident pairs: **0**. |

### 2.4 `color=` being ignored

| | |
| --- | --- |
| **Symptom** | `OBJMobject("earth.obj", color="#4E6478")` rendered white. |
| **Cause** | `earth.mtl` says `Kd 1.0 1.0 1.0`, and `init_colors` checked the .mtl before checking whether a colour had been passed — the opposite of what the docstring promised. |
| **Fix** | `_explicit_color` is recorded in `__init__` and wins over the .mtl. |
| **Guard** | `test_explicit_colour_beats_the_mtl` |

### 2.5 Texture vanishing after a Transform

| | |
| --- | --- |
| **Symptom** | A textured Earth turned flat grey the moment `shade_smooth()` was applied after a `Transform`. |
| **Cause** | Shading multiplied a *cached copy* of the colours taken at construction. `Transform` writes straight into `data`, so the cache described colours the model no longer had. |
| **Fix** | Shading derives its base from the live `data`, dividing out any lighting it previously baked in (`_shade_lam`). No separate copy to go stale. |
| **Guard** | `test_shading_reads_live_colours_not_a_stale_copy` |

### 2.6 Blurry texture

| | |
| --- | --- |
| **Symptom** | The Earth's continents were soft smears, no matter how large the render. |
| **Cause** | Colours were sampled once per **vertex** and interpolated by the GPU, so a 4096×2048 image was effectively reduced to the mesh's 64×32 grid. |
| **Fix** | ManimGL already has a real textured-surface shader. `OBJTextured` feeds it the `.obj`'s own `vt` coordinates with `resolution=(0,0)`, giving a per-pixel `textureSample`. |
| **Note** | `set_texture_colors()` is still there as the cheap path; `per="corner"` is much better than `per="face"` if you use it. |

### 2.7 Things sinking into a hillside

| | |
| --- | --- |
| **Symptom** | Buildings placed on a mountain were half buried, or leaning off a slope. |
| **Cause** | Two mistakes. Ground height was taken from the **nearest** vertex, which on a slope is usually downhill from the object. And the requested position was often on a steep face. |
| **Fix** | `flat_spot()` searches the neighbourhood for the least steep patch; the ground is then the **maximum** height under the object's footprint, not the nearest. |
| **Watch out** | A search radius that is too generous walks the object somewhere else entirely — 2.6 units let an armchair migrate into a building. 1.4 with a distance penalty is about right. |

### 2.8 Close-ups framing the wrong thing

| | |
| --- | --- |
| **Symptom** | A shot captioned "armchair" showed a building. |
| **Cause** | Camera targets were hard-coded to the coordinates *asked for*, but `flat_spot` had since moved the model. |
| **Fix** | Ask the model where it ended up: `frame.reorient(..., arm.get_center(), ...)`. |

### 2.9 A point cloud that was nearly invisible

| | |
| --- | --- |
| **Symptom** | The final dissolve looked like an empty black frame. |
| **Cause** | `radius` is in scene units. A value tuned for a 3-unit model is invisible around a 20-unit landscape. The building had also been recoloured near-black earlier in the scene. |
| **Fix** | Scale `radius` with the scene (0.016 → 0.052), and repaint dark models before sampling them. |

### 2.10 Smaller ones worth knowing

| Symptom | Cause and fix |
| --- | --- |
| `ValueError: expected non-negative integer` when scattering trees | `np.random.default_rng(seed)` refuses negative seeds; positions can be negative. Use `abs(...)`. |
| A legend whose colours do not match the model | Do not index a palette by `material_names.index(name)`. Use `OBJMobject.legend()`, which is built from the colours actually handed out. |
| `part_colors` empty after a Transform | `Transform` copies **data**, not attributes. Anything set on the target object does not migrate. |
| `NameError` on `LEFT`/`OUT` at render time | Direction constants used inside `obj_mobject.py` must be in its own top-level `manimlib.constants` import. |
| `AttributeError: 'NoneType' object has no attribute '__dict__'` loading `loader.py` by path | Register the module in `sys.modules` before `exec_module`, or `@dataclass` cannot resolve it. |
| The bump map not found | `earth.mtl` contains both `map_bump 4096_bump.jpg` and a typo'd `bump D096_bump.jpg`. `map_bump` must take priority over bare `bump`. |
| A model lying on its side | `.obj` says Y is up; Rhino, Revit and SketchUp export Z-up. Use `up_axis="z"`, or `"auto"` to guess from the smallest extent. |
| `height=` not doing what you expect | In manim `height` is the **y** extent. `OBJMobject` deliberately redefines it as **z**, because that is what "how tall" means for a standing model. Use `depth=` for y. |

---

## 3. Directions that do not work

Do not spend time on these again.

| Idea | Why it fails |
| --- | --- |
| **Welding vertices to cure z-fighting** | The duplicate surfaces are triangulated along *opposite diagonals*, so the triangles never coincide exactly. Tolerances from 1e-4 to 0.1 caught at most 153 of ~4,800 offending faces. Only a geometric overlap test works. |
| **All-pairs overlap test within a plane bucket** | O(k²); took 13 s. The per-plane 2D grid hash does the same job in ~1 s. |
| **Plain `subdivide(smooth=False)` to smooth a model** | The new midpoints lie exactly on the old flat faces, so the shape does not change at all. Only the triangle count goes up. Use `smooth=True`, or do not bother. |
| **`smooth_subdivide=True` on architecture** | Loop subdivision rounds sharp corners. Correct for a sphere or a scanned figure; it melts the edges of a building. |
| **`displace()` without subdividing first** | Displacement can only move vertices that exist. A 1,986-vertex globe has perhaps four points across India. |
| **`shade_smooth()` on a `textured()` model** | The textured shader takes colour from the image, so there is nothing for smooth shading to bake into. For even lighting pass `shading=(0, 0, 0)`. |
| **A `VGroup` of thousands of `Line`s for a wireframe** | Far too slow. `wireframe()` builds one `VMobject` with many subpaths. |
| **Running Python from inside `manimlib/`** | `manimlib/typing.py` shadows the standard library `typing`. Run from the project root. |
| **Setting `self.camera.background_color` in `construct()`** | Does nothing in ManimGL. Pass `-c "#RRGGBB"` on the command line. |
| **Trusting frame counts from `-l`** | `-l` renders at 854×480 but still 30 fps. Divide frames by 30 for the true duration. |

---

## 4. Numbers to expect

If a run disagrees with these, something has changed. `tests/` checks the
ones marked ✓.

### Models

| file | triangles as loaded | after `dedupe` | axis | notes |
| --- | --- | --- | --- | --- |
| `building.obj` | 15,024 ✓ | **7,938** ✓ | Z-up | 14,181 verts, 6 materials, 1,254 groups |
| `earth.obj` | 3,968 ✓ | — | Y-up | UV sphere, has `vt` + three maps |
| `chair.obj` | 6,893 | 6,716 | Y-up | no `.mtl`, no `vt`, no `vn` |
| `mountain.obj` | 6,962 | — | Y-up | terrain |
| `terrain.obj` | 3,042 | — | Z-up | terrain |
| `armchair.obj` | 2,832 | — | Z-up | blocky collision mesh |
| `house.obj` | 1,792 | — | Y-up | cottage |
| `tree_a` / `tree_b` / `palm` | 876 / 760 / 1,246 | — | Y-up | |

`chair.obj` gets manim's default `BLUE_D` when loaded plain — it carries no
colour of its own. The mint and orange in the demos come from a palette
passed in the scene.

### Reshaping

| operation | in → out | time |
| --- | --- | --- |
| `earth.subdivide(1)` | 3,968 → 15,872 ✓ | 0.03 s |
| `earth.subdivide(2)` | 3,968 → 63,488 ✓ | 0.16 s |
| `chair.decimate(1500)` | 6,716 → 1,500 ✓ | 0.02 s |
| `dedupe` on `building.obj` | 15,024 → 7,938 | ~5 s first run, 0.01 s cached |
| `displace` after `subdivide(2)` | radius spread 0.57 → 28.26 ✓ | 0.12 s |

Decimation down to 3,000 is invisible on the chair; 1,500 shows slightly
angular cushions; 500 reads as deliberate low-poly but is still a chair.

### Rendering

Measured on 2 CPUs with a software GPU and 1,984 MB of RAM.

| scene | resolution | triangles | render time | peak memory |
| --- | --- | --- | --- | --- |
| one building, 48 s | 1280×720 | 7,938 | 2.5 min | 1,132 MB |
| six models, 72 s | 1280×720 | ~21,000 | 2.5 min | ~1,300 MB |
| eight models, 90 s | **2560×1440** | ~70,000 | **13 min** | **1,804 MB of 1,984** |

QHD with that much geometry was the ceiling — 78 MB of headroom left. For
4K, cut geometry first (`decimate`, or drop the globe to `subdivide(1)`).

### Tests

`python tests/test_obj.py` — 21 checks, about 9 seconds. The mesh-side
ones run with no manim installed at all.

---

## 5. What this will never do

These are limits of the renderer, not missing features.

- **No shadows.** One light, diffuse plus specular, per fragment. Nothing
  casts a shadow on anything.
- **One light source.** `self.camera.light_source` is a single `Point`. No
  area lights, no HDRI, no ambient occlusion, no global illumination.
- **No PBR.** `shading=(reflectiveness, gloss, shadow)` is a toy model.
- **No normal or specular maps.** One diffuse texture and an optional dark
  one. `displace()` fakes relief with real geometry instead.
- **No transparency sorting.** Overlapping translucent surfaces can draw in
  the wrong order.
- **No physics, no rigging.** No rigid bodies, cloth, fluids, particles or
  skinned characters.

And two limits of this library:

- `decimate()` transfers UVs and materials from the nearest original
  vertex/face. Decimation genuinely destroys the correspondence, so a
  texture will slide a little.
- `subdivide(smooth=True)` rounds sharp corners, as above.

**This is a 3D illustration tool, not a 3D rendering tool.** It is for
explaining things with models — exploded views, labelled parts, cutaways,
build-up animations. For photoreal images or simulation, model in Blender,
export `.obj` or `.glb`, and bring the result here for the explanatory part.

---

## 6. If you are picking this up

1. `pip install -e .` from the project folder, plus ManimGL from git.
2. `python tests/test_obj.py` — 9 seconds, tells you the library is
   intact before you spend 13 minutes on a render.
3. Read §3 before trying to improve anything.
4. Render a draft with `-l` first. It is roughly six times faster and shows
   every mistake that matters except texture sharpness.
