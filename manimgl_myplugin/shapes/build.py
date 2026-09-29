"""
manimgl_myplugin.shapes.build -- three ways to get a mesh.

ManimGL already ships Sphere, Torus, Cylinder, Cone, Cube, Prism, Disk3D
and ParametricSurface, so there is nothing to gain from writing those
again. What was missing is a way to get any of them *into* a
:class:`MeshData`, where they can be subdivided, decimated, displaced,
textured, wireframed or built up triangle by triangle -- and two builders
for the shapes manim has no answer for.

    from_surface(mob)          anything manim can already draw
    revolve(profile)           spin an outline around the z axis
    extrude(path, profile)     sweep a cross-section along a path

Everything returns a ``MeshData`` with UV coordinates, so the rest of the
toolkit works on the result without knowing where it came from.

``MeshData`` currently lives in the ``obj`` helper because that is where it
grew. It is really shared ground; if a third helper starts using it, move it
to a module of its own.
"""

from __future__ import annotations

import numpy as np

from ..obj.loader import MeshData

__all__ = ["revolve", "extrude", "from_surface"]


# ------------------------------------------------------------ plumbing --

def _grid_mesh(points, uvs, nu, nv, wrap_u=False, wrap_v=False, name="shape"):
    """
    Stitch an ``nu x nv`` grid of points into triangles.

    ``wrap_u`` / ``wrap_v`` join the last row or column back to the first,
    which is what closes a surface of revolution around its axis. Quads that
    collapse to a line -- the ones at the pole of a sphere, say -- are
    dropped rather than emitted as zero-area triangles that no renderer can
    shade and no normal can be computed for.
    """
    points = np.asarray(points, dtype=np.float32).reshape(nu, nv, 3)
    uvs = np.asarray(uvs, dtype=np.float32).reshape(nu, nv, 2)

    index = np.arange(nu * nv).reshape(nu, nv)
    iu = np.arange(nu if wrap_u else nu - 1)
    iv = np.arange(nv if wrap_v else nv - 1)
    a = index[np.ix_(iu, iv)]
    b = index[np.ix_((iu + 1) % nu, iv)]
    c = index[np.ix_((iu + 1) % nu, (iv + 1) % nv)]
    d = index[np.ix_(iu, (iv + 1) % nv)]

    quads = np.stack([a, b, c, d], axis=-1).reshape(-1, 4)
    tris = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])

    flat = points.reshape(-1, 3)
    area = np.linalg.norm(np.cross(flat[tris[:, 1]] - flat[tris[:, 0]],
                                   flat[tris[:, 2]] - flat[tris[:, 0]]), axis=1)
    tris = tris[area > 1e-12]

    return _mesh(flat, uvs.reshape(-1, 2), tris, name)


def _mesh(vertices, uvs, tris, name):
    tris = np.asarray(tris, dtype=np.int32)
    return MeshData(
        vertices=np.asarray(vertices, dtype=np.float32),
        tri_v=tris,
        tri_vt=tris.copy(),                 # uvs share the vertex layout
        tri_vn=np.full_like(tris, -1),
        tri_material=np.zeros(len(tris), dtype=np.int32),
        tri_group=np.zeros(len(tris), dtype=np.int32),
        tri_object=np.zeros(len(tris), dtype=np.int32),
        material_names=[name], group_names=[name], object_names=[name],
        uvs=np.asarray(uvs, dtype=np.float32),
        normals=np.zeros((0, 3), dtype=np.float32),
        source=f"<{name}>",
    )


def _merge(meshes, name):
    verts, uvs, tris, offset = [], [], [], 0
    for m in meshes:
        verts.append(m.vertices)
        uvs.append(m.uvs)
        tris.append(np.asarray(m.tri_v) + offset)
        offset += len(m.vertices)
    return _mesh(np.concatenate(verts), np.concatenate(uvs),
                 np.concatenate(tris), name)


# ------------------------------------------------------------ builders --

