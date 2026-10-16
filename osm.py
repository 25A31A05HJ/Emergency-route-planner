"""OpenStreetMap helpers: place search (Nominatim) and road/hospital download
(Overpass API). Free, no API key needed."""
from __future__ import annotations

import math
import re

import requests

from graph import finalize_network, haversine_m

HEADERS = {"User-Agent": "EmergencyRoutePlanner/2.0 (student project)"}
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
HIGHWAYS = ("motorway|trunk|primary|secondary|tertiary|unclassified|residential|"
            "living_street|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link")
# Typical urban ambulance speeds (km/h) when OpenStreetMap has no maxspeed tag
DEFAULT_SPEED = {
    "motorway": 70, "motorway_link": 50, "trunk": 55, "trunk_link": 40,
    "primary": 45, "primary_link": 35, "secondary": 40, "secondary_link": 30,
    "tertiary": 35, "tertiary_link": 28, "unclassified": 30,
    "residential": 25, "living_street": 15,
}


# ----------------------------------------------------------------- network I/O
def geocode(query: str, limit: int = 5, near=None) -> list:
    params = {"q": query, "format": "json", "limit": limit}
    if near:
        lat, lon = near
        params["viewbox"] = f"{lon - 0.08},{lat + 0.08},{lon + 0.08},{lat - 0.08}"
    r = requests.get("https://nominatim.openstreetmap.org/search",
                     params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return [{"name": x["display_name"], "lat": float(x["lat"]), "lon": float(x["lon"])}
            for x in r.json()]


def _overpass(query: str) -> dict:
    errors = []
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=90)
            if r.status_code == 200:
                return r.json()
            errors.append(f"{url.split('/')[2]}: HTTP {r.status_code}")
        except Exception as exc:  # network error, timeout, bad JSON ...
            errors.append(f"{url.split('/')[2]}: {type(exc).__name__}")
    raise RuntimeError("OpenStreetMap servers are busy or unreachable (" + "; ".join(errors) + ").")


def fetch_roads(lat, lon, radius_m) -> dict:
    q = ('[out:json][timeout:60];way["highway"~"^(' + HIGHWAYS + ')$"]'
         f'(around:{int(radius_m)},{lat},{lon});out body geom;')
    return _overpass(q)


def fetch_hospital_elements(lat, lon, radius_m, include_clinics=False) -> list:
    kinds = "hospital|clinic" if include_clinics else "hospital"
    around = f"(around:{int(radius_m)},{lat},{lon})"
    q = (f'[out:json][timeout:60];(node["amenity"~"^({kinds})$"]{around};'
         f'way["amenity"~"^({kinds})$"]{around};'
         f'relation["amenity"~"^({kinds})$"]{around};);out center tags;')
    return _overpass(q).get("elements", [])


# ----------------------------------------------------------------- parsing
def _speed(tags) -> float:
    default = DEFAULT_SPEED.get(tags.get("highway", ""), 30)
    m = re.match(r"\s*(\d+)", str(tags.get("maxspeed", "")))
    if m:
        v = float(m.group(1))
        if "mph" in str(tags.get("maxspeed")):
            v *= 1.609
        if 10 <= v <= 100:
            return v
    return float(default)


def _oneway(tags) -> str:
    ow = str(tags.get("oneway", "")).lower()
    if ow in ("yes", "true", "1"):
        return "forward"
    if ow in ("-1", "reverse"):
        return "reverse"
    if ow in ("no", "false", "0"):
        return "both"
    if tags.get("junction") == "roundabout" or tags.get("highway") in ("motorway", "motorway_link"):
        return "forward"
    return "both"


def network_from_overpass(data, center, radius_m, respect_oneway=True):
    """Turn Overpass 'way' geometry into a junction graph.
    Only junctions / dead ends become nodes; bends are kept as edge geometry."""
    lat0, lon0 = center
    limit = radius_m * 1.1
    runs, counts = [], {}

    for w in data.get("elements", []):
        if w.get("type") != "way":
            continue
        tags = w.get("tags", {})
        nodes, geom = w.get("nodes", []), w.get("geometry", [])
        if len(nodes) != len(geom) or len(nodes) < 2:
            continue
        cur = []
        for nid, g in zip(nodes, geom):
            if g is not None and haversine_m(lat0, lon0, g["lat"], g["lon"]) <= limit:
                cur.append((nid, g["lat"], g["lon"]))
            else:
                if len(cur) >= 2:
                    runs.append((cur, tags))
                cur = []
        if len(cur) >= 2:
            runs.append((cur, tags))

    for cur, _ in runs:
        for nid in {n for n, _, _ in cur}:
            counts[nid] = counts.get(nid, 0) + 1

    coord, best = {}, {}
    for cur, tags in runs:
        speed = _speed(tags)
        name = tags.get("name") or tags.get("ref") or "Unnamed road"
        mode = _oneway(tags) if respect_oneway else "both"
        start, acc = 0, 0.0
        geom = [(cur[0][1], cur[0][2])]
        for i in range(1, len(cur)):
            acc += haversine_m(cur[i - 1][1], cur[i - 1][2], cur[i][1], cur[i][2])
            geom.append((cur[i][1], cur[i][2]))
            if counts.get(cur[i][0], 0) > 1 or i == len(cur) - 1:
                u, v = cur[start][0], cur[i][0]
                if u != v and acc > 0:
                    coord[u] = (cur[start][1], cur[start][2])
                    coord[v] = (cur[i][1], cur[i][2])
                    cost = acc / speed
                    cands = []
                    if mode in ("both", "forward"):
                        cands.append(((u, v), geom))
                    if mode in ("both", "reverse"):
                        cands.append(((v, u), geom[::-1]))
                    for key, g in cands:
                        if key not in best or cost < best[key][0]:
                            best[key] = (cost, acc, speed, name, g)
                start, acc = i, 0.0
                geom = [(cur[i][1], cur[i][2])]

    ids = sorted(coord)
    index = {nid: i for i, nid in enumerate(ids)}
    lats = [coord[nid][0] for nid in ids]
    lons = [coord[nid][1] for nid in ids]
    edges = [(index[u], index[v], L, sp, name, g)
             for (u, v), (_, L, sp, name, g) in best.items()]
    return finalize_network(lats, lons, edges, center, radius_m, "OpenStreetMap")
