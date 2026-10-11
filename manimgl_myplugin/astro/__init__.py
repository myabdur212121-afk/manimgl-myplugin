"""
manimgl_myplugin.astro -- planets, moons, rings and the Sun.

    from manimgl_myplugin.astro import Mars, Saturn, Moon, Sun

    self.add(Mars(radius=3))
    self.add(Saturn(radius=3, quality="4k"))
    self.add(Sun(radius=1.6))

Each named class carries nothing but measured facts -- radius, flattening,
axial tilt, which texture, where the rings begin and end -- so nobody has
to look Saturn's oblateness up again. :class:`Body` takes the same
arguments directly for anything not in the table.

The Sun's corona is real geometry: six concentric shells of additive
light around an unlit globe, calibrated against a measured falloff and
proven by occlusion -- a planet in front cuts the glow, a planet behind
is veiled under it. It needs the glow renderer patch (see notes 2.20).

Textures are from Solar System Scope (CC BY 4.0) at 2k, 4k or 8k, fetched
on first use. Rings are flat annuli made with ``shapes.revolve``, and the
two shadows -- rings across the globe, globe across the rings -- are solved
analytically and painted in, because the renderer itself has none.
"""

from .bodies import (
    Body, RingBand, named, CORONA_SHELLS,
    Mercury, Venus, Earth, Moon, Mars, Jupiter, Saturn, Uranus, Neptune,
    Sun,
)
from .data import BODIES, BodyFacts

__all__ = [
    "Body", "RingBand", "BodyFacts", "BODIES", "named", "CORONA_SHELLS",
    "Sun",
    "Mercury", "Venus", "Earth", "Moon", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune",
]
