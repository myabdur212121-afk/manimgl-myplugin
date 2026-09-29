"""
Planets, moons and rings.

    manimgl examples/astro/01_planets.py Planets -w -m -c "#02040A" \
        --video_dir /tmp/out

Each body knows its own radius, flattening, axial tilt and texture, so a
line is enough. Saturn also knows where its rings begin and end, and the
two shadows -- rings across the planet, planet across the rings -- are
solved and painted in, because the renderer itself has none.
"""

import numpy as np
from manimlib import *

from manimgl_myplugin.astro import (
    Mercury, Venus, Earth, Moon, Mars, Jupiter, Saturn, Uranus, Neptune,
)

INK, DIM, CYAN, GOLD = "#EAF0F8", "#7E93AC", "#6FE3D4", "#F2B33D"
MONO = "DejaVu Sans Mono"


class Planets(ThreeDScene):

    def hud(self, text, *, corner=DL, size=20, color=CYAN):
        mob = Text(text, font=MONO, font_size=size, color=color)
        mob.fix_in_frame().to_corner(corner, buff=0.4)
        return mob

    def beat(self, body, code, note=None, wait=2.0, spin=0.25, fade=True):
        caption = self.hud(code)
        info = (self.hud(note, corner=UL, size=19, color=INK) if note else None)
        self.add(caption, *( [info] if info else []))
        self.play(FadeIn(body, scale=0.9), run_time=0.9)
        body.add_updater(lambda m, dt: m.rotate(spin * dt, OUT))
        self.wait(wait)
        body.clear_updaters()
        if fade:
            self.play(FadeOut(body), FadeOut(caption),
                      *( [FadeOut(info)] if info else []), run_time=0.6)
        return body

    def construct(self):
        frame = self.camera.frame
        sun = self.camera.light_source
        frame.set_height(9.5)
        frame.reorient(0, 70, 0)
        sun.move_to(np.array([-13.0, -6.0, 4.0]))

        title = VGroup(
            Text("nine bodies", font_size=52, color=INK),
            Text("each one knows its own numbers", font=MONO,
                 font_size=22, color=GOLD),
        ).arrange(DOWN, buff=0.3).fix_in_frame()
        self.play(Write(title[0]), run_time=1.1)
        self.play(FadeIn(title[1], shift=0.2 * UP), run_time=0.6)
        self.wait(0.7)
        self.play(FadeOut(title, shift=0.3 * UP), run_time=0.6)

        # ---- the rocky ones -------------------------------------------------
        self.beat(Mars(radius=3), "Mars(radius=3)",
                  "3,396 km · tilt 25.2°")
        self.beat(Moon(radius=3), "Moon(radius=3)",
                  "1,737 km · not a planet, hence Body")
        self.beat(Earth(radius=3), "Earth(radius=3)",
                  "night side lit by its own map")
        self.beat(Mercury(radius=3), "Mercury(radius=3)", "2,440 km")

        # ---- texture quality is a parameter ----------------------------------
        frame.reorient(0, 70, 0)
        code = self.hud('Mars(radius=3, quality="2k" / "4k")')
        left = Mars(radius=2.4, quality="2k").shift(3.0 * LEFT)
        right = Mars(radius=2.4, quality="4k").shift(3.0 * RIGHT)
        tags = VGroup(Text("2k", font=MONO, font_size=22, color=DIM),
                      Text("4k", font=MONO, font_size=22, color=GOLD))
        tags[0].fix_in_frame().move_to(3.1 * LEFT + 2.6 * UP)
        tags[1].fix_in_frame().move_to(3.1 * RIGHT + 2.6 * UP)
        self.add(code, tags)
        self.play(FadeIn(left), FadeIn(right), run_time=1.0)
        self.wait(2.4)
        self.play(FadeOut(Group(left, right)), FadeOut(code), FadeOut(tags),
                  run_time=0.6)

        # ---- the gas giants ---------------------------------------------------
        self.beat(Jupiter(radius=3), "Jupiter(radius=3)",
                  "flattening 0.065 — visibly squashed")
        self.beat(Neptune(radius=3), "Neptune(radius=3)", "24,764 km")
        self.beat(Uranus(radius=2.6), "Uranus(radius=2.6)",
                  "tilt 97.8° — its rings stand up")

        # ---- Saturn, and what the shadows do -----------------------------------
        frame.reorient(0, 66, 0)
        code = self.hud("Saturn(radius=3, shadows=False)")
        plain = Saturn(radius=3, shadows=False)
        self.play(FadeIn(plain), run_time=0.9)
        self.wait(1.8)

        shadowed = Saturn(radius=3, light=sun.get_location())
        note = self.hud("the planet's shadow cuts into the rings",
                        corner=UL, size=19, color=INK)
        self.play(FadeOut(plain), FadeOut(code), run_time=0.5)
        code = self.hud("Saturn(radius=3)      # shadows on")
        self.play(FadeIn(shadowed), FadeIn(code), FadeIn(note), run_time=0.9)
        self.wait(2.4)

        self.play(frame.animate.reorient(0, 84, 0), run_time=2.6)
        self.wait(1.4)
        self.play(frame.animate.reorient(0, 40, 0), run_time=2.6)
        self.wait(1.8)
        self.clear()

        # ---- everything together ------------------------------------------------
        frame.reorient(0, 72, 0).set_height(12.5)
        row = Group(
            Mercury(radius=0.5), Venus(radius=0.8), Earth(radius=0.85),
            Mars(radius=0.6), Jupiter(radius=1.6),
            Saturn(radius=1.3, shadows=False), Uranus(radius=1.0),
            Neptune(radius=1.0),
        )
        for i, body in enumerate(row):
            body.shift((i - 3.5) * 2.9 * RIGHT)
        code = self.hud("Mercury · Venus · Earth · Mars · Jupiter · "
                        "Saturn · Uranus · Neptune", size=18)
        self.add(code)
        self.play(LaggedStart(*[FadeIn(b, scale=0.85) for b in row],
                              lag_ratio=0.12, run_time=3.0))
        for body in row:
            body.add_updater(lambda m, dt: m.rotate(0.2 * dt, OUT))
        self.wait(3.0)
        for body in row:
            body.clear_updaters()

        outro = VGroup(
            Text("astro", font=MONO, font_size=34, color=INK),
            Text("radius · flattening · tilt · rings · shadows",
                 font=MONO, font_size=19, color=GOLD),
        ).arrange(DOWN, buff=0.26).fix_in_frame().to_edge(DOWN, buff=0.5)
        self.play(FadeOut(code), FadeIn(outro, shift=0.2 * UP), run_time=0.9)
        self.wait(2.2)
        self.play(FadeOut(outro), FadeOut(row), run_time=1.2)
