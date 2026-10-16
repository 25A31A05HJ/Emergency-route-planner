"""Dijkstra and A* on Adjacency List and Adjacency Matrix + benchmarking."""
from __future__ import annotations

import heapq
import random
import time
from dataclasses import dataclass

from graph import INF, haversine_m

ALGOS = ["Dijkstra", "A*"]
REPS = ["Adjacency List", "Adjacency Matrix"]


@dataclass
class SearchResult:
    path: list
    cost: float          # minutes
    expanded: int        # nodes popped from the priority queue
    elapsed_ms: float


def available_combos(graph):
    reps = REPS if graph.matrix_ok else REPS[:1]
    return [(a, r) for r in reps for a in ALGOS]


def _build_path(prev, src, dst):
    path, cur = [], dst
    while cur != -1:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path if path and path[0] == src else []


def _search(neighbours, n, src, dst, h):
    """Best-first search. h(u)=0 -> Dijkstra, h(u)=straight-line time -> A*."""
    g = [INF] * n
    prev = [-1] * n
    closed = [False] * n
    g[src] = 0.0
    pq = [(h(src), src)]
    expanded = 0
    while pq:
        _, u = heapq.heappop(pq)
        if closed[u]:
            continue
        closed[u] = True
        expanded += 1
        if u == dst:
            break
        gu = g[u]
        for v, w in neighbours(u):
            nd = gu + w
            if nd < g[v]:
                g[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd + h(v), v))
    return g, prev, expanded


def run_search(graph, algo: str, rep: str, src: int, dst: int) -> SearchResult:
    n = graph.n
    if algo == "A*":
        lats, lons = graph.net.lats, graph.net.lons
        glat, glon = lats[dst], lons[dst]
        speed = graph.net.max_speed_ms          # fastest possible road -> never overestimates
        h = lambda u: haversine_m(lats[u], lons[u], glat, glon) / speed / 60.0
    else:
        h = lambda u: 0.0

    if rep == "Adjacency List":
        adj = graph.adj_list
        neighbours = lambda u: adj[u]                       # only real neighbours
    else:
        if not graph.matrix_ok:
            raise ValueError("Map too large for an adjacency matrix.")
        mat = graph.adj_matrix

        def neighbours(u):                                  # scans the WHOLE row: O(V)
            row = mat[u]
            return [(v, row[v]) for v in range(n) if row[v] != INF]

    t0 = time.perf_counter()
    g, prev, expanded = _search(neighbours, n, src, dst, h)
    elapsed = (time.perf_counter() - t0) * 1000.0
    return SearchResult(_build_path(prev, src, dst), g[dst], expanded, elapsed)


def find_nearest_hospital(graph, algo, rep, src, hospitals):
    """Route to every candidate hospital; return (best, all) sorted by ETA."""
    options = [(h, run_search(graph, algo, rep, src, h.node)) for h in hospitals]
    options.sort(key=lambda x: x[1].cost)
    return options[0], options


# ----------------------------------------------------------------- route info
def route_geometry(graph, path):
    """Full lat/lon polyline following the real road curves."""
    if not path:
        return []
    if len(path) == 1:
        return [(graph.net.lats[path[0]], graph.net.lons[path[0]])]
    pts = []
    for a, b in zip(path, path[1:]):
        geom = graph.edges[graph.edge_map[(a, b)]][7]
        pts.extend(geom if not pts else geom[1:])
    return pts


def path_distance_m(graph, path) -> float:
    return sum(graph.edges[graph.edge_map[(a, b)]][2] for a, b in zip(path, path[1:]))


def route_steps(graph, path):
    """Group consecutive road segments by street name."""
    steps = []
    for a, b in zip(path, path[1:]):
        e = graph.edges[graph.edge_map[(a, b)]]
        name, metres, minutes = e[6], e[2], e[5]
        if steps and steps[-1]["Road"] == name:
            steps[-1]["Distance (m)"] += metres
            steps[-1]["Time (min)"] += minutes
        else:
            steps.append({"Road": name, "Distance (m)": metres, "Time (min)": minutes})
    for s in steps:
        s["Distance (m)"] = round(s["Distance (m)"])
        s["Time (min)"] = round(s["Time (min)"], 2)
    return steps


# ----------------------------------------------------------------- benchmark
def benchmark(graph, num_queries: int, seed: int = 7):
    combos = available_combos(graph)
    rng = random.Random(seed)
    pairs = []
    while len(pairs) < num_queries:
        s, t = rng.randrange(graph.n), rng.randrange(graph.n)
        if s != t:
            pairs.append((s, t))

    stats = {c: {"ms": 0.0, "exp": 0, "costs": []} for c in combos}
    for s, t in pairs:
        for combo in combos:
            res = run_search(graph, combo[0], combo[1], s, t)
            stats[combo]["ms"] += res.elapsed_ms
            stats[combo]["exp"] += res.expanded
            stats[combo]["costs"].append(res.cost)

    mismatches = 0
    for i in range(len(pairs)):
        costs = [stats[c]["costs"][i] for c in combos]
        if max(costs) - min(costs) > 1e-6:
            mismatches += 1

    rows = [{"Algorithm": c[0], "Representation": c[1],
             "Avg time (ms)": round(stats[c]["ms"] / num_queries, 4),
             "Avg nodes expanded": round(stats[c]["exp"] / num_queries, 1)} for c in combos]
    return rows, mismatches
