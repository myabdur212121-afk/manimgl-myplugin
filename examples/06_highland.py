"""
Highland -- eight models, a moving sun, and everything turned up.

    mountain.obj  ZeusYang/TinySoftRenderer    6,962  Y-up  a real mountain range
    tree_a.obj    Renumics/spotlight             876  Y-up  low-poly conifer
    palm.obj      CaptainProton42                1,246 Y-up  palm
    building.obj  ladybug-tools                7,938  Z-up  Engel House
    house.obj     RobLoach/node-raylib         1,792  Y-up  cottage
    chair.obj     cnr-isti-vclab/meshlab       6,716  Y-up  office chair
    armchair.obj  code-iai/iai_maps            2,832  Z-up  armchair
    earth.obj     AudranDoublet/opr            3,968  Y-up  + its own texture

Nothing here is flat: the land is a subdivided mountain range, the armchair
is smoothed out of a blocky collision mesh, and the globe carries real
displaced relief.

Render (QHD):
    manimgl examples/06_highland.py Highland -w -r 2560x1440 \
        -c "#05070E" --video_dir videos/10_highland
"""

import numpy as np
from manimlib import *

from manim_obj import OBJMobject, BuildMesh

INK, DIM, CYAN, GOLD = "#EAF0F8", "#7E93AC", "#6FE3D4", "#F2B33D"
MONO = "DejaVu Sans Mono"

ROCK = ["#22331F", "#3C5C33", "#6E8F4A", "#A8A878", "#E6E2D0"]
PINE = ["#2C1E14", "#24512F", "#4E8A45"]

# Conifers high on the slopes, palms down by the flats.
PINES = [(-7.0, 4.2), (-4.6, 6.0), (-8.4, 1.0), (-5.6, -2.6), (-8.0, -5.2),
         (-2.2, -6.4), (2.0, -6.8), (5.8, -5.0), (7.6, -1.4), (6.4, 3.2)]
PALMS = [(-1.0, 7.4), (3.2, 6.6), (-3.4, 2.0), (1.2, 3.0)]

# Where the one light stands, shot by shot.
SUN_STOPS = [
    ((-16, -12, 7), "low, behind us"),
    ((0, -6, 18), "high noon"),
    ((16, 4, 6), "afternoon, from the right"),
    ((7, 15, 1.4), "almost on the horizon"),
    ((-12, 9, 10), "back over the far ridge"),
]


