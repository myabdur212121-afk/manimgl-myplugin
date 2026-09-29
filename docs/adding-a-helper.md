# Adding a helper

Every helper is a subpackage that could stand on its own. Keeping them the
same shape is what makes the collection usable after ten of them exist.

## The shape

```
manimgl_myplugin/
└── <helper>/
    ├── __init__.py        what this helper exports, and nothing else
    └── …                  as many modules as it needs

docs/<helper>/
├── reference.md           every parameter and method — the specification
└── notes.md               bugs hit, causes, dead ends, expected numbers

examples/<helper>/         runnable scenes
tests/test_<helper>.py     checks that would have caught the bugs you hit
```

## Wiring it up

Add the helper and the names it contributes to `_HELPERS` in
`manimgl_myplugin/__init__.py`:

```python
_HELPERS = {
    "obj": ("OBJMobject", "load_mesh", ...),
    "<helper>": ("YourMobject", "your_function", ...),
}
```

They are then importable both ways, and imported only on first use:

```python
from manimgl_myplugin import YourMobject            # short
from manimgl_myplugin.<helper> import YourMobject   # explicit
```

**Keep the renderer-free part separate.** If some of your helper is plain
numpy — parsing, geometry, data wrangling — put it in its own module that
imports no manim. It stays testable without a GPU, and useful on its own.

Then add a row to the table in the root `README.md`.

## The two documents

**`reference.md`** — what it does. Every parameter, every method, with a
short runnable example for each group. This is where detail belongs; the
root README only names the helper and links here.

**`notes.md`** — what it cost. Six sections:

| § | contents |
| --- | --- |
| 1 | what this is, in five lines |
| 2 | problems faced: **symptom → cause → fix → the test that guards it** |
| 3 | directions that do not work, and why |
| 4 | numbers to expect — counts, timings, memory |
| 5 | what it will never do, and whether that is this code or the renderer |
| 6 | what to do first if you are picking it up |

§2 and §3 are the ones that pay for themselves. Write the symptom as
something a person would actually *see* — "walls speckled with two
colours", not "depth buffer precision issue". A symptom nobody can
recognise is not worth writing down.

§4 is how the next person knows something broke without reading any code.

## Tests

One file, `tests/test_<helper>.py`. It should run in seconds without
rendering anything, and every check should correspond to something that was
once broken, so a failure points straight at an entry in `notes.md`.

Follow the existing file: plain `python tests/test_obj.py` works, pytest
works too, and the checks that need ManimGL skip themselves when it is not
installed.

## Before you push

```bash
python tests/test_<helper>.py
manimgl examples/<helper>/<scene>.py <Scene> -w -l -c "#070B14" --video_dir /tmp/out
```

A draft render at `-l` is about six times faster than `-m` and shows every
mistake that matters except texture sharpness.

**Do not commit rendered video.** The scenes and any input assets are
enough to produce it again, and video makes the repository unusable within
a few projects.
