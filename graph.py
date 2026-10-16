"""Road network (real OpenStreetMap or offline demo) + traffic model.
Stored as an Adjacency List AND (lazily) an Adjacency Matrix."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

INF = float("inf")
EARTH_R = 6371000.0
MATRIX_LIMIT = 2500     # a V x V matrix above this many junctions is too big


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(a)))


def to_xy(lat, lon, lat0, lon0):
    """Local metres (x east, y north) relative to a reference point."""
    return ((lon - lon0) * 111320.0 * math.cos(math.radians(lat0)),
            (lat - lat0) * 110540.0)


# ----------------------------------------------------------------- network
@dataclass
class RoadNetwork:
    lats: list
    lons: list
    edges: list          # (u, v, length_m, speed_kmh, name, geometry[(lat, lon), ...])
    center: tuple
    radius_m: float
    source: str
    max_speed_ms: float

    @property
    def n(self) -> int:
        return len(self.lats)

    @property
    def bounds(self):
        return min(self.lats), min(self.lons), max(self.lats), max(self.lons)

    def nearest_node(self, lat, lon):
        """Snap a GPS point to the closest junction -> (node, distance_m)."""
        c = math.cos(math.radians(lat))
        best, bd = 0, INF
        for i in range(len(self.lats)):
            dy = self.lats[i] - lat
            dx = (self.lons[i] - lon) * c
            d = dx * dx + dy * dy
            if d < bd:
                best, bd = i, d
        return best, haversine_m(lat, lon, self.lats[best], self.lons[best])


def _largest_scc(n, edges):
    """Largest strongly connected component (iterative Kosaraju), so every
    junction can reach every other one even with one-way streets."""
    adj = [[] for _ in range(n)]
    radj = [[] for _ in range(n)]
    for e in edges:
        adj[e[0]].append(e[1])
        radj[e[1]].append(e[0])
    seen = [False] * n
    order = []
    for s in range(n):
        if seen[s]:
            continue
        seen[s] = True
        stack = [(s, 0)]
        while stack:
            u, i = stack.pop()
            if i < len(adj[u]):
                stack.append((u, i + 1))
                v = adj[u][i]
                if not seen[v]:
                    seen[v] = True
                    stack.append((v, 0))
            else:
                order.append(u)
    comp = [-1] * n
    best = []
    c = 0
    for s in reversed(order):
        if comp[s] != -1:
            continue
        comp[s] = c
        members, stack = [], [s]
        while stack:
            u = stack.pop()
            members.append(u)
            for v in radj[u]:
                if comp[v] == -1:
                    comp[v] = c
                    stack.append(v)
        if len(members) > len(best):
            best = members
        c += 1
    return set(best)


def finalize_network(lats, lons, edges, center, radius_m, source) -> RoadNetwork:
    if not lats or not edges:
        raise ValueError("No usable roads were found for this area.")
    keep = sorted(_largest_scc(len(lats), edges))
    remap = {old: i for i, old in enumerate(keep)}
    new_edges = [(remap[u], remap[v], L, sp, name, geom)
                 for (u, v, L, sp, name, geom) in edges if u in remap and v in remap]
    if len(keep) < 2 or not new_edges:
        raise ValueError("The road network found is too small. Try a bigger radius.")
    max_speed = max(e[3] for e in new_edges) / 3.6
    return RoadNetwork([lats[o] for o in keep], [lons[o] for o in keep],
                       new_edges, center, radius_m, source, max_speed)


def subnetwork(net: RoadNetwork, radius_m: float) -> RoadNetwork:
    """Smaller copy of the network (junctions within radius_m of the centre)."""
    lat0, lon0 = net.center
    idx = [i for i in range(net.n)
           if haversine_m(lat0, lon0, net.lats[i], net.lons[i]) <= radius_m]
    remap = {old: i for i, old in enumerate(idx)}
    edges = [(remap[u], remap[v], L, sp, nm, g) for (u, v, L, sp, nm, g) in net.edges
             if u in remap and v in remap]
    return finalize_network([net.lats[i] for i in idx], [net.lons[i] for i in idx],
                            edges, net.center, radius_m, net.source)


def build_demo_network(lat0, lon0, size, seed) -> RoadNetwork:
    """Offline fallback: a grid-like city placed around (lat0, lon0)."""
    rng = random.Random(seed)
    spacing = 250.0
    mid = (size - 1) * spacing / 2
    lats, lons = [], []
    for r in range(size):
        for c in range(size):
            x = c * spacing - mid + rng.uniform(-35, 35)
            y = r * spacing - mid + rng.uniform(-35, 35)
            lats.append(lat0 + y / 110540.0)
            lons.append(lon0 + x / (111320.0 * math.cos(math.radians(lat0))))

    def idx(r, c):
        return r * size + c

    pairs = []
    for r in range(size):
        for c in range(size):
            if c + 1 < size:
                pairs.append((idx(r, c), idx(r, c + 1), f"Demo Street {r + 1}"))
            if r + 1 < size:
                pairs.append((idx(r, c), idx(r + 1, c), f"Demo Avenue {c + 1}"))
            if r + 1 < size and c + 1 < size and rng.random() < 0.2:
                pairs.append((idx(r, c), idx(r + 1, c + 1), "Demo Link Road"))
    edges = []
    for u, v, name in pairs:
        L = haversine_m(lats[u], lons[u], lats[v], lons[v])
        g = [(lats[u], lons[u]), (lats[v], lons[v])]
        edges.append((u, v, L, 40.0, name, g))
        edges.append((v, u, L, 40.0, name, g[::-1]))
    return finalize_network(lats, lons, edges, (lat0, lon0), size * spacing * 0.75, "Demo city")


# ----------------------------------------------------------------- traffic
@dataclass
class CityGraph:
    net: RoadNetwork
    traffic_level: int
    seed: int
    edges: list          # (u, v, length_m, speed, mult, minutes, name, geometry)
    adj_list: list       # adj_list[u] = [(v, minutes), ...]
    edge_map: dict       # (u, v) -> index in edges
    hotspots: list       # [(lat, lon, sigma_m)]
    _matrix: list = field(default=None, repr=False)

    @property
    def n(self) -> int:
        return self.net.n

    @property
    def matrix_ok(self) -> bool:
        return self.n <= MATRIX_LIMIT

    @property
    def adj_matrix(self) -> list:
        """V x V matrix of travel minutes (INF = no road). Built on first use."""
        if self._matrix is None:
            n = self.n
            m = [[INF] * n for _ in range(n)]
            for e in self.edges:
                m[e[0]][e[1]] = e[5]
            self._matrix = m
        return self._matrix


def apply_traffic(net: RoadNetwork, level: int, seed: int) -> CityGraph:
    """Simulated traffic: congestion hotspots + noise slow down nearby roads.
    (Free public APIs do not provide live traffic, see README.)"""
    lat0, lon0 = net.center
    rng = random.Random(seed * 7919 + 13)
    sigma = max(350.0, net.radius_m * 0.18)
    hotspots = []
    for _ in range(7):
        ang = rng.uniform(0, 2 * math.pi)
        r = net.radius_m * 0.8 * math.sqrt(rng.random())
        x, y = r * math.cos(ang), r * math.sin(ang)
        hotspots.append((lat0 + y / 110540.0,
                         lon0 + x / (111320.0 * math.cos(math.radians(lat0))), sigma))
    active = hotspots[: 2 + level // 2] if level > 0 else []
    act_xy = [to_xy(h[0], h[1], lat0, lon0) for h in active]
    strength = 0.5 * level

    edges, edge_map = [], {}
    adj = [[] for _ in range(net.n)]
    for (u, v, L, sp, name, geom) in net.edges:
        mlat = (net.lats[u] + net.lats[v]) / 2
        mlon = (net.lons[u] + net.lons[v]) / 2
        mx, my = to_xy(mlat, mlon, lat0, lon0)
        mult = 1.0 + rng.random() * 0.05 * level
        for hx, hy in act_xy:
            d2 = (mx - hx) ** 2 + (my - hy) ** 2
            mult += strength * math.exp(-d2 / (2 * sigma ** 2))
        minutes = L / (sp / 3.6) / 60.0 * mult
        edge_map[(u, v)] = len(edges)
        edges.append((u, v, L, sp, mult, minutes, name, geom))
        adj[u].append((v, minutes))
    return CityGraph(net, level, seed, edges, adj, edge_map, active)
