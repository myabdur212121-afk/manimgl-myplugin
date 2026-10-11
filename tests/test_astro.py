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
                                    Jupiter, Uranus, Body, Sun, named,
                                    CORONA_SHELLS)
    from manimlib import Mobject, VMobject, YELLOW
    from manimlib.mobject.types.dot_cloud import DotCloud
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


def test_marker_default_size_is_the_ring_scale():
    """
    Notes 2.16: the default grew from 0.05 (an invisible 4x3 px dot at
    the demo framing) to 0.10 -- the cell_note ring's number and scale,
    so a dot and a ring on one globe read as one family.
    """
    if _skip():
        return
    import inspect
    from manimgl_myplugin.astro.bodies import Body
    sig = inspect.signature(Body.marker)
    assert abs(sig.parameters["size"].default - 0.10) < 1e-12
    earth = Earth(radius=3, shadows=False)
    dot = earth.marker(23.8, 90.4)
    assert abs(dot.radius - 0.10) < 1e-9            # size * radius / 3


def test_cell_note_ring_uses_the_family_width():
    """
    The ring's stroke was a literal 2.0 that happened to equal
    OVERLAY_WIDTH; it now reads the constant, so a future width change
    cannot strand it (notes 2.16).
    """
    if _skip():
        return
    from manimgl_myplugin.astro.bodies import OVERLAY_WIDTH
    earth = Earth(radius=3, shadows=False)
    ring = earth.cell_note(23.8, 90.4, index=2)[1]
    widths = np.unique(np.asarray(ring.get_stroke_widths(), dtype=float))
    assert len(widths) == 1 and abs(widths[0] - OVERLAY_WIDTH) < 1e-12


def test_arc_between_leaves_the_surface_and_comes_back():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    arc = earth.arc_between((23.8, 90.4), (51.5, -0.1), height=0.25,
                           edge_dot=False)
    r = np.linalg.norm(np.asarray(arc.get_points()) - earth.get_center(), axis=1)
    assert abs(r[0] - 3) < 0.15 and abs(r[-1] - 3) < 0.15   # flat at both ends
    assert r.max() > 3.4                                # and up in between


def test_arc_between_pins_its_two_ends():
    """
    Notes 2.17: the default journey is a VGroup of the arc and a
    painted dot at each end; a dict reaches the dots' own parameters,
    False gives the bare arc.
    """
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    flight = earth.arc_between((23.8, 90.4), (51.5, -0.1))
    assert len(flight.submobjects) == 3

    def surface_radius(dot):
        pts = np.concatenate([np.asarray(sm.get_points()) for sm
                              in dot.get_family() if sm.has_points()])
        return np.linalg.norm(pts - earth.get_center(), axis=1)

    # paint sits on the ground: radius x (1 + height), height a fraction
    assert np.allclose(surface_radius(flight[1]), 3 * 1.015, atol=0.01)
    assert np.allclose(surface_radius(flight[2]), 3 * 1.015, atol=0.01)

    bare = earth.arc_between((23.8, 90.4), (51.5, -0.1), edge_dot=False)
    assert not bare.submobjects

    def span(dot):
        pts = np.concatenate([np.asarray(sm.get_points()) for sm
                              in dot.get_family() if sm.has_points()])
        return max(np.ptp(pts[:, i]) for i in range(3))

    big = earth.arc_between((23.8, 90.4), (51.5, -0.1),
                            edge_dot=dict(size=0.2))
    assert span(big[1]) > span(flight[1])          # size was honoured


def test_terminator_closes_the_ring():
    """Notes 2.17: endpoint=False sampling left 1.875 degrees open."""
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    pts = np.asarray(earth.terminator(follow=False).get_points())
    assert np.linalg.norm(pts[0] - pts[-1]) < 1e-9


def test_axis_line_is_honest_by_default():
    """
    Notes 2.17: the buried middle used to shine through -- 241 gold
    pixels of it inside the disc -- because the X-ray was hardcoded.
    The honest look is the default; the X-ray is asked for.
    """
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    axis = earth.axis_line(follow=False)
    assert axis.depth_test and axis.z_index == 1 and not axis.updaters
    xray = earth.axis_line(follow=False, see_through=True)
    assert not xray.depth_test and xray.updaters
    # and it still crosses the poles: every point on the body's axis,
    # out to the overhang
    ax = earth.axis / np.linalg.norm(earth.axis)
    v = np.asarray(axis.get_points())
    along = v @ ax
    radial = np.linalg.norm(v - np.outer(along, ax), axis=1)
    assert radial.max() < 1e-6
    assert abs(np.abs(along).max() - 3 * 1.4) < 1e-6