class Highland(ThreeDScene):

    # ------------------------------------------------------------ helpers --
    def hud(self, text, *, corner=DL, size=20, color=CYAN):
        mob = Text(text, font=MONO, font_size=size, color=color)
        mob.fix_in_frame().to_corner(corner, buff=0.4)
        return mob

    def swap(self, old, new, run_time=0.55):
        if old is None:
            self.play(FadeIn(new, shift=0.15 * UP), run_time=run_time)
        else:
            self.play(FadeOut(old, shift=0.15 * UP),
                      FadeIn(new, shift=0.15 * UP), run_time=run_time)
        return new

    def ground_at(self, x, y):
        pts = self._ground
        return float(pts[np.argmin(((pts[:, :2] - np.array([x, y])) ** 2).sum(1)), 2])

    def flat_spot(self, x, y, search=1.4, step=0.35, patch=1.1):
        """
        The least steep place within reach of where you asked for.

        A mountain has slopes almost everywhere, and a building dropped on
        one leans into the hillside or hangs off it. Rather than hand-pick
        coordinates, score the neighbourhood by how much the ground varies
        and take the calmest patch.
        """
        pts = self._ground
        best, best_score = (x, y), np.inf
        reach = np.arange(-search, search + 1e-9, step)
        for dx in reach:
            for dy in reach:
                cx, cy = x + dx, y + dy
                near = pts[((pts[:, :2] - np.array([cx, cy])) ** 2).sum(1) < patch ** 2]
                if len(near) < 6:
                    continue
                # prefer flat, and prefer staying near the spot asked for
                score = near[:, 2].std() + 0.10 * np.hypot(dx, dy)
                if score < best_score:
                    best, best_score = (cx, cy), score
        return best

    def stand(self, mob, x, y, sink=0.0, settle=True, footprint=0.6):
        """
        Put a model's feet on the mountain rather than its middle.

        The ground is taken as the *highest* point under the footprint, not
        the nearest one: on a slope the nearest sample is often downhill, and
        a building placed on it ends up half buried in the hillside.
        """
        if settle:
            x, y = self.flat_spot(x, y, patch=max(footprint, 0.8))
        pts = self._ground
        under = pts[((pts[:, :2] - np.array([x, y])) ** 2).sum(1) < footprint ** 2]
        z = float(under[:, 2].max()) if len(under) else self.ground_at(x, y)
        mob.move_to(np.array([x, y, z]))
        mob.shift((mob.get_shape()[2] / 2 - sink) * OUT)
        return mob

    # -------------------------------------------------------------- scene --
    def construct(self):
        frame = self.camera.frame
        sun = self.camera.light_source
        sun.move_to(np.array(SUN_STOPS[0][0]))

        # ---- 1. title -------------------------------------------------------
        title = Text("Highland", font_size=64, color=INK)
        sub = Text("eight models · one moving sun", font=MONO,
                   font_size=23, color=GOLD)
        card = VGroup(title, sub).arrange(DOWN, buff=0.3).fix_in_frame()
        frame.reorient(-30, 86, 0, (0, 0, 0.6), 12.0)
        self.play(Write(title), run_time=1.3)
        self.play(FadeIn(sub, shift=0.2 * UP), run_time=0.7)
        self.wait(0.7)
        self.play(FadeOut(card, shift=0.3 * UP), run_time=0.6)

        # ---- 2. the land, coarse then smoothed -------------------------------
        code = self.swap(None, self.hud('OBJMobject("mountain.obj", up_axis="y")'))
        coarse = OBJMobject("mountain.obj", width=20, up_axis="y",
                            color_by="z", gradient=ROCK,
                            shading=(0.30, 0.20, 0.55))
        coarse.shift(1.2 * IN)

        self.play(BuildMesh(coarse, order="radial", spread=0.8, run_time=4.5))
        self.play(frame.animate.reorient(-18, 74, 0, (0, 0, 0.8), 15.0),
                  run_time=2.8)

        # the point of the shot: same file, four times the triangles
        code = self.swap(code, self.hud("land.subdivide(1)   # 6,962 -> 27,848"))
        land = OBJMobject("mountain.obj", width=20, up_axis="y",
                          subdivide=1,              # Loop: the ridges round off
                          color_by="z", gradient=ROCK,
                          shading=(0.30, 0.20, 0.55))
        land.shift(1.2 * IN)
        counts = self.hud(f"{coarse.num_faces:,}  ->  {land.num_faces:,} triangles",
                          corner=UL, size=22, color=INK)
        self.play(FadeIn(counts), run_time=0.4)
        self.play(Transform(coarse, land), run_time=2.2)
        self.remove(coarse)
        self.add(land)
        self._ground = land.get_points()
        self.wait(1.0)
        self.play(FadeOut(counts), run_time=0.4)

        # ---- 3. trees --------------------------------------------------------
        code = self.swap(code, self.hud("OBJMobject(..., decimate=420)"))
        trees = Group()
        for i, (x, y) in enumerate(PINES):
            t = OBJMobject("tree_a.obj", height=1.9, up_axis="y", decimate=420,
                           color_by="z", gradient=PINE)
            t.rotate(np.random.default_rng(i + 7).uniform(0, TAU), OUT)
            trees.add(self.stand(t, x, y, sink=0.06, settle=False, footprint=0.35))
        for i, (x, y) in enumerate(PALMS):
            t = OBJMobject("palm.obj", height=2.0, up_axis="y", decimate=600,
                           color_by="z", gradient=["#4A3520", "#6E8F4A", "#9CC46A"])
            t.rotate(np.random.default_rng(i + 31).uniform(0, TAU), OUT)
            trees.add(self.stand(t, x, y, sink=0.06, settle=False, footprint=0.35))

        self.play(LaggedStart(*[GrowFromPoint(t, t.get_center() + 0.7 * IN)
                                for t in trees],
                              lag_ratio=0.10, run_time=3.4))

        # ---- 4. two buildings -------------------------------------------------
        code = self.swap(code, self.hud('OBJMobject("building.obj", up_axis="z")'))
        engel = OBJMobject("building.obj", height=3.2, up_axis="z",
                           color_by="material",
                           palette=["#9FB4CC", "#E9A13B", "#6FD6C0",
                                    "#D96F6F", "#9C8CD4", "#6FA8DC"])
        self.stand(engel, 6.0, -6.2, sink=0.15, footprint=1.9)

        cottage = OBJMobject("house.obj", height=2.1, up_axis="y",
                             color_by="z",
                             gradient=["#7A4B32", "#C98F5A", "#EBD7A8"])
        cottage.rotate(35 * DEGREES, OUT)
        self.stand(cottage, -6.2, -6.4, sink=0.1, footprint=1.2)

        for mob in (engel, cottage):
            ghost = mob.copy().shift(6 * OUT).set_opacity(0.0)
            self.add(ghost)
            self.play(Transform(ghost, mob), run_time=1.6, rate_func=smooth)
            self.remove(ghost)
            self.add(mob)

        legend = engel.legend(font=MONO, font_size=15, text_color=DIM)
        legend.fix_in_frame().to_corner(UR, buff=0.4)
        self.play(FadeIn(legend, shift=0.2 * LEFT), run_time=0.7)
        self.play(frame.animate.reorient(14, 70, 0, (0.6, 0, 1.0), 14.0),
                  run_time=3.2)
        self.play(FadeOut(legend), run_time=0.5)

        # ---- 5. two chairs, both smoothed -------------------------------------
        code = self.swap(code, self.hud("decimate(2000).subdivide(1)"))
        chair = OBJMobject("chair.obj", height=1.15, up_axis="y",
                           decimate=2000, subdivide=1,   # coarsen, then round
                           color_by="material",
                           palette=["#E9A13B", "#C9D6E4", "#6FD6C0", "#D96F6F"])
        self.stand(chair, -1.6, -9.0, sink=0.05, footprint=0.45)

        arm = OBJMobject("armchair.obj", height=1.25, up_axis="z",
                         subdivide=1,                   # blocky mesh -> soft
                         color_by="z",
                         gradient=["#7A2E2E", "#C9564A", "#E8A07A"])
        arm.rotate(-50 * DEGREES, OUT)
        self.stand(arm, 1.8, -9.4, sink=0.05, footprint=0.5)

        self.play(FadeIn(chair, shift=0.4 * OUT),
                  FadeIn(arm, shift=0.4 * OUT), run_time=1.4)
        self.wait(0.8)

        # ---- 6. the sun goes round ---------------------------------------------
        code = self.swap(code, self.hud("self.camera.light_source.move_to(...)"))
        self.play(frame.animate.reorient(-8, 72, 0, (0.4, 0, 1.0), 15.5),
                  run_time=2.0)

        where = None
        for position, caption in SUN_STOPS[1:]:
            new = self.hud(caption, corner=UL, size=22, color=INK)
            if where is None:
                self.play(FadeIn(new), run_time=0.3)
            else:
                self.play(FadeOut(where), FadeIn(new), run_time=0.3)
            where = new
            self.play(sun.animate.move_to(np.array(position)), run_time=2.6)
            self.wait(0.9)
        self.play(FadeOut(where), run_time=0.4)
        self.play(sun.animate.move_to(np.array([-13, -9, 11])), run_time=1.6)

        # ---- 7. down among the chairs -------------------------------------------
        code = self.swap(code, self.hud("armchair.subdivide(1)   # 2,832 -> 11,328"))
        seat = arm.get_center()
        self.play(frame.animate.reorient(18, 78, 0,
                                         (seat[0], seat[1], seat[2]), 3.2),
                  run_time=3.6)
        self.wait(1.4)
        wires = arm.wireframe(color=GOLD, width=1.0, feature_angle=26,
                              max_edges=3000, nudge=0.002)
        self.play(ShowCreation(wires), run_time=2.0)
        self.wait(0.8)
        self.play(FadeOut(wires), run_time=0.6)

        code = self.swap(code, self.hud('chair.split_by("group")'))
        desk = chair.get_center()
        self.play(frame.animate.reorient(-10, 76, 0,
                                         (desk[0], desk[1], desk[2]), 3.0),
                  run_time=2.8)
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

        # ---- 8. earthrise, with relief that is really there ----------------------
        code = self.swap(code, self.hud(
            'earth.subdivide(2).displace(bump).textured()'))
        globe = OBJMobject("earth.obj", height=10.0, up_axis="y",
                           subdivide=2, displace=True,
                           displace_strength=0.035).textured()
        globe.move_to(np.array([7.0, 17.0, -2.0]))
        globe.add_updater(lambda m, dt: m.rotate(0.12 * dt, OUT))
        self.add(globe)

        self.play(sun.animate.move_to(np.array([3, 22, 7])), run_time=0.1)
        self.play(
            frame.animate.reorient(-6, 86, 0, (2.4, 3.0, 3.4), 15.0),
            globe.animate.move_to(np.array([7.0, 17.0, 5.6])),
            run_time=5.4,
        )
        self.wait(2.2)
        self.play(frame.animate.reorient(-4, 80, 0, (2.0, 1.4, 2.6), 17.0),
                  run_time=2.8)

        # ---- 9. dust ---------------------------------------------------------------
        code = self.swap(code, self.hud("model.point_cloud(n)"))
        globe.clear_updaters()
        solid = Group(land, *trees, engel, cottage, chair, arm)
        lit = engel.copy().set_color_by("z",
                                        gradient=["#3A9BD0", "#79E3C8", "#FFF2B8"])
        cloud = Group(
            land.point_cloud(24000, radius=0.052),
            *[t.point_cloud(420, radius=0.030) for t in trees],
            lit.point_cloud(6000, radius=0.032),
            cottage.point_cloud(3000, radius=0.030),
            chair.point_cloud(1200, radius=0.022),
            arm.point_cloud(1200, radius=0.022),
        )
        self.play(FadeOut(solid), FadeOut(globe), FadeIn(cloud), run_time=2.4)
        self.play(frame.animate.reorient(28, 64, 0, (0, 0, 1.0), 16.0),
                  run_time=3.6)

        # ---- outro --------------------------------------------------------------------
        outro = VGroup(
            Text("manim_obj", font_size=46, color=INK),
            Text("eight files · none of them touched by hand",
                 font=MONO, font_size=21, color=GOLD),
        ).arrange(DOWN, buff=0.28).fix_in_frame().to_edge(DOWN, buff=0.55)
        self.play(FadeOut(code), run_time=0.4)
        self.play(FadeIn(outro, shift=0.2 * UP), run_time=1.0)
        self.wait(2.4)
        self.play(FadeOut(outro), FadeOut(cloud), run_time=1.4)
