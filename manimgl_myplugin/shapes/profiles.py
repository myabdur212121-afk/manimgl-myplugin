"""
manimgl_myplugin.shapes.profiles -- the small arrays the builders take.

A *profile* is an ``(N, 2)`` array. :func:`~manimgl_myplugin.shapes.revolve`
reads it as ``(radius, height)`` pairs -- the outline seen from the side,
which it spins around the z axis. :func:`~manimgl_myplugin.shapes.extrude`
reads it as a closed loop in the plane across its path -- the shape of the
nozzle, so to speak.

A *path* is an ``(M, 3)`` array: where that nozzle travels.

Nothing here is special. They are ordinary numpy arrays and writing your own
is the point:

    z = np.linspace(0, 2, 60)
    r = 0.3 + 0.2 * np.sin(4 * z)
    mesh = revolve(np.stack([r, z], axis=-1))
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "circle_profile", "square_profile", "polygon_profile", "star_profile",
    "semicircle_profile", "line_path", "arc_path", "helix_path",
]


# ------------------------------------------------------------ profiles --

def circle_profile(radius: float = 1.0, sides: int = 32) -> np.ndarray:
    """A closed circle. The usual cross-section for a tube or a spring."""
    t = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    return np.stack([radius * np.cos(t), radius * np.sin(t)], axis=-1)


def square_profile(size: float = 1.0) -> np.ndarray:
    """A closed square, for ducts and bars."""
    h = size / 2
    return np.array([[-h, -h], [h, -h], [h, h], [-h, h]], dtype=float)


def polygon_profile(sides: int = 6, radius: float = 1.0) -> np.ndarray:
    """A regular polygon -- extrude it along a line to get a prism."""
    return circle_profile(radius, sides)


def star_profile(points: int = 5, outer: float = 1.0,
                 inner: float = 0.45) -> np.ndarray:
    """A star, alternating between two radii."""
    t = np.linspace(0, 2 * np.pi, 2 * points, endpoint=False)
    r = np.where(np.arange(2 * points) % 2 == 0, outer, inner)
    return np.stack([r * np.cos(t), r * np.sin(t)], axis=-1)


def semicircle_profile(radius: float = 1.0, samples: int = 48) -> np.ndarray:
    """``revolve`` this and you get a sphere. The simplest example there is."""
    t = np.linspace(0, np.pi, samples)
    return np.stack([radius * np.sin(t), -radius * np.cos(t)], axis=-1)


# --------------------------------------------------------------- paths --

def line_path(start=(0, 0, 0), end=(0, 0, 1), samples: int = 2) -> np.ndarray:
    """A straight run. Extrude a polygon along it and you have a prism."""
    return np.linspace(np.asarray(start, dtype=float),
                       np.asarray(end, dtype=float), samples)


def arc_path(radius: float = 1.0, angle: float = np.pi / 2,
             samples: int = 64, plane: str = "xy") -> np.ndarray:
    """A circular bend, for elbows and pipework."""
    t = np.linspace(0, angle, samples)
    a, b = radius * np.cos(t), radius * np.sin(t)
    zero = np.zeros_like(t)
    return {"xy": np.stack([a, b, zero], -1),
            "xz": np.stack([a, zero, b], -1),
            "yz": np.stack([zero, a, b], -1)}[plane]


def helix_path(turns: float = 4.0, radius: float = 1.0, pitch: float = 0.35,
               samples: int = 400) -> np.ndarray:
    """
    A rising spiral: ``turns`` loops of the given ``radius``, each one
    ``pitch`` higher than the last. Extrude a circle along it for a spring.
    """
    t = np.linspace(0, turns * 2 * np.pi, samples)
    return np.stack([radius * np.cos(t), radius * np.sin(t),
                     pitch * t / (2 * np.pi)], axis=-1)
