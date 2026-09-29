"""
manimgl_myplugin.astro.data -- what each body actually is.

Numbers here are measured facts, not scene settings: radii and flattening
from the IAU working group values, ring edges in units of the planet's own
radius. Keeping them in one table is the point of the helper -- nobody
should have to look up Saturn's oblateness again.

Textures come from Solar System Scope (CC BY 4.0, attribution in the
reference) at 2k, 4k or 8k, and are downloaded on first use.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["RingBand", "BodyFacts", "BODIES", "TEXTURE_BASE", "QUALITIES"]

TEXTURE_BASE = "https://www.solarsystemscope.com/textures/download"
QUALITIES = ("2k", "4k", "8k")


@dataclass(frozen=True)
class RingBand:
    """
    One flat annulus of a ring system.

    ``inner`` and ``outer`` are in units of the planet's equatorial radius,
    which is how ring edges are always quoted. ``opacity`` stands in for
    optical depth -- the B ring is nearly solid, the C ring barely there.
    """
    inner: float
    outer: float
    opacity: float = 0.8
    name: str = ""


@dataclass(frozen=True)
class BodyFacts:
    """Everything about a body that does not depend on the scene."""
    name: str
    equatorial_radius_m: float
    flattening: float = 0.0
    axial_tilt_deg: float = 0.0
    texture: str | None = None          # Solar System Scope stem
    night_texture: str | None = None
    rings: tuple[RingBand, ...] = ()
    solid: bool = True                  # False for the gas giants
    #: Sidereal rotation period in hours. Negative means retrograde --
    #: Venus and Uranus really do turn the other way.
    rotation_period_h: float = 24.0
    note: str = ""


#: Saturn's rings, edges in Saturn radii. The Cassini Division between B
#: and A is left out on purpose -- it is a real gap, so it is a real hole in
#: the geometry rather than a transparent patch of texture.
_SATURN_RINGS = (
    RingBand(1.239, 1.527, 0.22, "C"),
    RingBand(1.527, 1.951, 0.85, "B"),
    #        1.951  2.027          Cassini Division -- nothing here
    RingBand(2.027, 2.269, 0.55, "A"),
)

#: Uranus is tipped almost onto its side, so its rings stand up vertically.
_URANUS_RINGS = (
    RingBand(1.637, 1.653, 0.35, "alpha"),
    RingBand(1.863, 1.872, 0.40, "epsilon"),
)

_JUPITER_RINGS = (RingBand(1.72, 1.81, 0.10, "main"),)

_NEPTUNE_RINGS = (RingBand(2.15, 2.16, 0.12, "Adams"),)


BODIES: dict[str, BodyFacts] = {
    "mercury": BodyFacts("Mercury", 2_439_700, 0.0, 0.03, "mercury",
                       rotation_period_h=1407.6),
    "venus": BodyFacts("Venus", 6_051_800, 0.0, 177.4, "venus_atmosphere",
                       note="the cloud deck, not the surface",
                       rotation_period_h=-5832.5),
    "earth": BodyFacts("Earth", 6_378_137, 0.003353, 23.44, "earth_daymap",
                       night_texture="earth_nightmap",
                       rotation_period_h=23.9345),
    "moon": BodyFacts("Moon", 1_737_400, 0.0012, 6.68, "moon",
                       rotation_period_h=655.72),
    "mars": BodyFacts("Mars", 3_396_190, 0.005886, 25.19, "mars",
                       rotation_period_h=24.6229),
    "jupiter": BodyFacts("Jupiter", 71_492_000, 0.06487, 3.13, "jupiter",
                         rings=_JUPITER_RINGS, solid=False,
                       rotation_period_h=9.925),
    "saturn": BodyFacts("Saturn", 60_268_000, 0.09796, 26.73, "saturn",
                        rings=_SATURN_RINGS, solid=False,
                       rotation_period_h=10.656),
    "uranus": BodyFacts("Uranus", 25_559_000, 0.02293, 97.77, "uranus",
                        rings=_URANUS_RINGS, solid=False,
                        note="tipped on its side, so the rings stand up",
                       rotation_period_h=-17.24),
    "neptune": BodyFacts("Neptune", 24_764_000, 0.01708, 28.32, "neptune",
                         rings=_NEPTUNE_RINGS, solid=False,
                       rotation_period_h=16.11),
}


def texture_url(stem: str, quality: str = "2k", ext: str = "jpg") -> str:
    """Where a Solar System Scope texture lives."""
    if quality not in QUALITIES:
        raise ValueError(f"quality must be one of {QUALITIES}, not {quality!r}")
    return f"{TEXTURE_BASE}/{quality}_{stem}.{ext}"