def test_surface_point_is_paint_not_a_pin():
    """
    Real geometry on the sphere: the disc rides at radius x (1 + height)
    -- height is a fraction of the radius -- so the camera's zoom grows
    and shrinks it; the pin is a camera-facing billboard, the paint
    is a disc lying on the ground.
    """
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    dot = earth.surface_point(23.8, 90.4, follow=False)
    pts = np.concatenate([np.asarray(sm.get_points()) for sm
                          in dot.get_family() if sm.has_points()])
    r = np.linalg.norm(pts - earth.get_center(), axis=1)
    assert np.allclose(r, 3 * 1.015, atol=0.01)
    assert dot.get_fill_opacity() == 1.0         # paint, not an outline


def test_surface_tex_and_mathtex_bend_onto_the_globe():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    for mob in (earth.surface_tex(r"day: $24\,$h", 0, 0, follow=False),
                earth.surface_mathtex(r"\omega^2 r", 30, 120, follow=False)):
        pts = np.concatenate([np.asarray(sm.get_points()) for sm
                              in mob.get_family() if sm.has_points()])
        r = np.linalg.norm(pts - earth.get_center(), axis=1)
        assert np.allclose(r, 3 * 1.015, atol=0.01)


def test_surface_cell_note_paints_a_closed_ring():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    note = earth.surface_cell_note(23.8, 90.4, index=2, follow=False)
    ring_pts = np.asarray(note[1].get_points())
    assert np.linalg.norm(ring_pts[0] - ring_pts[-1]) < 1e-9   # closed
    r = np.linalg.norm(ring_pts - earth.get_center(), axis=1)
    assert np.allclose(r, 3 * 1.015, atol=0.01)
    assert note[0].submobjects                      # the P tag is there


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


# ------------------------------------------------- new facts and overlays --

def test_the_new_facts_are_on_every_body():
    # the Sun orbits nothing and owns no moons, so the two orbit fields
    # and the moon count are planet-and-moon business only
    fields = ("mass_kg", "surface_gravity_m_s2", "mean_temp_c")
    orbit_fields = ("semi_major_axis_m", "orbital_period_days", "moon_count")
    for key, f in BODIES.items():
        for field in fields + (orbit_fields if key != "sun" else ()):
            assert getattr(f, field) is not None, (key, field)
    assert abs(BODIES["earth"].mass_kg - 5.9722e24) < 0.01e24
    assert abs(BODIES["earth"].surface_gravity_m_s2 - 9.8) < 0.1
    assert BODIES["saturn"].moon_count >= 274        # 293 confirmed mid-2026
    assert BODIES["jupiter"].moon_count >= 95
    assert BODIES["moon"].semi_major_axis_m < 1e9     # around Earth, not the Sun
    # cross-check: gravity tracks G M / R^2 for the rocky planets
    for key in ("mercury", "venus", "earth", "mars"):
        f = BODIES[key]
        g_calc = 6.674e-11 * f.mass_kg / f.equatorial_radius_m ** 2
        assert abs(g_calc - f.surface_gravity_m_s2) < 0.6, key


def test_points_at_agrees_with_point_at():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    lats, lons = [23.8, -33.9, 0.0, 71.2], [90.4, 151.2, -45.0, 0.0]
    vec = earth._points_at(lats, lons, [0.05] * 4)
    for i, (la, lo) in enumerate(zip(lats, lons)):
        assert np.allclose(vec[i], earth.point_at(la, lo, 0.05), atol=1e-6)


def test_an_overlay_does_not_move_the_body():
    """
    Grafting a marker or an arc on one side shifted the family bounding
    box, so the body's own centre -- and with it point_at -- wandered.
    The centre is the globe's now.
    """
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    c0 = earth.get_center().copy()
    p0 = earth.point_at(23.8, 90.4)
    earth.marker(23.8, 90.4)
    earth.arc_between((23.8, 90.4), (51.5, -0.1))
    assert np.allclose(earth.get_center(), c0, atol=1e-9)
    assert np.allclose(earth.point_at(23.8, 90.4), p0, atol=1e-9)


