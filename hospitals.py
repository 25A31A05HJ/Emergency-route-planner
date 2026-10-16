"""Hospitals (from OpenStreetMap or demo data) stored in an AVL tree by specialty."""
from __future__ import annotations

import random
from dataclasses import dataclass

from avl_tree import AVLTree
from graph import haversine_m

MAX_SNAP_M = 500        # ignore hospitals farther than this from any mapped road
DEMO_SPECS = ["Cardiology", "Trauma", "Neurology", "Pediatrics", "Orthopedics", "Burns", "Obstetrics"]

SPEC_SYNONYMS = {
    "paediatrics": "Pediatrics", "paediatric": "Pediatrics", "pediatrics": "Pediatrics",
    "orthopaedics": "Orthopedics", "orthopedics": "Orthopedics",
    "gynaecology": "Obstetrics", "gynecology": "Obstetrics", "obstetrics": "Obstetrics",
    "emergency": "General Emergency", "general": "General Emergency",
}
NAME_KEYWORDS = {
    "Cardiology": ["heart", "cardi"],
    "Pediatrics": ["child", "pedia", "paedia", "kids"],
    "Neurology": ["neuro", "brain"],
    "Orthopedics": ["ortho", "bone", "joint"],
    "Obstetrics": ["maternity", "women", "gyn", "obstet", "matern"],
    "Ophthalmology": ["eye", "netra", "ophthal"],
    "Oncology": ["cancer", "onco"],
    "Burns": ["burn"],
    "Trauma": ["trauma", "accident"],
}

HOSPITAL_DEFS = [  # used only for the offline demo city
    ("City General Hospital", ["General Emergency", "Trauma", "Orthopedics"]),
    ("Heart Care Institute", ["Cardiology", "General Emergency"]),
    ("NeuroLife Centre", ["Neurology", "Trauma", "General Emergency"]),
    ("Sunrise Children's Hospital", ["Pediatrics", "General Emergency"]),
    ("Phoenix Burn Unit", ["Burns", "Trauma", "General Emergency"]),
    ("Metro Multispeciality", ["Cardiology", "Neurology", "General Emergency"]),
    ("Lifeline Trauma Centre", ["Trauma", "Orthopedics", "Burns", "General Emergency"]),
    ("Green Valley Hospital", ["Pediatrics", "Cardiology", "General Emergency"]),
]


@dataclass
class Hospital:
    hid: int
    name: str
    node: int
    lat: float
    lon: float
    specialties: list
    source: str          # "OSM tag", "name", "assumed", "demo"

    @property
    def tag(self) -> str:
        return f"H{self.hid}"


def _infer(tags, name):
    specs, source = set(), None
    raw = tags.get("healthcare:speciality") or tags.get("healthcare:specialty") or ""
    for part in str(raw).replace(",", ";").split(";"):
        part = part.strip().lower().replace("_", " ")
        if part:
            specs.add(SPEC_SYNONYMS.get(part, part.title()))
            source = "OSM tag"
    low = name.lower()
    for spec, words in NAME_KEYWORDS.items():
        if any(w in low for w in words):
            specs.add(spec)
            source = source or "name"
    if tags.get("emergency") != "no":
        specs.add("General Emergency")
        source = source or "assumed"
    if not specs:
        specs.add("General Emergency")
        source = "assumed"
    return sorted(specs), source


def hospitals_from_osm(elements, net, demo_specs=True):
    found = []
    for el in elements:
        lat, lon = el.get("lat"), el.get("lon")
        if lat is None:
            c = el.get("center")
            if not c:
                continue
            lat, lon = c["lat"], c["lon"]
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:en") or tags.get("operator") or "Unnamed hospital"
        node, dist = net.nearest_node(lat, lon)
        if dist > MAX_SNAP_M:
            continue
        if any(h.name == name and haversine_m(h.lat, h.lon, lat, lon) < 150 for h in found):
            continue
        specs, source = _infer(tags, name)
        if demo_specs and specs == ["General Emergency"]:
            rng = random.Random(int(el.get("id", len(found))))
            specs = sorted(set(specs) | set(rng.sample(DEMO_SPECS, rng.choice([1, 2]))))
            source = "demo"
        found.append(Hospital(0, name, node, lat, lon, specs, source))
    found.sort(key=lambda h: h.name.lower())
    for i, h in enumerate(found):
        h.hid = i + 1
    return found


def demo_hospitals(net):
    """Spread demo hospitals over the network (farthest-point sampling)."""
    rng = random.Random(99)
    chosen = [rng.randrange(net.n)]
    while len(chosen) < min(len(HOSPITAL_DEFS), net.n):
        best, best_d = None, -1.0
        for node in range(net.n):
            if node in chosen:
                continue
            d = min(haversine_m(net.lats[node], net.lons[node], net.lats[c], net.lons[c])
                    for c in chosen)
            if d > best_d:
                best, best_d = node, d
        chosen.append(best)
    rng.shuffle(chosen)
    return [Hospital(i + 1, name, chosen[i], net.lats[chosen[i]], net.lons[chosen[i]],
                     list(specs), "demo")
            for i, (name, specs) in enumerate(HOSPITAL_DEFS[: len(chosen)])]


def build_hospital_tree(hospitals) -> AVLTree:
    tree = AVLTree()
    for h in hospitals:
        for spec in h.specialties:
            tree.insert(spec, h)
    return tree
