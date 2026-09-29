"""
manimgl_myplugin.shapes -- meshes from formulas rather than files.

Three builders, and a handful of small arrays to feed them:

    from_surface(mob)          anything ManimGL can already draw
    revolve(profile)           spin an outline around the z axis
    extrude(path, profile)     sweep a cross-section along a path

There is deliberately no ``sphere()`` or ``cube()`` here. ManimGL has those
already; :func:`from_surface` brings them into the toolkit instead, which is
less code and more shapes. What manim has no answer for is revolving an
outline and sweeping along a path, so those two are written out.

All three return a :class:`MeshData` with UVs, which every other part of
the plugin already knows how to work with.
"""

from .build import revolve, extrude, from_surface
from .profiles import (
    circle_profile, square_profile, polygon_profile, star_profile,
    semicircle_profile, line_path, arc_path, helix_path,
)

__all__ = [
    "revolve", "extrude", "from_surface",
    "circle_profile", "square_profile", "polygon_profile", "star_profile",
    "semicircle_profile", "line_path", "arc_path", "helix_path",
]
