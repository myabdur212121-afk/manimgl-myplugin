# `manim_obj` — .obj models in ManimGL

`OBJMobject` লোড করে যেকোনো Wavefront `.obj` মডেল, সরাসরি ManimGL সিনে।

```python
from manimlib import *
from manim_obj import OBJMobject

class Demo(ThreeDScene):
    def construct(self):
        model = OBJMobject("building.obj", height=4, up_axis="z")
        self.add(model)
```

- **ফাইল:** `~/src/manim_obj/` (`loader.py`, `obj_mobject.py`, `__init__.py`)
- **ইম্পোর্ট পাথ:** `site-packages/manim_obj.pth` → `/home/user/src`
- **ভার্সন:** 1.0.0 · ManimGL 1.7.2-এ পরীক্ষিত

---

## ১. কীভাবে কাজ করে

ManimGL-এর `surface.wgsl` শেডারে একটা ফিচার আছে: `resolution` uniform যদি `(0, 0)` হয়, তাহলে ও পয়েন্টগুলোকে **grid হিসেবে না পড়ে, ত্রিভুজের তালিকা হিসেবে** পড়ে — প্রতি ৩টা রেকর্ড = ১টা ত্রিভুজ।

`OBJMobject` হলো ঠিক সেই কনফিগারেশনের একটা `Surface`:

```python
class OBJMobject(Surface):
    verts_per_record = 1          # প্রতি রেকর্ড = ১টা vertex
    # __init__ এ: resolution=(0, 0)
```

তাই এটা **আসল Surface** — GPU lighting, depth test, camera-ordered transparency, আর `shift` / `rotate` / `set_color` / `Transform` / `FadeIn` সবকিছু কোনো বাড়তি কাজ ছাড়াই চলে।

> **নোট:** এই মোডে শেডার প্রতি ত্রিভুজের normal winding থেকে হিসাব করে, অর্থাৎ **flat shading**। মসৃণ শেডিং চাইলে `.shade_smooth()` — সেটা CPU-তে vertex normal থেকে আলো বেক করে দেয় (নিচে §6)।

---

## ২. মডেল কোথা থেকে আসতে পারে

`source` হিসেবে যা যা দেওয়া যায়:

| কী দেবে | উদাহরণ |
|---|---|
| ফাইল পাথ | `OBJMobject("~/models/car.obj")` |
| শুধু নাম (খুঁজবে `~/models`-এ) | `OBJMobject("building.obj")` |
| **URL** (একবার ডাউনলোড, পরে ক্যাশ) | `OBJMobject("https://site.com/teapot.obj")` |
| কাঁচা OBJ টেক্সট | `OBJMobject("v 0 0 0\nv 1 0 0\n...")` |
| আগেই লোড করা `MeshData` | `OBJMobject(mesh)` |
| `.stl` / `.ply` / `.glb` | trimesh fallback দিয়ে |

```python
# নিজে ডাউনলোড করতে চাইলে
from manim_obj import fetch_model
path = fetch_model("https://.../model.obj", "car.obj")   # .mtl-ও সাথে আনে
```

পার্স করা মেশ `~/.cache/manim_obj/`-এ pickle হয়ে থাকে, তাই দ্বিতীয়বার লোড তাৎক্ষণিক।

---

## ৩. প্যারামিটার

```python
OBJMobject(
    source,
    height=4,              # z-বিস্তার  (width=x, depth=y, scale=গুণক)
    up_axis="y",           # "y" | "z" | "x" | "auto" | None
    center=True,
    color=BLUE_D,
    opacity=1.0,
    color_by="material",   # নিচে §5
    palette=[...],
    gradient=[...],
    use_mtl=True,          # .mtl থেকে Kd রং আর d স্বচ্ছতা
    smooth=False,          # Gouraud শেডিং বেক করবে কিনা
    shading=(0.25, 0.3, 0.4),
    flip_faces=False,      # winding উল্টে দেয় (মডেল উল্টো দেখালে)
    face_filter=fn,        # fn(center, normal, i) -> bool
    vertex_func=fn,        # fn(points) -> points   (bend/twist/noise)
    depth_test=True,
    cache=True,
)
```

### ⚠️ `height` এখানে মানে **উচ্চতা** (z), manim-এর y নয়

Manim-এ `set_height()` আসলে **y-অক্ষ** মাপে — 2D-র জন্য ঠিক, কিন্তু 3D মডেলের জন্য বিভ্রান্তিকর। `OBJMobject` তাই নিজের মতো করে:

| প্যারামিটার | কোন অক্ষ |
|---|---|
| `height` | **z** — মডেল কত লম্বা |
| `width` | x |
| `depth` | y |

### `up_axis` — কোন দিক উপরে

OBJ স্পেকে Y-up, কিন্তু CAD (Rhino, Revit, SketchUp) সাধারণত Z-up। ভুল দিলে মডেল কাত হয়ে শুয়ে থাকবে।

