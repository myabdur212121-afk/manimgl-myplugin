"""
OBJMobject demo 2 -- two models pulled straight off the internet.

    earth.obj   AudranDoublet/opr          a 3ds Max UV sphere, 3,968 triangles
    chair.obj   cnr-isti-vclab/meshlab     a LightWave office chair, 6,716

Neither was cleaned up or converted first. Both are Y-up, which is the OBJ
convention and the library's default, so neither needs an `up_axis`.

Render:
    manimgl examples/03_earth_chair.py EarthAndChair -w -m \
        -c "#070B14" --video_dir videos/06_earth_chair
"""

from manimlib import *

from manim_obj import OBJMobject, BuildMesh

INK, DIM, CYAN, GOLD = "#E8EEF7", "#8095AE", "#6FE3D4", "#F2B33D"
MONO = "DejaVu Sans Mono"

CHAIR_PALETTE = ["#E9A13B", "#9FB4CC", "#6FD6C0", "#D96F6F"]


class EarthAndChair(ThreeDScene):

    # ----------------------------------------------------------- helpers --
    def hud(self, text, *, corner=DL, size=20, color=CYAN):
        mob = Text(text, font=MONO, font_size=size, color=color)
        mob.fix_in_frame().to_corner(corner, buff=0.4)
        return mob

    def swap(self, old, new, run_time=0.6):
        self.play(FadeOut(old, shift=0.2 * UP), FadeIn(new, shift=0.2 * UP),
                  run_time=run_time)
        return new

    @staticmethod
    def spin(mob, speed=0.4):
        """Turn the model itself, so the camera can stay put."""
        mob.add_updater(lambda m, dt: m.rotate(speed * dt, OUT))
        return mob

    # ------------------------------------------------------------- scene --
    def construct(self):
        frame = self.camera.frame
        frame.set_height(6.2)
        frame.reorient(0, 74, 0)

        # ---- 1. title -----------------------------------------------------
        title = Text("two more models", font_size=58, color=INK)
        sub = Text("downloaded, dropped in, nothing else",
                   font_size=25, color=DIM)
        card = VGroup(title, sub).arrange(DOWN, buff=0.3).fix_in_frame()

        self.play(Write(title), run_time=1.1)
        self.play(FadeIn(sub, shift=0.2 * UP), run_time=0.7)
        self.wait(0.8)
        self.play(FadeOut(card, shift=0.3 * UP), run_time=0.6)

        # ---- 2. the earth, as it comes out of the file ---------------------
        earth = OBJMobject("earth.obj", height=3.9, color="#8FA2B8")
        # ^ that really is the whole setup: no up_axis, no scale, no convert

        code = self.hud('OBJMobject("earth.obj", height=3.9)')
        name = self.hud(f"earth.obj · {earth.num_faces:,} triangles · UV sphere",
                        corner=UL, size=23, color=INK)
        self.play(FadeIn(code), FadeIn(name), run_time=0.6)

        self.play(BuildMesh(earth, order="y", spread=0.8, run_time=4.0))
        self.spin(earth)
        self.wait(1.2)

        # ---- 3. flat facets -> one round ball ------------------------------
        # A sphere is the honest test of shading: 3,968 flat faces, or smooth.
        code = self.swap(code, self.hud("earth.shade_smooth()"))
        self.play(Transform(earth, earth.copy().shade_smooth()), run_time=1.6)
        self.wait(1.6)

        # ---- 4. the real texture, looked up per pixel -----------------------
        # The .obj carries vt coordinates, so the image can go to the GPU
        # instead of being averaged down onto 1,986 vertices.
        code = self.swap(code, self.hud('earth.textured("earth.jpg")'))
        globe = earth.textured()                 # image named by the .mtl
        earth.clear_updaters()
        self.play(FadeOut(earth), FadeIn(globe), run_time=1.4)
        self.spin(globe)
        self.wait(2.2)

        # ---- 5. make room, bring in the chair --------------------------------
        code = self.swap(code, self.hud('OBJMobject("chair.obj", height=3.4)'))
        self.play(globe.animate.scale(0.66).shift(2.7 * LEFT), run_time=1.4)

        chair = OBJMobject("chair.obj", height=3.4)
        chair.shift(2.7 * RIGHT)
        chair.set_color_by("material", palette=CHAIR_PALETTE)

        name2 = self.hud(f"chair.obj · {chair.num_faces:,} triangles · "
                         f"{len(chair.mesh.material_names)} materials",
                         corner=UR, size=23, color=INK)
        self.play(FadeIn(name2), run_time=0.4)
        self.play(BuildMesh(chair, order="y", spread=0.8, run_time=3.6))
        self.spin(chair, speed=-0.4)
        self.wait(1.6)

        # ---- 6. take the chair apart ------------------------------------------
        code = self.swap(code, self.hud('chair.split_by("group")'))
        chair.clear_updaters()
        parts = chair.split_by("group")
        self.remove(chair)
        self.add(parts)
        self.play(
            *[p.animate.shift(0.18 * i * OUT + 0.11 * i * RIGHT)
              for i, p in enumerate(parts)],
            run_time=2.2,
        )
        self.wait(1.8)
        self.play(
            *[p.animate.shift(-0.18 * i * OUT - 0.11 * i * RIGHT)
              for i, p in enumerate(parts)],
            run_time=1.8,
        )
        self.remove(parts)
        self.add(chair)
        self.spin(chair, speed=-0.4)

        # ---- 7. and the same call works on either -----------------------------
        code = self.swap(code, self.hud("model.point_cloud(6000)"))
        globe.clear_updaters()
        chair.clear_updaters()
        # A point cloud is one colour per point anyway, so sampling the
        # texture per vertex is exactly right here. set_points lines the
        # copy up with wherever the globe has drifted to.
        ghost = earth.copy().set_texture_colors(
            earth.mesh.texture_path("diffuse"), brighten=1.15)
        ghost.set_points(globe.get_points())
        clouds = Group(ghost.point_cloud(6000, radius=0.028),
                       chair.point_cloud(6000, radius=0.028))
        self.play(FadeOut(globe), FadeOut(chair), FadeIn(clouds), run_time=1.6)
        self.wait(2.0)

        # ---- 8. outro ----------------------------------------------------------
        outro = VGroup(
            Text("same one line, any .obj", font_size=38, color=INK),
            Text('OBJMobject("earth.obj", height=3.9)', font=MONO,
                 font_size=21, color=GOLD),
            Text('OBJMobject("chair.obj", height=3.4)', font=MONO,
                 font_size=21, color=GOLD),
        ).arrange(DOWN, buff=0.24).fix_in_frame().to_edge(DOWN, buff=0.5)

        self.play(FadeOut(code), FadeOut(name), FadeOut(name2), run_time=0.5)
        self.play(FadeIn(outro, shift=0.2 * UP), run_time=0.9)
        self.wait(2.2)
        self.play(FadeOut(outro), FadeOut(clouds), run_time=1.2)