def revolve(profile, segments: int = 96, name: str = "revolve") -> MeshData:
    """
    Spin an outline around the z axis -- a potter's wheel.

    ::

        from manimgl_myplugin.shapes import revolve, semicircle_profile

        ball = revolve(semicircle_profile())          # a sphere

        z = np.linspace(0, 2, 60)                     # or any outline at all
        r = 0.3 + 0.2 * np.sin(4 * z)
        vase = revolve(np.stack([r, z], axis=-1))

    ``profile`` is an ``(N, 2)`` array of ``(radius, height)``: the shape
    seen from the side. Anything with an axis of symmetry is one of these --
    sphere, cylinder, cone, torus, bottle, chess piece.

    ``segments`` is how many steps go around. The profile's own length is
    the resolution up the object, so a 48-point profile at 96 segments gives
    a 96 x 48 grid.

    UVs run around in u and along the profile in v, which is the same layout
    an equirectangular map uses -- convenient if you mean to
    :meth:`~MeshData.displace` the result with elevation data.
    """
    profile = np.asarray(profile, dtype=np.float64).reshape(-1, 2)
    if len(profile) < 2:
        raise ValueError("a profile needs at least two points")

    theta = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    r, z = profile[:, 0], profile[:, 1]
    points = np.stack([
        np.outer(np.cos(theta), r),
        np.outer(np.sin(theta), r),
        np.tile(z, (segments, 1)),
    ], axis=-1)

    uvs = np.stack(np.meshgrid(np.linspace(0, 1, segments, endpoint=False),
                               np.linspace(0, 1, len(profile)),
                               indexing="ij"), axis=-1)
    return _grid_mesh(points, uvs, segments, len(profile),
                      wrap_u=True, name=name)


def extrude(path, profile, closed_path: bool = False,
            caps: bool | None = None, name: str = "extrude") -> MeshData:
    """
    Sweep a cross-section along a path -- toothpaste from a nozzle.

    ::

        from manimgl_myplugin.shapes import extrude, helix_path, circle_profile

        spring = extrude(helix_path(turns=4, pitch=0.35),
                         circle_profile(0.07))

        duct = extrude(helix_path(turns=4, pitch=0.35),
                       square_profile(0.14))          # same path, square nozzle

    ``path`` is an ``(M, 3)`` array of where the nozzle goes; ``profile`` an
    ``(N, 2)`` closed loop describing its mouth. Change either and you get a
    different object, which is why this covers springs, tubes, ducts, rails,
    handrails and prisms without a class for each.

    ``caps`` closes the two open ends; it defaults to on for an open path and
    off for a closed one, where there are no ends to close.

    The cross-section is carried along by rotation-minimising transport, so
    it does not spin as the path curves. A Frenet frame would flip wherever
    the curve straightens out, putting a twist in the middle of a pipe.
    """
    path = np.asarray(path, dtype=np.float64).reshape(-1, 3)
    profile = np.asarray(profile, dtype=np.float64).reshape(-1, 2)
    if len(path) < 2 or len(profile) < 3:
        raise ValueError("extrude needs at least two path points and a "
                         "profile of three or more")
    if caps is None:
        caps = not closed_path

    m, k = len(path), len(profile)
    tangents = np.gradient(path, axis=0)
    tangents /= np.maximum(np.linalg.norm(tangents, axis=1, keepdims=True), 1e-12)

    seed = np.array([0.0, 0.0, 1.0])
    if abs(seed @ tangents[0]) > 0.9:
        seed = np.array([1.0, 0.0, 0.0])
    normals = np.empty_like(path)
    start = seed - (seed @ tangents[0]) * tangents[0]
    normals[0] = start / np.linalg.norm(start)
    for i in range(1, m):
        carried = normals[i - 1] - (normals[i - 1] @ tangents[i]) * tangents[i]
        length = np.linalg.norm(carried)
        normals[i] = carried / length if length > 1e-9 else normals[i - 1]
    binormals = np.cross(tangents, normals)

    points = (path[:, None, :]
              + profile[None, :, 0, None] * normals[:, None, :]
              + profile[None, :, 1, None] * binormals[:, None, :])
    uvs = np.stack(np.meshgrid(np.linspace(0, 1, m),
                               np.linspace(0, 1, k, endpoint=False),
                               indexing="ij"), axis=-1)

    mesh = _grid_mesh(points, uvs, m, k, wrap_u=closed_path, wrap_v=True,
                      name=name)
    if caps and not closed_path:
        mesh = _cap_ends(mesh, points[0], points[-1], name)
    return mesh


