> Part of [manimgl_myplugin](../../README.md). This page is the full
> specification of the `astro` helper.

# The `astro` helper — reference

Planets, moons and rings that already know their own numbers.

```python
from manimgl_myplugin.astro import Mars, Saturn

self.add(Mars(radius=3))
self.add(Saturn(radius=3, quality="4k"))
```

A body is a `Group` of a globe and, where there are any, a set of flat ring
annuli. Both are ordinary meshes from `shapes.revolve` painted by the `obj`
helper, so `wireframe`, `point_cloud` and `BuildMesh` work on them too.

---

## The bodies

| class | radius (km) | flattening | tilt | rings |
| --- | --- | --- | --- | --- |
| `Mercury` | 2,440 | 0 | 0.03° | |
| `Venus` | 6,052 | 0 | 177.4° | cloud deck, not the surface |
| `Earth` | 6,378 | 0.0034 | 23.44° | day map + night map |
| `Moon` | 1,737 | 0.0012 | 6.68° | |
| `Mars` | 3,396 | 0.0059 | 25.19° | |
| `Jupiter` | 71,492 | 0.0649 | 3.13° | one faint band |
| `Saturn` | 60,268 | **0.0980** | 26.73° | C, B, A with the Cassini gap |
| `Uranus` | 25,559 | 0.0229 | **97.77°** | rings stand up |
| `Neptune` | 24,764 | 0.0171 | 28.32° | Adams ring |

Saturn is a tenth flatter at the poles than at the equator, and it shows.
Earth's 0.3% does not.

Every body also carries its numbers: mass, surface gravity, orbit size and
period, mean temperature and moon count — `earth.info()` prints the lot,
and `earth.facts` is the raw `BodyFacts`. Two of those decay: moon counts
are confirmed counts as of mid-2026 and still rising (Saturn passed 290 in
2025), and the Moon's orbit row is measured **around Earth**, not the Sun.

`named("mars", radius=3)` when the name is in a variable; `BODIES` is the
raw table.

---

## The Sun and its corona

```python
sun = Sun(radius=1.6)
self.camera.light_source.move_to(sun.get_center())   # light the others from it
self.add(sun)
```

`Sun` is a `Body` like the rest — same radius, quality and resolution
parameters — with two differences: the globe is shaded flat, because it is
the light rather than something lit by one, and around it go **six
concentric shells of light**, the corona.

This is real geometry, not a picture glued to the camera. Each shell is an
inverse-fresnel sphere — brightest facing the body, fading to nothing at
its own edge — drawn with **additive blend** and **no depth writing**.
Because the shells sit in the scene like everything else:

- a planet **in front** of the sun cuts the glow — a transit leaves the
  light 39% darker at the planet's disc,
- a planet **behind** it is drawn under the light — the glow lies over
  it, no black dot (a night-side body reads as a dim patch, a lit one
  shines through the haze),
- a planet **behind the disc** is hidden by it, by the ordinary depth test.

The shell opacities are fitted, not chosen: each shell was rendered on its
own, its response measured, and the six fitted by nnls against a
limb-to-3.1R falloff (684 → 71); the assembled scene lands on the same
profile within five percent. The table is `CORONA_SHELLS` in `bodies.py`,
and `sun.corona` is the group of six if you ever want to reach one.

### The renderer patch

`blend_mode="add"` and `depth_write=False` are read by a **patched
manimlib** — upstream draws everything with ordinary alpha blend, and a
tint can only darken a bright background, never add to it. The patch is
112 lines across two renderer files, kept at
`manim-handover/patches/manimgl-glow-renderer.patch`:

```bash
git apply manimgl-glow-renderer.patch    # inside your manim checkout
```

Without it, everything in this package still builds and runs — the shells
just draw as flat veils, and a warning says so at construction.

### Parameters

`corona=True` — `False` leaves the star bare. `corona_resolution=(128, 64)`
is the mesh of each shell. Everything else is `Body`'s own list.

### Limits, said plainly

- Beyond about 2.7 radii the outer tail is a **surface** of light, not a
  volume: a body passing behind the very outer shell at a grazing angle
  can look covered where a true corona would let its light pass.
- The corona adds light around the sun only. It is not scene-wide bloom:
  bright pixels elsewhere do not spill onto their neighbours.
- The sun does not light the other bodies by itself — move the scene's
  light onto it (above), or every planet keeps its default lighting.

---

## Parameters

