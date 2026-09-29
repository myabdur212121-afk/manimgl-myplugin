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

### 2.6 Construction that looked 40× too slow

First `Saturn()` took 42 seconds; timing each stage showed 1.1 s of work
and the rest was downloading textures. Time the parts before optimising
anything.

### 2.7 The Sahara came out in the Pacific

| | |
| --- | --- |
| **Symptom** | Markers placed by latitude and longitude landed nowhere near the right country, though they sat correctly on the surface. |
| **Cause** | An equirectangular texture starts at longitude −180 on its left edge; `revolve` starts its sweep on the +x axis. The map is therefore half a turn round from the maths, and `point_at` was using the maths. |
| **Fix** | `point_at` adds 180° to the longitude before building the vector. |
| **Guard** | `test_point_at_agrees_with_the_texture` — samples the real texture at five named places and checks land is land. |

Nothing about the render looked wrong; the dots sat neatly on the globe.
Only naming a place and checking the colour underneath caught it.

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

Tests: `python tests/test_astro.py` — 29 checks, about 20 s (the first run
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

---

## 6. If you are picking this up

1. `python tests/test_astro.py` — the first run pulls a few textures.
2. If a shadow seems missing, check where the sun is before checking the
   code. See 2.2.
3. To add a body, add a row to `BODIES` in `data.py` and a line at the
   bottom of `bodies.py`. No new behaviour should be needed; if it is,
   that is worth a second look.
