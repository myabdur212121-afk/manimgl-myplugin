> Part of [manimgl_myplugin](../../README.md).

# The `shapes` helper — working notes

Read this before changing anything.

---

## 1. What this is

Three ways to get a `MeshData` without a file on disk:

```
from_surface(mob)        anything ManimGL already draws
revolve(profile)         spin an outline around the z axis
extrude(path, profile)   sweep a cross-section along a path
```

`build.py` holds the three builders and the grid-stitching they share;
`profiles.py` holds the small arrays that feed them. Everything returns a
mesh with UVs, so `subdivide`, `decimate`, `displace`, `textured`,
`wireframe`, `point_cloud` and `BuildMesh` all work on the result.

**Why there is no `sphere()` or `cube()` here.** ManimGL already ships
`Sphere`, `Torus`, `Cylinder`, `Cone`, `Cube`, `Prism`, `Disk3D`,
`Square3D` and `ParametricSurface`. Writing those again would add code,
add a second name for each shape, and give nothing back. `from_surface`
borrows all of them instead. The plan started with ten shape functions and
ended with three; that was the right trade.

---

## 2. Problems faced, and what fixed them

### 2.1 A cube that came apart into six discs

| | |
| --- | --- |
| **Symptom** | `from_surface(Cube()).subdivide(3)` rendered as six bulging discs floating apart, not a rounded cube. |
| **Cause** | `Cube` is six separate `Square3D` mobjects. Merging them kept **24 corners instead of 8** — the mesh looked closed but was not connected, so Loop subdivision read every edge as a free boundary and curled each face away on its own. |
| **Fix** | `MeshData.weld()`, called automatically by `from_surface` for groups. Rounds coordinates onto a grid and keeps one vertex per cell. |
| **Guard** | `test_from_surface_welds_a_cube_into_eight_corners`, `test_a_welded_cube_subdivides_into_one_blob` |

This is the bug that justified prototyping before committing to the design.

### 2.2 Zero-area triangles at the poles

| | |
| --- | --- |
| **Symptom** | Normals came out as NaN near the top and bottom of a revolved sphere. |
| **Cause** | At a pole the profile radius is zero, so the quad between the last two rings collapses to a line. |
| **Fix** | `_grid_mesh` measures each triangle and drops the degenerate ones. |
| **Guard** | `test_revolve_drops_the_degenerate_pole_quads` |

### 2.3 A twist in the middle of a straight pipe

| | |
| --- | --- |
| **Symptom** | An extruded square section rotated along its own length. |
| **Cause** | A Frenet frame is defined by the curve's normal, which is undefined — and therefore flips — wherever the path straightens out. |
| **Fix** | Rotation-minimising transport: start with any vector across the first tangent, then at each step project out the new tangent rather than recomputing from scratch. |
| **Guard** | `test_extrude_frame_does_not_spin_on_a_straight_run` |

### 2.4 Open ends on a prism

| | |
| --- | --- |
| **Symptom** | `extrude` along a straight line gave a tube with no top or bottom; you could see inside it. |
| **Fix** | `caps`, defaulting to on for an open path and off for a closed one, where there are no ends to close. Each end gets a triangle fan, the first one wound backwards so both face outwards. |
| **Guard** | `test_extrude_caps_an_open_path_by_default` |

### 2.5 Flat shapes blowing up the frame

| | |
| --- | --- |
| **Symptom** | `OBJMobject(torus_mesh, height=2.4)` filled the whole screen. |
| **Cause** | `height` is the **z** extent. A torus is 0.6 tall and 2.6 wide, so forcing z to 2.4 scaled everything by four. |
| **Fix** | Not a code change — size flat things by `width=`, or `model.scale(target / max(model.get_shape()))`. |

I hit this twice while making the demo. It is the single easiest mistake here.

---

## 3. Directions that do not work

| Idea | Why it fails |
| --- | --- |
| **Writing `sphere()`, `cube()`, `torus()` here** | They exist in ManimGL. `from_surface` reaches all of them in one function. |
| **`from_surface(Dodecahedron())`** | Dodecahedron and the `VCube` family are vector mobjects, not `Surface`s — there is no grid of points to read. Raises `TypeError` and should. |
| **A Frenet frame for `extrude`** | Flips on straight sections. See 2.3. |
| **Welding UVs along with positions** | Two patches meeting at an edge usually need *different* texture coordinates there. `weld` merges positions only. |
| **`extrude` with a two-point profile** | A profile is a closed loop; two points make a line, and the result is a degenerate ribbon. Refused. |
| **Assuming `revolve` output is watertight** | It is closed around the axis, but a profile that does not start and end on the axis leaves the top and bottom open — a bowl really is a bowl. Add the closing points yourself if you want a solid. |

---

## 4. Numbers to expect

| call | triangles |
| --- | --- |
| `revolve(semicircle_profile())` | 8,832 |
| `revolve(profile_of_60, segments=96)` | ~11,300 |
| `extrude(helix_path(turns=4), circle_profile(0.07, 16))` | 12,800 |
| `extrude(line_path(), polygon_profile(6))` | 24 (12 sides + 12 cap) |
| `from_surface(Sphere(resolution=(64, 32)))` | 3,780 |
| `from_surface(Cube())` | 12, from **8** vertices |
| `from_surface(Cube(), weld=False)` | 12, from 24 vertices |

`revolve` builds an `N x M` grid, so triangle count is roughly
`2 x segments x len(profile)`, minus the degenerate quads at any pole.

Tests: `python tests/test_shapes.py` — 18 checks, about 3 seconds.

---

## 5. What this will never do

- **No booleans.** No union, subtraction or intersection of solids. That
  needs a proper CSG library.
- **No text or fonts as geometry.**
- **Nothing irregular.** A tree, a chair, a scanned face — these are not
  formulas. That is what the `obj` helper is for.
- **No guarantee of watertightness.** Fine for rendering, not for 3D
  printing or volume calculations.
- `revolve` spins around **z only**. Rotate the result if you want another
  axis.

---

## 6. If you are picking this up

1. `python tests/test_shapes.py` — 3 seconds.
2. Read §3 before adding anything; the shape you want may already exist in
   ManimGL, in which case `from_surface` is the answer.
3. To add a builder: return a `MeshData` with UVs and everything
   downstream works. No registration, no base class.
