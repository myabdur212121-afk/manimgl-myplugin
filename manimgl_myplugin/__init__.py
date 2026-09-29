"""
manimgl_myplugin — a set of helpers for ManimGL.

Each helper lives in its own subpackage and can be used on its own; the
names they export are re-exported here so scene code stays short:

    from manimgl_myplugin import OBJMobject         # short form
    from manimgl_myplugin.obj import OBJMobject     # explicit form

Helpers
-------
``obj``
    Wavefront ``.obj`` models as native ManimGL mobjects: loading, axis
    conversion, materials, real texture mapping, decimate / subdivide /
    displace, wireframes, point clouds, and a build-up animation.
    See ``docs/obj/reference.md``.
``shapes``
    Meshes from formulas instead of files -- revolve an outline, sweep a
    cross-section along a path, or read one out of any ManimGL surface.
    See ``docs/shapes/reference.md``.
``astro``
    Planets, moons and rings, each knowing its own radius, flattening and
    axial tilt. See ``docs/astro/reference.md``.

Anything that touches the renderer is imported lazily, so the parts that
are plain numpy — mesh reading and reshaping, for instance — work on a
machine with no manim installed at all.
"""

from __future__ import annotations

__version__ = "0.1.0"

#: helper name -> the names it contributes to the top level
_HELPERS: dict[str, tuple[str, ...]] = {
    "obj": (
        "OBJMobject", "OBJTextured", "OBJGroup", "BuildMesh",
        "MeshData", "Material",
        "load_mesh", "parse_obj", "parse_mtl", "fetch_model",
        "MODELS_DIR", "CACHE_DIR", "AXIS_MATRICES", "DEFAULT_PALETTE",
    ),
    "shapes": (
        "revolve", "extrude", "from_surface",
        "circle_profile", "square_profile", "polygon_profile",
        "star_profile", "semicircle_profile",
        "line_path", "arc_path", "helix_path",
    ),
    "astro": (
        "Body", "RingBand", "BodyFacts", "BODIES", "named",
        "Mercury", "Venus", "Earth", "Moon", "Mars",
        "Jupiter", "Saturn", "Uranus", "Neptune",
    ),
}

_OWNER = {name: helper for helper, names in _HELPERS.items() for name in names}


def __getattr__(name: str):                     # PEP 562
    """Pull a name in from whichever helper owns it, on first use."""
    helper = _OWNER.get(name)
    if helper is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(f"{__name__}.{helper}"), name)
    globals()[name] = value                     # only look it up once
    return value


def __dir__():
    return sorted(set(globals()) | set(_OWNER))


def helpers() -> dict[str, tuple[str, ...]]:
    """``{helper name: the names it exports}`` — handy at a prompt."""
    return {name: tuple(names) for name, names in _HELPERS.items()}


__all__ = ["helpers", "__version__", *sorted(_OWNER)]
