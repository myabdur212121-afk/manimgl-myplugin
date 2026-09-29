"""
manimgl_myplugin.astro.bodies -- planets, moons and their rings.

    from manimgl_myplugin.astro import Mars, Saturn

    self.add(Mars(radius=3))
    self.add(Saturn(radius=3, quality="4k"))

A :class:`Body` is a ``Group`` of a globe and, where there are any, a set
of flat ring annuli. Both are ordinary meshes made by ``shapes.revolve``
and painted by the ``obj`` helper, so everything else in the toolkit --
``wireframe``, ``point_cloud``, ``BuildMesh`` -- works on them too.

The named subclasses carry nothing but facts: radius, flattening, axial
tilt, which texture, where the rings start and stop. See ``data.py``.
"""

from __future__ import annotations

import hashlib
import numpy as np

from manimlib.constants import DEGREES, OUT, RIGHT
from manimlib.mobject.mobject import Group

from ..obj.loader import CACHE_DIR, MODELS_DIR, fetch_model
from ..obj.mobject import OBJMobject
from ..shapes import revolve
from .data import BODIES, BodyFacts, RingBand, texture_url

__all__ = ["Body", "RingBand", "Mercury", "Venus", "Earth", "Moon", "Mars",
           "Jupiter", "Saturn", "Uranus", "Neptune", "named"]

#: ManimGL's own default light position, so a body looks right with no setup.
DEFAULT_LIGHT = np.array([-10.0, 10.0, 10.0])

#: How far out the Solar System Scope ring strip reaches, in planet radii.
#: The image covers the whole system from the inner D ring to the outer A.
RING_TEXTURE_SPAN = (1.11, 2.27)