def test_markers_and_arcs_follow_the_body():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    dot = earth.marker(23.8, 90.4)
    arc = earth.arc_between((23.8, 90.4), (51.5, -0.1), edge_dot=False)
    d0 = np.asarray(dot.get_points()).copy()
    a0 = np.asarray(arc.get_points()).copy()

    earth.shift([2.0, 0.0, 0.0])
    assert np.allclose(np.asarray(dot.get_points()), d0 + [2, 0, 0], atol=1e-6)
    assert np.allclose(np.asarray(arc.get_points()), a0 + [2, 0, 0], atol=1e-6)

    earth.rotate(np.pi / 6, np.array([0.0, 0.0, 1.0]),
                 about_point=earth.get_center())
    assert not np.allclose(np.asarray(dot.get_points()), d0 + [2, 0, 0],
                           atol=1e-4)      # it turned with the body too


def test_a_label_stays_pinned_and_readable():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    lbl = earth.label(23.8, 90.4, "Dhaka", font_size=30)

    # a shift is plain: point_at still knows where the body is
    earth.shift([1.5, 0.0, 0.0])
    lbl.update(0)
    radial = earth.point_at(23.8, 90.4, 0.10) - earth.get_center()
    target = earth.get_center() + radial + 0.02 * radial / np.linalg.norm(radial)
    assert np.linalg.norm(lbl.get_all_points().mean(0) - target) < 0.15

    # the text plane faces out of the surface, not into it
    pts = lbl.get_all_points()
    normal = np.linalg.svd(pts - pts.mean(0))[2][-1]
    radial /= np.linalg.norm(radial)
    assert abs(normal @ radial) > 0.95

    # a rotation is beyond point_at's analytic reach, so expect it by hand:
    # the pin point rides along with the body, and the text re-uprights
    # around it on the new tangent plane
    c1 = earth.get_center().copy()
    pin = target.copy()
    earth.rotate(np.pi / 5, np.array([0.0, 0.0, 1.0]), about_point=c1)
    lbl.update(0)
    v = pin - c1
    phi = np.pi / 5
    expected = c1 + np.array([v[0] * np.cos(phi) - v[1] * np.sin(phi),
                               v[0] * np.sin(phi) + v[1] * np.cos(phi), v[2]])
    assert np.linalg.norm(lbl.get_all_points().mean(0) - expected) < 0.15


def test_kwargs_reach_the_text():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    small = earth.label(0, 0, "X", font_size=18, follow=False)
    big = earth.label(0, 0, "X", font_size=54, follow=False)
    assert big.get_height() > small.get_height() * 2


def test_graticule_highlight_and_labels():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    grid = earth.graticule(30)
    assert len(grid) == 17                       # 5 parallels + 12 meridians
    # plain mesh by default now: no equator is slipped in when the step
    # misses it -- that is what highlight= is for
    mixed = earth.graticule((20, 40), follow=False)
    assert len(mixed) == 8 + 9                   # 8 parallels, 9 meridians

    tagged = earth.graticule(30, labels=True)
    assert len(tagged) == 17 + 5                 # five pinned latitude tags
    assert sum(1 for m in tagged if m.updaters) == 5

    # a named circle is drawn even when the step misses it: no round step
    # lands on Earth's 23.44-degree tropics
    tropics = earth.graticule(30, highlight="tropics", follow=False)
    assert len(tropics) == 17 + 2
    everything = earth.graticule(30, highlight=True, follow=False)
    assert len(everything) == 17 + 4             # tropics + polar circles


def test_tropics_and_polar_circles_sit_at_the_tilt():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    tropics = earth.tropics()
    assert len(tropics) == 2
    from manimgl_myplugin.astro.bodies import (OVERLAY_WIDTH,
                                               SPECIAL_WIDTH_FACTOR)
    assert (tropics[0].data["stroke_width"][0]
            == OVERLAY_WIDTH * SPECIAL_WIDTH_FACTOR)
    target = earth.point_at(23.44, 0, 0.004)     # Earth's own tilt
    d = np.linalg.norm(np.asarray(tropics[0].get_points()) - target, axis=1)
    assert d.min() < 0.05

    circles = earth.polar_circles()
    target2 = earth.point_at(90 - 23.44, 0, 0.004)
    d2 = np.linalg.norm(np.asarray(circles[0].get_points()) - target2, axis=1)
    assert d2.min() < 0.05

    untilted = Body(radius=2)
    assert len(untilted.tropics()) == 1          # the equator stands in



