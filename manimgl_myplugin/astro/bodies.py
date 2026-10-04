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
from pathlib import Path

import numpy as np

from manimlib.animation.rotation import Rotating
from manimlib.constants import DEGREES, OUT, RIGHT, TAU
from manimlib.mobject.geometry import Arc, Line
from manimlib.mobject.mobject import Group
from manimlib.mobject.types.dot_cloud import DotCloud
from manimlib.mobject.types.vectorized_mobject import VGroup, VMobject

from ..obj.loader import CACHE_DIR, MODELS_DIR, fetch_model
from ..obj.mobject import OBJMobject
from ..shapes import revolve
from .data import BODIES, BodyFacts, RingBand, texture_url

__all__ = ["Body", "RingBand", "Mercury", "Venus", "Earth", "Moon", "Mars",
           "Jupiter", "Saturn", "Uranus", "Neptune", "named"]

#: ManimGL's own default light position, so a body looks right with no setup.
DEFAULT_LIGHT = np.array([-10.0, 10.0, 10.0])


def _apply_occlusion(mob, see_through: bool):
    """
    Overlays default to the honest look: the body hides them once
    they go round the back. The depth test does that hiding, but it
    needs two props to hold in this renderer (see notes 2.13): the
    overlay draws after the body, which it asks for with ``z_index``
    because the draw order of equal-index mobjects is not stable
    between renders, and an X-ray overlay re-states its freedom every
    frame, because ``ThreeDScene.add`` force-applies the depth test
    to whatever it is handed. ``clear_updaters()`` on the returned
    mobject takes that back for manual control.
    """
    mob.set_z_index(1)
    if see_through:
        mob.deactivate_depth_test()

        def stay_through(m, dt):
            for sm in m.get_family():
                sm.depth_test = False

        for sm in mob.get_family():
            sm.add_updater(stay_through)
    else:
        mob.apply_depth_test()
    return mob

#: Markers and guide lines default to this, so they read against
#: both a blue planet and a red one.
GOLD_MARKER = "#F2B33D"

#: One width for every stroke that hugs the surface. The depth test
#: only bites on a stroke a few pixels wide -- the measured floor is
#: 5 -- so at this light default the far side of a hugging line
#: still shows through a little. The maintainer chose that look with
#: the numbers on the table (notes 2.14, 2.15); width 6 is where
#: the line holds completely.
OVERLAY_WIDTH = 2.0

