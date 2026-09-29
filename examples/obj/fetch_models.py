#!/usr/bin/env python3
"""
Download the demo building model into ~/models/building.obj.

    python3 tools/get_building.py            # fetch (skips if already there)
    python3 tools/get_building.py --force    # fetch again
    python3 tools/get_building.py --list     # what else is on offer

Model: Engel House (Ze'ev Rechter, 1933), Tel Aviv -- a Bauhaus landmark, the
first building in Israel raised on pilotis. From the ladybug-tools/3d-models
collection of AEC reference models.

The file is a Rhino export: z-up, a mix of triangles and quads, backslash
continued face lines, 6 named materials and 1,254 object groups -- a good
stress test for the loader rather than a tidy little cube.
"""

from __future__ import annotations

import argparse
import sys

from manimgl_myplugin import load_mesh
from manimgl_myplugin.obj.loader import MODELS_DIR, fetch_model

BASE = "https://raw.githubusercontent.com/ladybug-tools/3d-models/master/obj"

CATALOGUE = {
    "building": (f"{BASE}/engel-house/AngelHouse_Bauhaus-in-Israel.obj",
                 "building.obj",
                 "Engel House, Tel Aviv -- Bauhaus, 15k triangles, 6 materials"),
    "urban":    (f"{BASE}/urban_model_001/model.obj", "urban.obj",
                 "A small urban block, 11 objects"),
    "villa":    (f"{BASE}/seaside-villa-obj/seaside-villa.obj", "villa.obj",
                 "Seaside villa, ~6 MB, comes with a real .mtl"),
    "tree":     (f"{BASE}/tree.obj", "tree.obj", "A tree, nice for scenery"),
    "duck":     (f"{BASE}/Duck1.obj", "duck.obj", "The classic rubber duck"),
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?", default="building", choices=list(CATALOGUE))
    ap.add_argument("--force", action="store_true", help="re-download")
    ap.add_argument("--list", action="store_true", help="show the catalogue")
    args = ap.parse_args(argv)

    if args.list:
        print(f"Models are saved in {MODELS_DIR}\n")
        for key, (_, filename, blurb) in CATALOGUE.items():
            mark = "yes" if (MODELS_DIR / filename).exists() else " - "
            print(f"  [{mark}] {key:9} {filename:14} {blurb}")
        return 0

    url, filename, blurb = CATALOGUE[args.name]
    print(f"{args.name}: {blurb}")
    path = fetch_model(url, filename, force=args.force, quiet=False)

    mesh = load_mesh(path)
    print()
    print(mesh.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
