"""
manimgl_myplugin.obj.mobject
=====================

``OBJMobject`` -- a Wavefront .obj model as a first-class ManimGL mobject.

Why it works
------------
ManimGL's ``surface.wgsl`` reads its points as a plain list of triangles,
three records to each, whenever the ``resolution`` uniform is ``(0, 0)``.
``OBJMobject`` is a :class:`~manimlib.mobject.types.surface.Surface` that
does exactly that, so an imported mesh gets the same GPU lighting, depth
testing and camera-ordered transparency as ``Sphere`` or ``Torus``, and
every ordinary mobject method (``shift``, ``rotate``, ``set_color``,
``Transform``, ...) just works on it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

from manimlib.animation.animation import Animation
from manimlib.constants import BLUE_D, DOWN, GREY_A, GREY_B, GREY_D
from manimlib.constants import LEFT, ORIGIN, OUT, RIGHT, WHITE
from manimlib.mobject.mobject import Group, Mobject
from manimlib.mobject.types.dot_cloud import DotCloud
from manimlib.mobject.types.surface import Surface, TexturedSurface
from manimlib.mobject.types.vectorized_mobject import VMobject
from manimlib.utils.color import color_to_rgb, rgb_to_color
from manimlib.utils.rate_functions import smooth

from .loader import MeshData, MODELS_DIR, load_mesh, fetch_model

__all__ = ["OBJMobject", "OBJGroup", "BuildMesh", "AXIS_MATRICES", "DEFAULT_PALETTE"]


#: OBJ files disagree about which way is up. These send the file's axes to
#: manim's (x right, y depth, z up), keeping the handedness.
AXIS_MATRICES: dict[str, np.ndarray] = {
    "z": np.eye(3),                                             # already z-up (CAD)
    "y": np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float),   # y-up (the usual)
    "x": np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], float),    # x-up (rare)
}

#: Colours handed out by ``color_by="material" | "group" | "object"``.
DEFAULT_PALETTE = [
    "#58C4DD", "#FFB81C", "#83C167", "#FC6255", "#9A72AC",
    "#29ABCA", "#F0AC5F", "#5CD0B3", "#D147BD", "#C59978",
]


def _rgb(color) -> np.ndarray:
    return np.array(color_to_rgb(color), dtype=np.float32)


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.divide(v, n, out=np.zeros_like(v, dtype=float), where=n > 1e-12)


# ============================================================================
#  OBJMobject
# ============================================================================

class OBJMobject(Surface):
    """
    A Wavefront .obj model you can drop straight into a ManimGL scene.

    Quick start
    -----------
    ::

        from manimgl_myplugin import OBJMobject

        model = OBJMobject("building.obj", height=4, up_axis="z")
        self.add(model)

    Anything that names a model works -- a path, a bare filename looked up in
    ``~/models``, raw OBJ text, or a URL, which is downloaded once and cached::

        OBJMobject("https://example.com/teapot.obj", height=3)

    Parameters
    ----------
    source
        Path, filename, URL, raw OBJ text, or a ready :class:`MeshData`.
    height, width, depth, scale
        Size in manim units. ``height`` is the z extent, ``width`` the x
        extent, ``depth`` the y extent; give one and the other two follow.
        ``scale`` instead multiplies the file's own units.
    up_axis : {"y", "z", "x", "auto", None}
        Which axis of the *file* points up. ``"y"`` is the OBJ convention and
        the default; CAD exports (Rhino, Revit, SketchUp) are usually
        ``"z"``. ``"auto"`` guesses the axis with the smallest extent, which
        suits buildings and terrain. ``None`` leaves the axes untouched.
    center : bool
        Put the model's bounding-box centre at the origin. Default ``True``.
    color
        A single colour for the whole model, or a list blended across it.
        Leave it ``None`` to let ``color_by`` / the .mtl decide.
    opacity : float
    color_by : str or callable or None
        How to paint the model:

        ``"material"`` / ``"group"`` / ``"object"``
            one palette colour per named part of the file
        ``"x"`` / ``"y"`` / ``"z"`` / ``"height"``
            a gradient along that axis
        ``"normal"``
            colour from the direction each face points
        ``"random"``
            a different palette colour per face
        callable
            ``f(center, normal, index) -> colour``, called per triangle

    palette, gradient
        Colour lists for the categorical and gradient modes above.
    use_mtl : bool
        Take diffuse colours and opacities from the .mtl file when it has
        them. Default ``True``; ``color`` and ``color_by`` override it.
    smooth : bool
        Bake smooth (Gouraud) vertex-normal shading instead of the GPU's
        flat per-face shading. See :meth:`shade_smooth`.
    shading : (reflectiveness, gloss, shadow)
    flip_faces : bool
        Reverse the winding, which flips which side the light falls on. Try
        it when a model comes out looking inside-out.
    face_filter : callable
        ``f(center, normal, index) -> bool``, keeping only the triangles it
        likes. Handy for cutaways.
    decimate : int or float
        Throw triangles away until only this many are left (or this fraction
        of them, at or below 1), keeping the shape as close as it can.
        See :meth:`MeshData.decimate`.
    subdivide : int
        Split every triangle into four, this many times over. With
        ``smooth_subdivide`` (the default) the model genuinely rounds off,
        outline included; turn it off for anything with sharp corners.
        See :meth:`MeshData.subdivide`.
    displace : str or True
        A height map to push the vertices out along their normals, turning
        painted relief into real geometry. ``True`` uses the one the .mtl
        names. Only works with enough vertices to move, so pair it with
        ``subdivide``. ``displace_strength`` is a fraction of the model's
        size. See :meth:`MeshData.displace`.
    dedupe : {"auto", "rare", "common", "first", "last"} or list or False
        Throw away triangles that sit exactly on top of another triangle.
        CAD exports often write the same wall twice on two different layers;
        the depth test cannot choose between them, so the wall comes out
        speckled with the two colours fighting pixel by pixel. ``"auto"``
        (the default) removes the twins that carry *different* materials --
        the only ones that are actually visible -- keeping the rarer, more
        specific material and saying so on stdout. Same-material twins are
        left alone because they cannot show. Pass a rule name to choose the
        survivor differently, a list of material names in priority order, or
        ``False`` to load the file exactly as written.
        See :meth:`MeshData.dedupe_coincident`.
    vertex_func : callable
        ``f(points) -> points``, applied to the ``(V, 3)`` vertex array after
        the axis swap -- bends, twists, explosions, anything.
    depth_test : bool
        Default ``True``, which is what a solid needs.
    cache : bool
        Cache the parsed mesh on disk. Default ``True``.
    """

    # One vertex per record: the points are the triangle corners themselves.
    verts_per_record: int = 1

    def __init__(
        self,
        source,
        *,
        height: float | None = None,
        width: float | None = None,
        depth: float | None = None,
        scale: float | None = None,
        up_axis: str | None = "y",
        center: bool = True,
        color=None,
        opacity: float = 1.0,
        color_by: str | Callable | None = None,
        palette: Sequence | None = None,
        gradient: Sequence | None = None,
        use_mtl: bool = True,
        smooth: bool = False,
        shading: tuple[float, float, float] = (0.25, 0.3, 0.4),
        flip_faces: bool = False,
        face_filter: Callable | None = None,
        dedupe: bool | str | Sequence[str] = "auto",
        decimate: int | float | None = None,
        subdivide: int = 0,
        smooth_subdivide: bool = True,
        displace: str | bool | None = None,
        displace_strength: float = 0.04,
        vertex_func: Callable | None = None,
        depth_test: bool = True,
        cache: bool = True,
        **kwargs,
    ):
        mesh = load_mesh(source, cache=cache)

        if dedupe is not False and dedupe is not None:
            rule = "rare" if dedupe in (True, "auto") else dedupe
            mesh, removed = mesh.dedupe_coincident(rule, report=True)
            if removed and dedupe == "auto":
                print(f"[manimgl_myplugin] dropped {removed} coincident duplicate "
                      f"faces (z-fighting); pass dedupe=False to keep them")

        # Coarsen first, then refine, then push the relief out: each step
        # wants the one before it to have settled.
        if decimate:
            mesh = mesh.decimate(decimate)
        if subdivide:
            mesh = mesh.subdivide(subdivide, smooth=smooth_subdivide)
        if displace is not None and displace is not False:
            height_map = (mesh.texture_path("bump") if displace is True
                          else displace)
            if height_map is None:
                raise FileNotFoundError(
                    f"{mesh.source} names no bump map, so displace=True has "
                    "nothing to use -- give it a path instead")
            mesh = mesh.displace(height_map, strength=displace_strength)

        if face_filter is not None:
            centers, normals = mesh.face_centers(), mesh.face_normals()
            keep = np.array([bool(face_filter(c, n, i))
                             for i, (c, n) in enumerate(zip(centers, normals))])
            mesh = mesh.select(keep)

        matrix = self._axis_matrix(up_axis, mesh)
        if matrix is not None:
            mesh = mesh.transform(matrix)
        if vertex_func is not None:
            mesh = mesh.copy()
            mesh.vertices = np.asarray(
                vertex_func(mesh.vertices), dtype=np.float32
            ).reshape(-1, 3)
        if flip_faces:
            mesh = mesh.copy()
            mesh.tri_v = mesh.tri_v[:, ::-1].copy()
            mesh.tri_vt = mesh.tri_vt[:, ::-1].copy()
            mesh.tri_vn = mesh.tri_vn[:, ::-1].copy()

        self.mesh = mesh
        self.up_axis = up_axis
        # Wanted by init_points / init_colors, which Mobject.__init__ calls
        self._fit = dict(height=height, width=width, depth=depth,
                         scale=scale, center=center)
        self.color_by = color_by
        self.palette = list(palette) if palette else list(DEFAULT_PALETTE)
        self.gradient = list(gradient) if gradient else [GREY_D, GREY_A]
        self.use_mtl = use_mtl
        self.default_shading = tuple(shading)
        self._explicit_color = color is not None
        #: Per-vertex lighting currently baked in by shade_smooth, so it can
        #: be divided back out. None means the colours are unshaded.
        self._shade_lam: np.ndarray | None = None
        self._smooth_wanted = smooth
        #: Filled in by :meth:`color_by_part` -- ``{part name: colour}``
        self.part_colors: dict[str, object] = {}
        self.part_color_kind: str = "material"

        super().__init__(
            color=color if color is not None else BLUE_D,
            opacity=opacity,
            shading=shading,
            depth_test=depth_test,
            resolution=(0, 0),      # == "these points are a triangle list"
            **kwargs,
        )

        if smooth:
            self.shade_smooth()

    # -- construction --------------------------------------------------------

    @staticmethod
    def _axis_matrix(up_axis: str | None, mesh: MeshData) -> np.ndarray | None:
        if up_axis is None:
            return None
        key = str(up_axis).lower()
        if key == "auto":
            key = "xyz"[int(np.argmin(mesh.size))]
        if key not in AXIS_MATRICES:
            raise ValueError(
                f"up_axis must be one of 'x', 'y', 'z', 'auto' or None, got {up_axis!r}"
            )
        m = AXIS_MATRICES[key]
        return None if np.allclose(m, np.eye(3)) else m

    def init_points(self) -> None:
        self.set_points(self.mesh.triangle_points())
        fit = self._fit
        if fit["center"]:
            self.center()
        if fit["scale"] is not None:
            self.scale(fit["scale"])
        # Sized along the axis a person means, not manim's 2D naming: for a
        # model standing up in the scene, "height" is how tall it is (z).
        for key, dim in (("height", 2), ("width", 0), ("depth", 1)):
            if fit[key] is not None:
                self.rescale_to_fit(fit[key], dim)
                break

    def init_colors(self) -> None:
        if self.color_by is not None:
            self.set_color_by(self.color_by)
        elif self._explicit_color:
            # An explicit colour= wins over whatever the .mtl says, which is
            # what the docstring promises and what people expect.
            super().init_colors()
        elif self.use_mtl and self._mtl_has_colors():
            self.color_by_mtl()
        else:
            super().init_colors()
        self.set_opacity(self.opacity)
        self._shade_lam = None

    # -- facts ---------------------------------------------------------------

    @property
    def num_faces(self) -> int:
        return self.mesh.num_faces

    @property
    def num_vertices(self) -> int:
        return self.mesh.num_vertices

    def parts(self, kind: str = "material") -> dict[str, int]:
        """``{name: triangle count}`` for the model's materials/groups/objects."""
        return self.mesh.face_counts(kind)

    def info(self) -> str:
        """A short readable description -- handy while you find your feet."""
        w, d, h = self.get_shape()          # x, y, z extents
        return (
            f"{self.mesh.summary()}\n"
            f"  in scene : {w:.2f} wide (x) x {d:.2f} deep (y) x {h:.2f} tall (z)"
            f"  at {np.round(self.get_center(), 2).tolist()}"
        )

    def transformed_vertices(self) -> np.ndarray:
        """
        ``(V, 3)`` -- where each *file* vertex ended up in the scene, after the
        axis swap, the fit and every transform since.
        """
        out = np.zeros((self.mesh.num_vertices, 3), dtype=np.float32)
        out[self.mesh.tri_v.reshape(-1)] = self.get_points()
        return out

    def face_centers(self) -> np.ndarray:
        """``(F, 3)`` centroid of every triangle, in scene coordinates."""
        return self.get_points().reshape(-1, 3, 3).mean(axis=1)

    def face_normals(self) -> np.ndarray:
        """``(F, 3)`` unit normal of every triangle, in scene coordinates."""
        p = self.get_points().reshape(-1, 3, 3)
        return _normalize(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])).astype(np.float32)

    # -- colour --------------------------------------------------------------

    def set_face_colors(self, rgb: np.ndarray, opacity=None):
        """Paint the model from an ``(F, 3)`` array of rgb values in [0, 1]."""
        rgb = np.asarray(rgb, dtype=np.float32).reshape(-1, 3)
        with self.data.being_written() as data:
            data["rgba"][:, :3] = np.repeat(rgb, 3, axis=0)
            if opacity is not None:
                op = np.asarray(opacity, dtype=np.float32).reshape(-1)
                data["rgba"][:, 3] = (np.repeat(op, 3) if op.size > 1 else op[0])
        self._shade_lam = None
        return self

    def set_texture_colors(self, image, *, per: str = "corner",
                           samples: int = 3, brighten: float = 1.0):
        """
        Paint the model from its own texture map, using the ``vt``
        coordinates in the .obj file.

        ::

            earth = OBJMobject("earth.obj", height=4)
            earth.set_texture_colors("4096_earth.jpg")

        This is not real texture mapping. A ManimGL surface carries colour on
        its *vertices*, so the most this can do is sample the image once per
        vertex and let the GPU interpolate in between -- there is no lookup
        per pixel. On a mesh that is reasonably dense for its screen size,
        which is most scanned or spherical models, it reads as the texture
        anyway, and it costs nothing at render time.

        ``per``
            ``"corner"`` samples at each of a triangle's three UVs, so the
            colour gradates across the face -- much smoother, and the
            default. ``"face"`` takes one colour for the whole triangle,
            which gives a deliberately faceted, low-poly look.
        ``samples``
            Only for ``per="face"``: how many points inside the triangle to
            average (1 is the centre alone).
        ``brighten``
            Scales the result, which helps when a texture was authored for a
            lit scene and looks muddy under flat shading.

        ``image`` is a path or a URL; a URL is downloaded once and cached
        next to the models.

        Needs Pillow, and an .obj that actually carries ``vt`` lines --
        :attr:`MeshData.uvs` is empty otherwise, and this raises.
        """
        try:
            from PIL import Image
        except ImportError as exc:                       # pragma: no cover
            raise ImportError(
                "set_texture_colors needs Pillow: pip install pillow") from exc

        mesh = self.mesh
        if mesh.uvs is None or not len(mesh.uvs) or mesh.tri_vt.max() < 0:
            raise ValueError(
                f"{mesh.source} has no vt coordinates, so there is nothing to "
                "look the texture up with -- use color_by=... instead")

        path = str(image)
        if path.startswith(("http://", "https://")):
            path = str(fetch_model(path, companions=False, quiet=True))
        pixels = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
        height, width = pixels.shape[:2]

        def sample(points: np.ndarray) -> np.ndarray:
            # u wraps around the seam; v is measured from the bottom in OBJ
            # files but from the top in images.
            col = np.clip((points[:, 0] % 1.0) * (width - 1), 0, width - 1)
            row = np.clip((1.0 - points[:, 1] % 1.0) * (height - 1), 0, height - 1)
            return pixels[row.astype(np.int32), col.astype(np.int32)]

        uv = mesh.uvs[np.clip(mesh.tri_vt, 0, len(mesh.uvs) - 1)]   # (F, 3, 2)

        if str(per).lower() == "corner":
            rgb = sample(uv.reshape(-1, 2))                         # (3F, 3)
            with self.data.being_written() as data:
                data["rgba"][:, :3] = np.clip(rgb * brighten, 0.0, 1.0)
            self._shade_lam = None
            return self

        weights = np.array([[1 / 3, 1 / 3, 1 / 3]]) if samples <= 1 else np.array(
            [[1 / 3, 1 / 3, 1 / 3], [.6, .2, .2], [.2, .6, .2], [.2, .2, .6]]
        )[:samples]
        rgb = np.zeros((len(uv), 3), dtype=np.float32)
        for w in weights:
            rgb += sample((uv * w[None, :, None]).sum(axis=1))
        rgb /= len(weights)

        return self.set_face_colors(np.clip(rgb * brighten, 0.0, 1.0))

    def textured(self, image=None, dark_image=None, **kwargs) -> "OBJTextured":
        """
        The same model drawn with **real** texture mapping.

        ::

            earth = OBJMobject("earth.obj", height=4).textured()
            self.add(earth)

        Leave ``image`` out and the file is asked what it wants: the .mtl
        names its images in ``map_Kd``, and they are looked for next to the
        .obj and then in the models directory. A .mtl only ever names an
        image, never contains one, so the picture does have to be there --
        but you should not have to repeat its name.

        Where :meth:`set_texture_colors` samples the image once per vertex
        and lets the colours blur into each other, this hands the image to
        the GPU and looks it up per pixel, so the map stays sharp however
        close the camera gets. Use it whenever the .obj carries ``vt``
        coordinates and you have the texture file; it is both crisper and
        cheaper.

        ``dark_image`` is an optional second texture for the unlit side --
        city lights on a night-time Earth, for instance.

        The result is a :class:`OBJTextured`, not an ``OBJMobject``: it takes
        its colour from the image, so the ``set_color_by`` family no longer
        applies. Everything positional -- ``rotate``, ``scale``, ``shift``,
        :class:`BuildMesh` -- works as before.
        """
        mesh = self.mesh
        if mesh.uvs is None or not len(mesh.uvs) or mesh.tri_vt.max() < 0:
            raise ValueError(
                f"{mesh.source} has no vt coordinates, so the texture has "
                "nothing to be pinned to -- use set_color_by(...) instead")

        if image is None:
            image = mesh.texture_path("diffuse")
            if image is None:
                named = [m.texture for m in mesh.materials.values() if m.texture]
                raise FileNotFoundError(
                    f"{mesh.source} does not say which image to use"
                    if not named else
                    f"the .mtl asks for {named[0]!r}, which is not next to "
                    f"the .obj or in {MODELS_DIR}; download it, or pass the "
                    "path to textured() yourself")

        # map_Ke is the glow map -- city lights on the night side of a globe.
        # It is exactly what the second texture slot is for, so use it.
        if dark_image is None:
            dark_image = mesh.texture_path("emissive")
        elif dark_image is False:
            dark_image = None

        return OBJTextured(self, image, dark_image, **kwargs)

    def set_color_by(self, mode: str | Callable, **kwargs):
        """
        Repaint using one of the ``color_by`` modes. See the class docstring.
        """
        if callable(mode):
            return self.color_by_function(mode, **kwargs)
        key = str(mode).lower()
        if key in ("material", "group", "object"):
            return self.color_by_part(key, **kwargs)
        if key in ("x", "y", "z", "height", "depth", "width"):
            axis = {"height": "z", "depth": "y", "width": "x"}.get(key, key)
            return self.color_by_axis(axis, **kwargs)
        if key == "normal":
            return self.color_by_normal(**kwargs)
        if key == "random":
            return self.color_by_random(**kwargs)
        if key == "mtl":
            return self.color_by_mtl(**kwargs)
        raise ValueError(f"unknown color_by mode: {mode!r}")

    def color_by_part(self, kind: str = "material", palette=None):
        """
        One palette colour per material / group / object.

        Only the names that actually own triangles get a colour, and the
        mapping is kept in :attr:`part_colors` so a legend can be built from
        exactly what was drawn rather than from a guess.
        """
        palette = list(palette or self.palette)
        labels, names = self.mesh.labels(kind), self.mesh.names(kind)
        used = np.unique(labels)
        self.part_colors = {
            names[lab]: palette[i % len(palette)] for i, lab in enumerate(used)
        }
        self.part_color_kind = kind
        lookup = {lab: _rgb(palette[i % len(palette)]) for i, lab in enumerate(used)}
        rgb = np.array([lookup[l] for l in labels], dtype=np.float32)
        return self.set_face_colors(rgb)

    def legend(self, font: str = "DejaVu Sans Mono", font_size: int = 16,
               text_color=GREY_A, swatch: float = 0.18, buff: float = 0.14,
               counts: bool = True):
        """
        A swatch-and-name key for the colours :meth:`color_by_part` handed
        out, ordered by how much of the model each one covers. ``fix_in_frame``
        it and drop it in a corner.
        """
        from manimlib.mobject.geometry import Square
        from manimlib.mobject.svg.text_mobject import Text
        from manimlib.mobject.types.vectorized_mobject import VGroup

        if not self.part_colors:
            raise RuntimeError("call set_color_by('material') before legend()")
        totals = self.parts(self.part_color_kind)
        rows = VGroup()
        for name, color in sorted(self.part_colors.items(),
                                  key=lambda kv: -totals.get(kv[0], 0)):
            n = totals.get(name, 0)
            chip = Square(side_length=swatch, fill_color=color,
                          fill_opacity=1, stroke_width=0)
            label = Text(f"{name}   {n:,}" if counts else name,
                         font=font, font_size=font_size, color=text_color)
            rows.add(VGroup(chip, label).arrange(RIGHT, buff=swatch))
        return rows.arrange(DOWN, buff=buff, aligned_edge=LEFT)

    def color_by_mtl(self, fallback=None):
        """Diffuse colour (and ``d`` opacity) from the .mtl file."""
        mats, names = self.mesh.materials, self.mesh.material_names
        base = _rgb(fallback if fallback is not None else self.color)
        rgbs, ops = [], []
        for name in names:
            m = mats.get(name)
            rgbs.append(_rgb(m.hex_color) if (m and m.diffuse) else base)
            ops.append(m.opacity if m else 1.0)
        labels = self.mesh.tri_material
        return self.set_face_colors(np.array(rgbs)[labels],
                                    opacity=np.array(ops)[labels] * self.opacity)

    def color_by_axis(self, axis: str = "z", gradient=None, reverse: bool = False):
        """A gradient along ``x``, ``y`` or ``z``."""
        i = "xyz".index(axis)
        stops = [_rgb(c) for c in (gradient or self.gradient)]
        vals = self.face_centers()[:, i].astype(np.float64)
        lo, hi = vals.min(), vals.max()
        t = np.zeros_like(vals) if hi - lo < 1e-9 else (vals - lo) / (hi - lo)
        if reverse:
            t = 1.0 - t
        stops = np.array(stops)
        pos = t * (len(stops) - 1)
        i0 = np.clip(np.floor(pos).astype(int), 0, len(stops) - 1)
        i1 = np.clip(i0 + 1, 0, len(stops) - 1)
        f = (pos - i0)[:, None]
        return self.set_face_colors(stops[i0] * (1 - f) + stops[i1] * f)

    def color_by_normal(self, saturation: float = 1.0):
        """Colour each face from the direction it points -- a debug view that looks good."""
        rgb = np.abs(self.face_normals())
        rgb = rgb * saturation + (1 - saturation)
        return self.set_face_colors(np.clip(rgb, 0, 1))

    def color_by_random(self, palette=None, seed: int | None = 0):
        """A random palette colour per triangle."""
        palette = np.array([_rgb(c) for c in (palette or self.palette)])
        rng = np.random.default_rng(seed)
        return self.set_face_colors(palette[rng.integers(0, len(palette), self.num_faces)])

    def color_by_function(self, func: Callable):
        """
        ``func(center, normal, index) -> colour``, called once per triangle.

        ::

            model.color_by_function(
                lambda c, n, i: TEAL if n[2] > 0.9 else GREY_C
            )
        """
        centers, normals = self.face_centers(), self.face_normals()
        rgb = np.array([_rgb(func(c, n, i))
                        for i, (c, n) in enumerate(zip(centers, normals))],
                       dtype=np.float32)
        return self.set_face_colors(rgb)

    def set_part_color(self, pattern: str, color=None, opacity=None, *,
                       kind: str = "material", regex: bool = False):
        """
        Recolour just the named part, leaving the rest alone::

            model.set_part_color("glass", BLUE_A, opacity=0.35)
        """
        mask = np.repeat(self.mesh.match_faces(pattern, kind, regex), 3)
        if not mask.any():
            return self
        with self.data.being_written() as data:
            if color is not None:
                data["rgba"][mask, :3] = _rgb(color)
            if opacity is not None:
                data["rgba"][mask, 3] = opacity
        self._shade_lam = None
        return self

    def _mtl_has_colors(self) -> bool:
        return any(m.diffuse for m in self.mesh.materials.values())

    # -- shading -------------------------------------------------------------

    def shade_smooth(self, light_direction=(-1.0, -1.0, 1.5),
                     ambient: float = 0.42, strength: float = 0.72):
        """
        Smooth (Gouraud) shading.

        ManimGL's mesh shader only knows flat per-face normals, so this bakes
        lighting from averaged *vertex* normals into the vertex colours and
        switches the GPU's own shading off. Curved models stop looking
        faceted; flat-walled ones are usually better left alone.
        """
        light = _normalize(np.array(light_direction, dtype=float))
        normals = self.mesh.corner_normals(smooth=True)
        lam = ambient + strength * np.clip(normals @ light, 0, 1)
        base = self._unshaded_rgb()
        with self.data.being_written() as data:
            data["rgba"][:, :3] = np.clip(base * lam[:, None], 0, 1)
        self.set_shading(0.0, 0.0, 0.0)
        self._shade_lam = lam
        self._smooth_wanted = True
        return self

    def _unshaded_rgb(self) -> np.ndarray:
        """
        The colours as they were before any baked lighting.

        Derived from the live vertex data rather than from a copy kept to one
        side, because ``Transform`` writes straight into ``data`` and would
        leave such a copy describing the colours the model used to have.
        """
        rgb = np.asarray(self.data["rgba"][:, :3], dtype=float)
        lam = self._shade_lam
        if lam is None or len(lam) != len(rgb):
            return rgb
        return np.clip(rgb / np.maximum(lam[:, None], 1e-6), 0.0, 1.0)

    def shade_flat(self):
        """Back to the GPU's flat per-face shading (the default)."""
        if self._shade_lam is not None:
            base = self._unshaded_rgb()
            with self.data.being_written() as data:
                data["rgba"][:, :3] = base
            self._shade_lam = None
        self.set_shading(*self.default_shading)
        self._smooth_wanted = False
        return self

    # -- pulling the model apart ---------------------------------------------

    def get_part(self, pattern: str, *, kind: str = "material",
                 regex: bool = False, **kwargs) -> "OBJMobject":
        """
        A new ``OBJMobject`` holding only the matching triangles, sitting
        exactly where they already are::

            windows = model.get_part("glass")
        """
        mask = self.mesh.match_faces(pattern, kind, regex)
        if not mask.any():
            raise KeyError(
                f"no {kind} matches {pattern!r}. Available: "
                f"{sorted(self.parts(kind))[:12]}"
            )
        return self._submesh(self.mesh.select(mask), mask, **kwargs)

    def split_by(self, kind: str = "material", **kwargs) -> "OBJGroup":
        """
        Break the model into one ``OBJMobject`` per material / group / object,
        wrapped in an :class:`OBJGroup` so you can ``explode()`` it.
        """
        parts, names = [], []
        labels = self.mesh.labels(kind)
        for i, name in enumerate(self.mesh.names(kind)):
            mask = labels == i
            if mask.any():
                parts.append(self._submesh(self.mesh.select(mask), mask, **kwargs))
                names.append(name)
        return OBJGroup(*parts, names=names, kind=kind)

    def filter_faces(self, predicate: Callable, **kwargs) -> "OBJMobject":
        """``predicate(center, normal, index) -> bool``, as a new model."""
        centers, normals = self.mesh.face_centers(), self.mesh.face_normals()
        mask = np.array([bool(predicate(c, n, i))
                         for i, (c, n) in enumerate(zip(centers, normals))])
        return self._submesh(self.mesh.select(mask), mask, **kwargs)

    def slice(self, axis: str = "z", low: float = -np.inf,
              high: float = np.inf, **kwargs) -> "OBJMobject":
        """Keep the triangles whose centre falls in a slab -- a quick cutaway."""
        i = "xyz".index(axis)
        c = self.face_centers()[:, i]
        mask = (c >= low) & (c <= high)
        return self._submesh(self.mesh.select(mask), mask, **kwargs)

    def _submesh(self, mesh: MeshData, mask: np.ndarray, **kwargs) -> "OBJMobject":
        """A child model that inherits this one's colours and placement."""
        part = OBJMobject(
            mesh, up_axis=None, center=False,
            shading=self.default_shading,
            depth_test=self.depth_test,
            use_mtl=False, **kwargs,
        )
        part.set_points(self.get_points().reshape(-1, 3, 3)[mask].reshape(-1, 3))
        if "color" not in kwargs and "color_by" not in kwargs:
            with part.data.being_written() as data:
                data["rgba"] = self.data["rgba"].reshape(-1, 3, 4)[mask].reshape(-1, 4)
            part._shade_lam = None
        part.set_shading(*self.get_shading())
        return part

    # -- extra mobjects derived from the model -------------------------------

    def wireframe(self, color=WHITE, width: float = 1.0, *,
                  feature_angle: float = 25.0, max_edges: int = 8000,
                  nudge: float = 0.0) -> VMobject:
        """
        The model's edges as a single ``VMobject``.

        ``feature_angle`` keeps only creases -- edges where the two faces turn
        by more than that many degrees -- plus open boundaries. For a building
        that draws the outlines and skips the noise inside flat walls. Pass
        ``feature_angle=0`` for every edge.

        The result is a plain VMobject, so ``ShowCreation`` works on it, which
        is the easiest way to animate a model appearing.
        """
        verts = self.transformed_vertices()
        tri = self.mesh.tri_v
        normals = self.face_normals()

        edge_faces: dict[tuple[int, int], list[int]] = {}
        for f, (a, b, c) in enumerate(tri):
            for u, v in ((a, b), (b, c), (c, a)):
                edge_faces.setdefault((u, v) if u < v else (v, u), []).append(f)

        cos_limit = np.cos(np.deg2rad(feature_angle))
        keep = []
        for edge, faces in edge_faces.items():
            if len(faces) == 1:
                keep.append(edge)
            elif feature_angle <= 0:
                keep.append(edge)
            elif float(normals[faces[0]] @ normals[faces[1]]) < cos_limit:
                keep.append(edge)

        if len(keep) > max_edges:
            step = len(keep) / max_edges
            keep = [keep[int(i * step)] for i in range(max_edges)]

        offset = nudge * OUT
        vmob = VMobject(stroke_color=color, stroke_width=width, fill_opacity=0)
        for u, v in keep:
            vmob.start_new_path(verts[u] + offset)
            vmob.add_line_to(verts[v] + offset)
        if self.depth_test:
            vmob.apply_depth_test()
        return vmob

    def bounding_box_mobject(self, color=GREY_B, width: float = 1.5,
                             buff: float = 0.0) -> VMobject:
        """A wireframe box around the model."""
        lo, hi = self.get_bounding_box()[0] - buff, self.get_bounding_box()[2] + buff
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        edges = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3),
                 (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]
        vmob = VMobject(stroke_color=color, stroke_width=width, fill_opacity=0)
        for u, v in edges:
            vmob.start_new_path(corners[u])
            vmob.add_line_to(corners[v])
        return vmob

    def point_cloud(self, n_points: int = 4000, color=None,
                    radius: float = 0.02, glow_factor: float = 0.0,
                    seed: int | None = 0) -> DotCloud:
        """
        ``n_points`` dots scattered over the surface, area-weighted.

        A lovely way to bring a model in: ``ReplacementTransform`` a point
        cloud into the solid, or the other way round.
        """
        rng = np.random.default_rng(seed)
        tri = self.get_points().reshape(-1, 3, 3)
        areas = 0.5 * np.linalg.norm(
            np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
        total = areas.sum()
        probs = areas / total if total > 0 else np.full(len(areas), 1 / len(areas))
        pick = rng.choice(len(tri), size=n_points, p=probs)
        r1, r2 = rng.random(n_points), rng.random(n_points)
        s = np.sqrt(r1)
        w = np.stack([1 - s, s * (1 - r2), s * r2], axis=1)[:, :, None]
        pts = (tri[pick] * w).sum(axis=1)
        cloud = DotCloud(pts, radius=radius, glow_factor=glow_factor)
        if color is not None:
            cloud.set_color(color)
        else:
            cloud.set_rgba_array(self.data["rgba"].reshape(-1, 3, 4).mean(axis=1)[pick])
        if self.depth_test:
            cloud.apply_depth_test()
        return cloud

    # -- convenience ---------------------------------------------------------

    @classmethod
    def from_url(cls, url: str, name: str | None = None, **kwargs) -> "OBJMobject":
        """Download (once, then cached) and build in a single call."""
        return cls(fetch_model(url, name), **kwargs)

    def copy_model(self, **overrides) -> "OBJMobject":
        """A fresh model from the same mesh, with some parameters changed."""
        return OBJMobject(self.mesh, up_axis=None, **overrides)


# ============================================================================
#  A group of parts
# ============================================================================

class OBJTextured(TexturedSurface):
    """
    An :class:`OBJMobject` painted by a real texture lookup in the shader.

    Made by :meth:`OBJMobject.textured` rather than directly. ManimGL's
    ``TexturedSurface`` normally expects a parametric grid and derives the
    image coordinates from it; this feeds it a plain triangle list instead
    and takes the coordinates straight from the ``vt`` lines of the file.
    """

    def __init__(self, source: OBJMobject, image_file, dark_image_file=None,
                 **kwargs):
        self.source = source
        self.mesh = source.mesh
        super().__init__(source, str(image_file),
                         None if dark_image_file is None else str(dark_image_file),
                         **kwargs)

    def init_points(self) -> None:
        src = self.source
        self.resize_points(len(src.data))
        # Zero resolution is how the shader is told these points are a plain
        # list of triangles rather than a grid.
        self.set_resolution((0, 0))
        self.data["point"] = src.data["point"]
        self.data["opacity"][:, 0] = src.data["rgba"][:, 3]
        self.data["im_coords"] = self.corner_uvs()

    def corner_uvs(self) -> np.ndarray:
        """``(3F, 2)`` image coordinates, one per triangle corner."""
        mesh = self.mesh
        uv = mesh.uvs[np.clip(mesh.tri_vt, 0, len(mesh.uvs) - 1)].reshape(-1, 2)
        uv = np.asarray(uv, dtype=np.float32).copy()
        # OBJ counts v from the bottom of the image, the sampler from the top.
        uv[:, 1] = 1.0 - uv[:, 1]
        return uv

    @property
    def num_faces(self) -> int:
        return self.mesh.num_faces


class OBJGroup(Group):
    """
    What :meth:`OBJMobject.split_by` hands back: the parts of one model, each
    a mobject of its own, plus the little bit of bookkeeping that makes
    ``group["glass"]`` and ``group.explode(0.4)`` possible.
    """

    def __init__(self, *parts: OBJMobject, names: Sequence[str] = (),
                 kind: str = "material"):
        super().__init__(*parts)
        self.names = list(names) or [f"part_{i}" for i in range(len(parts))]
        self.kind = kind
        self._home = [p.get_center().copy() for p in parts]

    def __getitem__(self, key):
        if isinstance(key, str):
            for name, part in zip(self.names, self.submobjects):
                if key.lower() in name.lower():
                    return part
            raise KeyError(f"no part matching {key!r}; have {self.names}")
        return super().__getitem__(key)

    def named(self) -> dict[str, OBJMobject]:
        return dict(zip(self.names, self.submobjects))

    def explode(self, factor: float = 0.5, about=None, direction=None):
        """
        Push every part away from the centre -- the classic exploded view.
        ``factor`` 0 puts it back together.
        """
        about = self.get_center() if about is None else np.array(about)
        for part, home in zip(self.submobjects, self._home):
            offset = (home - about) if direction is None else np.array(direction)
            part.move_to(home + factor * offset)
        return self

    def set_part_colors(self, mapping: dict):
        """``{"glass": BLUE_A, "roof": GREY_C}`` in one go."""
        for key, color in mapping.items():
            try:
                self[key].set_color(color)
            except KeyError:
                pass
        return self


# ============================================================================
#  Animation
# ============================================================================

class BuildMesh(Animation):
    """
    Grow a model into place triangle by triangle -- each one blooming from its
    own centre, in an order you choose.

    ::

        self.play(BuildMesh(building, order="z", run_time=5))

    Parameters
    ----------
    order : {"z", "x", "y", "-z", "random", "radial"} or (F,) array
        Which triangles arrive first.
    spread : float
        How much of the run time separates the first triangle from the last.
        ``0`` grows them all together, ``1`` is a slow sweep.
    """

    def __init__(self, mobject: OBJMobject, order="z", spread: float = 0.7,
                 rate_func=smooth, **kwargs):
        self.order = order
        self.spread = float(np.clip(spread, 0.0, 0.98))
        super().__init__(mobject, rate_func=rate_func, **kwargs)

    def begin(self) -> None:
        mob = self.mobject
        self.target_points = mob.get_points().copy()
        tri = self.target_points.reshape(-1, 3, 3)
        self.centers = np.repeat(tri.mean(axis=1), 3, axis=0)
        self.start_times = self._starts(tri.mean(axis=1))
        super().begin()

    def _starts(self, centers: np.ndarray) -> np.ndarray:
        order = self.order
        if isinstance(order, str):
            key = order.lower()
            if key in ("x", "y", "z", "-x", "-y", "-z"):
                vals = centers[:, "xyz".index(key[-1])]
                if key.startswith("-"):
                    vals = -vals
            elif key == "random":
                vals = np.random.default_rng(0).random(len(centers))
            elif key == "radial":
                vals = np.linalg.norm(centers - centers.mean(0), axis=1)
            else:
                raise ValueError(f"unknown order {order!r}")
        else:
            vals = np.asarray(order, dtype=float)
        lo, hi = vals.min(), vals.max()
        t = np.zeros_like(vals) if hi - lo < 1e-9 else (vals - lo) / (hi - lo)
        return np.repeat(t * self.spread, 3)

    def interpolate_mobject(self, alpha: float) -> None:
        t = self.rate_func(self.time_spanned_alpha(alpha))
        window = max(1.0 - self.spread, 1e-6)
        local = np.clip((t - self.start_times) / window, 0.0, 1.0)[:, None]
        self.mobject.set_points(
            self.centers + (self.target_points - self.centers) * local
        )

    def finish(self) -> None:
        self.mobject.set_points(self.target_points)
        super().finish()