```python
Body(
    radius=3.0,                  # scene units
    quality="2k",                # "2k" | "4k" | "8k"
    resolution=(192, 96),        # globe mesh, not texture sharpness
    ring_resolution=(180, 110),  # segments around, steps per planet radius
    shadows=True,
    shadow_strength=0.85,        # 1 = an opaque ring blocks everything
    rings=True,                  # or False, or a list of RingBand
    tilt=None,                   # degrees; defaults to the real value
    texture=None,                # override the map
    night_texture=None,          # False turns Earth's night lights off
    dem=None,                    # a height map, if you have one
    exaggeration=20.0,
    light=None,                  # where the sun is when shadows are baked
)
```

Plus `spin`, `stop_spin`, `turn` and the `axis` property — see *Turning*.

### `quality`

Solar System Scope publishes **2k and 8k only**. Asking their server for 4k
returns an HTML error page that looks like a successful download, which is
a good way to end up with a corrupt JPEG. So `quality="4k"` fetches the 8k
once and halves it locally — a real 4k map, cached in `~/models`.

The mesh does not change with quality. The texture is looked up per pixel,
so a 192×96 globe with an 8k map is still sharp.

### `shadows` and `shadow_strength`

The renderer has no shadows at all. But a sphere and a flat annulus are
simple enough to intersect directly, so both shadows are solved and painted
in:

- **Planet across the rings** — for each ring vertex, does the line to the
  sun pass within one planet radius of the centre? Squashing z by the
  flattening first turns the oblate spheroid into a unit sphere and makes
  the test exact. Darkens the vertex colours.
- **Rings across the planet** — a textured surface takes its colour from
  the image, not the vertices, so there is nowhere to darken a point.
  The mask is computed in texture space instead, at half resolution and
  resampled up, which is sharper than the mesh and gives a soft edge for
  free. The result is cached.

`shadow_strength` is how much light a fully opaque band blocks: 1 is total,
0 is none. Each band is scaled by its own opacity on top, so the thin C
ring casts a fainter shadow than B.

**Where the shadow lands.** With the sun high above the ring plane the
shadow falls on the winter hemisphere, which is already in darkness, and
you will not see it. It shows best near equinox, with the sun close to the
ring plane. That is true of the real planet too.

```python
saturn.bake_shadows(light=np.array([-13, -9, 0.8]))   # redo after moving the sun
saturn.follow_light(self, every=15)                    # track it during a scene
```

`follow_light` updates the rings every frame and the globe every `every`
frames, because repainting a 4k texture 30 times a second is not possible.

### Turning

`rotate()` is manim's own and turns the body about an axis of the **scene**.
For a tilted planet that is almost never what you want: the pole swings
round in a circle instead of the planet spinning underneath it.

`spin()` and `turn()` use `body.axis` — the body's own pole, read from the
mesh so it stays correct after you move or rotate the body.

```python
self.add(Earth().spin(0.3))          # radians per second, forever
self.add(Mars().spin(period=8))      # one full turn every 8 seconds
self.add(Jupiter().spin(day=3))      # one Earth day = 3 seconds

self.play(earth.turn(PI))                                  # half a turn
self.play(earth.turn(TAU, run_time=5, rate_func=smooth))   # with easing

earth.stop_spin()
```

`day=` scales every body by its real sidereal period, so Jupiter (9.9 h)
visibly outruns Mars (24.6 h), and Venus and Uranus turn **backwards**
because they really do.

| | period (h) | | period (h) |
| --- | --- | --- | --- |
| Mercury | 1407.6 | Jupiter | 9.93 |
| Venus | **−5832.5** | Saturn | 10.66 |
| Earth | 23.93 | Uranus | **−17.24** |
| Moon | 655.7 | Neptune | 16.11 |
| Mars | 24.62 | | |

`turn()` returns a `Rotating`, so every animation argument works —
`run_time`, `rate_func`, `lag_ratio`.

### Geography and motion

Everything here follows the body: tilt it, move it, spin it, and the
answers move too.

