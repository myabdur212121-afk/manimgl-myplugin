> Part of [manimgl_myplugin](../../README.md).

# The `astro` helper — working notes

Read this before changing anything.

---

## 1. What this is

Planets, moons and rings. `data.py` is a table of measured facts — radius,
flattening, axial tilt, texture name, ring edges. `bodies.py` turns a row
of that table into a `Group`: a globe from `shapes.revolve`, plus flat ring
annuli from the same function, painted by the `obj` helper.

The named classes hold no behaviour at all, only facts. That is the whole
point: nobody should have to look Saturn's oblateness up twice.

---

## 2. Problems faced, and what fixed them

### 2.1 A 4k texture that was really an error page

| | |
| --- | --- |
| **Symptom** | `Mars(quality="4k")` raised `HTTPError 404` from urllib, while `curl -L` on the same URL reported **200**. |
| **Cause** | Solar System Scope publishes **2k and 8k only**. Asking for 4k returns a 16 KB HTML error page; `curl -L` follows it and calls the result a success. My earlier probe had been fooled by exactly this. |
| **Fix** | `quality="4k"` fetches the 8k once and halves it with Lanczos. A real 4k map, cached, and the user gets what they asked for. |
| **Guard** | `test_named_and_quality` |

Check the MIME type, not the status code, when probing a download.

### 2.2 A ring shadow nobody could see

| | |
| --- | --- |
| **Symptom** | Shadows on, shadows off — Saturn looked identical. |
| **Cause** | Two separate things. First the arithmetic: `shade = 1 - opacity*(1 - darkness)` with `darkness=0.78` and `opacity=0.85` works out to 0.81, a 19% dip nobody would notice. The parameter name said darkness but the number behaved like brightness. |
| **Fix** | Renamed to `shadow_strength`, where 1 means a fully opaque band blocks everything: `shade = 1 - opacity * strength`. At 0.85 the shadow drops to 0.28. |
| **Guard** | `test_shadow_strength_controls_how_dark` |

The second thing was not a bug: with the sun high above the ring plane the
shadow falls on the winter hemisphere, which is already dark. It shows near
equinox, sun close to the ring plane — as it does on the real planet. Worth
knowing before assuming the code is broken.

### 2.3 Nowhere to paint the shadow on the globe

| | |
| --- | --- |
| **Symptom** | The obvious approach — darken the globe's vertices where the rings cross — has nothing to darken. |
| **Cause** | `OBJTextured` wraps ManimGL's `TexturedSurface`, whose per-vertex data is point, im_coords and opacity. Colour comes from the image. There is no rgb to touch. |
| **Fix** | Compute the shadow in **texture space** instead: build a lat/lon grid, intersect each point's ray to the sun with the ring plane, darken the texels that land between a band's edges. Half resolution and resampled up, which is both faster and softer — a real ring shadow has a penumbra. Cached by light direction. |
| **Guard** | `test_the_rings_shadow_the_globe` |

### 2.4 Soft transparency that the shader throws away

Reading `textured_surface.wgsl` before designing the rings saved a lot of
time:

```wgsl
if (color.a == 0.0) { discard; }     // a hard cutout works
result.a = in.opacity;               // partial alpha is overwritten
```

So a ring cannot be made semi-transparent by its texture. Opacity has to
come from the **vertices**, which is why `_paint_band` samples the ring
strip into per-vertex rgba rather than handing the PNG to `textured()`.
It also means the rings can be darkened for the planet's shadow, which a
textured surface could not be.

### 2.5 A flat ring that went black from below

`add_light` darkens by the `shadow` term wherever `dot(normal, to_light)`
is negative. A flat annulus seen from the unlit side is exactly that.
Rings are built with `shading=(0, 0, 0)`; they scatter light rather than
reflecting it off a surface, so no shading is the physical answer as well
as the convenient one.

### 2.6 A tilted planet that wobbled instead of spinning

| | |
| --- | --- |
| **Symptom** | `earth.add_updater(lambda m, dt: m.rotate(0.3 * dt, OUT))` made the pole swing round in a circle rather than the planet turning under it. |
| **Cause** | `OUT` is the *scene's* z axis. Earth's pole leans 23.44° away from it, so rotating about OUT precesses the pole instead of spinning the body. Measured: 90° about OUT moves the pole 32.7°; 90° about its own axis moves it 0.0°. |
| **Fix** | `body.axis`, `spin()` and `turn()`. The axis is read from the pole vertex of the mesh rather than recomputed from the tilt, so it stays right after the body is moved or rotated. |
| **Guard** | `test_spin_leaves_the_pole_alone_but_rotate_does_not` |

