"""
The full tour -- one landscape, every part of manim_obj working at once.

Models, all straight off the internet, four different exporters:
    terrain.obj   ericstoneking/42          3,042   Z-up
    tree_a.obj    Renumics/spotlight          876   Y-up, low-poly conifer
    tree_b.obj    redcamel/RedGL2             760   Y-up, bare branches
    building.obj  ladybug-tools             7,938   Z-up, Engel House
    chair.obj     cnr-isti-vclab/meshlab    6,716   Y-up
    earth.obj     AudranDoublet/opr         3,968   Y-up + its own texture

What this exercises:
    loading         up_axis z/y, height/width, dedupe, decimate, subdivide
    colour          material, group, z-gradient, normal, mtl, a callable,
                    set_part_color, legend, textured() from the .mtl
    shading         shade_smooth, shade_flat, per-model `shading` tuples
    geometry        slice, split_by, filter_faces, wireframe, point_cloud
    animation       BuildMesh, Transform, updaters
    the scene       a camera that flies, and a light source that moves

Render:
    manimgl examples/05_landscape.py Landscape -w -m \
        -c "#05080F" --video_dir videos/09_landscape
"""

import numpy as np
from manimlib import *

from manim_obj import OBJMobject, BuildMesh, load_mesh

INK, DIM, CYAN, GOLD = "#E8EEF7", "#7E93AC", "#6FE3D4", "#F2B33D"
MONO = "DejaVu Sans Mono"

GRASS = ["#1E3326", "#2F5A38", "#5C8B4A", "#9CB86A", "#D9CE94"]
STONE = "#AFC0D4"

# Where the trees stand, in terrain units from the middle.
TREE_SPOTS = [
    (-5.2, 3.4, "a"), (-3.1, 4.6, "a"), (-6.1, 0.9, "a"), (-4.4, -2.2, "b"),
    (-6.4, -4.1, "a"), (-2.0, -5.0, "a"), (1.4, -5.4, "b"), (4.6, -4.2, "a"),
    (6.0, -1.3, "a"), (5.3, 2.6, "b"), (3.0, 4.9, "a"), (0.2, 5.6, "a"),
    (-1.6, 1.2, "a"), (2.4, 1.9, "b"),
]


