"""
Regression tests for manimgl_myplugin.

Every number in here was measured, and every check corresponds to something
that was once broken. If one fails, NOTES.md says what it means.

    python tests/test_obj.py      # no pytest needed
    pytest tests/test_obj.py -q

The loader tests need only numpy/scipy/trimesh/Pillow. The mobject tests
need ManimGL and skip themselves if it is not installed.
"""

import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from manimgl_myplugin.obj.loader import load_mesh, parse_obj          # noqa: E402

try:
    from manimgl_myplugin import OBJMobject, BuildMesh
    HAVE_MANIMGL = True
except Exception:                                          # pragma: no cover
    HAVE_MANIMGL = False


# --------------------------------------------------------------- parsing --

def test_backslash_continuations_keep_every_face():
    """
    Some exporters wrap long `f` lines with a backslash. Splitting on
    newlines used to drop the tail and lose 3,678 of 15,024 triangles.
    """
    mesh = load_mesh("building.obj")      # load_mesh never dedupes
    assert mesh.num_faces == 15024, mesh.num_faces
    assert len(mesh.vertices) == 14181


def test_ngons_are_fanned():
    five = "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nv -1 .5 0\nf 1 2 3 4 5\n"
    assert parse_obj(five).num_faces == 3


def test_negative_indices():
    """`f -3 -2 -1` counts back from the end of the vertex list."""
    mesh = parse_obj("v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\n")
    assert mesh.num_faces == 1
    assert np.allclose(mesh.vertices[mesh.tri_v[0]].sum(axis=0), [1, 1, 0])


def test_mtl_is_read_including_the_maps():
    mesh = load_mesh("earth.obj")
    mat = mesh.materials["01___Default"]
    assert mat.diffuse == (1.0, 1.0, 1.0)          # white: colour is in the image
    assert mat.texture == "4096_earth.jpg"
    assert mat.emissive_texture == "4096_night_lights.jpg"
    # the file also has a typo'd `bump D096_bump.jpg`; map_bump must win
    assert mat.bump_texture == "4096_bump.jpg"


def test_texture_paths_resolve():
    mesh = load_mesh("earth.obj")
    for kind in ("diffuse", "emissive", "bump"):
        assert mesh.texture_path(kind) is not None, kind
    assert load_mesh("chair.obj").texture_path() is None   # no .mtl at all


def test_other_formats_through_trimesh():
    import trimesh
    ball = trimesh.creation.icosphere(subdivisions=2)
    with tempfile.TemporaryDirectory() as d:
        for ext in ("stl", "ply", "glb"):
            path = os.path.join(d, f"probe.{ext}")
            ball.export(path)
            assert load_mesh(path).num_faces == 320, ext


def test_the_mesh_side_works_without_manim():
    """
    `from manimgl_myplugin import load_mesh` must not drag ManimGL in. The mesh
    half is plain numpy and is useful on its own, so obj_mobject is
    imported lazily (PEP 562) rather than at package import.
    """
    import subprocess
    probe = """
import sys
from importlib.abc import MetaPathFinder
class Block(MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == 'manimlib' or name.startswith('manimlib.'):
            raise ImportError('manimlib not installed (simulated)')
sys.meta_path.insert(0, Block())
sys.path.insert(0, %r)
from manimgl_myplugin import load_mesh
print(load_mesh('earth.obj').subdivide(1).decimate(4000).num_faces)
""" % os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    out = subprocess.run([sys.executable, "-c", probe],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-400:]
    assert out.stdout.strip().endswith("4000")


# ---------------------------------------------------------------- dedupe --

def test_dedupe_removes_the_twins_and_leaves_none():
    """
    The test building has the same walls written twice on two material
    layers. Both get drawn and z-fight. A vertex weld cannot find them --
    the twins are triangulated along opposite diagonals -- so this is a
    geometric overlap test.
    """
    raw = load_mesh("building.obj")
    clean, removed = raw.dedupe_coincident(report=True)
    assert removed == 7086, removed
    assert clean.num_faces == 7938, clean.num_faces
    assert len(clean.coincident_pairs(cross_material_only=False)) == 0
    # the shape must not change, only the redundancy
    assert np.allclose(raw.size, clean.size)
    # every surface was drawn twice, so the area should roughly halve
    assert 0.5 < clean.face_areas().sum() / raw.face_areas().sum() < 0.65


def test_dedupe_keeps_the_rare_material():
    clean = load_mesh("building.obj").dedupe_coincident()
    counts = clean.face_counts("material")
    assert counts["Translucent_Glass_Gray"] == 301   # glass must survive intact
    assert counts["Layer_2-1 E F"] == 4


# ------------------------------------------------------------- reshaping --