- `"y"` — ডিফল্ট, সাধারণ OBJ / Blender / গেম মডেল
- `"z"` — CAD এক্সপোর্ট (আমাদের building.obj এটাই)
- `"auto"` — সবচেয়ে ছোট বিস্তারের অক্ষকে উপর ধরে (বিল্ডিং/টেরেইনে কাজে দেয়, চরিত্রে নয়)
- `None` — কিছুই বদলাবে না

---

## ৪. জেনে নেওয়া

```python
print(model.info())          # সব একসাথে, পড়ার মতো করে
model.num_faces              # 15024
model.num_vertices           # 14181
model.parts("material")      # {'Default': 12174, 'Translucent_Glass_Gray': 301, ...}
model.parts("group")         # 1254 টা গ্রুপ
model.face_centers()         # (F, 3) সিন-স্থানাঙ্কে
model.face_normals()         # (F, 3)
model.transformed_vertices() # (V, 3) — ফাইলের প্রতিটা vertex এখন কোথায়
model.mesh                   # কাঁচা MeshData, চাইলে numpy-তে কাজ করো
```

---

## ৫. রং

| কল | ফল |
|---|---|
| `set_color_by("material")` | প্রতি material-এ আলাদা প্যালেট রং |
| `set_color_by("group")` / `("object")` | একইভাবে group / object ধরে |
| `set_color_by("z")` | উচ্চতা বরাবর gradient (`"x"`, `"y"`-ও চলে) |
| `set_color_by("normal")` | মুখ যেদিকে তাকিয়ে সেই দিক থেকে রং |
| `set_color_by("random")` | প্রতি ত্রিভুজে এলোমেলো রং |
| `set_color_by("mtl")` | `.mtl` ফাইলের Kd / d |
| `set_color_by(fn)` | `fn(center, normal, i) -> color` |
| `set_part_color("glass", BLUE_A, opacity=0.4)` | শুধু নাম মিলে যাওয়া অংশ |
| `set_face_colors(rgb_array)` | সরাসরি `(F, 3)` numpy অ্যারে |
| `set_texture_colors("earth.jpg")` | `vt` ধরে টেক্সচার থেকে রং (প্রতি ভার্টেক্সে) |
| `textured()` | **আসল texture mapping** — ছবির নাম `.mtl` থেকে নিজেই নেয় |

```python
# নাম দিয়ে খোঁজা substring, case-insensitive; regex=True দিলে regex
model.set_part_color("glass", "#8FE8FF", opacity=0.75)
model.set_part_color(r"^Color_\d+$", RED, regex=True)

# ফাংশন দিয়ে: ছাদ আলাদা রং
model.set_color_by(lambda c, n, i: GOLD if n[2] > 0.95 else GREY_C)
```

### Legend

`color_by_part` কোন নামে কোন রং দিয়েছে সেটা `model.part_colors`-এ থাকে, আর সেটা থেকেই key বানানো যায় — তাই ছবি আর legend কখনো আলাদা হয়ে যাবে না:

```python
legend = model.legend(font_size=16)
legend.fix_in_frame().to_corner(UR)
```

---

### ৫ক. টেক্সচার থেকে রং

`.obj`-তে `vt` লাইন থাকলে তার নিজের টেক্সচার ম্যাপ থেকেই রং তুলে আনা যায়:

```python
earth = OBJMobject("earth.obj", height=3.9)
earth.set_texture_colors("earth_texture.jpg", brighten=1.15)
```

এটা **আসল texture mapping নয়**। ManimGL সারফেসে রং বসে **ভার্টেক্সে**, তাই সর্বোচ্চ
যা করা যায় — প্রতি ভার্টেক্সে একবার ছবি থেকে রং তুলে মাঝেরটা GPU-কে interpolate করতে
দেওয়া। পিক্সেলপ্রতি lookup হয় না।

| `per=` | কী করে | চেহারা |
| --- | --- | --- |
| `"corner"` (ডিফল্ট) | ত্রিভুজের তিন কোণার UV-তে আলাদা স্যাম্পল | মসৃণ, রং ছড়িয়ে যায় |
| `"face"` | পুরো ত্রিভুজে একটাই রং | ইচ্ছাকৃত low-poly, চৌকো |

`samples=` শুধু `per="face"`-এ খাটে (ত্রিভুজের ভেতরে কয়টা বিন্দুর গড়)। `brighten=`
ফলটা উজ্জ্বল করে। URL দিলে একবার ডাউনলোড করে ক্যাশ করে। Pillow লাগে। `vt` না থাকলে
`ValueError` দেয় — যেমন `chair.obj`।

### ৫খ. `.obj`-তে রং থাকে না — আর আসল টেক্সচার কীভাবে বসাবে

**`.obj` ফাইলে পৃষ্ঠের রং থাকেই না।** ওতে শুধু জ্যামিতি: `v` (বিন্দু), `vt`
(টেক্সচার স্থানাঙ্ক), `vn` (normal), `f` (মুখ)। রং থাকে তিন জায়গায়:

| কোথায় | কী | উদাহরণ |
| --- | --- | --- |
| `.mtl` ফাইল | material-প্রতি **একটা সমতল রং** | `Kd 1.0 1.0 1.0` |
| `.mtl` ফাইল | ছবির ফাইলের **নাম** (ছবি নয়) | `map_Kd 4096_earth.jpg` |
| আলাদা `.jpg`/`.png` | আসল পৃষ্ঠের বিস্তারিত | আলাদা করে নামাতে হয় |

তাই `earth.obj`-এর `.mtl`-এ লেখা আছে `Kd 1.0 1.0 1.0` — সাদা। মহাদেশগুলো
`4096_earth.jpg`-এ, আর সেই ছবিটা `.obj` নিজের ভেতরে রাখে না, শুধু নাম উল্লেখ করে।
`chair.obj`-এ তো `.mtl`-ই নেই, তাই তার কোনো রং নেই — প্যালেট থেকে আমরা দিই।

**পরিষ্কার ও মসৃণ চাইলে `textured()`:**

```python
earth = OBJMobject("earth.obj", height=3.9).textured()   # নাম বলতে হয় না
self.add(earth)
```

`.mtl`-এর `map_Kd` লাইন পড়ে ছবিটা `.obj`-র পাশে বা `~/models`-এ খোঁজে। `map_Ke`
(glow map) থাকলে সেটাও তুলে নেয় — পৃথিবীর অন্ধকার দিকে **শহরের আলো জ্বলে ওঠে**।

| | কীভাবে | চেহারা |
| --- | --- | --- |
| `set_texture_colors()` | ১,৯৮৬ ভার্টেক্সে ছবি থেকে রং তুলে GPU-কে মাঝেরটা মেলাতে দেয় | ছবিটা ৬৪×৩২-এ নেমে আসে — **ঘোলা** |
| `textured()` | ছবিটা GPU-তে পাঠায়, শেডার প্রতি পিক্সেলে `textureSample` করে | **তীক্ষ্ণ**, যত কাছেই যাও |

ম্যানিমের নিজের `TexturedSurface` শেডার ব্যবহার করে, শুধু প্যারামেট্রিক গ্রিডের বদলে
`.obj`-র ত্রিভুজের তালিকা আর তার `vt` স্থানাঙ্ক খাওয়ানো হয়।

**সীমা:** `textured()`-এ আলোছায়া ত্রিভুজপ্রতি সমতল — `shade_smooth()` আর খাটে না,
কারণ শেডার রং নেয় ছবি থেকে, ভার্টেক্স থেকে নয়। সমান আলো চাইলে
`textured(img, shading=(0, 0, 0))`। `dark_image=` দিয়ে অন্ধকার দিকের জন্য আলাদা ছবি
দেওয়া যায় (যেমন রাতের শহরের আলো)।

তুলনা: `videos/06_earth_chair/texture_sharpness.png`

### কেন `OBJMobject` প্রথমে `Sphere()`-এর মতো মসৃণ নয়

| | ত্রিভুজ | normal | ফল |
| --- | --- | --- | --- |
| `manimlib.Sphere()` | ১০,০০০ (resolution `(101,51)`) | প্যারামেট্রিক সূত্র থেকে `np.gradient`, **প্রতি ভার্টেক্সে** | মসৃণ |
| `OBJMobject("earth.obj")` | ৩,৯৬৮ | ত্রিভুজের তালিকা, **প্রতি ফেসে** একটা | খাঁজকাটা |

`Sphere` একটা সমীকরণ, তাই যেকোনো বিন্দুতে সঠিক normal বের করা যায়। `.obj` শুধু
ত্রিভুজের স্তূপ — সেখান থেকে ঘেঁষা ভার্টেক্স normal বানাতে হয়, আর সেটাই করে
`.shade_smooth()` (বা `OBJMobject(..., smooth=True)`)। তারপর দুটো আর আলাদা করা যায় না।
শুধু **সিলুয়েটটা** ৬৪-বাহুর বহুভুজই থেকে যায় — ওটা জ্যামিতি, বেশি ত্রিভুজ ছাড়া ঠিক হয় না।

তুলনা: `videos/06_earth_chair/sphere_vs_obj.png`

## ৬. শেডিং

```python
model.shade_smooth()   # vertex normal থেকে Gouraud আলো বেক করে, GPU শেডিং বন্ধ
model.shade_flat()     # আবার GPU-র flat per-face শেডিং (ডিফল্ট)
model.set_shading(0.4, 0.2, 0.5)   # reflectiveness, gloss, shadow
```

`shade_smooth()` গোলাকার মডেলে (মূর্তি, গাড়ি, প্রাণী) faceted ভাব দূর করে। সমতল দেয়ালের বিল্ডিংয়ে flat-ই ভালো দেখায়।

---

## ৭. মডেল কেটে ভাগ করা