def test_the_mesh_covers_a_body_with_no_texture():
    """The graticule is drawn from the body's geometry, not its texture,
    so a plain Body -- tilted, textureless -- wears it just the same."""
    if _skip():
        return
    rock = Body(radius=2, tilt=23.44)
    grid = rock.graticule(30)
    assert len(grid) == 17
    pts = np.concatenate([np.asarray(sm.get_points()) for sm in grid])
    r = np.linalg.norm(pts - rock.get_center(), axis=1)
    assert 1.9 < r.min() and r.max() < 2.15      # hugging the surface

    before = np.asarray(grid[0].get_points()).copy()
    rock.shift([1.0, 0.0, 0.0])
    assert np.allclose(np.asarray(grid[0].get_points()), before + [1, 0, 0],
                       atol=1e-6)                # and riding along



def test_the_mesh_stops_at_the_globe():
    """
    The mesh used to shine through the whole planet -- painter's order
    drew it over the texture, back hemisphere and all. The honest look
    is the default now, and the X-ray is an option. Two props hold the
    honest look in this renderer: the overlay asks for its turn after
    the body with z_index (the draw order of equal-index mobjects is
    not stable between renders), and an X-ray overlay re-states its
    freedom every frame, because ThreeDScene.add force-applies the
    depth test to whatever it is handed. The grid is drawn at
    ``OVERLAY_WIDTH`` (2, the light look of notes 2.15): the depth
    test only holds a hugging stroke from about 5 up, so at the
    default a quarter of the far cage still shows. The flags,
    z_index and the updater are the machinery this test guards.
    """
    if _skip():
        return
    from manimgl_myplugin.astro.bodies import (OVERLAY_WIDTH,
                                               SPECIAL_WIDTH_FACTOR)
    earth = Earth(radius=3, shadows=False)
    mesh = earth.graticule(30)
    assert all(line.depth_test for line in mesh)
    assert all(line.z_index == 1 for line in mesh)
    assert mesh.parallel(0).data["stroke_width"][0] == OVERLAY_WIDTH
    xray = earth.graticule(30, see_through=True, follow=False)
    assert all(not line.depth_test for line in xray)
    assert all(line.z_index == 1 for line in xray)
    # the freedom survives ThreeDScene.add, which force-applies the
    # depth test at add time; the updater puts it back every frame
    assert any(line.updaters for line in xray)

    # the other surface overlays carry the same switch, same default
    assert earth.marker(23.8, 90.4).depth_test
    assert earth.arc_between((23.8, 90.4), (51.5, -0.1))[0].depth_test
    assert earth.label(23.8, 90.4, "X", font_size=18).depth_test
    assert earth.terminator().depth_test
    assert not earth.marker(0, 0, see_through=True).depth_test

    # one width for every hugging stroke, the named circles heavier,
    # the axis honest now, its X-ray asked for (notes 2.17)
    # the arc flies rather than hugs -- no leak measured at its
    # light width (notes 2.14); it matches the family default now
    arc = earth.arc_between((23.8, 90.4), (51.5, -0.1), follow=False,
                            edge_dot=False)
    assert arc.data["stroke_width"][0] == 2.0
    assert earth.equator().data["stroke_width"][0] == (
        OVERLAY_WIDTH * SPECIAL_WIDTH_FACTOR)
    axis = earth.axis_line(follow=False)
    assert axis.depth_test and axis.z_index == 1      # honest (2.17)
    xray_axis = earth.axis_line(follow=False, see_through=True)
    assert not xray_axis.depth_test and xray_axis.updaters


def test_any_line_of_the_mesh_can_be_picked_up():
    """Highlighting one line is not a parameter -- it is manim on the
    mobject the grid hands back."""
    if _skip():
        return
    from manimgl_myplugin.astro.bodies import Graticule
    earth = Earth(radius=3, shadows=False)
    mesh = earth.graticule(30)
    assert isinstance(mesh, Graticule)
    assert len(mesh.parallels) == 5 and len(mesh.meridians) == 12
    assert len(mesh) == 17

    p60 = mesh.parallel(60)
    m90 = mesh.meridian(90)
    assert any(p60 is m for m in mesh)
    assert any(m90 is m for m in mesh)
    p60.set_stroke(YELLOW, 4)          # plain manim from here on

    try:
        mesh.parallel(23.44)
        raise AssertionError("23.44 is on no round grid")
    except ValueError as exc:
        assert "latitude_line" in str(exc)

    fancy = earth.graticule(30, highlight=True)
    assert len(fancy) == 17 + 4
    assert len(fancy.specials) == 5    # equator, both tropics, both circles


