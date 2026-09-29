"""
manim_obj -- Wavefront .obj models in ManimGL
=============================================

::

    from manimlib import *
    from manim_obj import OBJMobject

    class Demo(ThreeDScene):
        def construct(self):
            model = OBJMobject("building.obj", height=4, up_axis="z")
            self.add(model)

``OBJMobject`` is a real ``Surface``, so GPU lighting, depth testing,
camera-ordered transparency and every mobject method work on it unchanged.

Cheat sheet
-----------
======================================  ====================================
``OBJMobject(src, height=4)``           load a path / filename / URL / text
``.info()``                             what did I just load?
``.set_color_by("material")``           palette per named part
``.set_color_by("z", gradient=[...])``  gradient up the model
``.set_color_by(lambda c, n, i: ...)``  colour from a function
``.set_part_color("glass", BLUE_A,      recolour one named part
  opacity=0.4)``
``.shade_smooth()`` / ``.shade_flat()`` Gouraud vs flat lighting
``.get_part("roof")``                   one part as its own mobject
``.split_by("material")``               an ``OBJGroup`` you can ``explode()``
``.slice("z", high=1.2)``               cutaway
``.wireframe(feature_angle=25)``        crease edges as a ``VMobject``
``.point_cloud(4000)``                  dots over the surface
``BuildMesh(model, order="z")``         grow it in, triangle by triangle
======================================  ====================================
"""

from .loader import (
    MeshData,
    Material,
    load_mesh,
    parse_obj,
    parse_mtl,
    fetch_model,
    MODELS_DIR,
    CACHE_DIR,
)
from .obj_mobject import (
    OBJTextured,
    OBJMobject,
    OBJGroup,
    BuildMesh,
    AXIS_MATRICES,
    DEFAULT_PALETTE,
)

__version__ = "1.6.0"

__all__ = [
    "OBJMobject",
    "OBJTextured", "OBJGroup", "BuildMesh",
    "MeshData", "Material",
    "load_mesh", "parse_obj", "parse_mtl", "fetch_model",
    "MODELS_DIR", "CACHE_DIR", "AXIS_MATRICES", "DEFAULT_PALETTE",
    "__version__",
]
