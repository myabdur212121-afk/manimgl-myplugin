"""
Making shapes without a file.

Three builders, and what each is for:

    from_surface(mob)        anything ManimGL already draws
    revolve(profile)         spin an outline -- a potter's wheel
    extrude(path, profile)   sweep a cross-section -- toothpaste from a nozzle

Render:
    manimgl examples/shapes/01_making_shapes.py Shapes -w -m -c "#070B14" \
        --video_dir /tmp/out
"""

import numpy as np
from manimlib import *

from manimgl_myplugin import OBJMobject, BuildMesh
from manimgl_myplugin.shapes import (
    revolve, extrude, from_surface,
    circle_profile, square_profile, polygon_profile, star_profile,
    semicircle_profile, helix_path, line_path, arc_path,
)

INK, DIM, CYAN, GOLD = "#EAF0F8", "#7E93AC", "#6FE3D4", "#F2B33D"
MONO = "DejaVu Sans Mono"
EARTH = "/home/user/models/4096_earth.jpg"
BUMP = "/home/user/models/4096_bump.jpg"


def pawn_profile(samples=70):
    """Any outline at all -- this one happens to look like a chess piece."""
    z = np.linspace(0, 2.0, samples)
    r = (0.52 * np.exp(-((z - 0.06) / 0.14) ** 2)      # the base
         + 0.30 * np.exp(-((z - 0.42) / 0.30) ** 2)     # the neck
         + 0.34 * np.exp(-((z - 1.62) / 0.26) ** 2)     # the head
         + 0.10)
    return np.stack([r, z], axis=-1)


class Shapes(ThreeDScene):

    def hud(self, text, *, corner=DL, size=20, color=CYAN):
        mob = Text(text, font=MONO, font_size=size, color=color)
        mob.fix_in_frame().to_corner(corner, buff=0.4)
        return mob

    def show(self, mesh, code, note=None, colour="#9FB4CC", smooth=True,
             wait=1.6, build=False, textured=None):
        model = OBJMobject(mesh, up_axis=None, color=colour,
                           shading=(0.3, 0.25, 0.5))
        if textured:
            model = model.textured(textured)
        elif smooth:
            model.shade_smooth()
        # size by the largest extent: height alone blows up anything flat
        model.scale(2.5 / max(model.get_shape()))

        caption = self.hud(code)
        count = self.hud(f"{model.num_faces:,} triangles", corner=UL,
                         size=19, color=DIM)
        extra = (self.hud(note, corner=UR, size=19, color=INK)
                 if note else None)

        self.add(caption, count, *( [extra] if extra else []))
        if build:
            self.play(BuildMesh(model, order="radial", run_time=2.4))
        else:
            self.play(FadeIn(model, shift=0.3 * OUT), run_time=0.9)
        model.add_updater(lambda m, dt: m.rotate(0.35 * dt, OUT))
        self.wait(wait)
        model.clear_updaters()
        self.play(FadeOut(Group(model)), FadeOut(caption), FadeOut(count),
                  *( [FadeOut(extra)] if extra else []), run_time=0.6)

    def construct(self):
        self.camera.frame.set_height(4.2)
        self.camera.frame.reorient(-24, 72, 0)

        title = VGroup(
            Text("three ways to make a mesh", font_size=48, color=INK),
            Text("no .obj file anywhere", font=MONO, font_size=22, color=GOLD),
        ).arrange(DOWN, buff=0.3).fix_in_frame()
        self.play(Write(title[0]), run_time=1.1)
        self.play(FadeIn(title[1], shift=0.2 * UP), run_time=0.6)
        self.wait(0.7)
        self.play(FadeOut(title, shift=0.3 * UP), run_time=0.6)

        # ---- 1. revolve: the outline is just numbers ----------------------
        self.show(revolve(semicircle_profile()),
                  "revolve(semicircle_profile())",
                  "a semicircle, spun", "#6FA8DC", build=True)

        self.show(revolve(pawn_profile()),
                  "revolve(my_own_outline)",
                  "any outline you like", "#E9A13B")

        # ---- 2. extrude: same path, different nozzle -----------------------
        self.show(extrude(helix_path(turns=4, pitch=0.35), circle_profile(0.07, 16)),
                  "extrude(helix_path(...), circle_profile(0.07))",
                  "a round wire, coiled", "#C9A227")

        self.show(extrude(helix_path(turns=4, pitch=0.35), square_profile(0.14)),
                  "extrude(helix_path(...), square_profile(0.14))",
                  "same path, square nozzle", "#E87A5A")

        self.show(extrude(arc_path(radius=1.2, angle=PI), circle_profile(0.16, 20)),
                  "extrude(arc_path(...), circle_profile(0.16))",
                  "a bend in a pipe", "#6FD6C0")

        self.show(extrude(line_path((0, 0, -1), (0, 0, 1)), star_profile(5, .8, .35)),
                  "extrude(line_path(...), star_profile(5))",
                  "ends capped automatically", "#9C8CD4", smooth=False)

        # ---- 3. from_surface: borrow what manim already has ----------------
        self.show(from_surface(Torus(resolution=(64, 32))).decimate(500),
                  "from_surface(Torus()).decimate(500)",
                  "manim's torus, made cheap", "#D96F6F", smooth=False)

        self.show(from_surface(Cube()).subdivide(3),
                  "from_surface(Cube()).subdivide(3)",
                  "a cube, rounded off", "#A8C46A")

        self.show(from_surface(Sphere(resolution=(128, 64))).displace(BUMP, strength=.07),
                  "from_surface(Sphere()).displace(bump)",
                  "relief that is really there", "#B9C6D6")

        self.show(from_surface(ParametricSurface(
                      lambda u, v: (u, v, 0.35 * np.sin(3 * u) * np.cos(3 * v)),
                      u_range=(-1, 1), v_range=(-1, 1), resolution=(64, 64))),
                  "ParametricSurface(...).textured(earth)",
                  "any formula at all", textured=EARTH)

        outro = VGroup(
            Text("revolve · extrude · from_surface", font=MONO,
                 font_size=26, color=INK),
            Text("everything downstream works the same", font=MONO,
                 font_size=20, color=GOLD),
        ).arrange(DOWN, buff=0.28).fix_in_frame()
        self.play(FadeIn(outro, shift=0.2 * UP), run_time=0.9)
        self.wait(2.2)
        self.play(FadeOut(outro), run_time=0.9)