```python
windows = model.get_part("glass")              # নাম দিয়ে একটা অংশ
group   = model.split_by("material")           # OBJGroup — প্রতি material একটা
group["glass"].set_color(CYAN)
group.explode(0.6)                             # exploded view
group.set_part_colors({"glass": BLUE_A, "Color_000": GOLD})

floor1  = model.slice("z", low=-1.0, high=0.2) # কাটাকুটি (cutaway)
roof    = model.filter_faces(lambda c, n, i: n[2] > 0.9)
```

প্রতিটা ফেরত আসে **নতুন `OBJMobject`** হিসেবে, ঠিক যেখানে ছিল সেখানেই, আগের রং নিয়ে — তাই সরাসরি `self.play(part.animate.shift(UP))` করা যায়।

---

## ৮. মডেল থেকে বানানো অন্য mobject

```python
wires = model.wireframe(color=GOLD, feature_angle=30)   # crease edges, একটাই VMobject
self.play(ShowCreation(wires))

box   = model.bounding_box_mobject(color=GREY_B)
cloud = model.point_cloud(9000, radius=0.033)           # পৃষ্ঠজুড়ে ছড়ানো বিন্দু
```

`feature_angle` — শুধু সেই edge রাখে যেখানে দুই ফেসের কোণ এর চেয়ে বেশি, সাথে খোলা প্রান্ত। বিল্ডিংয়ে এটা কেবল রূপরেখা আঁকে, সমতল দেয়ালের ভেতরের triangulation-এর জঞ্জাল বাদ দেয়। `feature_angle=0` দিলে সব edge।

---

## ৯. অ্যানিমেশন

```python
from manim_obj import BuildMesh

self.play(BuildMesh(model, order="z", spread=0.75, run_time=5))
```

প্রতিটা ত্রিভুজ নিজের কেন্দ্র থেকে ফুটে ওঠে, নিচ থেকে উপরের দিকে।
`order`: `"z"`, `"-z"`, `"x"`, `"y"`, `"random"`, `"radial"`, বা নিজের `(F,)` অ্যারে।
`spread`: ০ = সবাই একসাথে, ১ = ধীর ঝাড়ু।

সাধারণ manim অ্যানিমেশনও সব চলে — `FadeIn`, `GrowFromCenter`, `Transform`, `Rotate`, `.animate`।

রং বদল মসৃণভাবে দেখাতে:

```python
target = model.copy().set_color_by("material")
self.play(Transform(model, target), run_time=1.5)
```

---

## ১০. এই প্রজেক্টে ব্যবহৃত মডেল

