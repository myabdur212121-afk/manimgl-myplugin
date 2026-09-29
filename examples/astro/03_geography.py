"""
Places on a planet, and one body going round another.

    manimgl examples/astro/03_geography.py Geography -w -m -c "#03050B" \
        --video_dir /tmp/out
"""
import numpy as np
from manimlib import *
from manimgl_myplugin.astro import Earth, Moon

MONO, INK, CYAN, GOLD = "DejaVu Sans Mono", "#EAF0F8", "#6FE3D4", "#F2B33D"
PLACES = [("Dhaka", 23.8, 90.4), ("London", 51.5, -0.1),
          ("Nairobi", -1.3, 36.8), ("Lima", -12.0, -77.0)]


class Geography(ThreeDScene):
    def hud(self, t, corner=DL, size=20, color=CYAN):
        m = Text(t, font=MONO, font_size=size, color=color)
        return m.fix_in_frame().to_corner(corner, buff=0.4)

    def construct(self):
        f = self.camera.frame
        f.set_height(8.5); f.reorient(-35, 72, 0)
        self.camera.light_source.move_to(np.array([-11.0, -9.0, 5.0]))

        earth = Earth(radius=3)
        code = self.hud("earth.graticule(30)")
        self.add(earth, code)
        self.play(ShowCreation(earth.graticule(30)), run_time=2.0)
        self.wait(0.8)
        self.clear()

        # ---- markers ---------------------------------------------------------
        earth = Earth(radius=3)
        code = self.hud("earth.marker(23.8, 90.4)     # Dhaka")
        self.add(earth, code)
        dots, tags = Group(), VGroup()
        for name, lat, lon in PLACES:
            dots.add(earth.marker(lat, lon, size=0.07))
            tag = Text(name, font=MONO, font_size=17, color=INK)
            tag.rotate(PI / 2, RIGHT)
            tag.move_to(earth.point_at(lat, lon, 0.28))
            tags.add(tag)
        self.play(LaggedStart(*[FadeIn(d, scale=0.4) for d in dots],
                              lag_ratio=0.25, run_time=1.8),
                  FadeIn(tags, run_time=1.8))
        self.wait(1.6)

        # ---- a path between two of them ---------------------------------------
        code2 = self.hud('earth.arc_between((23.8, 90.4), (51.5, -0.1))')
        self.play(FadeOut(code), FadeIn(code2), run_time=0.5)
        arcs = VGroup(earth.arc_between((23.8, 90.4), (51.5, -0.1)),
                      earth.arc_between((23.8, 90.4), (-1.3, 36.8)),
                      earth.arc_between((51.5, -0.1), (-12.0, -77.0)))
        self.play(LaggedStart(*[ShowCreation(a) for a in arcs],
                              lag_ratio=0.35, run_time=3.0))
        self.wait(1.8)
        self.clear()

        # ---- axis, spin, orbit --------------------------------------------------
        f.set_height(14).reorient(-20, 76, 0)
        earth = Earth(radius=2.2).spin(0.5)
        moon = Moon(radius=0.7).spin(0.15).orbit(earth, radius=5.2, period=9, tilt=12)
        pin = earth.axis_line()
        pin.add_updater(lambda m: m.become(earth.axis_line()))
        code = self.hud("moon.orbit(earth, radius=5.2, period=9, tilt=12)")
        note = self.hud("both spinning on their own axes", corner=UL,
                        size=19, color=INK)
        self.add(earth, moon, pin, code, note)
        self.wait(11)