#: The named circles are the feature, so they run visibly heavier
#: than the plain grid around them.
SPECIAL_WIDTH_FACTOR = 1.4

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
    # class-level sentinel: None while __init__ is ingesting the globe and
    # rings, a list once construction is done and tracking may begin
    _overlays: list | None = None

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

        # Group.__init__ ingests its arguments through self.add, so the
        # globe and rings would land in _overlays if the list existed
        # yet; it is created just after, once construction is done
        super().__init__(self.globe, *self.ring_group, **kwargs)
        self._overlays = []

        if shadows and self.bands:
            self.bake_shadows(self._light)
        # The rings lie in the equator, so tilting the whole group tips both
        # together -- which is exactly what a real axial tilt does.
        if self.tilt:
            self.rotate(self.tilt * DEGREES, RIGHT)

    def add(self, *mobjects):
        """Graft mobjects in; remember them as overlays for shed_overlays."""
        if self._overlays is not None:
            self._overlays.extend(mobjects)
        return super().add(*mobjects)

    def remove(self, *mobjects):
        if self._overlays is not None:
            self._overlays = [m for m in self._overlays
                              if m not in mobjects]
        return super().remove(*mobjects)

    def shed_overlays(self):
        """
        Take every overlay back off: markers, arcs, labels, anchors,
        decals -- anything grafted in after construction. The body is
        exactly what it was built as, and ``point_at`` answers are
        untouched either way.

        ::

            earth.marker(23.8, 90.4)
            earth.shed_overlays()          # the dot and its anchor go
        """
        if self._overlays:
            super().remove(*self._overlays)
            self._overlays.clear()
        return self

    # ------------------------------------------------------------ pieces --

    def get_center(self) -> np.ndarray:
        """
        The *globe's* centre, not the family bounding box's. Grafting a
        marker, an arc or a label on one side must never shift where the
        body thinks it is -- otherwise point_at, spin and orbit all start
        to wander as overlays come and go. Measured against the bounding
        box before the fix: adding one arc moved the centre by 5% of the
        radius.
        """
        globe = getattr(self, "globe", None)
        if globe is not None and globe.has_points():
            return globe.get_center()
        return super().get_center()

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

    # ----------------------------------------------------------- geography --

    def point_at(self, lat: float, lon: float, height: float = 0.0):
        """
        Where a latitude and longitude land, in scene coordinates.

        ::

            dhaka = earth.point_at(23.8, 90.4)

        Degrees, north and east positive, the way an atlas gives them, and
        lined up with the texture -- ``point_at(23, 13)`` really is in the
        Sahara.
        ``height`` lifts the point off the surface as a fraction of the
        radius, which is what you want for a marker that should not sink
        into the ground.

        Follows the body: tilt it or move it and the answer moves with it.
        """
        return self._points_at([lat], [lon], [height])[0]

    def _points_at(self, lats, lons, heights):
        """
        Vectorised :meth:`point_at` -- arrays in, ``(N, 3)`` scene points
        out. Same maths, one source of truth.
        """
        # The texture's left edge is longitude -180 and revolve starts its
        # sweep on +x, so the map is half a turn round from the maths.
        # Without the +180, asking for the Sahara hands you the Pacific.
        a = np.radians(np.asarray(lats, dtype=float))
        o = np.radians(np.asarray(lons, dtype=float) + 180.0)
        r = self.radius * (1.0 + np.asarray(heights, dtype=float))
        pts = np.stack([
            r * np.cos(a) * np.cos(o),
            r * np.cos(a) * np.sin(o),
            r * self._polar_scale() * np.sin(a),
        ], axis=-1)
        if self.tilt:
            t = self.tilt * DEGREES
            c, s = np.cos(t), np.sin(t)
            pts = np.stack([pts[:, 0],
                            c * pts[:, 1] - s * pts[:, 2],
                            s * pts[:, 1] + c * pts[:, 2]], axis=-1)
        return self.get_center() + pts

    def marker(self, lat: float, lon: float, color=GOLD_MARKER,
               size: float = 0.05, height: float = 0.01,
               follow: bool = True, see_through: bool = False,
               **kwargs) -> DotCloud:
        """
        A dot pinned to a place on the surface.

        ::

            self.add(earth.marker(23.8, 90.4))          # Dhaka

        Lifted very slightly off the ground by default, or the depth test
        leaves it half buried in the texture.

        ``follow`` (the default) grafts the dot into the body, so shifting,
        rotating, :meth:`spin` or :meth:`orbit` all carry it along at no
        per-frame cost. ``**kwargs`` reach the ``DotCloud`` -- ``radius``,
        ``glow_factor``, ``opacity`` and friends.
        """
        dot = DotCloud([self.point_at(lat, lon, height)],
                       radius=size * self.radius / 3.0, **kwargs)
        dot.set_color(color)
        _apply_occlusion(dot, see_through)
        if follow:
            self.add(dot)
        return dot

    def arc_between(self, start, end, height: float = 0.22,
                    samples: int = 80, follow: bool = True,
                    see_through: bool = False, **kwargs) -> VMobject:
        """
        The short way round between two places, lifted into an arc.

        ::

            self.add(earth.arc_between((23.8, 90.4), (51.5, -0.1)))

        Each point is a great-circle step pushed out by a sine bump, so the
        line leaves and lands flat and rises in the middle -- a flight path
        rather than a chord through the planet. The default width is
        light on purpose: the arc flies above the surface, where the
        depth test has nothing against it. Press it flat with
        ``height=0`` and it becomes a hugging stroke -- and a thin
        hugging stroke shows its far side, so ask for ``width=6``
        when you want that hidden.

        ``follow`` (the default) grafts the arc into the body so it rides
        along with every shift, rotate, spin and orbit. ``color`` and
        ``width`` name the two common stroke settings; anything else in
        ``**kwargs`` reaches ``set_stroke``.
        """
        p0 = self.point_at(*start) - self.get_center()
        p1 = self.point_at(*end) - self.get_center()
        n0, n1 = p0 / np.linalg.norm(p0), p1 / np.linalg.norm(p1)
        omega = np.arccos(np.clip(n0 @ n1, -1, 1))
        t = np.linspace(0, 1, samples)

        if omega < 1e-6:
            path = np.outer(np.ones_like(t), n0)
        else:                                   # spherical interpolation
            path = (np.outer(np.sin((1 - t) * omega), n0)
                    + np.outer(np.sin(t * omega), n1)) / np.sin(omega)

        lift = self.radius * (1 + height * np.sin(np.pi * t))
        arc = VMobject().set_points_smoothly(
            self.get_center() + path * lift[:, None])
        # it flies, not hugs: two probes measured no leak at this
        # width (notes 2.14), and a light line reads as a route
        # rather than geography -- the family default now. Pressed
        # flat with height=0 it becomes a hugging stroke, and a thin
        # hugging stroke shows its far side: width 6 holds it.
        arc.set_stroke(kwargs.pop("color", GOLD_MARKER),
                       kwargs.pop("width", 2.0), **kwargs)
        _apply_occlusion(arc, see_through)
        if follow:
            self.add(arc)
        return arc

    def graticule(self, step=30, *, lat_step=None, lon_step=None,
                  color="#8FE8FF", width: float = OVERLAY_WIDTH,
                  height: float = 0.004,
                  highlight=None, highlight_color=None,
                  labels: bool = False, label_font_size: int = 20,
                  label_lon: float = 25.0, follow: bool = True,
                  see_through: bool = False, **kwargs) -> Graticule:
        """
        The lat/lon mesh over the body -- the same idea as ManimGL's
        ``SurfaceMesh``, for a globe: a plain grid of blue lines, with
        nothing special about any of them. It works on every body,
        textured or not, because it is drawn from the body's own
        geometry rather than from its texture.

        ::

            mesh = earth.graticule(30)
            self.add(earth, mesh)
            self.play(ShowCreation(mesh))

        The grid hands back a :class:`Graticule`, and that mobject
        is where the work happens: ``mesh.parallel(60)`` and
        ``mesh.meridian(90)`` pick out any one line, and from there
        it is ordinary manim -- ``set_stroke``, ``animate``, anything.

        ``step`` is the spacing in degrees; give ``(lat_step, lon_step)``
        to space parallels and meridians differently. The special
        circles are **not** part of the look -- they wait off stage.
        ``highlight`` brings them on, drawn in ``highlight_color``: any
        of ``"equator"``, ``"tropics"`` and ``"poles"`` (the polar
        circles), each at the body's *own* axial tilt;
        ``highlight=True`` takes all three, and a single string works
        too. A named circle is drawn even when the step would miss it --
        no round step lands on 23.44 degrees. ``labels=True`` tags every
        parallel with its latitude. Lines sit a hair above the surface so
        the depth test does not eat them, ``follow`` grafts them into the
        body like :meth:`marker`, and ``see_through=True`` keeps the
        far side shining through the globe -- the X-ray view, the
        whole cage at once. The default width, 2, is the light look,
        chosen with the trade measured: this renderer only holds a
        stroke at the depth test from about 5 up, so at 2 the far
        side of the grid shows through faintly (notes 2.13-2.15);
        ``width=6`` hides it completely. ``**kwargs`` reach
        ``set_stroke``.
        """
        if isinstance(step, (tuple, list)):
            lat_step, lon_step = step
        lat_step = float(lat_step if lat_step else step)
        lon_step = float(lon_step if lon_step else step)
        if highlight is True:
            highlight = ("equator", "tropics", "poles")
        if isinstance(highlight, str):
            highlight = (highlight,)
        highlight = {str(h).lower() for h in (highlight or ())}
        highlight_color = highlight_color or GOLD_MARKER

        special = {}
        if "equator" in highlight:
            special[0.0] = True
        t = abs(self.tilt)
        if "tropics" in highlight and t > 1e-6:
            special[t] = True
            special[-t] = True
        if "poles" in highlight and 90.0 - t > 1e-6:
            special[90.0 - t] = True
            special[-(90.0 - t)] = True

        def is_special(lat: float) -> bool:
            return any(abs(lat - k) < 1e-6 for k in special)

        parallels, specials = [], []
        drawn = []

        def add_parallel(lat: float):
            lat = round(float(lat), 6)
            drawn.append(lat)
            line = self.latitude_line(
                lat, height=height, follow=False, see_through=see_through,
                color=highlight_color if is_special(lat) else color,
                width=width * SPECIAL_WIDTH_FACTOR if is_special(lat)
                else width, **kwargs)
            parallels.append(line)
            if is_special(lat):
                specials.append(line)

        for lat in np.arange(-90.0 + lat_step, 90.0, lat_step):
            add_parallel(float(lat))
        # a named circle must appear even when the step would miss it --
        # the tropics are at 23.44 degrees, which no round step hits
        for k in special:
            if not any(abs(k - p) < 1e-6 for p in drawn):
                add_parallel(k)
        meridians = [self.meridian_line(
                         lon, height=height, follow=False, color=color,
                         width=width, see_through=see_through, **kwargs)
                     for lon in np.arange(-180.0, 180.0, lon_step)]

        mesh = Graticule(parallels, meridians, specials)
        if labels:
            for lat in drawn:
                mesh.add(self._pinned_text(
                    _lat_tag(lat, label_font_size,
                             highlight_color if is_special(lat) else color),
                    lat, label_lon, height=0.06, follow=follow))
        if follow:
            self.add(*parallels, *meridians)
        return _apply_occlusion(mesh, see_through)

    def latitude_line(self, lat: float, *, color="#8FE8FF",
                      width: float = OVERLAY_WIDTH,
                      height: float = 0.004, samples: int = 181,
                      follow: bool = True, see_through: bool = False,
                      **kwargs) -> VMobject:
        """
        One circle of latitude, drawn on the surface and riding along with
        the body. ``see_through=True`` lets it shine through the globe;
        the default is the honest, occluded look. ``**kwargs`` reach
        ``set_stroke``.
        """
        lons = np.linspace(-180.0, 180.0, samples)
        pts = self._points_at(np.full_like(lons, float(lat)), lons,
                              np.full_like(lons, height))
        line = VMobject().set_points_smoothly(pts)
        line.lat = round(float(lat), 6)
        line.set_stroke(color, width, **kwargs)
        if follow:
            self.add(line)
        return _apply_occlusion(line, see_through)

    def meridian_line(self, lon: float, *, color="#8FE8FF",
                      width: float = OVERLAY_WIDTH,
                      height: float = 0.004, samples: int = 181,
                      follow: bool = True, see_through: bool = False,
                      **kwargs) -> VMobject:
        """
        One line of longitude, pole to pole -- the partner of
        :meth:`latitude_line`, same knobs, same behaviour.
        """
        lats = np.linspace(-90.0, 90.0, samples)
        pts = self._points_at(lats, np.full_like(lats, float(lon)),
                              np.full_like(lats, height))
        line = VMobject().set_points_smoothly(pts)
        line.lon = round(float(lon), 6)
        line.set_stroke(color, width, **kwargs)
        if follow:
            self.add(line)
        return _apply_occlusion(line, see_through)

    def equator(self, **kwargs) -> VMobject:
        """Latitude zero, highlighted by default."""
        kwargs.setdefault("color", GOLD_MARKER)
        kwargs.setdefault("width", OVERLAY_WIDTH * SPECIAL_WIDTH_FACTOR)
        return self.latitude_line(0.0, **kwargs)

    def tropics(self, **kwargs) -> VGroup:
        """
        The two circles where the sun stands straight overhead at a
        solstice -- at the body's own axial tilt, 23.44 degrees for Earth.
        A body with no tilt has no tropics, so its equator stands in.
        """
        kwargs.setdefault("color", GOLD_MARKER)
        kwargs.setdefault("width", OVERLAY_WIDTH * SPECIAL_WIDTH_FACTOR)
        t = abs(self.tilt)
        if t < 1e-6:
            return VGroup(self.equator(**kwargs))
        return VGroup(self.latitude_line(t, **kwargs),
                      self.latitude_line(-t, **kwargs))

    def polar_circles(self, **kwargs) -> VGroup:
        """
        The solstice twilight circles, at ±(90° − tilt). Same rule as
        :meth:`tropics`: an untilted body has none, so its equator stands
        in.
        """
        kwargs.setdefault("color", "#7E93AC")
        kwargs.setdefault("width", OVERLAY_WIDTH * SPECIAL_WIDTH_FACTOR)
        t = abs(self.tilt)
        if 90.0 - t < 1e-6:
            return VGroup(self.equator(**kwargs))
        return VGroup(self.latitude_line(90.0 - t, **kwargs),
                      self.latitude_line(-(90.0 - t), **kwargs))

    def terminator(self, light=None, *, color="#8FE8FF",
                   width: float = OVERLAY_WIDTH,
                   samples: int = 192, follow: bool = True,
                   see_through: bool = False, **kwargs) -> VMobject:
        """
        The day-night line: the great circle whose points see the light on
        their horizon.

        ::

            self.play(ShowCreation(earth.terminator()))

        Exact for a sphere, and as close as the flattening allows for the
        rest -- a guide line, not an ephemeris. ``light`` is a scene-space
        position, defaulting to the one the shadows were baked with.
        """
        light = self._light if light is None else np.asarray(light, dtype=float)
        d = light - self.get_center()
        d = d / max(np.linalg.norm(d), 1e-9)
        d = self._to_local(d)              # undo the tilt, as the shadows do

        helper = np.eye(3)[int(np.argmin(np.abs(d)))]
        e1 = helper - d * (helper @ d)
        e1 = e1 / max(np.linalg.norm(e1), 1e-12)
        e2 = np.cross(d, e1)
        th = np.linspace(0, TAU, samples, endpoint=False)
        circle = self.radius * (np.outer(np.cos(th), e1) + np.outer(np.sin(th), e2))
        circle[:, 2] *= self._polar_scale()

        if self.tilt:                      # back out of the local frame
            t = self.tilt * DEGREES
            c, s = np.cos(t), np.sin(t)
            circle = np.stack([circle[:, 0],
                               c * circle[:, 1] - s * circle[:, 2],
                               s * circle[:, 1] + c * circle[:, 2]], axis=-1)
        line = VMobject().set_points_smoothly(self.get_center() + circle)
        line.set_stroke(color, width, **kwargs)
        _apply_occlusion(line, see_through)
        if follow:
            self.add(line)
        return line

    def axis_line(self, overhang: float = 1.4, color=GOLD_MARKER,
                  width: float = 0.03, follow: bool = True) -> Line:
        """
        The pole, drawn -- the quickest way to see whether a spin is right.

        A guide, not geography: X-ray on purpose, so the buried middle
        stays visible while you watch a spin. ``follow`` (the default)
        grafts it into the body like every other overlay, and it rides
        along with every shift, tilt and orbit.
        """
        arm = self.axis * self.radius * overhang
        centre = self.get_center()
        line = Line(centre - arm, centre + arm)
        line.set_stroke(color, width * 100)
        _apply_occlusion(line, True)
        if follow:
            self.add(line)
        return line

    # ------------------------------------------------- pinned overlays --

    def _pinned_text(self, mob, lat: float, lon: float, *,
                     height: float = 0.02, buff: float = 0.0,
                     follow: bool = True):
        """
        Keep a text mobject readable at a surface point: its *position*
        tracks the body through every shift, spin and orbit, while the text
        itself keeps facing out of the surface rather than tumbling with
        it. An invisible anchor rides inside the body; an updater rebuilds
        the text's points around the anchor each frame -- a handful of
        numpy, nothing more.
        """
        # Text and friends keep their points on the glyph submobjects, so
        # capture each family member's points around the whole mob's centre
        fam = [sm for sm in mob.get_family() if sm.has_points()]
        if not fam:
            raise ValueError("_pinned_text needs a mobject with points")
        base = [np.asarray(sm.get_points()) - mob.get_center() for sm in fam]
        anchor = DotCloud([self.point_at(lat, lon, height)], opacity=0.0)
        if follow:
            self.add(anchor)

        def stay_pinned(m, dt):
            p = np.asarray(anchor.get_points())[0]
            n = p - self.get_center()
            length = np.linalg.norm(n)
            n = n / length if length > 1e-9 else np.array([0.0, 0.0, 1.0])
            # upright on the tangent plane: as close to the scene's z as
            # the plane allows, so text never ends up on its side
            up = np.array([0.0, 0.0, 1.0]) - n * n[2]
            if np.linalg.norm(up) < 1e-6:            # straight over the pole
                up = np.array([0.0, 1.0, 0.0])
            else:
                up = up / np.linalg.norm(up)
            right = np.cross(up, n)
            rot = np.stack([right, up, n], axis=1)
            for sm, b in zip(fam, base):
                sm.set_points(b @ rot + p + n * buff)

        stay_pinned(mob, 0.0)
        if follow:
            mob.add_updater(stay_pinned)
        return mob

    def label(self, lat: float, lon: float, text: str, *,
              height: float = 0.10, buff: float = 0.02, font: str | None = None,
              follow: bool = True, see_through: bool = False, **kwargs):
        """
        A piece of text pinned to a place, staying readable while the body
        moves or turns.

        ::

            lbl = earth.label(23.8, 90.4, "Dhaka")
            self.add(earth, lbl)
            self.play(Write(lbl))

        The text is *not* grafted into the body -- it would tumble with the
        spin. Instead an invisible anchor rides along inside and an updater
        holds the text at that point, always facing out of the surface, so
        it reads from wherever the anchor is visible.

        ``**kwargs`` go straight to ManimGL's ``Text`` -- ``font_size``,
        ``color``, ``weight`` and friends -- so the label is as adjustable
        as any text you would write by hand.
        """
        from manimlib.mobject.svg.text_mobject import Text
        if font is None:
            mob = Text(text, **kwargs)
        else:
            mob = Text(text, font=font, **kwargs)
        mob = self._pinned_text(mob, lat, lon, height=height, buff=buff,
                                follow=follow)
        return _apply_occlusion(mob, see_through)

    def place_on_surface(self, mob, lat: float, lon: float, *,
                         height: float = 0.015, scale: float = 1.0,
                         follow: bool = True, see_through: bool = False):
        """
        Lay a flat mobject onto the surface at ``(lat, lon)``, bending it
        round the curvature as it goes.

        ::

            tag = Text("DHAKA", font_size=24, color=YELLOW)
            earth.place_on_surface(tag, 23.8, 90.4)

        The mobject's own plane is read as the tangent plane at that point:
        its x becomes east, its y north, and every point -- handles
        included -- is mapped onto the globe. Short for the tangent plane
        the result is a faithful decal; stretch it too far and the map
        projection distortion shows, as it does on a real globe.

        ``follow`` grafts the result into the body, so a decal rides along
        with every shift, spin and orbit -- painted on, in effect.
        """
        # Text and friends keep their points on the glyphs, not on the
        # group, so the map runs over every family member that has any
        fam = [sm for sm in mob.get_family() if sm.has_points()]
        if not fam:
            raise ValueError("place_on_surface needs a mobject with points")
        centre = np.concatenate([sm.get_points() for sm in fam]).mean(axis=0)
        r = self.radius
        for sm in fam:
            pts = np.asarray(sm.get_points(), dtype=float)
            local = (pts - centre) * scale
            # one unit of tangent length is this many degrees of angle;
            # clamp the east-west term near the poles, where it blows up
            coslat = max(np.cos(np.radians(lat)), 0.25)
            lats = lat + local[:, 1] / r * (180.0 / np.pi)
            lons = lon + local[:, 0] / (r * coslat) * (180.0 / np.pi)
            hs = height + local[:, 2] / r
            sm.set_points(self._points_at(lats, lons, hs))
        _apply_occlusion(mob, see_through)
        if follow:
            self.add(mob)
        return mob

    def surface_text(self, text: str, lat: float, lon: float, *,
                     height: float = 0.015, scale: float = 1.0,
                     follow: bool = True, see_through: bool = False,
                     font: str | None = None, **kwargs):
        """
        Text painted onto the surface, curving with it -- the convenience
        form of :meth:`place_on_surface`.

        ::

            self.add(earth.surface_text("DHAKA", 23.8, 90.4, font_size=30))

        ``**kwargs`` go to ManimGL's ``Text``.
        """
        from manimlib.mobject.svg.text_mobject import Text
        if font is None:
            mob = Text(text, **kwargs)
        else:
            mob = Text(text, font=font, **kwargs)
        return self.place_on_surface(mob, lat, lon, height=height,
                                     scale=scale, follow=follow,
                                     see_through=see_through)

    def cell_note(self, lat: float, lon: float, index: int = 0, *,
                  step: float = 30, arc_radius: float = 0.10,
                  color=GOLD_MARKER, coords: bool = True,
                  follow: bool = True, see_through: bool = False,
                  **kwargs) -> VGroup:
        """
        Name and ring one corner of the graticule cell a place falls in.

        ::

            note = earth.cell_note(23.8, 90.4, index=2, step=30)
            self.play(Write(note[0]), ShowCreation(note[1]))

        ``index`` picks among the cell's four corners -- 0 south-west,
        1 south-east, 2 north-east, 3 north-west -- and what comes back is
        ``VGroup(Tex label, small arc)`` ready for ``self.play``. The Tex
        names the corner (``P_2``) and, unless ``coords=False``, quotes its
        own latitude and longitude. ``**kwargs`` reach the ``Tex``. The
        ring is callout-sized and thin; at that scale the depth test
        does not reliably hide a stroke, so a corner near the limb may
        show a faint ghost -- the note is meant for the near side.
        """
        from manimlib.mobject.svg.tex_mobject import Tex

        step = float(step)
        lat0 = np.floor(lat / step) * step
        lon0 = np.floor((lon + 180.0) / step) * step - 180.0
        corners = [(lat0, lon0), (lat0, lon0 + step),
                   (lat0 + step, lon0 + step), (lat0 + step, lon0)]
        i = int(index) % 4
        clat, clon = corners[i]

        # ^{\circ}, not \degree: the stock manimgl preamble defines no
        # \degree, and a failed Tex compile is a hard error
        where = (rf"\,({clat:.0f}^{{\circ}},\,{clon:.0f}^{{\circ}})"
                 if coords else "")
        tag = Tex(rf"P_{{{i}}}" + where, **kwargs)

        # a three-quarter ring in the tangent plane at the corner, facing
        # out of the surface
        p = self.point_at(clat, clon, 0.02)
        n = p - self.get_center()
        n = n / max(np.linalg.norm(n), 1e-9)
        up = np.array([0.0, 0.0, 1.0]) - n * n[2]
        up = up / max(np.linalg.norm(up), 1e-9)
        right = np.cross(up, n)
        ring = Arc(start_angle=-70 * DEGREES, angle=320 * DEGREES,
                   radius=arc_radius * self.radius / 3.0)
        ring.set_points(np.asarray(ring.get_points())
                        @ np.stack([right, up, n], axis=1) + p)
        ring.set_stroke(color, 2.0)

        self._pinned_text(tag, clat, clon, height=0.02,
                          buff=arc_radius * self.radius / 1.2, follow=follow)
        return _apply_occlusion(VGroup(tag, ring), see_through)

    # ------------------------------------------------------------- motion --

    def orbit(self, around, radius: float, period: float = 12.0,
              tilt: float = 0.0, phase: float = 0.0):
        """
        Circle another body, keeping on spinning if it already was.

        ::

            self.add(earth.spin(0.4))
            self.add(moon.orbit(earth, radius=6, period=10))

        ``radius`` is in scene units from the centre of ``around``,
        ``period`` the seconds for one lap, ``tilt`` the degrees the orbit
        is inclined, ``phase`` where on the circle it starts.
        """
        self.stop_orbit()
        state = {"angle": float(phase)}
        incline = tilt * DEGREES

        def step(mob, dt):
            state["angle"] += TAU * dt / period
            a = state["angle"]
            offset = np.array([radius * np.cos(a), radius * np.sin(a), 0.0])
            if incline:
                c, s = np.cos(incline), np.sin(incline)
                offset = np.array([offset[0],
                                   c * offset[1] - s * offset[2],
                                   s * offset[1] + c * offset[2]])
            mob.shift(around.get_center() + offset - mob.get_center())

        self._orbit_updater = step
        self.add_updater(step)
        return self

    def stop_orbit(self):
        """Stop circling, stay where it is."""
        if getattr(self, "_orbit_updater", None) is not None:
            self.remove_updater(self._orbit_updater)
            self._orbit_updater = None
        return self

    # ------------------------------------------------------------ turning --

    @property
    def axis(self) -> np.ndarray:
        """
        The body's own pole, as a unit vector, wherever it is pointing now.

        Read from the mesh rather than worked out from the tilt, so it
        stays right after you move or rotate the body in the scene.
        """
        if getattr(self, "_pole_corner", None) is None:
            mesh = self.globe.mesh
            poles = np.argwhere(np.asarray(mesh.uvs)[:, 1] > 0.999).ravel()
            hit = np.argwhere(np.isin(mesh.tri_vt, poles))
            face, corner = hit[0]
            self._pole_corner = int(face) * 3 + int(corner)
        offset = (np.asarray(self.globe.get_points())[self._pole_corner]
                  - self.globe.get_center())
        length = np.linalg.norm(offset)
        return offset / length if length > 1e-9 else np.array([0.0, 0.0, 1.0])

    def spin(self, rate: float = 0.3, *, period: float | None = None,
             day: float | None = None):
        """
        Keep turning on the body's own axis, for as long as it is on screen.

        ::

            self.add(Earth().spin(0.3))            # 0.3 radians a second
            self.add(Mars().spin(period=8))        # one turn every 8 seconds
            self.add(Jupiter().spin(day=4))        # one Earth day = 4 seconds

        This is not the same as ``rotate``. ``rotate`` turns the body about
        an axis of the *scene*, which for a tilted planet makes the pole
        wander in a circle instead of the planet spinning. ``spin`` uses
        :attr:`axis`, the body's own pole, so Earth leans 23.44 degrees and
        turns underneath that lean, the way it actually does.

        ``day`` scales every body by its real sidereal period, so Jupiter
        visibly outruns Mars and Venus turns backwards, which it does.
        """
        if day is not None:
            hours = self.facts.rotation_period_h or 24.0
            rate = TAU / (day * abs(hours) / 24.0) * (1 if hours > 0 else -1)
        elif period is not None:
            rate = TAU / period

        self.stop_spin()
        self._spin_rate = rate

        def turn_a_little(mob, dt):
            mob.rotate(mob._spin_rate * dt, mob.axis,
                       about_point=mob.get_center())

        self._spin_updater = turn_a_little
        self.add_updater(turn_a_little)
        return self

    def stop_spin(self):
        """Take the spin off again."""
        if getattr(self, "_spin_updater", None) is not None:
            self.remove_updater(self._spin_updater)
            self._spin_updater = None
        return self

    def turn(self, angle: float = TAU, **kwargs) -> Rotating:
        """
        One measured turn on the body's own axis, as an animation.

        ::

            self.play(earth.turn(PI))
            self.play(earth.turn(TAU, run_time=4, rate_func=smooth))

        Everything ``Rotating`` takes is accepted -- ``run_time``,
        ``rate_func``, ``lag_ratio`` -- this only fills in the axis and the
        centre so you do not have to.
        """
        kwargs.setdefault("about_point", self.get_center())
        return Rotating(self, angle, axis=self.axis, **kwargs)

    # -------------------------------------------------------------- misc --

    def info(self) -> str:
        f = self.facts
        rings = (", ".join(f"{b.name} {b.inner:.2f}-{b.outer:.2f}"
                           for b in self.bands) or "none")
        extra = []
        if f.mass_kg is not None:
            extra.append(f"mass {f.mass_kg:.3g} kg")
        if f.surface_gravity_m_s2 is not None:
            extra.append(f"gravity {f.surface_gravity_m_s2} m/s2")
        if f.semi_major_axis_m is not None:
            extra.append(f"orbit {f.semi_major_axis_m / 1e9:,.2f} Gm")
        if f.orbital_period_days is not None:
            extra.append(f"year {f.orbital_period_days:,.2f} d")
        if f.mean_temp_c is not None:
            extra.append(f"mean {f.mean_temp_c} C")
        if f.moon_count is not None:
            extra.append(f"moons {f.moon_count}")
        lines = [
            f"{f.name}: r = {f.equatorial_radius_m / 1000:,.0f} km, "
            f"flattening {f.flattening:.4f}, tilt {self.tilt:.1f}deg",
            f"  mesh   : {self.globe.num_faces:,} triangles, "
            f"{self.quality} texture",
            f"  rings  : {rings}",
        ]
        if extra:
            lines.append("  facts  : " + ", ".join(extra))
        if f.note:
            lines.append(f"  note   : {f.note}")
        return "\n".join(lines)


