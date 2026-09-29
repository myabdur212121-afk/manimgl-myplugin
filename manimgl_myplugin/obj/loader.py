"""
manimgl_myplugin.obj.loader
================

Wavefront OBJ / MTL loading, downloading and caching.

Nothing in here knows about manim -- it is plain numpy, so it can be tested
and reused on its own.

Public API
----------
    load_mesh(source, **kw) -> MeshData      # path / URL / raw text / MeshData
    fetch_model(url, ...)   -> Path          # download (cached) into MODELS_DIR
    parse_obj(text, ...)    -> MeshData
    parse_mtl(text)         -> dict[str, Material]
    MeshData, Material
"""

from __future__ import annotations

import hashlib
import os
import pickle
import re
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Sequence

import numpy as np

__all__ = [
    "MeshData", "Material",
    "load_mesh", "parse_obj", "parse_mtl", "fetch_model",
    "MODELS_DIR", "CACHE_DIR",
]

#: Where ``fetch_model`` puts downloads. Override with $MANIM_OBJ_MODELS.
MODELS_DIR = Path(os.environ.get("MANIM_OBJ_MODELS", Path.home() / "models"))
#: Where parsed meshes are pickled. Override with $MANIM_OBJ_CACHE.
CACHE_DIR = Path(os.environ.get("MANIM_OBJ_CACHE", Path.home() / ".cache" / "manim_obj"))

_PARSER_VERSION = 5
_URL_RE = re.compile(r"^(https?|ftp)://", re.I)


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------


#: Bumped whenever the dedupe logic changes, so stale caches are ignored.
_DEDUPE_VERSION = 2


