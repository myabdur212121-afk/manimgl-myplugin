"""
The Sun, and its corona.

    manimgl examples/astro/04_sun.py SunDemo -w -m -c "#070B14" \
        --video_dir /tmp/out

One bare call builds the star: an unlit globe inside six shells of
additive light, the opacities fitted against a measured falloff. The
planet crossing in front is the honesty test -- the glow parts around it
where it passes before the disc, and lies over it like a veil further
out, because the corona is in the scene like everything else, not
painted over the picture afterwards. The crossing line is placed from
the camera itself, so it works at any angle. Needs the glow renderer
patch; without it the shells draw as flat veils and a warning says so.
"""

import numpy as np
from manimlib import *

from manimgl_myplugin.astro import Sun, Mercury

INK, DIM, GOLD = "#EAF0F8", "#7E93AC", "#F2B33D"
MONO = "DejaVu Sans Mono"


class SunDemo(ThreeDScene):

    def hud(self, text, *, corner=DL, size=20, color=GOLD):
        mob = Text(text, font=MONO, font_size=size, color=color)
        return mob.fix_in_frame().to_corner(corner, buff=0.4)

    def construct(self):
        frame = self.camera.frame
        frame.set_height(6.4).reorient(0, 68, 0)
        self.camera.light_source.move_to(ORIGIN)

        # ---- bare star against the full one --------------------------------
        bare = Sun(radius=1.3, corona=False).shift(2.2 * LEFT)
        lit = Sun(radius=1.3).shift(2.2 * RIGHT)
        tags = VGroup(
            Text("corona=False", font=MONO, font_size=20, color=DIM),
            Text("Sun(radius=1.3)", font=MONO, font_size=20, color=GOLD),
        )
        tags[0].fix_in_frame().move_to(2.2 * LEFT + 2.2 * UP)
        tags[1].fix_in_frame().move_to(2.2 * RIGHT + 2.2 * UP)
        self.play(FadeIn(Group(bare, lit), scale=0.92), FadeIn(tags),
                  run_time=1.2)
        self.wait(1.6)
        self.play(FadeOut(Group(bare, lit)), FadeOut(tags), run_time=0.7)

        # ---- the star alone, slowly turning --------------------------------
        sun = Sun(radius=1.6)
        code = self.hud("Sun(radius=1.6)   # one lift + five shells")
        self.play(FadeIn(sun, scale=0.9), FadeIn(code), run_time=1.0)
        sun.spin(0.06)
        self.wait(2.2)

        # ---- the honesty test: a crossing cuts, then veils ------------------
        # the line is laid through the camera axis, so the planet is in
        # front of the disc at the middle of the crossing and inside the
        # shells' reach at the ends -- cut first, veil after, whatever
        # angle the scene is watched from
        d = frame.get_implied_camera_location()
        d = d / np.linalg.norm(d)
        u = np.cross(d, OUT)
        u = u / np.linalg.norm(u)

        mercury = Mercury(radius=0.26, resolution=(96, 48))
        state = {"s": -3.4}

        def cross(m, dt):
            state["s"] += 0.9 * dt
            m.move_to(4.2 * d + state["s"] * u)

        mercury.move_to(4.2 * d - 3.4 * u)
        mercury.add_updater(cross)
        note = self.hud("in front: the glow parts; outside: it veils",
                        corner=UL, size=19, color=INK)
        # added after the sun on purpose: draw order must not matter,
        # the shells' z-index settles it
        self.play(FadeIn(mercury), FadeIn(note, shift=0.2 * UP), run_time=0.5)
        self.wait(6.5)
        mercury.clear_updaters()

        # ---- pull back to the full extent -----------------------------------
        note2 = self.hud("3.3R -- the last shell", corner=UL, size=19,
                         color=INK)
        self.play(FadeOut(note), FadeIn(note2, shift=0.2 * UP),
                  frame.animate.set_height(12.0).reorient(0, 62, 0),
                  run_time=2.4)
        self.wait(2.0)
        self.play(FadeOut(note2), FadeOut(code), FadeOut(sun),
                  FadeOut(mercury), run_time=0.8)
