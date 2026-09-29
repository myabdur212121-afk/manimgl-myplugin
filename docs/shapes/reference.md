> Part of [manimgl_myplugin](../../README.md). This page is the full
> specification of the `shapes` helper.

# The `shapes` helper — reference

Meshes from formulas rather than files.

```python
from manimgl_myplugin import OBJMobject
from manimgl_myplugin.shapes import revolve, semicircle_profile

mesh = revolve(semicircle_profile())          # a sphere
self.add(OBJMobject(mesh, height=3, up_axis=None))
```

Everything here returns a `MeshData` with UV coordinates, which is the
currency the rest of the toolkit trades in. Once you have one, `subdivide`,
`decimate`, `displace`, `textured`, `wireframe`, `point_cloud` and
`BuildMesh` all work, and they neither know nor care that there was no file.

---

## The three builders

### `from_surface(mob, name=None, weld=True)`

Read a mesh out of anything ManimGL can already draw.

```python
from manimlib import Sphere, Torus, Cube, ParametricSurface
from manimgl_myplugin.shapes import from_surface

mesh = from_surface(Sphere(resolution=(128, 64)))
mesh = mesh.displace("mola.img", strength=0.05)
```

This is why there is no `sphere()` in this module. ManimGL ships `Sphere`,
`Torus`, `Cylinder`, `Cone`, `Cube`, `Prism`, `Disk3D` and `Square3D`, and
`ParametricSurface` covers any formula you care to write. One function
brings all of them into reach.

| | |
| --- | --- |
| `mob` | a `Surface`, or a group of them |
| `weld` | fuse duplicated corners when merging a group. On by default, and you want it — see below |
| raises | `TypeError` for vector mobjects (`Dodecahedron`, `VCube`), which have no grid of points |

A `Cube` is six separate `Square3D` faces. Without welding, its shared
corners stay duplicated — 24 instead of 8 — and the mesh looks closed but
is not connected, so `subdivide(smooth=True)` peels the faces apart into six
discs. Pass `weld=False` only if you want the patches kept separate.

### `revolve(profile, segments=96)`

Spin an outline around the z axis — a potter's wheel.

```python
ball = revolve(semicircle_profile())

z = np.linspace(0, 2, 60)                      # or any outline at all
r = 0.3 + 0.2 * np.sin(4 * z)
vase = revolve(np.stack([r, z], axis=-1))
```

`profile` is an `(N, 2)` array of `(radius, height)` — the shape seen from
the side. Anything with an axis of symmetry is one of these: sphere,
cylinder, cone, torus, bottle, chess piece.

`segments` is how many steps go around; the profile's own length is the
resolution up the object. UVs run around in u and along the profile in v,
the same layout an equirectangular map uses — convenient if you mean to
`displace` the result with elevation data.

### `extrude(path, profile, closed_path=False, caps=None)`

Sweep a cross-section along a path — toothpaste from a nozzle.

```python
spring = extrude(helix_path(turns=4, pitch=0.35), circle_profile(0.07))
duct   = extrude(helix_path(turns=4, pitch=0.35), square_profile(0.14))
elbow  = extrude(arc_path(radius=1.2, angle=PI), circle_profile(0.16))
prism  = extrude(line_path((0,0,-1), (0,0,1)), polygon_profile(6, 0.8))
```

`path` is `(M, 3)` — where the nozzle goes. `profile` is an `(N, 2)` closed
loop — the shape of its mouth. Change either and you get a different object.

`caps` closes the two ends; it defaults to on for an open path and off for a
closed one. The cross-section is carried by rotation-minimising transport,
so it does not spin as the path curves — a Frenet frame would put a twist in
the middle of a straight pipe.

---

## Profiles and paths

Ordinary numpy arrays. Writing your own is the point.

| profile | shape |
| --- | --- |
| `circle_profile(radius=1, sides=32)` | a circle — tubes, springs |
| `square_profile(size=1)` | a square — ducts, bars |
| `polygon_profile(sides=6, radius=1)` | a regular polygon — prisms |
| `star_profile(points=5, outer=1, inner=0.45)` | a star |
| `semicircle_profile(radius=1, samples=48)` | revolve it for a sphere |

| path | shape |
| --- | --- |
| `line_path(start, end, samples=2)` | a straight run |
| `arc_path(radius=1, angle=π/2, plane="xy")` | a bend, for pipework |
| `helix_path(turns=4, radius=1, pitch=0.35)` | a rising spiral |

---

## `MeshData.weld(tol=1e-5)`

Fuse vertices that sit on top of each other — 24 corners of a cube become 8.

Surfaces built separately and then combined carry two copies of every shared
corner. Only positions are merged; UVs are left alone, because two patches
meeting at an edge often need different texture coordinates there.

---

## Two things that will catch you

**`height` is the z extent.** Sizing a torus or a bowl with `height=` blows
it up, because those are flat in z. Use `width=`, or:

```python
model.scale(2.5 / max(model.get_shape()))
```

**`revolve` is not automatically watertight.** It closes around the axis,
but a profile that does not begin and end on the axis leaves the ends open —
a bowl really is a bowl. Add the closing points yourself for a solid:

```python
revolve([[0, 0], [1, 0], [1, 2], [0, 2]])      # a capped cylinder
```

---

## Adding a builder

Return a `MeshData` with UVs. That is the whole contract — no registration,
no base class, and every downstream tool works immediately.

```python
def torus_knot(p=2, q=3, thickness=0.05):
    return extrude(knot_path(p, q), circle_profile(thickness))
```

See [`notes.md`](./notes.md) for the bugs already found and the directions
already known to be dead ends.