def _store(path: Path, payload) -> None:
    """Best-effort pickle write; a cache miss must never break a render."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass


def _tris_overlap(points: np.ndarray, tri: np.ndarray) -> bool:
    """True when any of ``points`` (n, 2) falls inside the 2D triangle ``tri``."""
    a, b, c = tri
    v0, v1, v2 = c - a, b - a, points - a
    d00 = v0 @ v0
    d01 = v0 @ v1
    d11 = v1 @ v1
    d20 = v2 @ v0
    d21 = v2 @ v1
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-20:
        return False
    u = (d11 * d20 - d01 * d21) / denom
    v = (d00 * d21 - d01 * d20) / denom
    return bool(((u >= 0) & (v >= 0) & (u + v <= 1)).any())


@dataclass
class Material:
    """One ``newmtl`` block of a .mtl file."""
    name: str
    diffuse: tuple[float, float, float] | None = None    # Kd
    ambient: tuple[float, float, float] | None = None    # Ka
    specular: tuple[float, float, float] | None = None   # Ks
    emissive: tuple[float, float, float] | None = None   # Ke
    opacity: float = 1.0                                 # d   (or 1 - Tr)
    shininess: float = 0.0                               # Ns
    texture: str | None = None                           # map_Kd
    emissive_texture: str | None = None                  # map_Ke
    bump_texture: str | None = None                      # map_bump / bump

    @property
    def hex_color(self) -> str | None:
        if self.diffuse is None:
            return None
        r, g, b = (int(255 * min(max(c, 0.0), 1.0)) for c in self.diffuse)
        return f"#{r:02X}{g:02X}{b:02X}"


def _quadric_decimate(mesh, n_target: int):
    """
    Call whichever quadric-decimation entry point this trimesh exposes.

    The signature has moved around between releases, so try the ones that
    have existed rather than pinning a version.
    """
    fn = getattr(mesh, "simplify_quadric_decimation", None)
    if fn is None:                                       # pragma: no cover
        raise RuntimeError("this trimesh has no quadric decimation")
    for kwargs in ({"face_count": n_target},
                   {"faces": n_target},
                   {"percent": n_target / max(len(mesh.faces), 1)}):
        try:
            return fn(**kwargs)
        except TypeError:
            continue
    return fn(n_target)


def parse_mtl(text: str) -> dict[str, Material]:
    """Parse the text of a .mtl file into ``{name: Material}``."""
    out: dict[str, Material] = {}
    cur: Material | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        kw, args = parts[0].lower(), parts[1:]
        try:
            if kw == "newmtl":
                cur = Material(name=" ".join(args))
                out[cur.name] = cur
            elif cur is None:
                continue
            elif kw == "kd":
                cur.diffuse = tuple(float(a) for a in args[:3])
            elif kw == "ka":
                cur.ambient = tuple(float(a) for a in args[:3])
            elif kw == "ks":
                cur.specular = tuple(float(a) for a in args[:3])
            elif kw == "ke":
                cur.emissive = tuple(float(a) for a in args[:3])
            elif kw == "d":
                cur.opacity = float(args[0])
            elif kw == "tr":
                cur.opacity = 1.0 - float(args[0])
            elif kw == "ns":
                cur.shininess = float(args[0])
            elif kw in ("map_kd", "map_ka"):
                cur.texture = args[-1]
            elif kw == "map_ke":
                cur.emissive_texture = args[-1]
            elif kw in ("map_bump", "map_disp"):
                cur.bump_texture = args[-1]
            elif kw in ("bump", "disp") and cur.bump_texture is None:
                cur.bump_texture = args[-1]
        except (ValueError, IndexError):
            continue  # a malformed line should never kill the load
    return out


# ----------------------------------------------------------------------------
# Mesh container
# ----------------------------------------------------------------------------

@dataclass
class MeshData:
    """
    A triangulated Wavefront mesh.

    Faces are already triangles: ``tri_v[i]`` holds the three indices into
    ``vertices`` of triangle ``i``.  ``tri_vt`` / ``tri_vn`` do the same for
    uvs / normals and hold ``-1`` where the file gave none.

    Every triangle also remembers which ``usemtl`` / ``g`` / ``o`` block it
    came from, as an index into ``material_names`` / ``group_names`` /
    ``object_names``.  That is what lets you colour or pull out parts of a
    model by name.
    """
    vertices: np.ndarray                      # (V, 3) float32
    tri_v: np.ndarray                         # (F, 3) int32
    tri_vt: np.ndarray                        # (F, 3) int32, -1 = none
    tri_vn: np.ndarray                        # (F, 3) int32, -1 = none
    tri_material: np.ndarray                  # (F,) int32
    tri_group: np.ndarray                     # (F,) int32
    tri_object: np.ndarray                    # (F,) int32
    material_names: list[str] = field(default_factory=list)
    group_names: list[str] = field(default_factory=list)
    object_names: list[str] = field(default_factory=list)
    uvs: np.ndarray | None = None             # (T, 2)
    normals: np.ndarray | None = None         # (N, 3)
    vertex_colors: np.ndarray | None = None   # (V, 3) from "v x y z r g b"
    materials: dict[str, Material] = field(default_factory=dict)
    source: str = "<memory>"

    # -- basic facts ---------------------------------------------------------

    @property
    def num_vertices(self) -> int:
        return len(self.vertices)

    @property
    def num_faces(self) -> int:
        return len(self.tri_v)

    @property
    def bounds(self) -> np.ndarray:
        """``[[xmin, ymin, zmin], [xmax, ymax, zmax]]`` in the file's own axes."""
        if not len(self.vertices):
            return np.zeros((2, 3))
        return np.array([self.vertices.min(0), self.vertices.max(0)])

    @property
    def size(self) -> np.ndarray:
        lo, hi = self.bounds
        return hi - lo

    @property
    def center(self) -> np.ndarray:
        lo, hi = self.bounds
        return (lo + hi) / 2

    def names(self, kind: str = "material") -> list[str]:
        """The distinct ``material`` / ``group`` / ``object`` names in the file."""
        return {
            "material": self.material_names,
            "group": self.group_names,
            "object": self.object_names,
        }[kind]

    def labels(self, kind: str = "material") -> np.ndarray:
        """Per-triangle index into :meth:`names`."""
        return {
            "material": self.tri_material,
            "group": self.tri_group,
            "object": self.tri_object,
        }[kind]

    def face_counts(self, kind: str = "material") -> dict[str, int]:
        """How many triangles each material / group / object owns."""
        labels, names = self.labels(kind), self.names(kind)
        counts = np.bincount(labels, minlength=len(names))
        return {n: int(c) for n, c in zip(names, counts) if c}

    # -- geometry ------------------------------------------------------------

    def triangle_points(self) -> np.ndarray:
        """``(3F, 3)`` corner positions, three rows per triangle."""
        if not self.num_faces:
            return np.zeros((0, 3), dtype=np.float32)
        return self.vertices[self.tri_v.reshape(-1)]

    def face_normals(self, normalize: bool = True) -> np.ndarray:
        """``(F, 3)`` geometric normal of each triangle, from its winding."""
        p = self.vertices[self.tri_v]                       # (F, 3, 3)
        n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        if normalize:
            n = _safe_normalize(n)
        return n

    def face_centers(self) -> np.ndarray:
        """``(F, 3)`` centroid of each triangle."""
        return self.vertices[self.tri_v].mean(axis=1)

    def face_areas(self) -> np.ndarray:
        """``(F,)`` area of each triangle."""
        return 0.5 * np.linalg.norm(self.face_normals(normalize=False), axis=1)

    def vertex_normals(self) -> np.ndarray:
        """
        ``(V, 3)`` area-weighted average of the normals of the faces meeting at
        each vertex -- what smooth (Gouraud) shading needs.
        """
        out = np.zeros_like(self.vertices, dtype=np.float64)
        raw = self.face_normals(normalize=False)            # length == 2 * area
        for corner in range(3):
            np.add.at(out, self.tri_v[:, corner], raw)
        return _safe_normalize(out).astype(np.float32)

    def corner_normals(self, smooth: bool = True) -> np.ndarray:
        """``(3F, 3)`` normal at every triangle corner, smooth or flat."""
        if smooth:
            return self.vertex_normals()[self.tri_v.reshape(-1)]
        return np.repeat(self.face_normals(), 3, axis=0)

    # -- editing -------------------------------------------------------------

    def copy(self) -> "MeshData":
        return replace(
            self,
            vertices=self.vertices.copy(),
            tri_v=self.tri_v.copy(),
            tri_vt=self.tri_vt.copy(),
            tri_vn=self.tri_vn.copy(),
            tri_material=self.tri_material.copy(),
            tri_group=self.tri_group.copy(),
            tri_object=self.tri_object.copy(),
            material_names=list(self.material_names),
            group_names=list(self.group_names),
            object_names=list(self.object_names),
        )

    def select(self, face_mask: np.ndarray) -> "MeshData":
        """A new mesh holding only the triangles where ``face_mask`` is true."""
        mask = np.asarray(face_mask)
        if mask.dtype != bool:
            keep = np.zeros(self.num_faces, dtype=bool)
            keep[mask] = True
            mask = keep
        out = self.copy()
        out.tri_v = self.tri_v[mask]
        out.tri_vt = self.tri_vt[mask]
        out.tri_vn = self.tri_vn[mask]
        out.tri_material = self.tri_material[mask]
        out.tri_group = self.tri_group[mask]
        out.tri_object = self.tri_object[mask]
        return out

    def select_named(self, pattern: str, kind: str = "material",
                     regex: bool = False) -> "MeshData":
        """Keep only triangles whose ``kind`` name matches ``pattern``."""
        return self.select(self.match_faces(pattern, kind, regex))

    def match_faces(self, pattern: str, kind: str = "material",
                    regex: bool = False) -> np.ndarray:
        """Boolean ``(F,)`` mask of triangles whose name matches ``pattern``."""
        names, labels = self.names(kind), self.labels(kind)
        if regex:
            rx = re.compile(pattern, re.I)
            hits = {i for i, n in enumerate(names) if rx.search(n)}
        else:
            low = pattern.lower()
            hits = {i for i, n in enumerate(names) if low in n.lower()}
        if not hits:
            return np.zeros(self.num_faces, dtype=bool)
        return np.isin(labels, list(hits))

    def transform(self, matrix: np.ndarray) -> "MeshData":
        """Right-multiply every vertex by a 3x3 ``matrix`` (returns a new mesh)."""
        out = self.copy()
        out.vertices = (self.vertices @ np.asarray(matrix, dtype=np.float32).T
                        ).astype(np.float32)
        return out

    # -- coincident (z-fighting) faces ---------------------------------------

    def _planes(self):
        """Canonical plane of every triangle: unit normal (sign-fixed) and offset."""
        p = self.vertices[self.tri_v]
        n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        length = np.linalg.norm(n, axis=1, keepdims=True)
        unit = np.divide(n, length, out=np.zeros_like(n), where=length > 1e-12)
        # Flip so the biggest component is positive: a face and its twin wound
        # the other way then land on the same plane.
        big = np.argmax(np.abs(unit), axis=1)
        sign = np.sign(unit[np.arange(len(unit)), big])
        sign[sign == 0] = 1.0
        canon = unit * sign[:, None]
        return canon, (canon * p[:, 0]).sum(1), p

    def coincident_pairs(self, *, angle_tol: float = 3.0,
                         distance_tol: float | None = None,
                         cross_material_only: bool = True) -> list[tuple[int, int]]:
        """
        Find triangles that sit on top of one another.

        CAD exporters often write the same wall twice -- once on a generic
        layer, once on a finish layer -- at the very same coordinates. Both
        get drawn, the depth test cannot separate them, and the wall comes out
        speckled or stripey with the two colours fighting pixel by pixel. This
        is what finds them.

        The twins are usually triangulated differently, so comparing vertex
        indices misses them; faces are grouped by the plane they lie in and
        then actually tested for overlap.
        """
        if not self.num_faces:
            return []
        if distance_tol is None:
            distance_tol = 0.002 * float(self.size.max())

        canon, offset, tri = self._planes()
        mats = self.tri_material
        n_key = np.round(canon / max(np.sin(np.deg2rad(angle_tol)), 1e-6)).astype(np.int64)
        d_key = np.round(offset / max(distance_tol, 1e-9)).astype(np.int64)

        planes: dict[tuple, list[int]] = {}
        for f, (nk, dk) in enumerate(zip(map(tuple, n_key), d_key)):
            planes.setdefault((*nk, int(dk)), []).append(f)

        # Four sample points per triangle: the centre plus one pulled toward
        # each corner. One of them lands inside the twin even when the two
        # were split along opposite diagonals.
        w = np.array([[1 / 3, 1 / 3, 1 / 3], [.6, .2, .2], [.2, .6, .2], [.2, .2, .6]])

        pairs: list[tuple[int, int]] = []
        for faces in planes.values():
            if len(faces) < 2:
                continue
            idx = np.array(faces)
            normal = canon[idx[0]]
            helper = np.eye(3)[int(np.argmin(np.abs(normal)))]
            u = helper - normal * (helper @ normal)
            u /= max(np.linalg.norm(u), 1e-12)
            v = np.cross(normal, u)

            pts = tri[idx]                                   # (k, 3, 3)
            flat = np.stack([pts @ u, pts @ v], axis=-1)     # (k, 3, 2)
            lo, hi = flat.min(axis=1), flat.max(axis=1)
            cell = max(float(np.median(hi - lo)), distance_tol) * 1.0

            grid: dict[tuple[int, int], list[int]] = {}
            for k in range(len(idx)):
                x0, y0 = np.floor(lo[k] / cell).astype(int)
                x1, y1 = np.floor(hi[k] / cell).astype(int)
                for gx in range(x0, x1 + 1):
                    for gy in range(y0, y1 + 1):
                        grid.setdefault((gx, gy), []).append(k)

            seen: set[tuple[int, int]] = set()
            for bucket in grid.values():
                for a in range(len(bucket)):
                    for b in range(a + 1, len(bucket)):
                        ka, kb = bucket[a], bucket[b]
                        if ka > kb:
                            ka, kb = kb, ka
                        if (ka, kb) in seen:
                            continue
                        seen.add((ka, kb))
                        fa, fb = int(idx[ka]), int(idx[kb])
                        if cross_material_only and mats[fa] == mats[fb]:
                            continue
                        if (hi[ka] < lo[kb]).any() or (hi[kb] < lo[ka]).any():
                            continue
                        if _tris_overlap(w @ flat[ka], flat[kb]) or \
                           _tris_overlap(w @ flat[kb], flat[ka]):
                            pairs.append((fa, fb))
        return pairs

    def dedupe_coincident(self, keep: str | Sequence[str] = "rare", *,
                          angle_tol: float = 3.0,
                          distance_tol: float | None = None,
                          cross_material_only: bool = False,
                          cache: bool = True,
                          report: bool = False):
        """
        Drop the duplicate of every pair of stacked triangles, which is what
        stops a doubled-up wall from flickering between two colours.

        ``keep`` decides which one survives when the two carry different
        materials:

        ``"rare"``    the material with fewer faces overall -- in a CAD export
                      the specific finish rather than the catch-all layer
                      (the default)
        ``"common"``  the other way round
        ``"first"`` / ``"last"``
                      by where the material first appears in the file
        a list        material names in priority order, best first

        When the twins share a material the colour is the same, but they are
        normally wound opposite ways, so one is lit and one is in shadow and
        the shading still fights -- a checkerboard of two brightnesses. Those
        are resolved too: the bigger face always wins, so a small detail lying
        flush on a wall can never punch a hole in it, and between equals the
        outward-facing one wins so the survivor is the lit one.

        Returns ``(mesh, n_removed)`` when ``report``, otherwise the mesh.
        """
        key = None
        if cache:
            stamp = hashlib.blake2b(digest_size=12)
            for arr in (self.vertices, self.tri_v, self.tri_material):
                stamp.update(np.ascontiguousarray(arr).tobytes())
            stamp.update(repr((keep, angle_tol, distance_tol,
                               cross_material_only, _DEDUPE_VERSION)).encode())
            key = CACHE_DIR / f"dedupe-{stamp.hexdigest()}.pkl"
            if key.exists():
                try:
                    with open(key, "rb") as fh:
                        mesh, removed = pickle.load(fh)
                    return (mesh, removed) if report else mesh
                except Exception:
                    pass

        pairs = self.coincident_pairs(angle_tol=angle_tol,
                                      distance_tol=distance_tol,
                                      cross_material_only=cross_material_only)
        if not pairs:
            if key is not None:
                _store(key, (self, 0))
            return (self, 0) if report else self

        rank = self._material_rank(keep)
        area = self.face_areas()
        # Twins of the same material are usually wound opposite ways, so one
        # is lit and one is in shadow -- same colour, but the shading still
        # fights. Keep the one facing outwards so the survivor is the lit one.
        normals, centers = self.face_normals(), self.face_centers()
        outward = ((centers - centers.mean(0)) * normals).sum(1) > 0

        drop = np.zeros(self.num_faces, dtype=bool)
        for a, b in pairs:
            ra, rb = rank[self.tri_material[a]], rank[self.tri_material[b]]
            if ra != rb:
                loser = a if ra > rb else b
            else:
                # Same material: never drop the bigger face -- a small detail
                # sitting flush on a big wall must not punch a hole in it.
                aa, ab = area[a], area[b]
                if abs(aa - ab) > 0.05 * max(aa, ab, 1e-12):
                    loser = a if aa < ab else b
                elif outward[a] != outward[b]:
                    loser = a if outward[b] else b
                else:
                    loser = max(a, b)
            drop[loser] = True

        out = self.select(~drop)
        removed = int(drop.sum())
        if key is not None:
            _store(key, (out, removed))
        return (out, removed) if report else out

    def _material_rank(self, keep) -> dict[int, int]:
        """Lower rank wins. Keyed by material index."""
        counts = np.bincount(self.tri_material, minlength=len(self.material_names))
        if isinstance(keep, str):
            if keep == "rare":
                order = np.argsort(counts, kind="stable")
            elif keep == "common":
                order = np.argsort(-counts, kind="stable")
            elif keep == "first":
                order = np.arange(len(self.material_names))
            elif keep == "last":
                order = np.arange(len(self.material_names))[::-1]
            else:
                raise ValueError(f"unknown keep rule: {keep!r}")
            return {int(m): i for i, m in enumerate(order)}
        wanted = [str(k).lower() for k in keep]
        rank = {}
        for i, name in enumerate(self.material_names):
            low = name.lower()
            hit = next((j for j, k in enumerate(wanted) if k in low), len(wanted))
            rank[i] = hit
        return rank


    # -- changing how many triangles there are -------------------------------

    def subdivide(self, level: int = 1, smooth: bool = True) -> "MeshData":
        """
        Split every triangle into four, ``level`` times over.

        ::

            mesh = load_mesh("earth.obj").subdivide(2)   # 3,968 -> 63,488

        ``smooth`` (the default) uses Loop subdivision: the new points are
        nudged towards their neighbours and the old ones drift as well, so
        the mesh creeps towards a rounded limit surface and the *outline*
        gets rounder, not just the shading. ``smooth=False`` puts the new
        points exactly on the old edges, which multiplies the triangle count
        without changing the shape at all -- occasionally useful as a
        scaffold for :meth:`displace`, and useless on its own.

        .. warning::
            Loop subdivision rounds sharp corners off, which is right for a
            sphere or a scanned figure and quite wrong for a building. Use
            ``smooth=False`` there, or do not subdivide at all.

        Texture coordinates and normals are split alongside the geometry,
        keyed on their own indices, so a seam in the UVs survives the split.
        Materials, groups and objects are inherited by the four children.
        """
        mesh = self
        for _ in range(max(0, int(level))):
            mesh = mesh._subdivide_once(bool(smooth))
        return mesh

    #: Which vertex of a triangle sits opposite each of its three edges.
    _EDGE_CORNERS = np.array([[0, 1], [1, 2], [2, 0]])

    @staticmethod
    def _split_edges(index: np.ndarray, values: np.ndarray):
        """Midpoint-split an attribute. Returns ``(values, midpoint index)``."""
        pairs = np.sort(index[:, MeshData._EDGE_CORNERS], axis=2).reshape(-1, 2)
        uniq, inv = np.unique(pairs, axis=0, return_inverse=True)
        mids = values[uniq].mean(axis=1)
        return (np.concatenate([values, mids]),
                len(values) + inv.reshape(-1, 3), uniq, inv)

    def _subdivide_once(self, smooth: bool) -> "MeshData":
        verts, faces = self.vertices, self.tri_v
        n_faces, n_verts = len(faces), len(verts)

        pairs = np.sort(faces[:, self._EDGE_CORNERS], axis=2).reshape(-1, 2)
        edges, inv = np.unique(pairs, axis=0, return_inverse=True)
        mid_id = n_verts + inv.reshape(n_faces, 3)
        midpoints = verts[edges].mean(axis=1)
        moved = verts

        if smooth:
            # Each edge is shared by at most two triangles; the vertices
            # facing it across those triangles pull the new point in.
            times_used = np.bincount(inv, minlength=len(edges))
            facing = faces[:, [2, 0, 1]].reshape(-1)
            facing_sum = np.zeros((len(edges), 3))
            np.add.at(facing_sum, inv, verts[facing])
            inner = times_used == 2
            midpoints[inner] = (
                0.375 * (verts[edges[inner, 0]] + verts[edges[inner, 1]])
                + 0.125 * facing_sum[inner]
            )

            # The old vertices drift towards the average of their neighbours.
            valence = np.bincount(edges.reshape(-1), minlength=n_verts)
            neighbour_sum = np.zeros((n_verts, 3))
            np.add.at(neighbour_sum, edges[:, 0], verts[edges[:, 1]])
            np.add.at(neighbour_sum, edges[:, 1], verts[edges[:, 0]])
            beta = np.where(valence == 3, 3 / 16,
                            3 / (8 * np.maximum(valence, 1)))
            moved = ((1 - valence * beta)[:, None] * verts
                     + beta[:, None] * neighbour_sum)

            # A vertex on an open edge follows the boundary, not the surface,
            # or the border of the mesh would shrink away.
            border = edges[times_used == 1]
            if len(border):
                b_sum = np.zeros((n_verts, 3))
                b_count = np.zeros(n_verts)
                np.add.at(b_sum, border[:, 0], verts[border[:, 1]])
                np.add.at(b_sum, border[:, 1], verts[border[:, 0]])
                np.add.at(b_count, border[:, 0], 1)
                np.add.at(b_count, border[:, 1], 1)
                on_border = b_count > 0
                moved[on_border] = (0.75 * verts[on_border]
                                    + 0.125 * b_sum[on_border])

        out = self.copy()
        out.vertices = np.concatenate([moved, midpoints]).astype(np.float32)
        out.tri_v = self._four_children(faces, mid_id)

        for idx_name, val_name, renorm in (("tri_vt", "uvs", False),
                                           ("tri_vn", "normals", True)):
            index, values = getattr(self, idx_name), getattr(self, val_name)
            if values is None or not len(values) or index.max() < 0:
                setattr(out, idx_name, self._four_children(index, index[:, :3]))
                continue
            # Split on the attribute's own indices: two triangles either side
            # of a UV seam have different vt numbers and must stay apart.
            new_vals, new_mid, _, _ = self._split_edges(index, values)
            if renorm:
                lengths = np.linalg.norm(new_vals, axis=1, keepdims=True)
                new_vals = new_vals / np.maximum(lengths, 1e-12)
            setattr(out, val_name, new_vals.astype(np.float32))
            setattr(out, idx_name, self._four_children(index, new_mid))

        for name in ("tri_material", "tri_group", "tri_object"):
            setattr(out, name, np.tile(getattr(self, name), 4))
        return out

    @staticmethod
    def _four_children(corner: np.ndarray, mid: np.ndarray) -> np.ndarray:
        """The four triangles a parent splits into, in a fixed order."""
        a, b, c = corner[:, 0], corner[:, 1], corner[:, 2]
        ab, bc, ca = mid[:, 0], mid[:, 1], mid[:, 2]
        return np.concatenate([
            np.stack([a, ab, ca], axis=1),
            np.stack([ab, b, bc], axis=1),
            np.stack([ca, bc, c], axis=1),
            np.stack([ab, bc, ca], axis=1),
        ]).astype(np.int32)

    def displace(self, image, *, strength: float = 0.05, middle: float = 0.5,
                 absolute: bool = False, invert: bool = False) -> "MeshData":
        """
        Push every vertex along its normal by the brightness of an image.

        ::

            mesh = load_mesh("earth.obj").subdivide(2)
            mesh = mesh.displace("bump.jpg", strength=0.04)

        A bump or height map is a greyscale picture where white means high
        and black means low. Each vertex reads the map at its own ``vt``
        coordinate and moves outwards or inwards accordingly, so the relief
        becomes real geometry -- it shows in the silhouette, and it casts its
        own shading -- rather than being painted on.

        ``strength`` is a fraction of the model's largest extent by default,
        which keeps it meaningful whatever units the file is in; pass
        ``absolute=True`` to give it in the file's own units instead.
        ``middle`` is the grey level that counts as "no change", so the
        default 0.5 lets a map push both ways. ``invert`` flips it, for the
        maps that are drawn the other way round.

        Needs Pillow and an .obj with ``vt`` lines. Subdivide first: the
        relief can only appear where there are vertices to move, and most
        models have nowhere near enough of their own.
        """
        try:
            from PIL import Image
        except ImportError as exc:                       # pragma: no cover
            raise ImportError("displace needs Pillow: pip install pillow") from exc
        if self.uvs is None or not len(self.uvs) or self.tri_vt.max() < 0:
            raise ValueError(
                f"{self.source} has no vt coordinates, so there is nothing to "
                "look the height map up with")

        path = str(image)
        if path.startswith(("http://", "https://")):
            path = str(fetch_model(path, companions=False, quiet=True))
        grey = np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
        rows, cols = grey.shape

        uv = self.uvs[np.clip(self.tri_vt, 0, len(self.uvs) - 1)].reshape(-1, 2)
        col = np.clip((uv[:, 0] % 1.0) * (cols - 1), 0, cols - 1).astype(np.int32)
        row = np.clip((1.0 - uv[:, 1] % 1.0) * (rows - 1), 0, rows - 1).astype(np.int32)
        per_corner = grey[row, col]
        if invert:
            per_corner = 1.0 - per_corner

        # A vertex is usually shared by several corners; average what they say.
        total = np.zeros(len(self.vertices))
        count = np.zeros(len(self.vertices))
        np.add.at(total, self.tri_v.reshape(-1), per_corner)
        np.add.at(count, self.tri_v.reshape(-1), 1)
        touched = count > 0
        height = np.zeros(len(self.vertices))
        height[touched] = total[touched] / count[touched]

        scale = 1.0 if absolute else float(self.size.max())
        offset = (height - middle) * strength * scale
        offset[~touched] = 0.0

        out = self.copy()
        out.vertices = (self.vertices
                        + self.vertex_normals() * offset[:, None]).astype(np.float32)
        return out

    def decimate(self, target, *, transfer: bool = True) -> "MeshData":
        """
        Fewer triangles, as close to the same shape as possible.

        ::

            mesh = load_mesh("chair.obj").decimate(1500)   # 6,716 -> 1,500
            mesh = load_mesh("chair.obj").decimate(0.25)   # keep a quarter

        ``target`` above 1 is a triangle count; at or below 1 it is the
        fraction to keep. The algorithm is quadric edge collapse: it scores
        every edge by how far the surface would move if its two ends were
        merged into one point, then keeps merging the cheapest. Flat regions
        collapse first and creases survive, because folding a crease away is
        expensive.

        This is the opposite of :meth:`subdivide` in more than direction --
        removing detail is a choice between things that are there, where
        adding it is a guess, so the result is predictable.

        ``transfer`` copies the UVs, normals and material assignments across
        to the new mesh from whatever was nearest in the old one. That is an
        approximation: decimation genuinely destroys the correspondence, and
        a texture will slide slightly. Set it to ``False`` for bare geometry.
        """
        n_target = (int(target) if target > 1
                    else max(4, int(round(float(target) * self.num_faces))))
        if n_target >= self.num_faces:
            return self

        try:
            import trimesh
        except ImportError as exc:                       # pragma: no cover
            raise ImportError("decimate needs trimesh") from exc

        raw = trimesh.Trimesh(vertices=np.asarray(self.vertices, dtype=np.float64),
                              faces=np.asarray(self.tri_v, dtype=np.int64),
                              process=False)
        small = _quadric_decimate(raw, n_target)

        out = self.copy()
        out.vertices = np.asarray(small.vertices, dtype=np.float32)
        out.tri_v = np.asarray(small.faces, dtype=np.int32)
        n_new = len(out.tri_v)

        if not transfer:
            out.uvs = np.zeros((0, 2), dtype=np.float32)
            out.normals = np.zeros((0, 3), dtype=np.float32)
            blank = np.full((n_new, 3), -1, dtype=np.int32)
            out.tri_vt, out.tri_vn = blank, blank.copy()
            for name in ("tri_material", "tri_group", "tri_object"):
                setattr(out, name, np.zeros(n_new, dtype=np.int32))
            return out

        from scipy.spatial import cKDTree

        # Materials follow whichever old triangle each new one landed on.
        old_centers = self.face_centers()
        new_centers = out.vertices[out.tri_v].mean(axis=1)
        _, nearest_face = cKDTree(old_centers).query(new_centers)
        for name in ("tri_material", "tri_group", "tri_object"):
            setattr(out, name, np.asarray(getattr(self, name))[nearest_face])

        # UVs and normals follow the nearest old vertex.
        _, nearest_vert = cKDTree(self.vertices).query(out.vertices)
        for idx_name, val_name in (("tri_vt", "uvs"), ("tri_vn", "normals")):
            values = getattr(self, val_name)
            index = getattr(self, idx_name)
            if values is None or not len(values) or index.max() < 0:
                setattr(out, idx_name, np.full((n_new, 3), -1, dtype=np.int32))
                continue
            width = values.shape[1]
            per_vertex = np.zeros((len(self.vertices), width))
            seen = np.zeros(len(self.vertices))
            np.add.at(per_vertex, self.tri_v.reshape(-1),
                      values[np.clip(index, 0, len(values) - 1)].reshape(-1, width))
            np.add.at(seen, self.tri_v.reshape(-1), 1)
            per_vertex[seen > 0] /= seen[seen > 0, None]
            setattr(out, val_name, per_vertex[nearest_vert].astype(np.float32))
            setattr(out, idx_name, out.tri_v.copy())
        return out

    def texture_path(self, kind: str = "diffuse") -> Path | None:
        """
        The image file this model's .mtl asks for, if it can be found.

        ``kind`` is ``"diffuse"`` (``map_Kd`` -- the colour), ``"emissive"``
        (``map_Ke`` -- glow, typically city lights) or ``"bump"``
        (``map_bump`` -- a height map).

        A .mtl only ever names its images; it never contains them. They are
        expected to sit next to the .obj, so that is where this looks, then
        in the models directory. Returns ``None`` when the file is not named
        or not there.
        """
        attr = {"diffuse": "texture", "emissive": "emissive_texture",
                "bump": "bump_texture"}[kind]
        names = [getattr(m, attr) for m in self.materials.values()]
        names = [n for n in names if n]
        if not names:
            return None

        roots = [MODELS_DIR]
        try:
            here = Path(self.source).resolve().parent
            roots.insert(0, here)
        except (OSError, ValueError):
            pass

        for name in names:
            stem = Path(str(name).replace("\\", "/")).name
            for root in roots:
                hit = root / stem
                if hit.exists():
                    return hit
        return None

    def summary(self) -> str:
        lo, hi = self.bounds
        lines = [
            f"MeshData  {Path(self.source).name}",
            f"  vertices : {self.num_vertices:,}",
            f"  triangles: {self.num_faces:,}",
            f"  size     : {self.size[0]:.2f} x {self.size[1]:.2f} x {self.size[2]:.2f}"
            f"   (min {lo.round(2).tolist()}, max {hi.round(2).tolist()})",
            f"  uvs      : {0 if self.uvs is None else len(self.uvs):,}",
            f"  normals  : {0 if self.normals is None else len(self.normals):,}",
        ]
        for kind in ("material", "group", "object"):
            counts = self.face_counts(kind)
            if len(counts) > 1 or (counts and kind == "material"):
                shown = ", ".join(f"{n} ({c:,})" for n, c in
                                  sorted(counts.items(), key=lambda kv: -kv[1])[:6])
                extra = "" if len(counts) <= 6 else f", +{len(counts) - 6} more"
                lines.append(f"  {kind + 's':9}: {len(counts)} -> {shown}{extra}")
        return "\n".join(lines)