A sphere gives no clue here: rotating it does not change its silhouette,
and its topmost *vertex* is not its pole. The pole has to be found through
the UVs.

### 2.7 Construction that looked 40× too slow

First `Saturn()` took 42 seconds; timing each stage showed 1.1 s of work
and the rest was downloading textures. Time the parts before optimising
anything.

### 2.8 The Sahara came out in the Pacific

| | |
| --- | --- |
| **Symptom** | Markers placed by latitude and longitude landed nowhere near the right country, though they sat correctly on the surface. |
| **Cause** | An equirectangular texture starts at longitude −180 on its left edge; `revolve` starts its sweep on the +x axis. The map is therefore half a turn round from the maths, and `point_at` was using the maths. |
| **Fix** | `point_at` adds 180° to the longitude before building the vector. |
| **Guard** | `test_point_at_agrees_with_the_texture` — samples the real texture at five named places and checks land is land. |

Nothing about the render looked wrong; the dots sat neatly on the globe.
Only naming a place and checking the colour underneath caught it.

### 2.9 An overlay that moved the body underneath it

| | |
| --- | --- |
| **Symptom** | After adding an arc, a marker's height above the surface read 2.819 instead of 3.000, and `point_at` answers drifted the more you added. |
| **Cause** | `Mobject.get_center()` is the bounding-box centre of the whole family. Grafting an asymmetric overlay — one arc, one marker, one label anchor — into the `Group` moved that centre, and every lat/lon computation is measured from it. |
| **Fix** | `Body.get_center()` now returns the globe's centre, with a `has_points()` guard and a fallback to `super()`. Overlays must never move where the body thinks it is. |
| **Guard** | `test_an_overlay_does_not_move_the_body` — centre and one `point_at` reading, before and after grafting an arc and a marker. |

The arc maths was exact; the ruler had moved. Isolating the arc from the
body proved that before anything else got touched.

### 2.10 Pinned text that never pinned

| | |
| --- | --- |
| **Symptom** | A `label()` stood where it was born and never tracked the body — yet the tests passed, because they only counted updaters. |
| **Cause** | manimgl's `Text` is a `VMobject` whose glyph outlines live on **submobjects**; the parent's own `get_points()` is empty. `_pinned_text` captured that empty array, so every re-pin was a `set_points` of nothing — a silent no-op. |
| **Fix** | Capture and re-set the points per family member (every submobject that `has_points()`), about the whole mob's centre. `place_on_surface` had the same disease and the same cure. |
| **Guard** | `test_a_label_stays_pinned_and_readable` now checks the position and the facing for real — and `test_surface_text_curves_onto_the_globe` checks every painted point sits on the shell. |

The lesson generalises: in manimgl, never trust `get_points()` on a
mobject you did not build point-by-point. `get_all_points()` is the
family-aware reader; tests should use it too.

### 2.11 A `Tex` that would not compile on a clean machine

| | |
| --- | --- |
| **Symptom** | `cell_note` died with `LatexError: Missing } inserted` from a formula that looked fine, after an earlier `dsfont.sty not found`. |
| **Cause** | Two layers. The stock manimgl preamble loads `dsfont`, `tipa` and `physics` but Debian's default texlive pull installs none of them; and no package in that preamble defines `\degree`, so the `P₂ (30°, 120°)` formula was doomed even once the preamble loaded. |
| **Fix** | Write the degrees as `^{\circ}` — the manim idiom — and give the sandbox dsfont/tipa stand-in stubs plus `texlive-science` for physics. |
| **Guard** | `test_cell_note_names_the_right_corner` — and it skips its Tex half with a note if the latex toolchain is absent. |

A failed `Tex` compile is a hard error, not a fallback: worth remembering
when a scene suddenly dies on a machine that rendered fine yesterday.

### 2.12 A mesh that shone through the planet

