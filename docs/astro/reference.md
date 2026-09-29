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

`named("mars", radius=3)` when the name is in a variable; `BODIES` is the
raw table.

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

### `rings`

```python
Saturn(rings=False)
Saturn(rings=[RingBand(1.2, 2.0, opacity=0.6, name="one")])
```

`RingBand(inner, outer, opacity, name)` — edges in planet radii, the way
ring data is always quoted. Opacity stands in for optical depth.

The Cassini Division is **not** a transparent patch of texture: B stops at
1.951 and A starts at 2.027, so the gap is a real hole in the geometry.
That matters, because the shader throws away fully transparent pixels but
overwrites partial alpha with the per-vertex opacity — soft transparency
from a texture does not survive. Ring colour and opacity are therefore
sampled from the strip into the vertices instead.

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

## Credits

Textures: [Solar System Scope](https://www.solarsystemscope.com/textures/),
CC BY 4.0. Radii, flattening and tilts from the IAU working group values;
Saturn ring edges from the Cassini radio occultation radii.