def _safe_normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.divide(v, n, out=np.zeros_like(v, dtype=float), where=n > 1e-12)


# ----------------------------------------------------------------------------
# The OBJ parser
# ----------------------------------------------------------------------------

def _logical_lines(text: str):
    """
    Yield OBJ lines with backslash continuations already joined.

    Exporters (Rhino among them) wrap long ``f`` lines with a trailing ``\\``.
    Read line by line, such a face silently loses its tail corners, so the
    lines have to be glued back together before anything else looks at them.
    """
    pending: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            pending.append(line[:-1].rstrip())
            continue
        if pending:
            pending.append(line)
            yield " ".join(pending)
            pending = []
        else:
            yield line
    if pending:
        yield " ".join(pending)


def parse_obj(text: str, *, source: str = "<memory>",
              materials: dict[str, Material] | None = None) -> MeshData:
    """
    Parse the text of a Wavefront .obj file.

    Handles ``v`` (with optional r g b), ``vt``, ``vn``, ``f`` in all four
    index spellings, negative (relative) indices, n-gons (fan triangulated),
    and the ``g`` / ``o`` / ``usemtl`` / ``mtllib`` grouping keywords.
    """
    verts: list[tuple[float, float, float]] = []
    vcols: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    norms: list[tuple[float, float, float]] = []

    tri_v: list[tuple[int, int, int]] = []
    tri_vt: list[tuple[int, int, int]] = []
    tri_vn: list[tuple[int, int, int]] = []
    tri_m: list[int] = []
    tri_g: list[int] = []
    tri_o: list[int] = []

    mat_names, grp_names, obj_names = ["default"], ["default"], ["default"]
    mat_ids = {"default": 0}
    grp_ids = {"default": 0}
    obj_ids = {"default": 0}
    cur_m = cur_g = cur_o = 0
    mtllibs: list[str] = []
    any_vertex_color = False

    def _intern(name, names, ids):
        i = ids.get(name)
        if i is None:
            i = len(names)
            ids[name] = i
            names.append(name)
        return i

    for raw in _logical_lines(text):
        if not raw or raw[0] == "#":
            continue
        parts = raw.split()
        if not parts:
            continue
        kw = parts[0]

        if kw == "v":
            try:
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
            except (IndexError, ValueError):
                continue
            if len(parts) >= 7:                       # v x y z r g b
                try:
                    vcols.append((float(parts[4]), float(parts[5]), float(parts[6])))
                    any_vertex_color = True
                except ValueError:
                    vcols.append((1.0, 1.0, 1.0))
            else:
                vcols.append((1.0, 1.0, 1.0))

        elif kw == "vt":
            try:
                uvs.append((float(parts[1]), float(parts[2]) if len(parts) > 2 else 0.0))
            except (IndexError, ValueError):
                continue

        elif kw == "vn":
            try:
                norms.append((float(parts[1]), float(parts[2]), float(parts[3])))
            except (IndexError, ValueError):
                continue

        elif kw == "f":
            corners = []
            for tok in parts[1:]:
                bits = tok.split("/")
                try:
                    vi = int(bits[0])
                except ValueError:
                    corners = []
                    break
                vi = vi - 1 if vi > 0 else len(verts) + vi
                ti = ni = -1
                if len(bits) > 1 and bits[1]:
                    ti = int(bits[1])
                    ti = ti - 1 if ti > 0 else len(uvs) + ti
                if len(bits) > 2 and bits[2]:
                    ni = int(bits[2])
                    ni = ni - 1 if ni > 0 else len(norms) + ni
                corners.append((vi, ti, ni))
            # fan triangulation: (0, k, k+1)
            for k in range(1, len(corners) - 1):
                a, b, c = corners[0], corners[k], corners[k + 1]
                tri_v.append((a[0], b[0], c[0]))
                tri_vt.append((a[1], b[1], c[1]))
                tri_vn.append((a[2], b[2], c[2]))
                tri_m.append(cur_m)
                tri_g.append(cur_g)
                tri_o.append(cur_o)

        elif kw == "usemtl":
            cur_m = _intern(" ".join(parts[1:]) or "default", mat_names, mat_ids)
        elif kw == "g":
            cur_g = _intern(" ".join(parts[1:]) or "default", grp_names, grp_ids)
        elif kw == "o":
            cur_o = _intern(" ".join(parts[1:]) or "default", obj_names, obj_ids)
        elif kw == "mtllib":
            mtllibs.extend(parts[1:])

    mesh = MeshData(
        vertices=np.array(verts, dtype=np.float32).reshape(-1, 3),
        tri_v=np.array(tri_v, dtype=np.int32).reshape(-1, 3),
        tri_vt=np.array(tri_vt, dtype=np.int32).reshape(-1, 3),
        tri_vn=np.array(tri_vn, dtype=np.int32).reshape(-1, 3),
        tri_material=np.array(tri_m, dtype=np.int32),
        tri_group=np.array(tri_g, dtype=np.int32),
        tri_object=np.array(tri_o, dtype=np.int32),
        material_names=mat_names,
        group_names=grp_names,
        object_names=obj_names,
        uvs=np.array(uvs, dtype=np.float32).reshape(-1, 2) if uvs else None,
        normals=np.array(norms, dtype=np.float32).reshape(-1, 3) if norms else None,
        vertex_colors=(np.array(vcols, dtype=np.float32).reshape(-1, 3)
                       if any_vertex_color else None),
        materials=dict(materials or {}),
        source=source,
    )
    mesh._mtllibs = mtllibs            # type: ignore[attr-defined]
    return mesh


