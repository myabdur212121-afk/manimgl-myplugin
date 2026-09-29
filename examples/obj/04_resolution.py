"""
Resolution, both directions -- and the texture the file asked for.

    manimgl examples/obj/04_resolution.py Resolution -w -m \
        -c "#070B14" --video_dir videos/08_resolution

Four ideas, in order:
    .textured()          the .mtl names its own image; stop repeating it
    decimate(target)     fewer triangles, same shape
    subdivide(n)         more triangles, and genuinely rounder
    displace(bump)       painted relief becomes real geometry
"""

from manimlib import *

from manimgl_myplugin import OBJMobject, load_mesh

INK, DIM, CYAN, GOLD = "#E8EEF7", "#8095AE", "#6FE3D4", "#F2B33D"
MONO = "DejaVu Sans Mono"


class Resolution(ThreeDScene):

    def hud(self, text, *, corner=DL, size=20, color=CYAN):
        mob = Text(text, font=MONO, font_size=size, color=color)
        mob.fix_in_frame().to_corner(corner, buff=0.4)
        return mob

    def swap(self, old, new, run_time=0.6):
        self.play(FadeOut(old, shift=0.2 * UP), FadeIn(new, shift=0.2 * UP),
                  run_time=run_time)
        return new

    @staticmethod
    def spin(mob, speed=0.35):
        mob.add_updater(lambda m, dt: m.rotate(speed * dt, OUT))
        return mob

    def construct(self):
        frame = self.camera.frame
        frame.set_height(6.4)
        frame.reorient(0, 74, 0)

        # ---- title ---------------------------------------------------------
        title = Text("how many triangles?", font_size=54, color=INK)
        sub = Text("take them away, or put more in", font_size=25, color=DIM)
        card = VGroup(title, sub).arrange(DOWN, buff=0.3).fix_in_frame()
        self.play(Write(title), run_time=1.1)
        self.play(FadeIn(sub, shift=0.2 * UP), run_time=0.7)
        self.wait(0.7)
        self.play(FadeOut(card, shift=0.3 * UP), run_time=0.6)

        # ---- 1. the file names its own texture -----------------------------
        code = self.hud("OBJMobject(\"earth.obj\").textured()")
        note = self.hud("the .mtl says map_Kd 4096_earth.jpg — so ask the file",
                        corner=UL, size=21, color=INK)
        self.play(FadeIn(code), FadeIn(note), run_time=0.6)

        globe = OBJMobject("earth.obj", height=3.6).textured()
        self.play(FadeIn(globe), run_time=1.2)
        self.spin(globe)
        self.wait(2.4)
        self.play(FadeOut(globe), FadeOut(note), run_time=0.8)

        # ---- 2. taking triangles away --------------------------------------
        code = self.swap(code, self.hud("chair.decimate(target)"))
        targets = [None, 3000, 1500, 500]
        chairs = Group()
        for n in targets:
            chair = OBJMobject("chair.obj", height=2.5,
                               decimate=n, color="#9FD6E8")
            chairs.add(chair)
        chairs.arrange(RIGHT, buff=0.55)

        labels = VGroup(*[
            Text(f"{c.num_faces:,}", font=MONO, font_size=19,
                 color=GOLD if n else INK)
            for c, n in zip(chairs, targets)
        ])
        for label, chair in zip(labels, chairs):
            label.rotate(PI / 2, RIGHT)     # stand it up, facing the camera
            label.next_to(chair, IN, buff=0.3)   # IN (-z) reads as "below"

        self.play(FadeIn(chairs, shift=0.3 * UP), FadeIn(labels), run_time=1.4)
        self.wait(3.0)

        keep = self.hud("same shape until the very end — flat parts go first",
                        corner=UL, size=21, color=INK)
        self.play(FadeIn(keep), run_time=0.5)
        self.wait(2.2)
        self.play(FadeOut(chairs), FadeOut(labels), FadeOut(keep), run_time=0.9)

        # ---- 3. putting triangles in ---------------------------------------
        code = self.swap(code, self.hud("earth.subdivide(2)   # 3,968 -> 63,488"))
        coarse = OBJMobject("earth.obj", height=2.9, color="#9FB4CC")
        fine = OBJMobject("earth.obj", height=2.9, color="#9FB4CC", subdivide=2)
        coarse.shift(2.4 * LEFT)
        fine.shift(2.4 * RIGHT)

        tags = VGroup(
            Text(f"{coarse.num_faces:,}", font=MONO, font_size=20, color=DIM),
            Text(f"{fine.num_faces:,}", font=MONO, font_size=20, color=GOLD),
        )
        for tag, mob in zip(tags, (coarse, fine)):
            tag.rotate(PI / 2, RIGHT)
            tag.next_to(mob, IN, buff=0.35)

        self.play(FadeIn(coarse), FadeIn(fine), FadeIn(tags), run_time=1.2)
        self.wait(2.6)

        edge = self.hud("look at the outline, not the shading",
                        corner=UL, size=21, color=INK)
        self.play(FadeIn(edge), run_time=0.5)
        self.wait(2.4)
        self.play(FadeOut(coarse), FadeOut(fine), FadeOut(tags),
                  FadeOut(edge), run_time=0.9)

        # ---- 4. relief that is really there --------------------------------
        code = self.swap(code, self.hud('earth.displace("4096_bump.jpg")'))
        relief = OBJMobject("earth.obj", height=3.4, color="#B9C6D6",
                            subdivide=2, displace=True, displace_strength=0.05)
        note = self.hud("the bump map is now geometry — it shows on the rim",
                        corner=UL, size=21, color=INK)
        self.play(FadeIn(relief), FadeIn(note), run_time=1.2)
        self.spin(relief, speed=0.3)
        self.wait(3.4)

        # and with its own colours on top
        code = self.swap(code, self.hud("...and .textured() over the top"))
        relief.clear_updaters()
        painted = relief.textured()
        self.play(FadeOut(relief), FadeIn(painted), run_time=1.2)
        self.spin(painted, speed=0.3)
        self.wait(3.2)

        # ---- outro ----------------------------------------------------------
        outro = VGroup(
            Text("fewer, or more — your call", font_size=34, color=INK),
            Text("decimate(1500)   ·   subdivide(2)   ·   displace(bump)",
                 font=MONO, font_size=20, color=GOLD),
        ).arrange(DOWN, buff=0.26).fix_in_frame().to_edge(DOWN, buff=0.5)

        self.play(FadeOut(code), FadeOut(note), run_time=0.5)
        self.play(FadeIn(outro, shift=0.2 * UP), run_time=0.9)
        self.wait(2.4)
        self.play(FadeOut(outro), FadeOut(painted), run_time=1.2)