```python
earth.point_at(23.8, 90.4)                        # Dhaka, in scene coords
earth.point_at(23.8, 90.4, height=0.1)            # lifted off the surface
earth.marker(23.8, 90.4)                          # a dot pinned to a place
earth.arc_between((23.8, 90.4), (51.5, -0.1))     # great-circle flight path
earth.graticule(step=30)                          # the lat/lon grid
earth.axis_line()                                 # the pole, drawn

earth.label(23.8, 90.4, "Dhaka")                  # readable text at a place
earth.cell_note(23.8, 90.4, index=2)              # name a grid cell corner
earth.place_on_surface(tag, 23.8, 90.4)           # bend a flat thing on
earth.surface_text("DHAKA", 23.8, 90.4)           # ...the short form
earth.surface_tex(r"P_2", 30, 120)                # LaTeX, painted on
earth.surface_point(23.8, 90.4)                   # paint, not a pin -- grows with the zoom
earth.meridian_line(90.4)                         # one line of longitude

earth.equator(); earth.tropics(); earth.polar_circles()
earth.terminator(light)                           # the day/night line

moon.orbit(earth, radius=5.2, period=9, tilt=12)
moon.stop_orbit()
```

Latitude and longitude are degrees, north and east positive, **lined up
with the texture** — `point_at(23, 13)` really is in the Sahara. That
needed a half-turn correction: the texture's left edge is longitude −180
while `revolve` starts its sweep on +x, and without it the Sahara came
out in the middle of the Pacific. There is a test that samples the map
and checks land is land.

`orbit` and `spin` compose — a moon can circle a planet while turning on
its own axis.

### Overlays that follow the body

`marker`, `arc_between` and `graticule` take `follow=True` by default:
the result is grafted into the body's family, so it rides along with
every shift, spin, tilt and orbit. Pass `follow=False` for the old
detached behaviour — you position it yourself. Anything grafted after
construction is remembered, and `earth.shed_overlays()` takes the lot
back off — handy between acts of a scene, where a `FadeOut` hides an
overlay but leaves it in the family.

Every surface overlay also takes `see_through=False`. The default is
the honest look: a line that has gone round the back of the globe is
hidden by it. `see_through=True` keeps the whole cage shining
through — useful when the *point* is that a globe is a cage, wrong
for almost everything else. The switch is more than a flag (this
renderer has three ways to hide a line, see notes 2.13): the overlay
draws after its body because it asks for the turn with `z_index`,
an X-ray overlay re-states its freedom every frame so that
`ThreeDScene.add` cannot take it back, and every hugging stroke is
drawn at `OVERLAY_WIDTH` (2) — the light look, chosen with the
trade measured: a thin stroke slips past the depth test in this
build (the floor is 5), so at the default roughly a quarter of the
far cage still shows through the globe, and `width=6` is where the
line is hidden completely (notes 2.14, 2.15). The named circles run
`SPECIAL_WIDTH_FACTOR` (1.4×) heavier, gold. `arc_between` matches
the family at 2.0 and flies, where no leak was measured. One
deliberate exception stays: `axis_line` is a thin X-ray guide, so
the buried middle of the pole stays visible while you watch a spin.
`clear_updaters()` on a returned X-ray mobject takes back manual
control.

The API system is: **a call builds, returns a mobject, and the work
happens on that mobject with ordinary manim.** Parameters exist only
for what your hand cannot reach once you hold the mobject.

`label(lat, lon, text, ...)` pins **readable** text to a place: the
position tracks the body through every move, and the text re-uprights on
the tangent plane each frame, so it never ends up on its side or facing
into the globe. It is a billboard on the tangent plane, not a camera
facing sprite (manimgl mobjects do not know where the camera is) and not
a rigid painting — the letters do not tumble with the planet. `height`
lifts it off the surface, `buff` stands it further off, and every other
keyword reaches manimgl's `Text` — `font_size`, `font`, `color`.

`cell_note(lat, lon, index)` names one corner of the graticule cell a
place falls in: a `P_i` tag and a three-quarter ring at the corner. The
corners run SW, SE, NE, NW from `index=0`, so the north-east corner of
Dhaka's 30° cell is `cell_note(23.8, 90.4, index=2)` → `P₂ (30°, 120°)`.
Keywords reach the `Tex`.

Anything that builds a mobject for you passes its keywords through:
`marker` → `DotCloud` (`radius`, `glow_factor`, `opacity`), `label` and
`surface_text` → `Text`, `cell_note` → `Tex`, and the line-drawing calls
→ `set_stroke`.

### Painting on the surface

`place_on_surface(mob, lat, lon)` reads the mobject's plane as the
tangent plane at that point — its x becomes east, its y north — and maps
every point, bezier handles included, onto the globe. `surface_text(...)`
is the same thing for a piece of text. For a decal short against the
radius the result is faithful; stretch it across a hemisphere and the
projection distortion shows, as it does on any flat map. With
`follow=True` (the default) the paint rides along with every move.