| | |
| --- | --- |
| **Symptom** | The graticule was visible from the far side: lines ran straight through the texture, as if the globe were glass. |
| **Cause** | Painter's order. ManimGL draws mobjects in the order they were added, and the mesh is added after the globe — so it painted over the texture, back hemisphere and all. The globe had been writing depth all along (`OBJMobject` defaults `depth_test=True`); the lines simply never tested it. |
| **Fix** | `apply_depth_test()` on the overlay, wrapped in one place: `_apply_occlusion`. Every surface overlay now defaults to the occluded, honest look and takes `see_through=True` for the X-ray view. |
| **Guard** | `test_the_mesh_stops_at_the_globe` — the flag and the draw order on every line of the grid, plus marker, arc, label and terminator. |
| **Correction** | The first proof quoted for this entry — 6,164 blue pixels before against 2,782 after — was not the depth test at all. That probe frame held two globes side by side, and the renderer had drawn the left grid between the two globes and the right grid after both (confirmed by instrumenting the draw passes), so the left half shone through for want of any globe depth to test against and the right half did not. The numbers measured the draw order, not the fix. What the fix really buys, measured properly after 2.13, is 28,668 blue pixels occluded against 62,095 X-ray at width 8 — the near hemisphere's wires and no more. |

The same message carried the API rule that had been forming: **a call
builds, returns a mobject, and the work happens on that mobject.**
Highlighting one line of a grid is not a parameter — `mesh.parallel(60)`
hands you the line and manim does the rest. Parameters stayed only for
what the hand cannot reach: the named circles, which the grid does not
draw until asked.

### 2.13 Three ways this renderer hides a line — and the one it keeps

| | |
| --- | --- |
| **Symptom** | After 2.12 the video still showed no difference between the honest mesh and `see_through=True`: the two acts measured 2,906 against 2,866 blue pixels, a ratio of 0.99. |
| **Cause 1** | `ThreeDScene.add` force-applies the depth test to every mobject it is handed, so an X-ray grid had its `depth_test` flag flipped back on the moment it was added. The freedom lasted until the add. |
| **Cause 2** | The draw order of equal-`z_index` mobjects is not stable between renders: the same two-globe scene drew its passes as globe–grid–globe in one render and globe–globe–grid in the next (instrumented with a spy on `draw_pass`). A depth-tested overlay only occludes when its body's depth is already in the buffer, so the look could change from render to render. |
| **Cause 3** | A perpendicular stroke only holds at the depth test once it is a few pixels wide. At the mesh's old width (1.6) the far side sails through whatever the flags say: one mixed grid measured 3,154 pixels against a 2,670 alone-reference, *more* with a globe in the way than without. At width 3 it half-leaks (0.61 of the reference), at width 10 it holds (0.46). The clip planes are no way round it either: the clip distance is evaluated at the stroke ribbon's corners, and a hugging circle's miter shift carries those corners across any horizon plane — a hand-built meridian ring kept 97% of its pixels through a clip that should have taken half, at every width tried. Re-measured on 2026-10-04, this time on the delivered API itself — a magenta `graticule(30)` on a plain radius-2.4 globe at the demo framing (frame 8.6, reorient −18/66, 720p) — the curve is gentler than the hand-built probe suggested: the occluded grid keeps 0.496 of its X-ray self at width 3, 0.471 at 4, 0.453 at 5, 0.449 at 6, 0.444 at 7 and 0.441–0.445 at 8–12. The asymptote, 0.443, is the near hemisphere itself, so the leak is the excess over it: +5.3% of the curve's pixels at 3, +2.8% at 4, +1.0% at 5, +0.6% at 6, +0.1% at 7. The floor moves with the framing — the hand-built probe read worse at its own — so a default wants a margin above the knee, and under spin plus a drifting camera widths 5 and 6 held their counts to 0.6% and 1.3% over 3 s. |
| **Fix** | Three props in `_apply_occlusion`: every overlay takes `z_index=1` so it always draws after its body whatever order the renderer assembles; the X-ray variant carries an updater that re-states `depth_test=False` every frame, outlasting the scene's force-apply (`clear_updaters()` takes manual control back); and the grid lines default to width 8, wide enough for the depth test to mean it. |
| **Measure** | Two renders each, identical pixel for pixel: occluded 28,668, X-ray 62,095 (ratio 0.46); and under spin plus a drifting camera the occluded count holds at 28,713–29,053 across 3 s. The fill overlays (markers, labels) need no width — squares behind the globe were hidden at any size. |
| **Guard** | `test_the_mesh_stops_at_the_globe` — flags, `z_index`, width 8 and the surviving updater. |

---

## 3. Directions that do not work