# ----------------------------------------------------------------------------
# Downloading
# ----------------------------------------------------------------------------

def fetch_model(url: str, name: str | None = None, *,
                dest_dir: Path | str | None = None,
                force: bool = False,
                companions: bool = True,
                timeout: float = 120.0,
                quiet: bool = False) -> Path:
    """
    Download a model and return its local path, re-using the file if it is
    already there.

    ``companions`` also tries the sibling ``.mtl`` named in the OBJ, so a
    textured/coloured model arrives complete in one call.
    """
    dest_dir = Path(dest_dir) if dest_dir else MODELS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = name or os.path.basename(url.split("?")[0]) or "model.obj"
    path = dest_dir / name

    if path.exists() and not force:
        if not quiet:
            print(f"[manimgl_myplugin] cached  {path}  ({path.stat().st_size:,} bytes)")
    else:
        if not quiet:
            print(f"[manimgl_myplugin] fetching {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "manimgl_myplugin/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            path.write_bytes(r.read())
        if not quiet:
            print(f"[manimgl_myplugin] saved    {path}  ({path.stat().st_size:,} bytes)")

    if companions and path.suffix.lower() == ".obj":
        for lib in _mtllibs_of(path):
            side = dest_dir / lib
            if side.exists():
                continue
            try:
                mtl_url = url.rsplit("/", 1)[0] + "/" + lib
                req = urllib.request.Request(mtl_url,
                                             headers={"User-Agent": "manimgl_myplugin/0.1"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    side.write_bytes(r.read())
                if not quiet:
                    print(f"[manimgl_myplugin] saved    {side} (material library)")
            except Exception:
                pass  # a missing .mtl is not fatal, colours just fall back
    return path


def _mtllibs_of(path: Path) -> list[str]:
    out = []
    try:
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                if line.startswith("mtllib"):
                    out.extend(line.split()[1:])
                elif line.startswith(("f ", "v ")) and out:
                    break
    except OSError:
        pass
    return out


# ----------------------------------------------------------------------------
# The one entry point
# ----------------------------------------------------------------------------

def load_mesh(source, *, cache: bool = True, load_mtl: bool = True,
              quiet: bool = True) -> MeshData:
    """
    Load a mesh from anything reasonable.

    ``source`` may be

    * a :class:`MeshData`            -- returned as is
    * an ``http(s)://`` URL          -- downloaded (cached) then parsed
    * a path to a ``.obj`` file      -- parsed, with its ``.mtl`` alongside
    * a path to any other mesh file  -- handed to ``trimesh`` if it is installed
    * raw OBJ text                   -- parsed directly
    """
    if isinstance(source, MeshData):
        return source

    if isinstance(source, (str, Path)):
        text = str(source)
        if _URL_RE.match(text):
            source = fetch_model(text, quiet=quiet)
        elif "\n" in text and not Path(text[:200]).exists():
            return parse_obj(text)                      # raw OBJ text

    path = Path(source).expanduser()
    if not path.exists():
        for cand in (MODELS_DIR / path.name, Path.cwd() / path):
            if cand.exists():
                path = cand
                break
        else:
            raise FileNotFoundError(
                f"No such model: {source}\n"
                f"  tried {path} and {MODELS_DIR / path.name}\n"
                f"  tip: OBJMobject('https://.../model.obj') downloads it for you."
            )

    if path.suffix.lower() != ".obj":
        return _load_via_trimesh(path)

    key = None
    if cache:
        st = path.stat()
        key = hashlib.sha1(
            f"{path.resolve()}|{st.st_mtime_ns}|{st.st_size}|{_PARSER_VERSION}".encode()
        ).hexdigest()
        hit = CACHE_DIR / f"{key}.pkl"
        if hit.exists():
            try:
                with open(hit, "rb") as fh:
                    return pickle.load(fh)
            except Exception:
                pass  # a stale or broken cache entry simply gets rebuilt

    mesh = parse_obj(path.read_text(errors="replace"), source=str(path))

    if load_mtl:
        libs = list(getattr(mesh, "_mtllibs", []))
        libs += [path.with_suffix(".mtl").name]
        for lib in libs:
            side = path.parent / lib
            if side.exists():
                mesh.materials.update(parse_mtl(side.read_text(errors="replace")))

    if cache and key:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_DIR / f"{key}.pkl", "wb") as fh:
                pickle.dump(mesh, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass
    return mesh


def _load_via_trimesh(path: Path) -> MeshData:
    """Fallback for .stl / .ply / .glb / ... -- trimesh ships with manimgl."""
    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            f"{path.suffix} models need trimesh: pip install trimesh"
        ) from exc
    scene = trimesh.load(str(path), force="mesh")
    verts = np.asarray(scene.vertices, dtype=np.float32)
    faces = np.asarray(scene.faces, dtype=np.int32)
    n = len(faces)
    return MeshData(
        vertices=verts,
        tri_v=faces,
        tri_vt=np.full((n, 3), -1, np.int32),
        tri_vn=np.full((n, 3), -1, np.int32),
        tri_material=np.zeros(n, np.int32),
        tri_group=np.zeros(n, np.int32),
        tri_object=np.zeros(n, np.int32),
        material_names=["default"], group_names=["default"], object_names=["default"],
        source=str(path),
    )