class Body(Group):
    """
    A planet, moon or asteroid: a textured globe, optionally with rings.

    ::

        Body(radius=3, texture="mars", equatorial_radius_m=3_396_190)

    Most of the time you want a named subclass instead -- :class:`Mars`,
    :class:`Saturn` and the rest already know their own numbers.

    Parameters
    ----------
    radius
        How big the globe is in scene units.
    quality : {"2k", "4k", "8k"}
        Which texture to use. Bigger is sharper and slower to fetch; the
        geometry is unaffected, because the texture is looked up per pixel.
        Cached in ``~/models`` after the first time. Only 2k and 8k are
        published, so 4k is made by halving the 8k once.
    ring_resolution
        ``(segments around, steps per planet radius across)`` for the ring
        annuli. The radial steps carry the colour banding, so they are
        worth more than they look.
    resolution
        ``(segments, rings)`` of the globe mesh. This controls the outline
        and the shading, not the texture sharpness -- the texture is looked
        up per pixel, so a modest mesh with a 4k map still looks crisp.
    shadow_strength
        How hard the shadows are: 1 means a fully opaque ring blocks all
        the light, 0 means no shadow at all. Each band is scaled by its own
        opacity on top, so the thin C ring casts a fainter shadow than B.
    shadows
        Work out where the rings fall across the globe and where the globe
        falls across the rings, and darken those places. Not real shadow
        mapping -- the renderer has none -- but for a sphere and a flat
        annulus the geometry is simple enough to solve directly, and it is
        what makes Saturn look like Saturn. Costs about a second at
        construction; see :meth:`bake_shadows` to redo it when the light
        moves.
    rings
        ``False`` leaves them off. A list of :class:`RingBand` replaces the
        built-in ones.
    tilt
        Axial tilt in degrees, defaulting to the real value. Uranus is 97.8,
        which is why its rings stand up.
    dem
        A height map to displace the globe with, if you have one. Rocky
        bodies have real elevation data -- MOLA for Mars, LOLA for the Moon
        -- but it is large and not bundled; pass a path and it is used.
    exaggeration
        How much to overdo the relief. Olympus Mons is 0.65% of Mars'
        radius, so at true scale you would see nothing.
    """

    facts: BodyFacts | None = None

    def __init__(
        self,
        radius: float = 3.0,
        *,
        quality: str = "2k",
        resolution: tuple[int, int] = (192, 96),
        ring_resolution: tuple[int, int] = (180, 110),
        shadows: bool = True,
        rings: bool | list[RingBand] = True,
        tilt: float | None = None,
        texture: str | None = None,
        night_texture: str | None | bool = None,
        dem: str | None = None,
        exaggeration: float = 20.0,
        shadow_strength: float = 0.85,
        light: np.ndarray | None = None,
        **kwargs,
    ):
        facts = self.facts or BodyFacts("body", 1.0)
        self.facts = facts
        self.radius = float(radius)
        self.quality = quality
        self.shadow_strength = float(shadow_strength)
        self.tilt = facts.axial_tilt_deg if tilt is None else float(tilt)
        self._light = np.array(DEFAULT_LIGHT if light is None else light,
                               dtype=float)

        if rings is True:
            self.bands = list(facts.rings)
        elif rings is False:
            self.bands = []
        else:
            self.bands = list(rings)

        self._texture_stem = texture or facts.texture
        self._night_stem = (facts.night_texture if night_texture is None
                            else (None if night_texture is False
                                  else night_texture))
        self._flattening = facts.flattening
        self._ring_resolution = ring_resolution

        self.globe = self._build_globe(resolution, dem, exaggeration)
        self.ring_group = Group(*[self._build_band(b) for b in self.bands])

        super().__init__(self.globe, *self.ring_group, **kwargs)

        if shadows and self.bands:
            self.bake_shadows(self._light)
        # The rings lie in the equator, so tilting the whole group tips both
        # together -- which is exactly what a real axial tilt does.
        if self.tilt:
            self.rotate(self.tilt * DEGREES, RIGHT)

    # ------------------------------------------------------------ pieces --

    def _polar_scale(self) -> float:
        return 1.0 - self._flattening

    def _build_globe(self, resolution, dem, exaggeration):
        segments, rings = resolution
        t = np.linspace(0, np.pi, rings)
        profile = np.stack([self.radius * np.sin(t),
                            -self.radius * self._polar_scale() * np.cos(t)], -1)
        mesh = revolve(profile, segments=segments, name=self.facts.name.lower())

        if dem is not None:
            mesh = mesh.displace(
                dem, strength=exaggeration * self.radius
                / max(self.facts.equatorial_radius_m, 1.0) * 1000.0)

        if self._texture_stem is None:
            return OBJMobject(mesh, up_axis=None, color="#9FB4CC")

        day = self._fetch_texture(self._texture_stem)
        night = (self._fetch_texture(self._night_stem)
                 if self._night_stem else None)
        return OBJMobject(mesh, up_axis=None).textured(day, night)

    def _build_band(self, band: RingBand):
        """One annulus: a horizontal line, spun."""
        segments, per_unit = self._ring_resolution
        steps = max(16, int(per_unit * (band.outer - band.inner)))
        r = np.linspace(band.inner, band.outer, steps) * self.radius
        profile = np.stack([r, np.zeros_like(r)], axis=-1)
        mesh = revolve(profile, segments=segments,
                       name=f"ring_{band.name or 'x'}")

        ring = OBJMobject(mesh, up_axis=None, color="#D8CBB0",
                          # shadow term 0: a flat ring seen from underneath
                          # would otherwise go black, and rings scatter light
                          # rather than reflecting it off a surface.
                          shading=(0.0, 0.0, 0.0))
        self._paint_band(ring, band)
        ring.band = band
        return ring

    def _paint_band(self, ring, band: RingBand):
        """Colour and opacity across the band, read from the ring strip."""
        strip = self._ring_strip()
        radius_of = np.linalg.norm(
            np.asarray(ring.get_points())[:, :2], axis=1) / self.radius
        lo, hi = RING_TEXTURE_SPAN
        u = np.clip((radius_of - lo) / (hi - lo), 0, 1)
        sample = strip[np.clip((u * (len(strip) - 1)).astype(int),
                               0, len(strip) - 1)]

        with ring.data.being_written() as data:
            data["rgba"][:, :3] = sample[:, :3]
            data["rgba"][:, 3] = sample[:, 3] * band.opacity
        ring._shade_lam = None
        ring._base_rgb = sample[:, :3].copy()

    def _ring_strip(self) -> np.ndarray:
        """The ring texture as a 1-D RGBA ramp from inner edge to outer."""
        if getattr(self, "_strip_cache", None) is not None:
            return self._strip_cache
        from PIL import Image

        stem = f"{self.facts.name.lower()}_ring_alpha"
        try:
            path = self._fetch_texture(stem, ext="png", quality="2k")
            img = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32)
            strip = img.reshape(-1, img.shape[-1]) if img.ndim == 2 else \
                img[img.shape[0] // 2]
            strip = strip / 255.0
        except Exception:
            # No strip for this body: a plain pale ramp still reads as a ring.
            n = 512
            fade = np.linspace(0.55, 0.95, n)
            strip = np.stack([fade * 0.87, fade * 0.82, fade * 0.70,
                              np.ones(n)], axis=-1).astype(np.float32)
        self._strip_cache = strip
        return strip

    def _fetch_texture(self, stem, ext="jpg", quality=None):
        """
        Find a texture, downloading it the first time.

        Solar System Scope publishes 2k and 8k, not 4k -- asking for the
        missing size gets an HTML error page that looks like a success. So
        ``quality="4k"`` fetches the 8k and halves it once, which is a real
        4k map and the same thing you would have got.
        """
        quality = quality or self.quality
        local = MODELS_DIR / f"{quality}_{stem}.{ext}"
        if local.exists():
            return str(local)

        if quality == "4k":
            from PIL import Image
            big = self._fetch_texture(stem, ext, quality="8k")
            image = Image.open(big)
            image.resize((image.width // 2, image.height // 2),
                         Image.LANCZOS).save(local, quality=94)
            print(f"[manimgl_myplugin] made     {local.name} from the 8k")
            return str(local)

        return str(fetch_model(texture_url(stem, quality, ext),
                               name=local.name, companions=False))

    # ----------------------------------------------------------- shadows --

    def bake_shadows(self, light=None, strength: float | None = None):
        """
        Work out the two shadows and paint them in.

        The rings throw a band across the globe, and the globe throws one
        across the rings. Neither is real shadow mapping -- the renderer has
        no shadows at all -- but a sphere and a flat annulus are simple
        enough to intersect directly, so the result is correct rather than
        faked, just precomputed.

        Call it again after moving the light. The globe half is the slow
        part, roughly a second, because it repaints the texture.
        """
        light = self._light if light is None else np.asarray(light, dtype=float)
        self._light = light
        power = self.shadow_strength if strength is None else float(strength)
        if not self.bands:
            return self
        local_light = self._to_local(light)
        self._shadow_on_rings(local_light, power)
        self._shadow_on_globe(local_light, power)
        return self

    def follow_light(self, scene, every: int = 0):
        """
        Keep the shadows pointing away from the scene's light as it moves.

        Rebaking the globe texture every frame is far too slow, so this
        updates the rings each frame and the globe only when asked --
        ``every=15`` redoes it about twice a second.
        """
        state = {"n": 0}

        def update(mob, dt):
            light = scene.camera.light_source.get_location()
            local = mob._to_local(np.asarray(light, dtype=float))
            mob._shadow_on_rings(local, mob.shadow_strength)
            state["n"] += 1
            if every and state["n"] % every == 0:
                mob._shadow_on_globe(local, mob.shadow_strength)

        self.add_updater(update)
        return self

    def _to_local(self, light):
        """Undo the axial tilt, so the ring plane is simply z = 0."""
        if not self.tilt:
            return light
        a = -self.tilt * DEGREES
        c, s = np.cos(a), np.sin(a)
        return np.array([light[0],
                         c * light[1] - s * light[2],
                         s * light[1] + c * light[2]])

    def _shadow_on_rings(self, light, power):
        """
        Darken ring points the globe stands in front of.

        Squash z by the flattening first and the oblate spheroid becomes a
        unit sphere, which turns the test into "does the ray pass within one
        radius of the centre".
        """
        squash = np.array([1.0, 1.0, 1.0 / max(self._polar_scale(), 1e-6)])
        light_s = light * squash
        for ring in self.ring_group:
            pts = np.asarray(ring.get_points()) * squash
            to_light = light_s - pts
            to_light /= np.maximum(np.linalg.norm(to_light, axis=1,
                                                  keepdims=True), 1e-9)
            along = -(pts * to_light).sum(axis=1)
            closest = np.linalg.norm(pts + along[:, None] * to_light, axis=1)
            blocked = (along > 0) & (closest < self.radius)
            base = getattr(ring, "_base_rgb", None)
            if base is None:
                continue
            with ring.data.being_written() as data:
                rgb = base.copy()
                rgb[blocked] *= 1.0 - 0.92 * power
                data["rgba"][:, :3] = rgb

    def _shadow_on_globe(self, light, power, grid=(1024, 512)):
        """
        Paint the ring shadow into a copy of the globe's own texture.

        A ManimGL textured surface takes its colour from the image, not from
        the vertices, so there is nowhere to darken a point. Working in the
        texture instead is also sharper than the mesh, and computing the
        mask at half resolution and letting it soften on the way up gives a
        penumbra for free -- which is what a real ring shadow has.
        """
        if self._texture_stem is None:
            return
        from PIL import Image

        nx, ny = grid
        lon = np.linspace(-np.pi, np.pi, nx, endpoint=False)
        lat = np.linspace(np.pi / 2, -np.pi / 2, ny)
        lo, la = np.meshgrid(lon, lat)

        pole = self._polar_scale()
        pts = np.stack([
            self.radius * np.cos(la) * np.cos(lo),
            self.radius * np.cos(la) * np.sin(lo),
            self.radius * pole * np.sin(la),
        ], axis=-1).reshape(-1, 3)

        d = light - pts
        d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
        facing = (pts * d).sum(axis=1) > 0          # only the lit side

        with np.errstate(divide="ignore", invalid="ignore"):
            t = -pts[:, 2] / d[:, 2]
        hit = pts + t[:, None] * d
        r = np.linalg.norm(hit[:, :2], axis=1) / self.radius
        crosses = facing & (t > 0) & np.isfinite(t)

        shade = np.ones(len(pts), dtype=np.float32)
        for band in self.bands:
            inside = crosses & (r >= band.inner) & (r <= band.outer)
            # a band of optical depth `opacity` blocks that much of the
            # light, scaled by how hard a shadow was asked for
            shade[inside] *= 1.0 - band.opacity * power

        mask = Image.fromarray((shade.reshape(ny, nx) * 255).astype(np.uint8))

        source = self._fetch_texture(self._texture_stem)
        image = Image.open(source).convert("RGB")
        mask = mask.resize(image.size, Image.BILINEAR)
        shaded = (np.asarray(image, dtype=np.float32)
                  * (np.asarray(mask, dtype=np.float32)[..., None] / 255.0))

        key = hashlib.blake2b(
            f"{source}|{self.radius}|{light.round(3).tolist()}|{power}|"
            f"{[(b.inner, b.outer, b.opacity) for b in self.bands]}".encode(),
            digest_size=10).hexdigest()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        out = CACHE_DIR / f"ringshadow-{key}.jpg"
        if not out.exists():
            Image.fromarray(shaded.astype(np.uint8)).save(out, quality=92)

        night = (self._fetch_texture(self._night_stem)
                 if self._night_stem else None)
        fresh = OBJMobject(self.globe.mesh, up_axis=None).textured(str(out), night)
        fresh.set_points(self.globe.get_points())
        self.replace_submobject(self.submobjects.index(self.globe), fresh)
        self.globe = fresh

    # -------------------------------------------------------------- misc --

    def info(self) -> str:
        f = self.facts
        rings = (", ".join(f"{b.name} {b.inner:.2f}-{b.outer:.2f}"
                           for b in self.bands) or "none")
        return (f"{f.name}: r = {f.equatorial_radius_m / 1000:,.0f} km, "
                f"flattening {f.flattening:.4f}, tilt {self.tilt:.1f}deg\n"
                f"  mesh   : {self.globe.num_faces:,} triangles, "
                f"{self.quality} texture\n"
                f"  rings  : {rings}")


def _preset(key: str) -> type:
    facts = BODIES[key]
    return type(facts.name, (Body,), {
        "facts": facts,
        "__doc__": (f"{facts.name}. Equatorial radius "
                    f"{facts.equatorial_radius_m / 1000:,.0f} km, flattening "
                    f"{facts.flattening:.4f}, axial tilt "
                    f"{facts.axial_tilt_deg:.2f} degrees."
                    + (f"\n\n{facts.note}." if facts.note else "")),
    })


Mercury = _preset("mercury")
Venus = _preset("venus")
Earth = _preset("earth")
Moon = _preset("moon")
Mars = _preset("mars")
Jupiter = _preset("jupiter")
Saturn = _preset("saturn")
Uranus = _preset("uranus")
Neptune = _preset("neptune")

_PRESETS = {k: v for k, v in zip(
    BODIES, [Mercury, Venus, Earth, Moon, Mars, Jupiter, Saturn, Uranus,
             Neptune])}


def named(key: str, **kwargs) -> Body:
    """``named("mars", radius=3)`` -- handy when the name is in a variable."""
    try:
        return _PRESETS[key.lower()](**kwargs)
    except KeyError:
        raise KeyError(f"no body called {key!r}; "
                       f"try one of {sorted(_PRESETS)}") from None