def _cap_ends(mesh, first_ring, last_ring, name):
    """Close both ends with a triangle fan around the ring's centre."""
    k = len(first_ring)
    verts, uvs, tris = [mesh.vertices], [mesh.uvs], [mesh.tri_v]
    base = len(mesh.vertices)
    for ring, flip in ((first_ring, True), (last_ring, False)):
        verts.append(np.vstack([ring, ring.mean(axis=0)]))
        uvs.append(np.full((k + 1, 2), 0.5, dtype=np.float32))
        fan = np.array([[base + k, base + i, base + (i + 1) % k]
                        for i in range(k)], dtype=np.int32)
        tris.append(fan[:, ::-1] if flip else fan)
        base += k + 1
    return _mesh(np.concatenate(verts), np.concatenate(uvs),
                 np.concatenate(tris), name)


def from_surface(mob, name: str | None = None, weld: bool = True) -> MeshData:
    """
    Read a mesh out of anything ManimGL can already draw.

    ::

        from manimlib import Sphere, Torus, Cube, ParametricSurface
        from manimgl_myplugin.shapes import from_surface

        mesh = from_surface(Sphere(resolution=(128, 64)))
        mesh = mesh.displace("mola.img", strength=0.05)

    This is the bridge, and it is why there is no ``sphere()`` here:
    ``Sphere``, ``Torus``, ``Cylinder``, ``Cone``, ``Cube``, ``Prism``,
    ``Disk3D`` and ``Square3D`` already exist, and ``ParametricSurface``
    covers any formula you care to write. One function brings all of them
    into reach of ``subdivide``, ``decimate``, ``displace``, ``textured``,
    ``wireframe``, ``point_cloud`` and ``BuildMesh``.

    Groups are merged: a ``Cube`` is six separate ``Square3D`` faces, and
    without ``weld`` their shared corners stay duplicated, leaving a mesh
    that looks closed but is not connected -- smooth subdivision then peels
    the faces apart into six bulging discs. Pass ``weld=False`` only if you
    want the patches kept separate on purpose.

    Raises ``TypeError`` for mobjects built from vectors rather than
    surfaces, such as ``Dodecahedron``; there is no grid of points to read.
    """
    from manimlib.mobject.types.surface import Surface

    name = name or type(mob).__name__.lower()

    if not isinstance(mob, Surface):
        parts = [from_surface(sub, name, weld=False) for sub in mob.submobjects
                 if isinstance(sub, Surface) or sub.submobjects]
        if not parts:
            raise TypeError(
                f"{type(mob).__name__} is not built from Surfaces, so there "
                "is no mesh to read -- Dodecahedron and the VCube family are "
                "vector mobjects")
        merged = _merge(parts, name)
        return merged.weld() if weld else merged

    nu, nv = mob.get_resolution()
    points = np.asarray(mob.get_points(), dtype=np.float32)
    if nu * nv != len(points):
        raise ValueError(f"{name}: resolution {nu}x{nv} does not account for "
                         f"{len(points)} points")

    uvs = np.stack(np.meshgrid(np.linspace(0, 1, nu),
                               np.linspace(0, 1, nv),
                               indexing="ij"), axis=-1)
    return _grid_mesh(points, uvs, nu, nv, name=name)
