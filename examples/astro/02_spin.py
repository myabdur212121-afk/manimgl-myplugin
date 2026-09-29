"""
spin() turns a body on its own axis; rotate() turns it on the scene's.

    manimgl examples/astro/02_spin.py Spin -w -m -c "#03050B" --video_dir /tmp/out
"""
import numpy as np
from manimlib import *
from manimgl_myplugin.astro import Earth, Jupiter, Mars, Venus, Saturn

MONO, INK, CYAN, GOLD, DIM = "DejaVu Sans Mono", "#EAF0F8", "#6FE3D4", "#F2B33D", "#7E93AC"


def axis_arrow(body, colour):
    """Draw the pole so you can watch whether it stays put."""
    a = body.axis * body.radius * 1.55
    c = body.get_center()
    return Line3D(c - a, c + a, width=0.035, color=colour)


class Spin(ThreeDScene):
    def construct(self):
        f = self.camera.frame
        f.set_height(9)
        f.reorient(0, 72, 0)
        self.camera.light_source.move_to(np.array([-12.0, -7.0, 5.0]))

        # ---- the two side by side -------------------------------------------
        wrong = Earth(radius=2.2).shift(3.2 * LEFT)
        right = Earth(radius=2.2).shift(3.2 * RIGHT)
        pin_l, pin_r = axis_arrow(wrong, "#D96F6F"), axis_arrow(right, GOLD)
        pin_l.add_updater(lambda m: m.become(axis_arrow(wrong, "#D96F6F")))
        pin_r.add_updater(lambda m: m.become(axis_arrow(right, GOLD)))

        wrong.add_updater(lambda m, dt: m.rotate(0.9 * dt, OUT,
                                                 about_point=m.get_center()))
        right.spin(0.9)

        labels = VGroup(
            Text("rotate(OUT)", font=MONO, font_size=22, color="#D96F6F"),
            Text("spin(0.9)", font=MONO, font_size=22, color=GOLD),
        )
        labels[0].fix_in_frame().move_to(3.4 * LEFT + 2.9 * UP)
        labels[1].fix_in_frame().move_to(3.4 * RIGHT + 2.9 * UP)
        note = Text("watch the pole, not the planet", font=MONO,
                    font_size=20, color=INK).fix_in_frame().to_edge(DOWN, buff=0.4)

        self.add(wrong, right, pin_l, pin_r, labels, note)
        self.wait(7)
        self.remove(wrong, right, pin_l, pin_r, labels, note)

        # ---- day= gives every body its true relative speed --------------------
        f.set_height(7.5)
        code = Text('spin(day=3)   # one Earth day = 3 seconds', font=MONO,
                    font_size=21, color=CYAN).fix_in_frame().to_edge(DOWN, buff=0.4)
        row = Group(Jupiter(radius=1.15, shadows=False).spin(day=3),
                    Earth(radius=1.15).spin(day=3),
                    Mars(radius=1.15).spin(day=3),
                    Venus(radius=1.15).spin(day=3))
        tags = VGroup()
        for i, (body, name) in enumerate(zip(row, ("Jupiter  9.9 h",
                                                   "Earth  23.9 h",
                                                   "Mars  24.6 h",
                                                   "Venus  −243 d"))):
            body.shift((i - 1.5) * 2.9 * RIGHT)
            tag = Text(name, font=MONO, font_size=17, color=DIM).fix_in_frame()
            tag.move_to((i - 1.5) * 2.55 * RIGHT + 2.45 * UP)
            tags.add(tag)
        self.add(row, tags, code)
        self.wait(8)
        self.remove(row, tags, code)

        # ---- turn(): a measured amount, as an animation -----------------------
        f.set_height(8)
        saturn = Saturn(radius=2.6)
        code = Text("self.play(saturn.turn(TAU, run_time=5, rate_func=smooth))",
                    font=MONO, font_size=19, color=CYAN)
        code.fix_in_frame().to_edge(DOWN, buff=0.4)
        self.add(saturn, code)
        self.play(saturn.turn(TAU, run_time=5, rate_func=smooth))
        self.wait(0.6)
