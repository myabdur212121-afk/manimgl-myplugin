"""
Regression tests for the shapes helper.

Every check here corresponds to something that was wrong at some point
while this was being built. See docs/shapes/notes.md.

    python tests/test_shapes.py
    pytest tests/test_shapes.py -q
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from manimgl_myplugin.shapes import (                       # noqa: E402
    revolve, extrude, from_surface,
    circle_profile, square_profile, polygon_profile,
    semicircle_profile, helix_path, line_path, arc_path,
)

try:
    from manimlib import (Sphere, Torus, Cylinder, Cone, Cube, Prism,
                          Dodecahedron, ParametricSurface)
    from manimgl_myplugin import OBJMobject
    HAVE_MANIMGL = True
except Exception:                                           # pragma: no cover
    HAVE_MANIMGL = False


def _radius(mesh):
    return np.linalg.norm(mesh.vertices - mesh.center, axis=1)


# -------------------------------------------------------------- revolve --

def test_revolve_makes_a_sphere():
    mesh = revolve(semicircle_profile(1.0, 48), segments=96)
    r = _radius(mesh)
    assert abs(r.mean() - 1.0) < 0.01, r.mean()
    assert r.std() < 0.01, "a revolved semicircle should be round"
    assert mesh.num_faces > 8000


def test_revolve_closes_around_the_axis():
    """wrap_u joins the last column back to the first -- no open seam."""
    mesh = revolve(semicircle_profile(1.0, 12), segments=16)
    edges = np.sort(mesh.tri_v[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    # a closed surface has every edge shared by two faces; the poles are the
    # only exception and they are few
    assert (counts == 2).mean() > 0.85, (counts == 2).mean()


def test_revolve_drops_the_degenerate_pole_quads():
    """At a pole the radius is zero and the quad collapses to a line."""
    mesh = revolve(semicircle_profile(1.0, 24), segments=32)
    a, b, c = (mesh.vertices[mesh.tri_v[:, i]] for i in range(3))
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    assert area.min() > 0, "a zero-area triangle got through"


def test_revolve_keeps_uvs():
    mesh = revolve(semicircle_profile())
    assert mesh.tri_vt.max() >= 0 and len(mesh.uvs) == len(mesh.vertices)
    assert mesh.uvs.min() >= 0 and mesh.uvs.max() <= 1


def test_revolve_rejects_a_one_point_profile():
    try:
        revolve([[1.0, 0.0]])
    except ValueError:
        return
    raise AssertionError("a profile of one point should be refused")


# -------------------------------------------------------------- extrude --

def test_extrude_makes_a_spring():
    mesh = extrude(helix_path(turns=4, radius=1.0, pitch=0.35),
                   circle_profile(0.07, 16))
    size = mesh.size
    assert size[0] > 1.9 and size[1] > 1.9, size      # two loops wide
    assert 1.2 < size[2] < 1.6, size[2]               # four turns of 0.35


def test_extrude_caps_an_open_path_by_default():
    """A prism must be closed at both ends; a spring has no ends to close."""
    open_ended = extrude(line_path((0, 0, -1), (0, 0, 1)),
                         polygon_profile(6, 0.8), caps=False)
    capped = extrude(line_path((0, 0, -1), (0, 0, 1)), polygon_profile(6, 0.8))
    assert capped.num_faces == open_ended.num_faces + 12    # two hex fans


def test_extrude_frame_does_not_spin_on_a_straight_run():
    """
    A Frenet frame flips where the curve straightens. Rotation-minimising
    transport must not, or a pipe develops a twist in the middle.
    """
    path = np.stack([np.linspace(0, 2, 40), np.zeros(40), np.zeros(40)], -1)
    mesh = extrude(path, square_profile(0.2), caps=False)
    ring0 = mesh.vertices[:4]
    ringN = mesh.vertices[4 * 39:4 * 39 + 4]
    # the corners should still be in the same orientation, only moved along x
    assert np.allclose(ring0[:, 1:], ringN[:, 1:], atol=1e-4)


def test_extrude_rejects_a_degenerate_profile():
    try:
        extrude(line_path(), [[0.0, 0.0], [1.0, 0.0]])
    except ValueError:
        return
    raise AssertionError("a two-point profile is not a loop")


def test_arc_path_bends_where_asked():
    mesh = extrude(arc_path(radius=1.0, angle=np.pi / 2), circle_profile(0.1, 12))
    assert mesh.num_faces > 100


# ---------------------------------------------------------------- weld --

def test_weld_fuses_duplicated_corners():
    from manimgl_myplugin import load_mesh
    text = ("v 0 0 0\nv 1 0 0\nv 0 1 0\n"
            "v 0 0 0\nv 1 0 0\nv 0 1 0\n"           # the same three again
            "f 1 2 3\nf 4 5 6\n")
    mesh = load_mesh(text)
    assert len(mesh.vertices) == 6
    assert len(mesh.weld().vertices) == 3
    assert mesh.weld().num_faces == 2               # faces are kept


# ------------------------------------------------------- from_surface --

def _skip():
    if not HAVE_MANIMGL:
        print("    (skipped: ManimGL not installed)")
        return True
    return False


def test_from_surface_reads_manims_own_shapes():
    if _skip():
        return
    for maker in (lambda: Sphere(resolution=(32, 16)),
                  lambda: Torus(resolution=(24, 12)),
                  Cylinder, Cone, Cube, Prism):
        mesh = from_surface(maker())
        assert mesh.num_faces > 0
        assert mesh.tri_vt.max() >= 0, f"{maker} lost its uvs"


def test_from_surface_takes_any_parametric_surface():
    if _skip():
        return
    saddle = ParametricSurface(lambda u, v: (u, v, u * v),
                               u_range=(-1, 1), v_range=(-1, 1),
                               resolution=(24, 24))
    assert from_surface(saddle).num_faces > 500


def test_from_surface_welds_a_cube_into_eight_corners():
    """
    A Cube is six separate Square3D faces. Unwelded, its 24 corners leave
    the faces disconnected and subdivide(smooth) peels them into six discs.
    """
    if _skip():
        return
    cube = from_surface(Cube())
    assert len(cube.vertices) == 8, len(cube.vertices)
    assert cube.num_faces == 12
    assert len(from_surface(Cube(), weld=False).vertices) == 24


def test_a_welded_cube_subdivides_into_one_blob():
    """If the weld failed this splits into six pieces that drift apart."""
    if _skip():
        return
    rounded = from_surface(Cube()).subdivide(3)
    r = _radius(rounded)
    assert r.std() / r.mean() < 0.12, "the faces came apart"


def test_from_surface_refuses_a_vector_mobject():
    if _skip():
        return
    try:
        from_surface(Dodecahedron())
    except TypeError:
        return
    raise AssertionError("Dodecahedron holds no Surface and should be refused")


# ------------------------------------------------- the whole pipeline --

def test_generated_meshes_feed_every_downstream_tool():
    if _skip():
        return
    mesh = revolve(semicircle_profile(1.0, 32), segments=64)
    assert mesh.subdivide(1).num_faces > mesh.num_faces
    assert mesh.decimate(500).num_faces <= 502

    model = OBJMobject(mesh, height=3, up_axis=None)
    assert model.wireframe(max_edges=800) is not None
    assert model.point_cloud(300) is not None
    globe = model.textured("/home/user/models/4096_earth.jpg")
    assert globe.num_faces == mesh.num_faces


def test_a_generated_sphere_can_be_displaced():
    if _skip():
        return
    mesh = revolve(semicircle_profile(1.0, 64), segments=128)
    bumpy = mesh.displace("/home/user/models/4096_bump.jpg", strength=0.06)
    assert np.ptp(_radius(bumpy)) > 10 * np.ptp(_radius(mesh))


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  ok    {name}")
        except Exception as exc:
            print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
            failed.append(name)
    print(f"\n  {len(tests) - len(failed)}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