def test_meridian_line_mirrors_latitude_line():
    if _skip():
        return
    # tilt 0, so the pole really is z and the check can be analytic
    earth = Earth(radius=3, tilt=0, shadows=False)
    line = earth.meridian_line(90.4)
    assert isinstance(line, VMobject)
    assert any(line is m for m in earth.submobjects)   # grafted in
    assert line.depth_test
    assert not earth.meridian_line(0.0, see_through=True,
                                   follow=False).depth_test

    # every point sits on the 90.4E meridian: its azimuth matches the
    # azimuth point_at itself uses for that longitude
    ref = earth.point_at(0.0, 90.4) - earth.get_center()
    ref_az = np.degrees(np.arctan2(ref[1], ref[0]))
    pts = np.asarray(line.get_points())
    lat = np.degrees(np.arcsin(np.clip(
        (pts[:, 2] - earth.get_center()[2]) / earth.radius, -1, 1)))
    az = np.degrees(np.arctan2(pts[:, 1] - earth.get_center()[1],
                               pts[:, 0] - earth.get_center()[0]))
    mid = np.abs(lat) < 85          # the poles themselves are on every lon
    d = np.abs((az[mid] - ref_az + 180) % 360 - 180)
    assert d.max() < 0.5                               # degrees of slack


def test_every_overlay_hands_back_a_mobject():
    """The API system: build with a call, then work on what came back."""
    if _skip():
        return
    from manimgl_myplugin.astro.bodies import Graticule
    from manimlib.mobject.types.dot_cloud import DotCloud
    earth = Earth(radius=3, shadows=False)
    outs = {
        earth.marker(23.8, 90.4): DotCloud,
        earth.arc_between((23.8, 90.4), (51.5, -0.1)): VMobject,
        earth.graticule(30): Graticule,
        earth.label(23.8, 90.4, "X", font_size=18): Mobject,
        earth.terminator(): VMobject,
        earth.latitude_line(60): VMobject,
        earth.meridian_line(90): VMobject,
        earth.equator(): VMobject,
    }
    for mob, kind in outs.items():
        assert isinstance(mob, Mobject) and isinstance(mob, kind)

def test_terminator_faces_the_light():
    if _skip():
        return
    body = Body(radius=3)                        # no tilt, no texture: a sphere
    light = np.array([9.0, -4.0, 3.0])
    line = body.terminator(light)
    pts = np.asarray(line.get_points())
    d = light - body.get_center()
    dots = (pts - body.get_center()) @ d
    # every point sees the light on its horizon: surface ~ perpendicular to it
    assert np.abs(dots).max() < 0.05 * np.linalg.norm(d) * 3
    r = np.linalg.norm(pts - body.get_center(), axis=1)
    assert 2.9 < r.min() and r.max() < 3.1


def test_surface_text_curves_onto_the_globe():
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    tag = earth.surface_text("DHAKA", 23.8, 90.4, font_size=26)
    assert any(tag is m for m in earth.submobjects)     # painted on, it follows
    pts = tag.get_all_points()
    r = np.linalg.norm(pts - earth.get_center(), axis=1)
    a = np.radians(23.8)
    shell = np.sqrt((earth.radius * np.cos(a)) ** 2
                    + (earth.radius * earth._polar_scale() * np.sin(a)) ** 2)
    assert np.abs(r - shell * 1.015).max() < 0.03      # every point on the shell


def test_shed_overlays_takes_the_body_back_to_birth():
    """Markers, arcs, anchors and decals all graft in; one call must take
    every one back off without moving the body."""
    if _skip():
        return
    earth = Earth(radius=3, shadows=False)
    base = len(earth.submobjects)
    c0 = earth.get_center().copy()
    earth.marker(23.8, 90.4)
    earth.arc_between((23.8, 90.4), (51.5, -0.1))
    lbl = earth.label(23.8, 90.4, "X", font_size=20)
    earth.surface_text("Y", 0.0, 0.0, font_size=20)
    assert len(earth.submobjects) > base

    earth.shed_overlays()
    assert len(earth.submobjects) == base
    assert not earth._overlays
    assert np.allclose(earth.get_center(), c0, atol=1e-9)
    # the shed label's updater must no longer pull on anything live
    assert lbl.updaters
    earth.shed_overlays()      # a second shed is a quiet no-op