class Landscape(ThreeDScene):

    # ------------------------------------------------------------ helpers --
    def hud(self, text, *, corner=DL, size=19, color=CYAN):
        mob = Text(text, font=MONO, font_size=size, color=color)
        mob.fix_in_frame().to_corner(corner, buff=0.38)
        return mob

    def swap(self, old, new, run_time=0.55):
        if old is None:
            self.play(FadeIn(new, shift=0.15 * UP), run_time=run_time)
        else:
            self.play(FadeOut(old, shift=0.15 * UP),
                      FadeIn(new, shift=0.15 * UP), run_time=run_time)
        return new

    def ground_at(self, x, y):
        """Height of the land under a point, so things can stand on it."""
        pts = self._ground_points
        flat = pts[:, :2] - np.array([x, y])
        return float(pts[np.argmin((flat ** 2).sum(axis=1)), 2])

    def sun_to(self, x, y, z, run_time=2.0, **kwargs):
        """Move the one light the whole scene is lit by."""
        return self.camera.light_source.animate.move_to(np.array([x, y, z]))

    # -------------------------------------------------------------- scene --
    def construct(self):
        frame = self.camera.frame
        sun = self.camera.light_source
        sun.move_to(np.array([-14, -10, 9]))

        # ---- 1. the land assembles itself ---------------------------------
        land = OBJMobject(
            "terrain.obj",
            width=15,              # x extent; this file is a CAD-style Z-up
            up_axis="z",
            color_by="z",          # green in the valleys, sand on the tops
            gradient=GRASS,
            shading=(0.32, 0.22, 0.55),
        )
        land.shift(0.35 * IN)
        self._ground_points = land.get_points()

        frame.reorient(-28, 88, 0, (0, 0, 0.4), 11.0)

        title = Text("manim_obj", font_size=58, color=INK)
        sub = Text("six models · one scene", font=MONO, font_size=23, color=GOLD)
        card = VGroup(title, sub).arrange(DOWN, buff=0.28).fix_in_frame()
        self.play(Write(title), run_time=1.2)
        self.play(FadeIn(sub, shift=0.2 * UP), run_time=0.7)
        self.wait(0.6)
        self.play(FadeOut(card, shift=0.3 * UP), run_time=0.6)

        code = self.swap(None, self.hud('OBJMobject("terrain.obj", up_axis="z")'))
        self.play(BuildMesh(land, order="radial", spread=0.8, run_time=4.5))
        self.play(frame.animate.reorient(-14, 72, 0, (0, 0, 0.6), 13.0),
                  run_time=2.6)

        # ---- 2. trees, made cheap enough to repeat ------------------------
        code = self.swap(code, self.hud("OBJMobject(..., decimate=420)"))
        trees = Group()
        for x, y, kind in TREE_SPOTS:
            tree = OBJMobject(
                f"tree_{kind}.obj",
                height=1.9 if kind == "a" else 1.55,
                up_axis="y",
                decimate=420,                  # 876 -> 420, nobody will know
                color_by="z",
                gradient=(["#3A2A1E", "#2F5A38", "#6FA24E"] if kind == "a"
                          else ["#4A3728", "#7A6248"]),
            )
            tree.rotate(np.random.default_rng(abs(int(100 * x + 7 * y))).uniform(0, TAU), OUT)
            tree.move_to(np.array([x, y, self.ground_at(x, y)]))
            tree.shift(tree.get_shape()[2] / 2 * OUT)
            trees.add(tree)

        count = self.hud(f"{len(trees)} trees · {trees[0].num_faces} triangles each",
                         corner=UL, size=20, color=INK)
        self.play(FadeIn(count), run_time=0.4)
        self.play(LaggedStart(*[GrowFromPoint(t, t.get_center() + 0.6 * IN)
                                for t in trees],
                              lag_ratio=0.12, run_time=3.2))
        self.wait(0.8)

        # ---- 3. the building lands ----------------------------------------
        code = self.swap(code, self.hud('OBJMobject("building.obj", dedupe="auto")'))
        house = OBJMobject(
            "building.obj", height=2.4, up_axis="z",
            color_by="material",
            palette=["#9FB4CC", "#E9A13B", "#6FD6C0", "#D96F6F", "#9C8CD4", "#6FA8DC"],
        )
        hx, hy = 1.0, -0.4
        house.move_to(np.array([hx, hy, self.ground_at(hx, hy)]))
        house.shift(house.get_shape()[2] / 2 * OUT)

        landing = house.copy().shift(5 * OUT).set_opacity(0.0)
        self.add(landing)
        self.play(Transform(landing, house), run_time=2.2, rate_func=smooth)
        self.remove(landing)
        self.add(house)

        legend = house.legend(font=MONO, font_size=15, text_color=DIM)
        legend.fix_in_frame().to_corner(UR, buff=0.4)
        self.play(FadeOut(count), FadeIn(legend, shift=0.2 * LEFT), run_time=0.8)
        self.play(frame.animate.reorient(18, 68, 0, (0.5, 0, 0.9), 12.0),
                  run_time=3.4)

        # glass, picked out by name
        code = self.swap(code, self.hud('set_part_color("glass", "#8FE8FF", 0.75)'))
        glazed = house.copy()
        glazed.set_color("#3A4859", opacity=1.0)
        glazed.set_part_color("glass", "#8FE8FF", opacity=0.75)
        self.play(Transform(house, glazed), FadeOut(legend), run_time=1.6)
        self.wait(1.0)

        # ---- 4. the sun crosses the sky -----------------------------------
        code = self.swap(code, self.hud("self.camera.light_source.move_to(...)"))
        sun_note = self.hud("one light, moving — every model re-shades",
                            corner=UL, size=20, color=INK)
        self.play(FadeIn(sun_note), run_time=0.4)

        self.play(sun.animate.move_to(np.array([0, -4, 16])), run_time=3.0)
        self.play(sun.animate.move_to(np.array([14, 6, 5])), run_time=3.0)
        self.play(sun.animate.move_to(np.array([6, 12, 1.2])), run_time=2.6)
        self.play(sun.animate.move_to(np.array([-9, -8, 8])), run_time=2.4)
        self.play(FadeOut(sun_note), run_time=0.4)

        # ---- 5. down to the chair ------------------------------------------
        code = self.swap(code, self.hud('chair.split_by("group")'))
        cx, cy = -2.6, -1.9
        chair = OBJMobject("chair.obj", height=0.85, up_axis="y",
                           decimate=1600, color_by="material",
                           palette=["#E9A13B", "#C9D6E4", "#6FD6C0", "#D96F6F"])
        chair.move_to(np.array([cx, cy, self.ground_at(cx, cy)]))
        chair.shift(chair.get_shape()[2] / 2 * OUT)
        self.add(chair)

        self.play(frame.animate.reorient(4, 78, 0, (cx, cy, 0.5), 1.9),
                  run_time=3.6)
        self.wait(0.6)

        parts = chair.split_by("group")
        self.remove(chair)
        self.add(parts)
        self.play(*[p.animate.shift(0.07 * i * OUT) for i, p in enumerate(parts)],
                  run_time=1.6)
        self.wait(1.0)
        self.play(*[p.animate.shift(-0.07 * i * OUT) for i, p in enumerate(parts)],
                  run_time=1.3)
        self.remove(parts)
        self.add(chair)

        # crease wireframe over the top
        code = self.swap(code, self.hud("chair.wireframe(feature_angle=28)"))
        wires = chair.wireframe(color=GOLD, width=1.0, feature_angle=28,
                                max_edges=2600, nudge=0.002)
        self.play(ShowCreation(wires), run_time=2.0)
        self.wait(0.8)
        self.play(FadeOut(wires), run_time=0.6)

        # ---- 6. earthrise ---------------------------------------------------
        code = self.swap(code, self.hud('OBJMobject("earth.obj").textured()'))
        globe = OBJMobject("earth.obj", height=9.5, up_axis="y").textured()
        globe.move_to(np.array([6.0, 13.0, -1.0]))
        globe.add_updater(lambda m, dt: m.rotate(0.13 * dt, OUT))
        self.add(globe)

        self.play(sun.animate.move_to(np.array([2, 20, 6])), run_time=0.1)
        self.play(
            frame.animate.reorient(-6, 85, 0, (2.0, 2.5, 3.0), 13.0),
            globe.animate.move_to(np.array([6.0, 13.0, 5.2])),
            run_time=5.0,
        )
        self.wait(2.0)
        self.play(frame.animate.reorient(-6, 80, 0, (2.0, 1.0, 2.2), 15.0),
                  run_time=2.6)

        # ---- 7. everything dissolves ----------------------------------------
        code = self.swap(code, self.hud("model.point_cloud(n)"))
        globe.clear_updaters()
        solid = Group(land, *trees, house, chair)
        # The camera is a long way back by now, so the dots have to be big
        # enough to see, and the house is repainted first -- its glass
        # colours were nearly black and vanished into the background.
        bright = house.copy().set_color_by("z", gradient=["#3A9BD0", "#79E3C8", "#FFF2B8"])
        cloud = Group(
            land.point_cloud(11000, radius=0.038),
            *[t.point_cloud(420, radius=0.030) for t in trees],
            bright.point_cloud(6000, radius=0.032),
            chair.point_cloud(1200, radius=0.022),
        )
        self.play(FadeOut(solid), FadeIn(cloud), FadeOut(globe), run_time=2.2)
        self.play(frame.animate.reorient(26, 66, 0, (0, 0, 0.8), 13.5),
                  run_time=3.4)

        # ---- outro ------------------------------------------------------------
        outro = VGroup(
            Text("manim_obj", font_size=42, color=INK),
            Text("load · colour · texture · reshape · animate",
                 font=MONO, font_size=20, color=GOLD),
        ).arrange(DOWN, buff=0.26).fix_in_frame().to_edge(DOWN, buff=0.55)
        self.play(FadeOut(code), run_time=0.4)
        self.play(FadeIn(outro, shift=0.2 * UP), run_time=1.0)
        self.wait(2.2)
        self.play(FadeOut(outro), FadeOut(cloud), run_time=1.4)