### The named circles, and the terminator

`graticule` is the same idea as ManimGL's `SurfaceMesh`, for a globe: a
plain mesh of blue lines with nothing special about any of them, drawn
from the body's geometry so it works on **every** body — textured or
not. It takes a tuple step `graticule((20, 40))`, and hands back a
`Graticule` — a mobject, so one line is picked up by hand:

```python
mesh = earth.graticule(30)
mesh.parallel(60).set_stroke(YELLOW, 4)     # any one parallel
mesh.meridian(90).set_stroke(YELLOW, 4)     # any one meridian
```

`mesh.parallel(lat)` raises `ValueError` for an angle the grid does not
carry, and the message points at `latitude_line`/`meridian_line`, which
draw any angle on their own. The special circles are parameters
*because they are not on the grid to pick up*: `highlight` brings the
equator, tropics and poles on in their own colour (`highlight=True`
takes all three; a named circle is drawn even when the step would miss
it — no round step lands on 23.44°), and `labels=True` pins readable
latitude tags.

`equator`, `tropics` and `polar_circles` as their own calls sit at the
body's own tilt — Earth's tropics land at ±23.44° — and on a body with
no tilt the tropics degenerate to the equator.

`terminator(light)` draws the day/night line for a light at that scene
point. It is exact for a **sphere**; on a flattened body like Saturn the
line is drawn on the sphere of the equatorial radius, which is right at
the equator and off by a fraction of a percent towards the poles.

### `dem`

Rocky bodies have real elevation data — MOLA for Mars, LOLA for the Moon —
but it is hundreds of megabytes and is not bundled. Pass a path and it is
used:

```python
Mars(radius=3, dem="megt90n000eb.img", exaggeration=25)
```

Olympus Mons is 0.65% of Mars' radius, so at true scale there is nothing to
see; `exaggeration` is there to be honest about that rather than hide it.

---

## Defaults

Every default is one of two kinds: a measured one, which changes only
with a new measurement, or a taste one, which stays the same across
the whole family. The rule for both is the same — the default is what
you write when you are explaining to someone and do not want to stop
and choose.

| where | default | why |
| --- | --- | --- |
| `Body` radius | 3.0 | one globe fills a default frame |
| quality | `"2k"` | sharp at video scale; 8k for close-ups |
| resolution | (192, 96) | outline and shading only — the texture is per pixel |
| shadows, strength | on, 0.85 | the ring shadows are what make Saturn read as Saturn |
| exaggeration | 20.0 | true relief is 0.65% of Mars' radius — invisible |
| `graticule` step | 30° | the SurfaceMesh spacing; 17 lines on a globe |
| grid colour | `#8FE8FF` | ice blue, reads over ocean and land alike |
| grid height | 0.004 | clear of the texture, close enough to hug |
| hugging line width | 2 = `OVERLAY_WIDTH` | the light look; at 2 a quarter of the far cage still shows — `width=6` holds it fully (notes 2.14–2.15) |
| named circles | gold, 1.4× the width | the named circle is the feature |
| `arc_between` width | 2.0 | it flies, not hugs — no leak measured at 2.0 |
| `arc_between` height | 0.22 | leaves and lands flat, rises mid-way |
| `arc_between` edge dots | on -- gold `surface_marker`s | a journey names its two ends; `edge_dot=dict(...)` restyles them |
| `marker` size / height | 0.10 / 0.01 | the `cell_note` ring's twin; clear of the ground |
| `label` height / buff | 0.10 / 0.02 | far enough off the surface to read |
| `cell_note` ring | radius 0.10, width 2 | a callout, deliberately small and light |
| `surface_point` / `surface_marker` | radius 0.10, the pin's scale | paint, not a pin -- real geometry, grows with the camera |
| `axis_line` | thin, honest | the arms past the poles carry the story; `see_through=True` is the X-ray gauge |
| `follow` | `True` | overlays ride with the body — the common case |
| `see_through` | `False` | the honest look; the X-ray is asked for |
| `spin` rate | 0.3 rad/s | a slow, readable turn |
| `orbit` period | 12 s | one unhurried lap |

---

## Credits

Textures: [Solar System Scope](https://www.solarsystemscope.com/textures/),
CC BY 4.0. Radii, flattening and tilts from the IAU working group values;
Saturn ring edges from the Cassini radio occultation radii.