def test_cell_note_names_the_right_corner():
    import shutil
    if _skip():
        return
    if shutil.which("latex") is None or shutil.which("dvisvgm") is None:
        print("      (no latex toolchain -- the Tex half waits for it)")
        return
    earth = Earth(radius=3, shadows=False)
    note = earth.cell_note(23.8, 90.4, index=2, step=30)
    assert len(note) == 2
    from manimlib.mobject.svg.tex_mobject import Tex
    assert isinstance(note[0], Tex)
    # the ring sits on the north-east corner of the (0..30, 90..120) cell
    p = earth.point_at(30, 120, 0.02)
    d = np.linalg.norm(np.asarray(note[1].get_points()) - p, axis=1)
    assert abs(d.max() - d.min()) < 0.02          # a rigid ring, one radius
    assert d.mean() > 0.05


def test_colour_reaches_the_glyph_fills():
    """
    manimlib's Text/Tex take ``color`` to Pango but the glyph fills come
    back white -- measured while filming BnCurve, when a gold word came
    out grey (notes 2.19). Every text route in the plugin now carries
    ``color`` over with ``set_fill``, and this holds it there.
    """
    if _skip():
        return
    from manimlib import Circle
    gold = "#F2B33D"
    wanted = Circle().set_fill(gold, opacity=1.0).uniforms["fill_rgba"]

    earth = Earth(radius=3, shadows=False)
    routes = (
        earth.surface_text("X", 0, 0, color=gold, follow=False),
        earth.surface_tex("day $t$", 0, 0, color=gold, follow=False),
        earth.surface_mathtex(r"\omega", 0, 0, color=gold, follow=False),
        earth.label(0, 0, "X", color=gold, follow=False),
    )
    for mob in routes:
        got = mob[0].uniforms["fill_rgba"]
        assert np.allclose(got, wanted, atol=1e-3), (mob, got, wanted)

    # the graticule's little value tags ride the same road
    grid = earth.graticule(30, labels=True)
    for sub in grid:
        for sm in sub.get_family():
            if type(sm).__name__ == "Text" and sm.has_points():
                assert not np.allclose(
                    sm.uniforms["fill_rgba"][:3], 1.0, atol=1e-3)


# ----------------------------------------------------------- the star --


def test_the_suns_row_matches_published_values():
    sun = BODIES["sun"]
    assert sun.equatorial_radius_m == 696_340_000
    assert abs(sun.rotation_period_h - 609.12) < 0.01    # 25.4 days
    assert abs(sun.axial_tilt_deg - 7.25) < 0.01         # to the ecliptic
    assert not sun.solid                                  # nothing to stand on
    assert texture_url(sun.texture).endswith("/2k_sun.jpg")


def test_sun_is_a_body_with_six_shells():
    if _skip():
        return
    sun = Sun(radius=1.6)
    assert isinstance(sun, Body)
    assert sun.facts.name == "Sun"
    assert len(sun.corona) == len(CORONA_SHELLS) == 6
    # the lift first, the widest shell last, at the measured multiples
    mults = [shell.radius / sun.radius for shell in sun.corona]
    assert np.allclose(mults, [row[0] for row in CORONA_SHELLS], rtol=1e-12)
    assert mults == sorted(mults)
    # the globe is the light, not something lit -- no shading on it
    assert np.allclose(sun.globe.uniforms["shading"], 0.0)


def test_the_corona_is_light_not_paint():
    if _skip():
        return
    for shell in Sun(radius=1.6).corona:
        assert shell.blend_mode == "add"       # adds to what is behind
        assert shell.depth_write is False      # leaves the depth buffer alone
        assert shell.z_index == 1              # above the z-0 world
    # every shell but the flat lift fades towards its own edge
    powers = [row[1] for row in CORONA_SHELLS]
    assert powers[0] is None
    assert all(p is not None for p in powers[1:])


def test_the_corona_is_the_body_not_an_overlay():
    if _skip():
        return
    assert len(Sun(radius=1.6, corona=False).corona) == 0
    sun = Sun(radius=1.6)
    sun.marker(23.8, 90.4)
    sun.shed_overlays()
    # shedding takes the marker back, never the glow
    assert len(sun.corona) == 6


def test_named_knows_the_sun():
    if _skip():
        return
    assert isinstance(named("sun"), Sun)


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