| Idea | Why it fails |
| --- | --- |
| **Trusting an HTTP 200 from a texture CDN** | See 2.1. A missing file comes back as an HTML page. |
| **Alpha in the ring texture for soft transparency** | The shader overwrites it. Per-vertex opacity instead. |
| **Making the Cassini Division transparent** | Same reason, and worse — it is a real gap, so make it a real hole. B stops at 1.951, A starts at 2.027. |
| **Darkening the globe's vertices for the ring shadow** | A textured surface has no vertex colour. Work in texture space. |
| **Rebaking the globe shadow every frame** | Repainting a 4k JPEG takes about a second. `follow_light` updates the rings each frame and the globe only every *n*th. |
| **Leaving `shading` on for the rings** | They go black from underneath. |
| **`rotate(OUT)` to spin a tilted body** | Precesses the pole. Use `spin()`. |
| **Trusting lat/lon without checking the map** | The texture is half a turn round from the maths. Sample it. |
| **Expecting relief at true scale** | Olympus Mons is 0.65% of Mars' radius. Without `exaggeration` there is nothing to see. |
| **`VGroup` around an `ImageMobject`** | VGroup refuses non-VMobjects. Plain `Group`. |
| **Reading `get_points()` off a `Text`** | Empty — the glyphs hold the points. See 2.10. |
| **`\degree` in a `Tex`** | Nothing in the stock preamble defines it. `^{\circ}`. |
| **A camera-facing label** | A mobject does not know where the camera is. The label is an upright billboard on the tangent plane; that is the honest limit. |
| **A `highlight_line`-style parameter for one grid line** | The grid hands back a mobject; `mesh.parallel(60).set_stroke(...)` already does it. Parameters only for what the hand cannot reach. |
| **`np.arange(-180 + step, 180, step)` for meridians** | Drops the ±180 column — 16 lines at step 30 where the parallels promise 17. Start at −180: the duplicate is the seam, same as the mesh. |

---

## 4. Numbers to expect

| | |
| --- | --- |
| `Mars(radius=3)` | 36,096 triangles, ~0.4 s with textures cached |
| `Saturn(radius=3)` | 36,096 globe + 36,000 ring = 72,096, ~1.1 s |
| first run, per body | 5–40 s, almost all of it the texture download |
| `2k_mars.jpg` | 750 KB · `8k_mars.jpg` 8.1 MB · derived `4k_mars.jpg` 2.3 MB |
| ring shadow bake | ~0.6 s at 1024×512, cached by light direction |
| Saturn flattening | 0.098 — the globe really is a tenth shorter pole to pole |
| `graticule(30)` | 17 lines — 5 parallels, 12 meridians, radius 3.002–3.012 |
| occlusion probe | width 8, one globe: 28,668 blue pixels occluded, 62,095 through (`see_through=True`) |
| Earth g cross-check | G·M/R² from the table matches the quoted 9.80 to within 0.02 |

Tests: `python tests/test_astro.py` — 46 checks, about 40 s (the first run
downloads textures).

---

## 5. What this will never do

- **No real shadows.** The two that exist are solved for this one geometry
  — a sphere and a flat annulus — and painted in. A moon will not cast a
  shadow on its planet, and nothing casts a shadow on anything else.
- **No orbits.** These are bodies, not a solar system. Position them
  yourself.
- **No atmospheres, no limb darkening, no clouds as a separate layer.**
  Venus is the cloud deck because that is the only texture there is.
- **No rotation rates, no ephemeris.** `add_updater` and pick a speed.
- **Gas giants have no elevation data** because they have no surface. That
  is not a gap in the helper.
- **No flattening the globe into a map.** `flat_map()` was built — the
  equirectangular unwrap at its true 2:1 — and then taken back out at
  review: effects multiply, and an unused one is surface area that still
  has to be maintained. When a scene needs a map, an image beside the
  globe says the same thing with nothing to maintain.
- **`terminator` is exact for a sphere only.** On a flattened body it is
  drawn on the sphere of the equatorial radius — right at the equator,
  a fraction of a percent off towards the poles.
- **`place_on_surface` is a tangent-plane decal.** Small against the
  radius it is faithful; continent-sized it distorts, as any flat
  projection must. `surface_text` inherits the same limit.
- **Moon counts are a date, not a truth.** Mid-2026 confirmed counts,
  still rising; Saturn was 274 within living memory.

---

## 6. If you are picking this up

1. `python tests/test_astro.py` — the first run pulls a few textures.
2. `cell_note` and any `Tex` need latex + dvisvgm, plus the packages the
   stock manimgl preamble loads: on Debian, `texlive-science` for physics,
   and dsfont/tipa stubs if you skip `texlive-fonts-extra` (see 2.11).
2. If a shadow seems missing, check where the sun is before checking the
   code. See 2.2.
3. To add a body, add a row to `BODIES` in `data.py` and a line at the
   bottom of `bodies.py`. No new behaviour should be needed; if it is,
   that is worth a second look.
