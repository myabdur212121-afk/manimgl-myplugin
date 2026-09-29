"""
Regression tests for the astro helper.

The table of facts is checked against published values, and the two
shadows against geometry that can be worked out by hand.

    python tests/test_astro.py
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from manimgl_myplugin.astro.data import BODIES, RingBand, texture_url  # noqa: E402

try:
    from manimgl_myplugin.astro import (Saturn, Mars, Moon, Earth, Venus,
                                    Jupiter, Uranus, Body, named)
    HAVE_MANIMGL = True
except Exception:                                           # pragma: no cover
    HAVE_MANIMGL = False


# ---------------------------------------------------------------- facts --

def test_the_table_matches_published_values():
    saturn = BODIES["saturn"]
    assert saturn.equatorial_radius_m == 60_268_000
    assert abs(saturn.flattening - 0.098) < 0.002      # ~10%, and it shows
    assert abs(saturn.axial_tilt_deg - 26.73) < 0.05
    assert abs(BODIES["earth"].flattening - 0.003353) < 1e-5
    assert abs(BODIES["uranus"].axial_tilt_deg - 97.77) < 0.1   # on its side


def test_gas_giants_are_marked_as_having_no_surface():
    for key in ("jupiter", "saturn", "uranus", "neptune"):
        assert not BODIES[key].solid, key
    for key in ("mercury", "venus", "earth", "moon", "mars"):
        assert BODIES[key].solid, key


def test_saturns_ring_edges_and_the_cassini_gap():
    bands = {b.name: b for b in BODIES["saturn"].rings}
    assert abs(bands["B"].outer - 1.951) < 0.01
    assert abs(bands["A"].inner - 2.027) < 0.01
    # the Cassini Division is a real hole, not a transparent patch
    assert bands["A"].inner > bands["B"].outer
    assert all(b.inner < b.outer for b in bands.values())


def test_texture_urls():
    assert texture_url("mars", "4k").endswith("/4k_mars.jpg")
    assert texture_url("saturn_ring_alpha", "2k", "png").endswith(".png")
    try:
        texture_url("mars", "16k")
    except ValueError:
        return
    raise AssertionError("an unknown quality should be refused")


# --------------------------------------------------------------- bodies --

def _skip():
    if not HAVE_MANIMGL:
        print("    (skipped: ManimGL not installed)")
        return True
    return False


def test_a_body_is_a_globe_plus_its_rings():
    if _skip():
        return
    assert len(Mars(radius=2).submobjects) == 1                 # no rings
    assert len(Saturn(radius=2, shadows=False).submobjects) == 4  # + C, B, A
    assert len(Saturn(radius=2, shadows=False, rings=False).submobjects) == 1


def test_flattening_squashes_the_poles():
    if _skip():
        return
    saturn = Saturn(radius=3, shadows=False, rings=False, tilt=0)
    w, d, h = saturn.globe.get_shape()
    assert abs(w - 6.0) < 0.05                       # equator
    assert abs(h / w - (1 - 0.098)) < 0.01           # 10% shorter pole to pole
    moon = Moon(radius=3, shadows=False, tilt=0)
    assert abs(moon.globe.get_shape()[2] / 6.0 - 1) < 0.01      # near enough


def test_rings_sit_where_the_table_says():
    if _skip():
        return
    saturn = Saturn(radius=3, shadows=False, tilt=0)
    radii = [np.linalg.norm(np.asarray(r.get_points())[:, :2], axis=1) / 3
             for r in saturn.ring_group]
    assert abs(min(r.min() for r in radii) - 1.239) < 0.01      # C inner
    assert abs(max(r.max() for r in radii) - 2.269) < 0.01      # A outer
    # nothing inside the Cassini Division
    allr = np.concatenate(radii)
    assert not ((allr > 1.96) & (allr < 2.02)).any()


def test_the_rings_lie_flat_in_the_equator():
    if _skip():
        return
    saturn = Saturn(radius=3, shadows=False, tilt=0)
    for ring in saturn.ring_group:
        assert np.abs(np.asarray(ring.get_points())[:, 2]).max() < 1e-4


def test_axial_tilt_tips_the_rings_with_the_planet():
    if _skip():
        return
    upright = Saturn(radius=3, shadows=False, tilt=0)
    tipped = Saturn(radius=3, shadows=False, tilt=60)
    assert np.abs(np.asarray(tipped.ring_group[0].get_points())[:, 2]).max() > 1
    assert np.abs(np.asarray(upright.ring_group[0].get_points())[:, 2]).max() < 1e-4


# -------------------------------------------------------------- shadows --

def test_the_globe_shadows_the_rings():
    """
    With the light on one side, ring points directly opposite the planet
    must come out darker than the ones beside the light.
    """
    if _skip():
        return
    light = np.array([-14.0, 0.0, 1.0])
    lit = Saturn(radius=3, shadows=False, tilt=0)
    shaded = Saturn(radius=3, tilt=0, light=light)

    def brightness(body):
        ring = body.ring_group[1]                    # the B ring
        pts = np.asarray(ring.get_points())
        rgb = np.asarray(ring.data["rgba"][:, :3])
        far = pts[:, 0] > 2.0                        # away from the light
        near = pts[:, 0] < -2.0                      # towards it
        return rgb[near].mean(), rgb[far].mean()

    near_lit, far_lit = brightness(lit)
    near_sh, far_sh = brightness(shaded)
    assert abs(near_sh - near_lit) < 0.02, "the sunward side must not change"
    assert far_sh < far_lit * 0.5, "the far side should fall into shadow"


def test_shadow_strength_controls_how_dark():
    if _skip():
        return
    light = np.array([-14.0, 0.0, 1.0])
    soft = Saturn(radius=3, tilt=0, light=light, shadow_strength=0.3)
    hard = Saturn(radius=3, tilt=0, light=light, shadow_strength=1.0)

    def far_side(body):
        ring = body.ring_group[1]
        pts = np.asarray(ring.get_points())
        return np.asarray(ring.data["rgba"][:, :3])[pts[:, 0] > 2.0].mean()

    assert far_side(hard) < far_side(soft)


def test_the_rings_shadow_the_globe():
    """
    The ring shadow is painted into a copy of the texture, because a
    ManimGL textured surface has no per-vertex colour to darken. Check the
    globe ends up pointing at a repainted image, and that the repaint
    really is darker.
    """
    if _skip():
        return
    from PIL import Image
    light = np.array([-14.0, -8.0, 1.0])
    plain = Saturn(radius=3, shadows=False, light=light)
    shaded = Saturn(radius=3, light=light)

    before = plain.globe.textures["LightTexture"].path
    after = shaded.globe.textures["LightTexture"].path
    assert str(after) != str(before), "the texture was not repainted"

    a = np.asarray(Image.open(before).convert("L"), dtype=float)
    b = np.asarray(Image.open(after).convert("L").resize(
        Image.open(before).size), dtype=float)
    ratio = b / np.maximum(a, 1)
    assert (ratio < 0.7).mean() > 0.01, "no part of the globe was darkened"
    assert ratio.min() < 0.4, "the shadow is too faint to see"


def test_shadows_off_leaves_the_original_texture():
    if _skip():
        return
    saturn = Saturn(radius=3, shadows=False)
    assert "2k_saturn" in str(saturn.globe.textures["LightTexture"].path)


# -------------------------------------------------------------- turning --

def test_axis_is_the_tilted_pole_not_the_world_z():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    tilt = np.radians(earth.tilt)
    assert np.allclose(earth.axis, [0, -np.sin(tilt), np.cos(tilt)], atol=0.01)
    assert abs(np.degrees(np.arccos(earth.axis @ [0, 0, 1])) - 23.44) < 0.1


def test_spin_leaves_the_pole_alone_but_rotate_does_not():
    """
    The whole point of spin. Turning about the scene's z axis makes a
    tilted planet's pole wander in a circle; turning about its own axis
    does not.
    """
    if _skip():
        return
    spun = Earth(radius=3, shadows=False).spin(0.4)
    before = spun.axis.copy()
    for updater in spun.get_updaters():
        updater(spun, 1.0)
    assert np.allclose(spun.axis, before, atol=1e-6), "spin moved the pole"

    wrong = Earth(radius=3, shadows=False)
    wrong.rotate(0.4, np.array([0.0, 0.0, 1.0]))
    assert not np.allclose(wrong.axis, before, atol=0.01)


def test_spin_rate_period_and_day():
    if _skip():
        return
    from manimlib.constants import TAU
    assert abs(Earth(shadows=False).spin(0.3)._spin_rate - 0.3) < 1e-9
    assert abs(Earth(shadows=False).spin(period=8)._spin_rate - TAU / 8) < 1e-9
    # day= uses the real sidereal period, so Jupiter outruns Earth
    fast = Jupiter(shadows=False).spin(day=4)._spin_rate
    slow = Earth(shadows=False).spin(day=4)._spin_rate
    assert fast > slow * 2


def test_venus_and_uranus_spin_backwards():
    if _skip():
        return
    assert Venus(shadows=False).spin(day=4)._spin_rate < 0
    assert Uranus(shadows=False).spin(day=4)._spin_rate < 0
    assert Mars(shadows=False).spin(day=4)._spin_rate > 0


def test_stop_spin_removes_the_updater():
    if _skip():
        return
    body = Mars(shadows=False).spin(0.5)
    assert len(body.get_updaters()) == 1
    body.stop_spin()
    assert len(body.get_updaters()) == 0


def test_turn_is_an_animation_about_the_bodys_own_axis():
    if _skip():
        return
    from manimlib.animation.rotation import Rotating
    earth = Earth(radius=3, shadows=False)
    anim = earth.turn(np.pi, run_time=2)
    assert isinstance(anim, Rotating)
    assert np.allclose(anim.axis, earth.axis)
    assert anim.run_time == 2


# ------------------------------------------------------------ geography --

def test_point_at_lands_on_the_surface_and_follows_the_tilt():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    for lat, lon in [(0, 0), (23.8, 90.4), (-45, 170), (51.5, -0.1)]:
        r = np.linalg.norm(earth.point_at(lat, lon) - earth.get_center())
        assert abs(r - 3) < 0.05, (lat, lon, r)
    # the north pole must be the spin axis, or geography and rotation disagree
    pole = earth.point_at(90, 0) - earth.get_center()
    assert np.allclose(pole / np.linalg.norm(pole), earth.axis, atol=0.01)


def test_point_at_agrees_with_the_texture():
    """
    The map was half a turn out at first: asking for the Sahara handed
    back the middle of the Pacific. Sample the texture where each place
    should be and check land is land.
    """
    if _skip():
        return
    from PIL import Image
    earth = Earth(radius=3, shadows=False, tilt=0)
    img = np.asarray(Image.open(
        earth.globe.textures["LightTexture"].path).convert("RGB"))
    h, w = img.shape[:2]

    def is_sea(lat, lon):
        point = earth.point_at(lat, lon) - earth.get_center()
        turn = (np.degrees(np.arctan2(point[1], point[0])) % 360) / 360
        u, v = turn, (lat + 90) / 180
        r, g, b = map(int, img[int((1 - v) * (h - 1)), int(u * (w - 1))])
        return b > r + 20

    assert not is_sea(23, 13), "the Sahara came out wet"
    assert not is_sea(21, 79), "India came out wet"
    assert not is_sea(23.8, 90.4), "Dhaka came out wet"
    assert is_sea(0, -150), "the Pacific came out dry"
    assert is_sea(0, -30), "the Atlantic came out dry"


def test_point_at_moves_with_the_body():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    before = earth.point_at(0, 0)
    earth.shift(np.array([2.0, 0.0, 0.0]))
    assert np.allclose(earth.point_at(0, 0), before + [2, 0, 0], atol=1e-6)


def test_height_lifts_a_marker_clear_of_the_surface():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    low = np.linalg.norm(earth.point_at(0, 0, 0.0) - earth.get_center())
    high = np.linalg.norm(earth.point_at(0, 0, 0.1) - earth.get_center())
    assert abs(high / low - 1.1) < 0.01


def test_arc_between_leaves_the_surface_and_comes_back():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    arc = earth.arc_between((23.8, 90.4), (51.5, -0.1), height=0.25)
    r = np.linalg.norm(np.asarray(arc.get_points()) - earth.get_center(), axis=1)
    assert abs(r[0] - 3) < 0.15 and abs(r[-1] - 3) < 0.15   # flat at both ends
    assert r.max() > 3.4                                     # and up in between


def test_graticule_and_axis_line_exist_and_sit_on_the_body():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    grid = earth.graticule(30)
    assert len(grid) == 17                      # 5 parallels + 12 meridians
    pts = np.concatenate([np.asarray(m.get_points()) for m in grid])
    r = np.linalg.norm(pts - earth.get_center(), axis=1)
    assert 2.9 < r.min() and r.max() < 3.2

    line = earth.axis_line()
    ends = np.asarray(line.get_points())
    direction = ends[-1] - ends[0]
    assert np.allclose(direction / np.linalg.norm(direction), earth.axis, atol=0.02)


def test_orbit_keeps_its_distance_and_comes_back_round():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    moon = Moon(radius=1, shadows=False).orbit(earth, radius=6, period=10)
    seen = []
    for _ in range(40):
        for u in moon.get_updaters():
            u(moon, 0.25)
        seen.append(np.linalg.norm(moon.get_center() - earth.get_center()))
    assert max(abs(d - 6) for d in seen) < 1e-6      # a circle, not a spiral
    assert np.allclose(moon.get_center(), earth.get_center() + [6, 0, 0], atol=1e-6)

    moon.stop_orbit()
    assert len(moon.get_updaters()) == 0


def test_orbit_and_spin_work_together():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    moon = Moon(radius=1, shadows=False).spin(0.5).orbit(earth, radius=5)
    assert len(moon.get_updaters()) == 2


# --------------------------------------------------------------- lookup --

def test_named_and_quality():
    if _skip():
        return
    assert isinstance(named("mars", radius=2), Body)
    try:
        named("pluto")
    except KeyError:
        pass
    else:
        raise AssertionError("an unknown body should raise")
    mars = Mars(radius=2, quality="4k")
    assert "4k_mars" in str(mars.globe.textures["LightTexture"].path)


def test_info_reads_sensibly():
    if _skip():
        return
    text = Saturn(radius=2, shadows=False).info()
    assert "60,268 km" in text and "C" in text and "A" in text


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