class Graticule(VGroup):
    """
    The lat/lon mesh as a mobject in its own right. Every line in it is
    an ordinary ``VMobject``, so whatever you want done to one line --
    highlight it, thicken it, animate it -- is done with manim's own
    methods on the mobject the grid handed back.

    ::

        mesh = earth.graticule(30)
        mesh.parallel(60).set_stroke(YELLOW, 4)     # one parallel
        mesh.meridian(90).set_stroke(YELLOW, 4)     # one meridian

    ``parallels``, ``meridians`` and ``specials`` hold the lines in
    drawn order. ``parallel(lat)`` / ``meridian(lon)`` pick one by
    angle, and raise ``ValueError`` for an angle this grid does not
    carry -- the message names the standalone call that draws any
    angle on its own.
    """

    def __init__(self, parallels=(), meridians=(), specials=(), **kwargs):
        self.parallels = list(parallels)
        self.meridians = list(meridians)
        self.specials = list(specials)
        super().__init__(*self.parallels, *self.meridians, **kwargs)

    @staticmethod
    def _pick(lines, angle, kind, at):
        for line in lines:
            if abs(at(line) - angle) < 1e-6:
                return line
        raise ValueError(
            f"this grid carries no {kind} at {angle:g} degrees; "
            f"{kind}_line({angle:g}) draws any angle on its own")

    def parallel(self, lat: float) -> VMobject:
        return self._pick(self.parallels, lat, "latitude", lambda l: l.lat)

    def meridian(self, lon: float) -> VMobject:
        return self._pick(self.meridians, lon, "longitude", lambda l: l.lon)


def _lat_tag(lat: float, font_size: int, color) -> "Text":
    """The little value tag ``graticule(labels=True)`` pins to a parallel."""
    from manimlib.mobject.svg.text_mobject import Text
    return Text(f"{round(lat)}\N{DEGREE SIGN}", font_size=font_size,
                color=color)


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