def test_subdivide_quadruples_and_keeps_uvs():
    mesh = load_mesh("earth.obj")
    one = mesh.subdivide(1)
    assert one.num_faces == mesh.num_faces * 4 == 15872
    assert one.subdivide(1).num_faces == 63488
    # uv and normal indices are split on their own keys, so seams survive
    assert one.tri_vt.max() >= 0 and one.tri_vn.max() >= 0
    assert len(one.uvs) > len(mesh.uvs)


def test_smooth_subdivide_rounds_the_shape_and_linear_does_not():
    mesh = load_mesh("earth.obj")
    radius = lambda m: np.linalg.norm(m.vertices - m.center, axis=1)   # noqa: E731
    spread = lambda m: radius(m).std() / radius(m).mean()              # noqa: E731
    # linear midpoints sit inside the sphere, so the surface stays faceted
    assert spread(mesh.subdivide(1, smooth=False)) > spread(mesh.subdivide(1))


def test_decimate_hits_the_target_and_keeps_the_silhouette():
    mesh = load_mesh("chair.obj")
    small = mesh.decimate(1500)
    assert abs(small.num_faces - 1500) <= 2, small.num_faces
    assert np.allclose(small.size, mesh.size, rtol=0.02)
    assert mesh.decimate(0.25).num_faces <= mesh.num_faces * 0.26
    # materials are carried over from the nearest old face
    assert len(set(small.tri_material)) >= 3


def test_displace_creates_real_relief():
    mesh = load_mesh("earth.obj").subdivide(2)
    radius = lambda m: np.linalg.norm(m.vertices - m.center, axis=1)   # noqa: E731
    before = np.ptp(radius(mesh))
    after = np.ptp(radius(mesh.displace(mesh.texture_path("bump"), strength=0.05)))
    assert after > 20 * before, (before, after)


def test_displace_without_uvs_raises():
    try:
        load_mesh("chair.obj").displace("/home/user/models/4096_bump.jpg")
    except ValueError:
        return
    raise AssertionError("a model with no vt should refuse to displace")


# ------------------------------------------------------- the mobject side --

def _skip_without_manimgl():
    if not HAVE_MANIMGL:
        print("    (skipped: ManimGL not installed)")
        return True
    return False


def test_explicit_colour_beats_the_mtl():
    """earth.mtl says `Kd 1 1 1`; an explicit colour= must still win."""
    if _skip_without_manimgl():
        return
    slate = OBJMobject("earth.obj", height=3, color="#4E6478")
    plain = OBJMobject("earth.obj", height=3)
    assert np.asarray(slate.data["rgba"][:, :3]).mean() < 0.6
    assert np.allclose(np.asarray(plain.data["rgba"][:, :3]), 1.0)   # mtl white


def test_shading_reads_live_colours_not_a_stale_copy():
    """
    Transform writes straight into `data`. Shading used to work off a copy
    taken at construction, so a textured model turned grey the moment it was
    smoothed after a Transform.
    """
    if _skip_without_manimgl():
        return
    earth = OBJMobject("earth.obj", height=3, color="#4E6478")
    textured = earth.copy().set_texture_colors(
        earth.mesh.texture_path("diffuse"), brighten=1.15)
    earth.data["rgba"][:] = textured.data["rgba"]          # what Transform does
    smoothed = earth.copy().shade_smooth()
    assert np.asarray(smoothed.data["rgba"][:, :3]).std() > 0.15


def test_height_means_the_z_extent():
    if _skip_without_manimgl():
        return
    model = OBJMobject("chair.obj", height=4)
    assert abs(model.get_shape()[2] - 4) < 1e-3


def test_textured_finds_its_own_image():
    if _skip_without_manimgl():
        return
    globe = OBJMobject("earth.obj", height=3).textured()
    assert globe.num_textures == 2          # diffuse + map_Ke night lights
    assert len(globe.data) == 3 * globe.num_faces


def test_textured_refuses_a_model_with_no_uvs():
    if _skip_without_manimgl():
        return
    try:
        OBJMobject("chair.obj", height=3).textured()
    except ValueError:
        return
    raise AssertionError("chair.obj has no vt and should refuse")


def test_constructor_pipeline():
    if _skip_without_manimgl():
        return
    assert OBJMobject("earth.obj", height=3, subdivide=2).num_faces == 63488
    assert OBJMobject("chair.obj", height=3, decimate=1500).num_faces == 1500
    both = OBJMobject("earth.obj", height=3, subdivide=1, displace=True)
    assert both.num_faces == 15872


def test_the_derived_mobjects_build():
    if _skip_without_manimgl():
        return
    model = OBJMobject("chair.obj", height=3, color_by="material")
    assert model.wireframe(max_edges=1200) is not None
    assert model.point_cloud(400) is not None
    assert len(model.split_by("group")) > 1
    assert model.legend() is not None
    assert BuildMesh(model.copy()) is not None


# ------------------------------------------------------------------ main --

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