**Engel House** (Ze'ev Rechter, ১৯৩৩), তেল আবিব — Bauhaus স্থাপত্যের নিদর্শন, ইসরায়েলের প্রথম pilotis-এর উপর দাঁড়ানো ভবন।

```bash
python3 tools/get_building.py          # ~/models/building.obj
python3 tools/get_building.py --list   # আরও মডেল (urban, villa, tree, duck)
```

উৎস: [ladybug-tools/3d-models](https://github.com/ladybug-tools/3d-models)

ফাইলটা সহজ নয়, বরং লোডারের ভালো পরীক্ষা:

| বৈশিষ্ট্য | মান |
|---|---|
| Vertices | 14,181 |
| ত্রিভুজ (triangulate করার পর) | **15,024** |
| ফেস টাইপ | 5,172 ত্রিভুজ + 4,926 চতুর্ভুজ (fan triangulation) |
| Material | 6 (`Translucent_Glass_Gray` সহ) |
| Group | 1,254 |
| অক্ষ | **Z-up** (Rhino এক্সপোর্ট) |
| বিশেষ ফাঁদ | `f` লাইনে **backslash continuation** |
| বিশেষ ফাঁদ ২ | **৭,০৮৬ ত্রিভুজ (৪৭%) হুবহু আরেকটার উপরে বসানো** — `dedupe` চালু থাকলে বাদ যায়, বাকি থাকে **৭,৯৩৮** |

> ঐ শেষ পয়েন্টটা আসল বাগ ধরিয়ে দিয়েছিল: প্রথম পার্সার লাইন ধরে ধরে পড়ত, ফলে `\` দিয়ে ভাঙা ফেসের লেজের কোণাগুলো হারিয়ে যেত — ১৫,০২৪-এর জায়গায় ১১,৩৪৬ ত্রিভুজ আসছিল। `_logical_lines()` এখন আগে লাইন জোড়া লাগায়।

---

### আরও দুটো টেস্ট মডেল

| ফাইল | উৎস | ত্রিভুজ | কী পরীক্ষা করে |
| --- | --- | --- | --- |
| `earth.obj` | AudranDoublet/opr (3ds Max) | 3,968 | UV sphere · `vt` টেক্সচার · smooth vs flat shading |
| `chair.obj` | cnr-isti-vclab/meshlab (LightWave) | 6,716 | `vn`/`vt` **ছাড়া** ফাইল · ৪ material · ৯ group |
| `terrain.obj` | ericstoneking/42 | 3,042 | **Z-up** ভূখণ্ড · z-gradient রঙের ভিত্তি |
| `tree_a.obj` | Renumics/spotlight | 876 | low-poly পাইন · `decimate` করে বহুবার বসানো |
| `tree_b.obj` | redcamel/RedGL2 | 760 | পাতাহীন গাছ · সরু ডালে decimate-এর সীমা |
| `mountain.obj` | ZeusYang/TinySoftRenderer | 6,962 | **Y-up** পাহাড়শ্রেণি · `subdivide(1)` → 27,848 |
| `palm.obj` | CaptainProton42 | 1,246 | তালগাছ |
| `house.obj` | RobLoach/node-raylib | 1,792 | কুটির · দ্বিতীয় দালান |
| `armchair.obj` | code-iai/iai_maps | 2,832 | কৌণিক collision মেশ · `subdivide(1)` → 11,328 |

দুটোই **Y-up**, অর্থাৎ OBJ-র স্বাভাবিক নিয়ম — `up_axis` দিতে হয় না। চেয়ারেও
**১৭৭টা coincident ডুপ্লিকেট ফেস** পাওয়া গেছে, তাই সমস্যাটা শুধু building মডেলের ছিল না।
ডেমো: `demos/06_earth_chair.py` → `videos/06_earth_chair/EarthAndChair.mp4`

## ১০ক. একই সারফেস দুবার (z-fighting)

CAD থেকে এক্সপোর্ট করা মডেলে খুব পরিচিত সমস্যা: একই দেয়াল দুইবার লেখা থাকে —
একবার সাধারণ layer-এ, একবার ফিনিশ layer-এ, **হুবহু একই স্থানাঙ্কে**। দুটোই আঁকা
হয়, GPU-র depth test কোনটা সামনে ঠিক করতে পারে না, তাই পিক্সেল ধরে ধরে দুই রং
লড়াই করে — দেয়ালে দাঁতের মতো zigzag দেখায়।

Engel House মডেলে ঠিক এটাই ছিল: **৭,০০০-এর বেশি জোড়া** ত্রিভুজ একই সমতলে একটার
উপর আরেকটা, তাদের মধ্যে ব্যবধান সর্বোচ্চ **0.0049 ইউনিট** (মডেলটা 44.65 ইউনিট
চওড়া) — অর্থাৎ কার্যত শূন্য। মোট পৃষ্ঠক্ষেত্র ছিল ঠিক দ্বিগুণ।

**দুই চেহারার সমস্যা।** যমজ দুটোর material ভিন্ন হলে দুই *রং* লড়াই করে — লাল/ধূসর
zigzag। material এক হলে রং এক, কিন্তু যমজ দুটো সাধারণত **উল্টো winding**-এ লেখা,
তাই একটার normal বাইরে আরেকটার ভেতরে তাকায় — একটা আলোকিত, একটা অন্ধকার, আর
দেখা যায় দুই শেডের **দাবার ছক**। দ্বিতীয়টা ছাদ আর স্ল্যাবের কিনারায় বেশি চোখে
পড়ত। দুটোই এখন সারানো।

**যা কাজ করেনি:** vertex weld। যমজ সারফেস দুটো *ভিন্ন কর্ণ বরাবর* triangulate করা,
তাই ত্রিভুজগুলো হুবহু এক নয় — 1e-4 থেকে 0.1 পর্যন্ত tolerance ঘুরিয়েও মোটে 20–153টা
ধরা পড়ে।

**যা কাজ করেছে:** জ্যামিতিক overlap টেস্ট। ফেসগুলোকে যে সমতলে আছে সেই অনুযায়ী
bucket করা হয়, সমতলের ভেতরে 2D grid hash দিয়ে প্রার্থী জোড়া বের করা হয়, তারপর
প্রতি ত্রিভুজের ৪টা নমুনা বিন্দু অন্যটার ভেতরে পড়ে কি না দেখা হয় — পুরো মডেলে
**~১ সেকেন্ড**।

```python
OBJMobject("building.obj")                      # dedupe="auto" — ডিফল্ট
OBJMobject("building.obj", dedupe=False)        # ফাইল যেমন আছে তেমন
OBJMobject("building.obj", dedupe="common")     # বড় material-টা টিকবে
OBJMobject("building.obj", dedupe=["glass", "Color_000"])   # নিজের অগ্রাধিকার

mesh, n = load_mesh("building.obj").dedupe_coincident(report=True)
pairs = load_mesh("building.obj").coincident_pairs()        # শুধু নির্ণয়
```

**কে টিকবে:**

| অবস্থা | বিজয়ী | কেন |
| --- | --- | --- |
| ভিন্ন material | ডিফল্ট `"rare"` — যে material-এ ফেস কম | সেটাই বেশি নির্দিষ্ট (কাচ, রঙিন ফিনিশ); সাধারণ `Default` স্তরটা বাদ যায় |
| একই material, ভিন্ন আকার | **বড়টা** | ছোট ডিটেইল দেয়ালের গায়ে লেপ্টে থাকলে বড়টা সরালে **ফুটো** হয়ে যেত |
| একই material, সমান আকার | **বাইরের দিকে মুখ করা** | টিকে থাকা মুখটা যেন আলোকিত দিকটা হয় |

প্রথম রান ~৫ সেকেন্ড, তারপর ফল ক্যাশ হয় — পরের লোডে **০.০১ সেকেন্ড**।
যাচাই: dedupe-র পর আবার `coincident_pairs()` চালালে **০** পাওয়া যায়।

before / after: `videos/05_obj/dedupe_before_after.png`

## ১০খ. রেজুলেশন — কমানো ও বাড়ানো

তিনটে মেথড, `MeshData`-তেও আছে, `OBJMobject`-এর কনস্ট্রাক্টরেও।

### `decimate(target)` — ত্রিভুজ কমানো

```python
OBJMobject("chair.obj", height=3, decimate=1500)   # ৬,৭১৬ → ১,৫০০
load_mesh("chair.obj").decimate(0.25)              # ২৫% রাখো
```

**Quadric edge collapse** — প্রতিটা বাহুর জন্য হিসাব হয় "দুই প্রান্ত মিলিয়ে দিলে
পৃষ্ঠ কতটা সরবে", তারপর সবচেয়ে সস্তাটা আগে ভাঙা হয়। সমতল জায়গা আগে খালি হয়,
ধারালো কোণা টেকে।

| চেয়ারে | দেখতে |
| --- | --- |
| ৬,৭১৬ → ৩,০০০ | পার্থক্য চোখে পড়ে না |
| → ১,৫০০ | গদির বাঁক সামান্য কৌণিক |
| → ৫০০ | স্পষ্ট low-poly, তবু চেয়ার |

`transfer=True` (ডিফল্ট) নিকটতম পুরোনো ত্রিভুজ/বিন্দু থেকে material ও UV টেনে আনে —
**আনুমানিক**, decimation সত্যিকারের মিল নষ্ট করে দেয়, তাই টেক্সচার একটু পিছলাতে পারে।

⚙️ backend: `fast-simplification` (২৮৪ KB), `restore_env.sh`-এ যোগ করা আছে।

### `subdivide(level, smooth=True)` — ত্রিভুজ বাড়ানো

```python
OBJMobject("earth.obj", height=4, subdivide=2)     # ৩,৯৬৮ → ৬৩,৪৮৮
```

| স্তর | ত্রিভুজ | সময় |
| --- | --- | --- |
| ১ | ১৫,৮৭২ | ০.০৩ সে |
| ২ | ৬৩,৪৮৮ | ০.১৬ সে |

- **`smooth=True`** (ডিফল্ট) — Loop subdivision। নতুন বিন্দু `⅜(A+B) + ⅛(C+D)`,
  পুরোনো বিন্দুও প্রতিবেশীদের দিকে সরে। **সিলুয়েট সত্যিই গোল হয়**।
- **`smooth=False`** — মাঝবিন্দু ঠিক বাহুর উপরে। সংখ্যা বাড়ে, **আকৃতি অপরিবর্তিত**।
  একমাত্র কাজ: `displace()`-এর জন্য বিন্দু জোগানো।

⚠️ **দালানে `smooth=True` দিও না** — ধারালো কোণা গলে যাবে।

`vt`/normal নিজেদের সূচক ধরে আলাদাভাবে ভাঙা হয়, তাই **UV seam টিকে থাকে**।

### `displace(image, strength=...)` — ছবি থেকে ভূমিরূপ

```python
OBJMobject("earth.obj", height=3.4,
           subdivide=2, displace=True, displace_strength=0.05)
```

প্রতিটা বিন্দু তার `vt` স্থানাঙ্কে height map-এর উজ্জ্বলতা পড়ে, তারপর নিজের normal
বরাবর সরে। ফল আঁকা ছায়া নয় — **সত্যিকারের জ্যামিতি**, সিলুয়েটেও দেখা যায়।

পৃথিবীতে মাপা ফল: ব্যাসার্ধের পরিসর **০.৫৭ → ২৮.২৬ ইউনিট**।

- `displace=True` হলে `.mtl`-এর `map_bump` নিজেই খুঁজে নেয়
- `strength` মডেলের সবচেয়ে বড় মাপের ভগ্নাংশ (`absolute=True` দিলে ফাইলের একক)
- `middle=0.5` কোন ধূসরটা "কোনো পরিবর্তন নয়", `invert=True` উল্টো ম্যাপের জন্য

⚠️ **আগে `subdivide`, পরে `displace`** — নইলে নাড়ানোর মতো বিন্দুই নেই।

সৎ কথা: আসল পৃথিবীতে এভারেস্ট ব্যাসার্ধের ০.১৪%, তাই বাস্তব মাপে অদৃশ্য। ডেমোতে
বাড়িয়ে দেখানো হয়েছে।

### সবচেয়ে কাজের জুটি

```python
OBJMobject("heavy.obj", height=4, decimate=20_000).textured()
```

বিস্তারিতটা জ্যামিতিতে নয়, **ছবিতে** থাকে — দেখতে প্রায় একই, চলে অনেক হালকা।
গেম ইন্ডাস্ট্রি ঠিক এটাই করে। `textured()` যেহেতু প্রতি পিক্সেলে ছবি পড়ে, ত্রিভুজ
কমলেও রং ঝকঝকে থাকে।

ডেমো: `demos/08_resolution.py` → `videos/08_resolution/Resolution.mp4`

## ১০গ. পূর্ণ দৃশ্য — চলমান ক্যামেরা ও আলো

`demos/09_landscape.py` — **ছয়টা মডেল একসাথে**, ৭২ সেকেন্ড।

### চলমান আলো

ManimGL-এ পুরো দৃশ্যের জন্য **একটাই আলোর উৎস**, আর সেটা একটা সাধারণ `Point`:

```python
sun = self.camera.light_source          # Point, ডিফল্ট [-10, 10, 10]
self.play(sun.animate.move_to(np.array([14, 6, 5])), run_time=3)
```

প্রতি ফ্রেমে ওর অবস্থান শেডারে `light_position` হিসেবে যায়, তাই নাড়ালেই **সব মডেল
একসাথে নতুন করে আলোকিত হয়**। কতটা সাড়া দেবে সেটা প্রতিটা মডেলের `shading` টাপল
ঠিক করে — ভূখণ্ডে `(0.1, …)` দিয়ে শুরু করেছিলাম, প্রায় কিছুই বদলাত না;
`(0.32, 0.22, 0.55)` করার পর সূর্যের গতি স্পষ্ট বোঝা যায়।

### চলমান ক্যামেরা

```python
frame = self.camera.frame
frame.reorient(-28, 88, 0, (0, 0, 0.4), 11.0)        # theta, phi, gamma, কেন্দ্র, উচ্চতা
self.play(frame.animate.reorient(18, 68, 0, (0.5, 0, 0.9), 12.0), run_time=3.4)
```

### মডেলকে ভূমির উপর বসানো

ভূখণ্ড সমতল নয়, তাই গাছ-দালান কোথায় বসবে তা হিসাব করতে হয়:

```python
def ground_at(self, x, y):
    pts = self.land.get_points()
    flat = pts[:, :2] - np.array([x, y])
    return float(pts[np.argmin((flat ** 2).sum(axis=1)), 2])

tree.move_to(np.array([x, y, self.ground_at(x, y)]))
tree.shift(tree.get_shape()[2] / 2 * OUT)      # পা মাটিতে, কেন্দ্র নয়
```

### যা যা একসাথে পরীক্ষা হয়

| | |
| --- | --- |
| লোড | `up_axis` z ও y, `height`/`width`, `dedupe`, `decimate` |
| রং | material, z-gradient, `set_part_color`, `legend()`, `textured()` |
| জ্যামিতি | `split_by`, `wireframe`, `point_cloud` |
| অ্যানিমেশন | `BuildMesh`, `Transform`, `LaggedStart`, updater |
| দৃশ্য | ক্যামেরার উড়াল, **আলোর উৎসের গতি** |

**যে ফাঁদে পড়েছিলাম:** দূর থেকে point cloud প্রায় অদৃশ্য ছিল — `radius` দৃশ্যের
মাপের সাথে মিলিয়ে নিতে হয় (০.০১৬ → ০.০৩৮), আর গাঢ় রঙের মডেল আগে উজ্জ্বল করে
নিতে হয়।

ভিডিও: `videos/09_landscape/Landscape.mp4`

## ১০ঘ. Highland — আটটা মডেল, QHD

`demos/10_highland.py` → `videos/10_highland/Highland.mp4` · **2560×1440, ৮৯.৫ সে**

### পাহাড়ের গায়ে জিনিস বসানো

সমতল ভূমিতে `ground_at()` যথেষ্ট, কিন্তু পাহাড়ে দুটো সমস্যা হয়:

**১. ঢালে বসলে দালান কাত হয়ে ঢুকে যায়।** সমাধান — কাছাকাছি **সবচেয়ে সমতল**
জায়গাটা নিজে খুঁজে নেওয়া:

```python
def flat_spot(self, x, y, search=1.4, step=0.35, patch=1.1):
    best, best_score = (x, y), np.inf
    for dx in np.arange(-search, search, step):
        for dy in np.arange(-search, search, step):
            near = pts[দূরত্ব < patch]
            score = near[:, 2].std() + 0.10 * np.hypot(dx, dy)  # সমতল, তবু কাছে
            ...
```

**২. নিকটতম বিন্দুর উচ্চতা নিলে অর্ধেক মাটিতে ডুবে যায়** — ঢালে নিকটতম বিন্দু
প্রায়ই নিচের দিকে পড়ে। সমাধান: পায়ের ছাপের নিচের **সর্বোচ্চ** উচ্চতা নেওয়া:

```python
under = pts[(দূরত্ব < footprint)]
z = under[:, 2].max()          # nearest নয়, max
```

`footprint` বস্তুভেদে আলাদা — দালানে ১.৯, চেয়ারে ০.৪৫।

⚠️ প্রথমে `search=2.6` দিয়েছিলাম, তাতে আর্মচেয়ার হেঁটে গিয়ে দালানের গায়ে বসে
পড়ত। ১.৪ করে আর দূরত্বের জরিমানা বাড়িয়ে ঠিক হয়েছে।

### ক্লোজ-আপে ক্যামেরা

হাতে লেখা স্থানাঙ্ক দিলে ভুল জিনিস ফ্রেমে আসে, কারণ `flat_spot` বস্তুকে সরিয়ে
দিয়েছে। বসানোর **পরে** আসল অবস্থান জিজ্ঞেস করো:

```python
seat = arm.get_center()
frame.animate.reorient(18, 78, 0, (seat[0], seat[1], seat[2]), 3.2)
```

### QHD রেন্ডার

```bash
manimgl demos/10_highland.py Highland -w -r 2560x1440 \
    -c "#05070E" --video_dir videos/10_highland
```

`-r WIDTHxHEIGHT` যেকোনো মাপ নেয় (`-l` 854×480, `-m` 1280×720, `--hd`, `--uhd`)।

| | |
| --- | --- |
| মোট ত্রিভুজ | ~৭০,০০০ (ভূখণ্ড 27,848 + পৃথিবী 63,488 আলাদা সময়ে) |
| রেন্ডার সময় | **~১৩ মিনিট** (2,684 ফ্রেম) |
| **সর্বোচ্চ মেমরি** | **১,৮০৪ MB / ১,৯৮৪ MB** — খালি ছিল মাত্র ৭৮ MB |

⚠️ **এই বাক্সে QHD-ই সীমা।** এর চেয়ে বেশি রেজুলেশন বা ত্রিভুজ দিলে OOM হবে।
4K চাইলে আগে ত্রিভুজ কমাতে হবে (`decimate`), বা পৃথিবীর `subdivide(2)` → `(1)`।

## ১১. রেন্ডার

```bash
# ডেমো, qm (720p30)
manimgl demos/05_obj_building.py BuildingDemo -w -m \
        -c "#070B14" --video_dir videos/05_obj

# -l 480p ড্রাফট · -m 720p · --hd 1080p · --uhd 4K
```

হেডলেস স্যান্ডবক্সে `-w` বাধ্যতামূলক (X11 নেই), আর ব্যাকগ্রাউন্ড `-c` ফ্ল্যাগ বা `--config_file` দিয়ে দিতে হয় — `construct()`-এর ভেতরে সেট করলে ManimGL-এ কাজ করে না।

---

## ১২. সমস্যা হলে

| উপসর্গ | কারণ | সমাধান |
|---|---|---|
| মডেল কাত হয়ে শুয়ে আছে | ভুল `up_axis` | `up_axis="z"` (বা `"y"`) |
| ভেতর-বাহির উল্টো, আলো অদ্ভুত | winding উল্টো | `flip_faces=True` |
| খাঁজকাটা, faceted | flat shading | `.shade_smooth()` |
| **দেয়ালে দাঁতের মতো দুই রঙের zigzag** | **z-fighting** — CAD এক্সপোর্টে একই দেয়াল দুই layer-এ দুবার লেখা | ডিফল্ট `dedupe="auto"` নিজেই সারায়; নিয়ম বদলাতে `dedupe="common"` বা material নামের তালিকা |
| দরকারি ফেস হারিয়ে গেছে | `dedupe` বেশি আগ্রাসী | `dedupe=False` দিয়ে ফাইল হুবহু লোড করো |
| `height` দিলে চ্যাপ্টা লাগে | তুমি y ভাবছ | `height` = z; y চাইলে `depth=` |
| রং বসছে না | `color_by` জিতে যাচ্ছে | `color_by=None`; `color=` এখন `.mtl`-কে হারায় |
| wireframe খুব ভারী | edge বেশি | `feature_angle` বাড়াও, `max_edges` কমাও |
| `FileNotFoundError` | `~/models`-এ নেই | পুরো পাথ বা URL দাও |
| রেন্ডার ধীর | 2 CPU / 1 GB | `-l` ড্রাফট, ব্যাকগ্রাউন্ড প্রসেস |

---

## ১৩. রিসেটের পর

Sandbox reset হলে apt/pip মুছে যায়, কিন্তু `/home/user` থাকে:

```bash
bash /home/user/tools/restore_env.sh
```

ManimCE + ManimGL + LaTeX + ফন্ট ফেরত আনে, **আর `manim_obj.pth`-ও আবার বসায়** — তাই `import manim_obj` সাথে সাথেই কাজ করবে।
