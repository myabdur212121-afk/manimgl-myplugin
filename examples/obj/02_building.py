"""
OBJMobject demo -- a real building, imported from a .obj file.

Model: Engel House (Ze'ev Rechter, 1933), Tel Aviv -- a Bauhaus landmark and
the first building in Israel raised on pilotis. Downloaded from the
ladybug-tools/3d-models collection by tools/get_building.py.

Render:
    manimgl examples/obj/02_building.py BuildingDemo -w -m \
        -c "#070B14" --video_dir videos/05_obj
"""

import numpy as np
from manimlib import *

from manimgl_myplugin import OBJMobject, BuildMesh

# ----------------------------------------------------------------- palette --
INK = "#E8EEF7"
DIM = "#8095AE"
CYAN = "#6FE3D4"
GOLD = "#F2B33D"
STONE = "#AFC0D4"

MATERIAL_PALETTE = ["#9FB4CC", "#E9A13B", "#6FD6C0", "#D96F6F", "#9C8CD4", "#6FA8DC"]
HEIGHT_GRADIENT = ["#17304C", "#2E7FA8", "#79E3C8", "#FFF2B8"]

MODEL = "building.obj"
MONO = "DejaVu Sans Mono"


class BuildingDemo(ThreeDScene):
    # ------------------------------------------------------------ helpers --

    def hud(self, text, *, corner=DL, font=None, size=20, color=CYAN, buff=0.45):
        """A caption pinned to the screen rather than to the 3D world."""
        mob = Text(text, font=font or MONO, font_size=size, color=color)
        mob.fix_in_frame()
        mob.to_corner(corner, buff=buff)
        return mob

    def swap_hud(self, old, new, run_time=0.6):
        if old is None:
            self.play(FadeIn(new, shift=0.2 * UP), run_time=run_time)
        else:
            self.play(FadeOut(old, shift=0.2 * UP),
                      FadeIn(new, shift=0.2 * UP), run_time=run_time)
        return new

    def orbit(self, speed=-0.035):
        """Keep the camera drifting around the model for the rest of the scene."""
        self.camera.frame.add_updater(lambda m, dt: m.increment_theta(speed * dt))

    # -------------------------------------------------------------- scene --

    def construct(self):
        frame = self.camera.frame
        frame.set_height(8.5)
        frame.reorient(-40, 74, 0)

        # ---- 1. title -----------------------------------------------------
        title = Text("OBJMobject", font_size=62, color=INK)
        rule = Line(LEFT, RIGHT, stroke_color=GOLD, stroke_width=3).set_width(4.2)
        sub = Text("any Wavefront .obj model, straight into ManimGL",
                   font_size=26, color=DIM)
        card = VGroup(title, rule, sub).arrange(DOWN, buff=0.3)
        card.fix_in_frame()

        self.play(Write(title), run_time=1.2)
        self.play(ShowCreation(rule), FadeIn(sub, shift=0.2 * UP), run_time=0.9)
        self.wait(0.9)
        self.play(FadeOut(card, shift=0.3 * UP), run_time=0.7)

        # ---- 2. load and build --------------------------------------------
        model = OBJMobject(
            MODEL,
            height=3.4,          # 3.4 units tall in z -- what "tall" means here
            up_axis="z",         # this file is a CAD export, so z already points up
            color=STONE,
            shading=(0.25, 0.3, 0.45),
        )
        print(model.info())

        code = self.hud('OBJMobject("building.obj", height=3.4, up_axis="z")')
        note = self.hud(
            f"Engel House · Tel Aviv · {model.num_faces:,} triangles",
            corner=UL, font=None, size=24, color=INK,
        )
        self.play(FadeIn(code), FadeIn(note), run_time=0.6)

        self.play(BuildMesh(model, order="z", spread=0.75, run_time=5.0))
        self.orbit()
        self.wait(1.0)

        # ---- 3. one colour per material ------------------------------------
        code = self.swap_hud(code, self.hud('model.set_color_by("material")'))
        by_material = model.copy().set_color_by("material", palette=MATERIAL_PALETTE)
        self.play(Transform(model, by_material), run_time=1.6)

        # Built from the colours the model actually handed out, so the key
        # can never drift out of step with the picture.
        legend = by_material.legend(font=MONO, font_size=16, text_color=DIM)
        legend.fix_in_frame().to_corner(UR, buff=0.45)
        self.play(FadeIn(legend, shift=0.2 * LEFT), run_time=0.8)
        self.wait(1.6)

        # ---- 4. pick a part out by name -------------------------------------
        code = self.swap_hud(
            code, self.hud('model.set_part_color("glass", "#8FE8FF", opacity=0.75)'))
        glazed = model.copy()
        glazed.set_color("#26303E", opacity=1.0)          # concrete, fully solid
        glazed.set_part_color("glass", "#8FE8FF", opacity=0.75)   # 301 triangles
        self.play(FadeOut(legend, shift=0.2 * RIGHT),
                  Transform(model, glazed), run_time=1.6)
        self.wait(2.0)

        # ---- 5. a gradient up the model -------------------------------------
        code = self.swap_hud(
            code, self.hud('model.set_color_by("z", gradient=[...])'))
        shaded = model.copy().set_color_by("z", gradient=HEIGHT_GRADIENT)
        self.play(Transform(model, shaded), run_time=1.6)
        self.wait(1.4)

        # ---- 6. crease wireframe --------------------------------------------
        code = self.swap_hud(
            code, self.hud("model.wireframe(feature_angle=30)"))
        plain = model.copy().set_color("#33455E", opacity=1.0)
        wires = model.wireframe(color=GOLD, width=1.1,
                                feature_angle=30, max_edges=5200, nudge=0.004)
        self.play(Transform(model, plain), run_time=1.0)
        self.play(ShowCreation(wires), run_time=3.2)
        self.wait(1.0)
        self.play(FadeOut(wires), run_time=0.8)

        # ---- 7. cut it into floors ------------------------------------------
        code = self.swap_hud(
            code, self.hud('model.slice("z", low, high)   # exploded axonometric'))
        back = model.copy().set_color_by("z", gradient=HEIGHT_GRADIENT)
        self.play(Transform(model, back), run_time=1.0)

        lo, hi = model.get_bounding_box()[0][2], model.get_bounding_box()[2][2]
        cuts = np.linspace(lo - 0.01, hi + 0.01, 5)
        slabs = Group(*[
            model.slice("z", low=a, high=b) for a, b in zip(cuts[:-1], cuts[1:])
        ])
        self.remove(model)
        self.add(slabs)
        self.play(
            *[s.animate.shift(i * 0.95 * OUT) for i, s in enumerate(slabs)],
            run_time=2.6, rate_func=smooth,
        )
        self.wait(2.2)
        self.play(
            *[s.animate.shift(-i * 0.95 * OUT) for i, s in enumerate(slabs)],
            run_time=2.0, rate_func=smooth,
        )
        self.remove(slabs)
        self.add(model)
        self.wait(0.6)

        # ---- 8. dissolve into a point cloud ----------------------------------
        code = self.swap_hud(code, self.hud("model.point_cloud(9000)"))
        bright = model.copy().set_color_by("z", gradient=["#3A9BD0", "#79E3C8", "#FFF2B8"])
        cloud = bright.point_cloud(9000, radius=0.033)
        self.play(FadeOut(model), FadeIn(cloud), run_time=1.6)
        self.wait(2.0)

        # ---- 9. outro --------------------------------------------------------
        outro = VGroup(
            Text("OBJMobject", font_size=44, color=INK),
            Text("load · colour · slice · explode · animate",
                 font=MONO, font_size=22, color=GOLD),
        ).arrange(DOWN, buff=0.28)
        outro.fix_in_frame().to_edge(DOWN, buff=0.6)

        self.play(FadeOut(code), FadeOut(note), run_time=0.6)
        self.play(FadeIn(outro, shift=0.2 * UP), run_time=0.9)
        self.wait(2.4)
        self.play(FadeOut(outro), FadeOut(cloud), run_time=1.2)
