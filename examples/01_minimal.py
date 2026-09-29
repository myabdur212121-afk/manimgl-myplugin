"""
The smallest scenes worth writing -- what using manim_obj actually looks like.

Render any one of them:
    manimgl examples/01_minimal.py Simplest -w -l -c "#070B14" --video_dir /tmp/out
    manimgl examples/01_minimal.py Coloured -w -l -c "#070B14" --video_dir /tmp/out
    manimgl examples/01_minimal.py Textured -w -l -c "#070B14" --video_dir /tmp/out
    manimgl examples/01_minimal.py Animated -w -l -c "#070B14" --video_dir /tmp/out
"""

from manimlib import *

from manim_obj import OBJMobject, BuildMesh


class Simplest(ThreeDScene):
    """Two lines. A model on screen."""

    def construct(self):
        self.camera.frame.reorient(0, 70, 0)

        chair = OBJMobject("chair.obj", height=4)
        self.add(chair)
        self.wait(2)


class Coloured(ThreeDScene):
    """One colour per material in the file, with a key in the corner."""

    def construct(self):
        self.camera.frame.reorient(0, 70, 0)

        chair = OBJMobject("chair.obj", height=4)
        chair.set_color_by("material", palette=["#E9A13B", "#9FB4CC",
                                                "#6FD6C0", "#D96F6F"])
        legend = chair.legend()
        legend.fix_in_frame().to_corner(UR)      # pinned to the screen, not the world

        self.add(chair, legend)
        self.wait(2)


class Textured(ThreeDScene):
    """The model's own texture, looked up per pixel."""

    def construct(self):
        self.camera.frame.reorient(0, 74, 0)

        earth = OBJMobject("earth.obj", height=4)
        globe = earth.textured("/home/user/models/earth_texture.jpg")

        self.add(globe)
        self.wait(2)


class Animated(ThreeDScene):
    """Assemble it out of its own triangles, then keep it turning."""

    def construct(self):
        self.camera.frame.reorient(0, 70, 0)

        chair = OBJMobject("chair.obj", height=4)
        chair.set_color_by("z", gradient=["#17304C", "#3FA7D6", "#FFF2B8"])

        self.play(BuildMesh(chair, order="y", run_time=3))

        # An updater runs every frame, so the model spins while the scene
        # carries on doing whatever else it likes.
        chair.add_updater(lambda m, dt: m.rotate(0.5 * dt, OUT))
        self.wait(3)
