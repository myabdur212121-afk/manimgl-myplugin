"""
manimgl_myplugin.astro -- planets, moons and rings.

    from manimgl_myplugin.astro import Mars, Saturn, Moon

    self.add(Mars(radius=3))
    self.add(Saturn(radius=3, quality="4k"))

Each named class carries nothing but measured facts -- radius, flattening,
axial tilt, which texture, where the rings begin and end -- so nobody has
to look Saturn's oblateness up again. :class:`Body` takes the same
arguments directly for anything not in the table.

Textures are from Solar System Scope (CC BY 4.0) at 2k, 4k or 8k, fetched
on first use. Rings are flat annuli made with ``shapes.revolve``, and the
two shadows -- rings across the globe, globe across the rings -- are solved
analytically and painted in, because the renderer itself has none.
"""

from .bodies import (
    Body, RingBand, named,
    Mercury, Venus, Earth, Moon, Mars, Jupiter, Saturn, Uranus, Neptune,
)
from .data import BODIES, BodyFacts

__all__ = [
    "Body", "RingBand", "BodyFacts", "BODIES", "named",
    "Mercury", "Venus", "Earth", "Moon", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune",
]
