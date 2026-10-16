"""🚑 Optimized Route Planner for Emergency Vehicles  (SDG 3 & SDG 11)
Real-world map version.  Run with:  streamlit run app.py 
"""
import math

import pandas as pd
import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium
except ImportError:
    st.error("Missing packages. Run: pip install -r requirements.txt")
    st.stop()

try:
    from streamlit_geolocation import streamlit_geolocation
    HAS_GEO = True
except Exception:
    HAS_GEO = False

from algorithms import (ALGOS, REPS, benchmark, find_nearest_hospital,
                        path_distance_m, route_geometry, route_steps, run_search)
from graph import MATRIX_LIMIT, apply_traffic, build_demo_network, haversine_m, subnetwork
from hospitals import build_hospital_tree, demo_hospitals, hospitals_from_osm
from osm import fetch_hospital_elements, fetch_roads, geocode, network_from_overpass

st.set_page_config(page_title="Emergency Route Planner", page_icon="🚑", layout="wide")
# GitHub creator profile
GITHUB_USERNAME = "VEERA PURNIMA VENKATA"

with st.sidebar:
    st.markdown("---")
    st.subheader("👨‍💻 About the Developer")

    st.image(
        f"https://github.com/{25A31A05HJ}.png",
        width=100
    )

    st.markdown(
        f"**[{VEERA PURNIMA VENKATA}](https://github.com/{25A31A05HJ})**"
    )
    st.caption("Creator of Emergency Route Planner")
S = st.session_state

DEFAULT_CENTER = (17.0005, 81.8040)          # Rajahmundry, Andhra Pradesh
for _k, _v in {"center": DEFAULT_CENTER, "area_name": "Rajahmundry, Andhra Pradesh, India",
               "net_key": None, "amb_ll": None, "pat_ll": None, "last_click": None,
               "map_ver": 0, "load_error": None, "lm_results": []}.items():
    S.setdefault(_k, _v)

# ------------------------------------------------------------------ styling
st.markdown(
    """
<style>
.hero{background:linear-gradient(90deg,#b71c1c,#e53935 60%,#ff7043);
      padding:1.3rem 1.6rem;border-radius:16px;color:#fff;margin-bottom:1rem;}
.hero h1{margin:0;font-size:2.0rem;color:#fff;}
.hero p{margin:.35rem 0 .6rem 0;opacity:.95;}
.badge{display:inline-block;background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.5);
       padding:.2rem .7rem;border-radius:999px;margin-right:.5rem;font-size:.85rem;}
.siren{display:inline-block;animation:pulse 1.2s infinite;}
@keyframes pulse{0%{transform:scale(1);}50%{transform:scale(1.25);}100%{transform:scale(1);}}
</style>
<div class="hero">
  <h1><span class="siren">🚑</span> Optimized Route Planner for Emergency Vehicles 🏥</h1>
  <p>Real-world map: <b>Ambulance ➜ 🆘 Patient ➜ ✚ Nearest suitable hospital</b> with traffic 🚦 — works in any city 🌍</p>
  <span class="badge">🩺 SDG 3 · Good Health &amp; Well-being</span>
  <span class="badge">🏙️ SDG 11 · Sustainable Cities</span>
  <span class="badge">🧠 Dijkstra · A* · AVL Tree</span>
</div>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ cached data
@st.cache_resource(show_spinner=False, max_entries=4)
def get_network(key):
    if key[0] == "demo":
        _, lat, lon, size, seed = key
        return build_demo_network(lat, lon, size, seed)
    _, lat, lon, radius, oneway, _clinics = key
    return network_from_overpass(fetch_roads(lat, lon, radius), (lat, lon), radius, oneway)


@st.cache_resource(show_spinner=False, max_entries=8)
def get_hospitals(key, demo_specs):
    """Returns (hospital list, used_fallback_flag)."""
    net = get_network(key)
    if key[0] == "demo":
        return demo_hospitals(net), False
    _, lat, lon, radius, _oneway, clinics = key
    found = hospitals_from_osm(fetch_hospital_elements(lat, lon, radius, clinics), net, demo_specs)
    if found:
        return found, False
    return demo_hospitals(net), True


@st.cache_resource(show_spinner=False, max_entries=6)
def get_graph(key, level, seed):
    return apply_traffic(get_network(key), level, seed)


# ------------------------------------------------------------------ map helpers
def emoji_marker(m, lat, lon, emoji, tooltip, size=30):
    html = (f'<div style="font-size:{size}px;line-height:{size}px;text-align:center;'
            f'filter:drop-shadow(0 0 3px #fff);">{emoji}</div>')
    folium.Marker([lat, lon], tooltip=tooltip,
                  icon=folium.DivIcon(html=html, icon_size=(size, size),
                                      icon_anchor=(size // 2, size // 2))).add_to(m)


def build_map(net, graph, hospitals, a_ll, p_ll, leg1, leg2, best, show_roads):
    m = folium.Map(location=net.center, zoom_start=14, tiles="OpenStreetMap", control_scale=True)
    folium.Circle(net.center, radius=net.radius_m, color="#777", weight=1, dash_array="6",
                  fill=False, tooltip="Loaded map area").add_to(m)

    for lat, lon, sigma in graph.hotspots:
        folium.Circle((lat, lon), radius=sigma * 1.2, color="#d32f2f", weight=1, fill=True,
                      fill_opacity=0.15, tooltip="🚦 Congestion hotspot").add_to(m)

    if show_roads:
        heavy = sorted((e for e in graph.edges if e[4] >= 1.6), key=lambda e: -e[4])[:600]
        for e in heavy:
            if (e[1], e[0]) in graph.edge_map and e[1] < e[0]:
                continue
            colour = "#b71c1c" if e[4] >= 3 else "#ef6c00"
            folium.PolyLine(e[7], color=colour, weight=3, opacity=0.8,
                            tooltip=f"{e[6]} · traffic x{e[4]:.1f}").add_to(m)

    for h in hospitals:
        emoji_marker(m, h.lat, h.lon, "🏥",
                     f"{h.tag} {h.name}<br>{', '.join(h.specialties)}", 26)

    pts = [a_ll, p_ll]
    if leg1 and len(leg1) > 1:
        folium.PolyLine(leg1, color="#1565c0", weight=6, opacity=0.9,
                        tooltip="🚑 Ambulance → Patient").add_to(m)
    if leg2 and len(leg2) > 1:
        folium.PolyLine(leg2, color="#6a1b9a", weight=6, opacity=0.9,
                        tooltip="🆘 Patient → Hospital").add_to(m)
    if best is not None:
        folium.CircleMarker((best.lat, best.lon), radius=24, color="#2e7d32", weight=4,
                            fill=False, tooltip=f"Chosen: {best.name}").add_to(m)
        pts.append((best.lat, best.lon))
    emoji_marker(m, a_ll[0], a_ll[1], "🚑", "Ambulance start", 34)
    emoji_marker(m, p_ll[0], p_ll[1], "🆘", "Patient", 34)
    pts += (leg1 or []) + (leg2 or [])
    m.fit_bounds([[min(p[0] for p in pts), min(p[1] for p in pts)],
                  [max(p[0] for p in pts), max(p[1] for p in pts)]])
    return m


def handle_click(out):
    click = out.get("last_clicked") if out else None
    if not click:
        return
    ll = (click["lat"], click["lng"])
    if S.get("last_click") == ll:
        return
    S["last_click"] = ll
    if S.get("click_mode", "🚑 Ambulance").startswith("🚑"):
        S["amb_ll"] = ll
    else:
        S["pat_ll"] = ll
    st.rerun()


def reset_pins():
    S["amb_ll"] = None
    S["pat_ll"] = None


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("⚙️ Control Room")

    st.subheader("📍 1. Choose your area")
    place = st.text_input("Search any city / area", value="Rajahmundry, Andhra Pradesh, India",
                          key="place_q")
    if st.button("🔎 Find this place"):
        try:
            res = geocode(place)
            if res:
                S["center"] = (res[0]["lat"], res[0]["lon"])
                S["area_name"] = res[0]["name"]
                S["want_load"] = True
            else:
                st.warning("Place not found. Try a more specific name.")
        except Exception as exc:
            st.error(f"Place search failed: {exc}")

    st.markdown("**📡 Use my current location**")
    if HAS_GEO:
        st.caption("Click the button, then press *Allow* in your browser.")
        loc = streamlit_geolocation()
    else:
        loc = None
        st.caption("Install `streamlit-geolocation` to enable this feature.")
    my = None
    if loc and loc.get("latitude") is not None and loc.get("longitude") is not None:
        my = (float(loc["latitude"]), float(loc["longitude"]))
        acc = loc.get("accuracy")
        st.success(f"You are at {my[0]:.5f}, {my[1]:.5f}" + (f" (±{acc:.0f} m)" if acc else ""))
        if st.button("📍 Center map on my location"):
            S["center"] = my
            S["area_name"] = "My current location"
            S["want_load"] = True
            S["amb_ll"] = my
            S["pat_ll"] = None
            st.rerun()
        g1, g2 = st.columns(2)
        if g1.button("🚑 I am the ambulance"):
            S["amb_ll"] = my
        if g2.button("🆘 I am the patient"):
            S["pat_ll"] = my

    st.caption(f"Area: {S['area_name']} ({S['center'][0]:.4f}, {S['center'][1]:.4f})")

    st.subheader("🗺️ 2. Map settings")
    radius_km = st.slider("Map radius (km)", 1.0, 4.0, 2.0, step=0.5,
                          help="Bigger radius = more roads but slower.")
    radius_m = int(radius_km * 1000)
    oneway = st.checkbox("Respect one-way streets", value=True)
    clinics = st.checkbox("Also include clinics", value=False)
    demo_specs = st.checkbox("Assign demo specialties when OpenStreetMap has none", value=True,
                             help="OpenStreetMap rarely lists hospital specialties.")

    want_load = S.pop("want_load", False)
    if st.button("🗺️ Load road map & hospitals", type="primary") or want_load:
        key = ("osm", round(S["center"][0], 5), round(S["center"][1], 5), radius_m, oneway, clinics)
        try:
            with st.spinner("Downloading roads & hospitals from OpenStreetMap (10–40 s)..."):
                get_network(key)
                get_hospitals(key, demo_specs)
            S["net_key"] = key
            S["map_ver"] += 1
            S["load_error"] = None
            for _pin in ("amb_ll", "pat_ll"):      # forget pins that are outside the new area
                if S[_pin] and haversine_m(S[_pin][0], S[_pin][1], *S["center"]) > radius_m * 1.2:
                    S[_pin] = None
        except Exception as exc:
            S["load_error"] = str(exc)
    if S["load_error"]:
        st.error(f"Could not load the map: {S['load_error']}")
        st.caption("Try again in a minute, or use the offline demo city below.")
    if st.button("🧪 Use offline demo city"):
        S["net_key"] = ("demo", S["center"][0], S["center"][1], 12, 42)
        S["map_ver"] += 1
        S["load_error"] = None
        reset_pins()

    with st.expander("🔎 Search a landmark (station, college, hospital...)"):
        lm_q = st.text_input("Landmark name", key="lm_q")
        if st.button("Search landmark"):
            try:
                S["lm_results"] = geocode(lm_q, near=S["center"]) if lm_q.strip() else []
                if not S["lm_results"]:
                    st.warning("Nothing found.")
            except Exception as exc:
                st.error(f"Search failed: {exc}")
        if S["lm_results"]:
            i = st.selectbox("Results", range(len(S["lm_results"])),
                             format_func=lambda k: S["lm_results"][k]["name"][:60])
            r = S["lm_results"][i]
            l1, l2 = st.columns(2)
            if l1.button("🚑 As ambulance"):
                S["amb_ll"] = (r["lat"], r["lon"])
            if l2.button("🆘 As patient"):
                S["pat_ll"] = (r["lat"], r["lon"])

# nothing loaded yet -> welcome screen
if S["net_key"] is None:
    st.info("👈 Pick your area (search a city, or turn on **current location**), then press "
            "**Load road map & hospitals**. No internet access to OpenStreetMap? Use the offline demo city.")
    st.stop()

# ------------------------------------------------------------------ loaded data
net_key = S["net_key"]
net = get_network(net_key)
hospitals, used_fallback = get_hospitals(net_key, demo_specs)
tree = build_hospital_tree(hospitals)

with st.sidebar:
    st.subheader("🚦 3. Emergency settings")
    traffic = st.slider("Traffic congestion", 0, 10, 5, help="0 = empty roads, 10 = gridlock")
    seed = st.number_input("Traffic pattern seed", 0, 9999, 7, step=1)
    specs_available = [k for k, _ in tree.inorder()]
    default_i = specs_available.index("General Emergency") if "General Emergency" in specs_available else 0
    specialty = st.selectbox("🩺 Specialty needed", specs_available, index=default_i)
    algo = st.radio("Search algorithm", ALGOS, index=1, horizontal=True)
    graph = get_graph(net_key, traffic, int(seed))
    if graph.matrix_ok:
        rep = st.radio("Graph representation", REPS, index=0)
    else:
        rep = REPS[0]
        st.warning(f"{net.n} junctions: an adjacency matrix ({net.n}² cells) is too big, "
                   f"so only the Adjacency List is used. Lower the radius (max {MATRIX_LIMIT}).")

if used_fallback:
    st.warning("No hospitals were found in OpenStreetMap for this area, so demo hospitals are shown. "
               "Try a larger radius or tick 'Also include clinics'.")

# default pins
if S["amb_ll"] is None:
    S["amb_ll"] = net.center
if S["pat_ll"] is None:
    dlat = 0.35 * net.radius_m / 110540.0
    dlon = 0.35 * net.radius_m / (111320.0 * math.cos(math.radians(net.center[0])))
    S["pat_ll"] = (net.center[0] + dlat, net.center[1] + dlon)

a_node, a_dist = net.nearest_node(*S["amb_ll"])
p_node, p_dist = net.nearest_node(*S["pat_ll"])
a_pos = (net.lats[a_node], net.lons[a_node])
p_pos = (net.lats[p_node], net.lons[p_node])

c1, c2, c3, c4 = st.columns(4)
c1.metric("🛣️ Junctions", net.n)
c2.metric("🔗 Road segments", len(net.edges))
c3.metric("🏥 Hospitals", len(hospitals))
c4.metric("🗺️ Source", net.source)

tab_route, tab_avl, tab_perf, tab_about = st.tabs(
    ["🗺️ Live Route", "🌳 Hospital AVL Tree", "⚡ Dijkstra vs A*", "📘 About"]
)

# ------------------------------------------------------------------ TAB 1
with tab_route:
    candidates, _, _ = tree.search(specialty)
    if not candidates:
        st.error("No hospital offers this specialty.")
    else:
        st.radio("🖱️ Click on the map to set:", ["🚑 Ambulance", "🆘 Patient"],
                 horizontal=True, key="click_mode")
        for label, dist in (("Ambulance", a_dist), ("Patient", p_dist)):
            if dist > 600:
                st.warning(f"{label} is {dist:.0f} m from the nearest mapped road "
                           "(probably outside the loaded area). Route starts from the nearest junction.")

        if a_node == p_node:
            leg1 = leg2 = None
            best = None
            st.warning("Ambulance and patient snap to the same junction. Move one of them.")
            m = build_map(net, graph, hospitals, a_pos, p_pos, None, None, None, False)
            out = st_folium(m, height=560, use_container_width=True,
                            returned_objects=["last_clicked"], key=f"map_{S['map_ver']}")
            handle_click(out)
        else:
            r1 = run_search(graph, algo, rep, a_node, p_node)
            (best, r2), options = find_nearest_hospital(graph, algo, rep, p_node, candidates)
            total = r1.cost + r2.cost
            dist_m = path_distance_m(graph, r1.path) + path_distance_m(graph, r2.path)

            free = get_graph(net_key, 0, int(seed))
            f1 = run_search(free, algo, rep, a_node, p_node)
            f2 = run_search(free, algo, rep, p_node, best.node)
            delay = total - (f1.cost + f2.cost)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("⏱️ Total ETA", f"{total:.1f} min")
            m2.metric("🚑 → 🆘 Pickup", f"{r1.cost:.1f} min")
            m3.metric("🆘 → 🏥 To hospital", f"{r2.cost:.1f} min")
            m4.metric("🚦 Traffic delay", f"+{max(delay, 0):.1f} min")

            leg1 = route_geometry(graph, r1.path)
            leg2 = route_geometry(graph, r2.path)
            show_roads = st.checkbox("Show congested roads (orange/red)", value=False)

            col_map, col_info = st.columns([3, 2])
            with col_map:
                m = build_map(net, graph, hospitals, a_pos, p_pos, leg1, leg2, best, show_roads)
                out = st_folium(m, height=580, use_container_width=True,
                                returned_objects=["last_clicked"], key=f"map_{S['map_ver']}")
                handle_click(out)
            with col_info:
                st.success(f"✚ Destination: **{best.name}** ({best.tag})")
                st.write(f"📏 Distance: **{dist_m / 1000:.2f} km**")
                st.write(f"🧠 Method: **{algo}** on **{rep}**")
                st.write(f"🔍 Junctions expanded (all searches): "
                         f"**{r1.expanded + sum(r.expanded for _, r in options)}**")
                url = ("https://www.google.com/maps/dir/?api=1"
                       f"&origin={a_pos[0]},{a_pos[1]}&waypoints={p_pos[0]},{p_pos[1]}"
                       f"&destination={best.lat},{best.lon}&travelmode=driving")
                st.link_button("🧭 Open in Google Maps", url)
                st.markdown(f"**🏥 Hospitals offering {specialty}**")
                st.dataframe(pd.DataFrame(
                    [{"Hospital": f"{h.tag} {h.name}",
                      "ETA from patient (min)": round(r.cost, 1)} for h, r in options]),
                    hide_index=True)
                with st.expander("🛣️ Turn-by-turn (roads)"):
                    st.write("**🚑 Ambulance → 🆘 Patient**")
                    st.dataframe(pd.DataFrame(route_steps(graph, r1.path)), hide_index=True)
                    st.write("**🆘 Patient → 🏥 Hospital**")
                    st.dataframe(pd.DataFrame(route_steps(graph, r2.path)), hide_index=True)

# ------------------------------------------------------------------ TAB 2
with tab_avl:
    st.subheader("🌳 Hospitals stored in an AVL tree (key = specialty)")
    a, b, c = st.columns(3)
    a.metric("Specialties (nodes)", len(tree))
    b.metric("Tree height", tree.height)
    c.metric("Rotations performed", tree.rotations)

    left, right = st.columns([3, 2])
    with left:
        st.graphviz_chart(tree.to_dot())
    with right:
        st.markdown("**Sorted (in-order) contents**")
        st.dataframe(pd.DataFrame(
            [{"Specialty": k, "Hospitals": ", ".join(h.tag for h in v)} for k, v in tree.inorder()]),
            hide_index=True)

    st.markdown("**🏥 Hospital list**")
    st.dataframe(pd.DataFrame(
        [{"Tag": h.tag, "Name": h.name, "Specialties": ", ".join(h.specialties),
          "Specialty source": h.source} for h in hospitals]), hide_index=True)
    st.caption("Specialty source: *OSM tag* = from OpenStreetMap, *name* = guessed from the hospital "
               "name, *assumed* = general emergency only, *demo* = sample data for the demonstration.")

    st.markdown("**🔎 Search demo**")
    demo = st.selectbox("Find hospitals for specialty", specs_available, key="avl_demo")
    found, comparisons, visited = tree.search(demo)
    st.write(f"Visited path: `{' → '.join(visited)}`")
    st.write(f"AVL comparisons: **{comparisons}** (a linear scan would need up to **{len(tree)}**)")
    st.write("Hospitals: " + ", ".join(f"{h.tag} {h.name}" for h in found))

# ------------------------------------------------------------------ TAB 3
with tab_perf:
    st.subheader("⚡ Performance: Dijkstra vs A* × Adjacency List vs Matrix")
    st.caption("Random start/end junctions on the loaded map. Times are measured in pure Python.")
    nq = st.slider("Number of random routes", 10, 100, 20, step=10,
                   help="The adjacency matrix is slow on big maps, so keep this small.")
    signature = (net_key, traffic, int(seed), nq)

    if st.button("▶️ Run benchmark"):
        with st.spinner("Running..."):
            rows, mism = benchmark(graph, nq)
        S["bench"] = (signature, rows, mism)

    bench = S.get("bench")
    if bench and bench[0] == signature:
        _, rows, mism = bench
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True)
        df["Combination"] = df["Algorithm"] + " + " + df["Representation"].str.replace("Adjacency ", "")
        x1, x2 = st.columns(2)
        with x1:
            st.markdown("**Average time per route (ms)**")
            st.bar_chart(df.set_index("Combination")["Avg time (ms)"])
        with x2:
            st.markdown("**Average nodes expanded**")
            st.bar_chart(df.set_index("Combination")["Avg nodes expanded"])
        if mism == 0:
            st.success("✅ All combinations found identical optimal travel times on every route.")
        else:
            st.error(f"⚠️ {mism} route(s) had differing costs.")
        dj = df[(df.Algorithm == "Dijkstra") & (df.Representation == "Adjacency List")].iloc[0]
        as_ = df[(df.Algorithm == "A*") & (df.Representation == "Adjacency List")].iloc[0]
        saved = 100 * (1 - as_["Avg nodes expanded"] / dj["Avg nodes expanded"])
        st.info(f"A* explored about **{saved:.0f}% fewer junctions** than Dijkstra (Adjacency List).")
    else:
        st.info("Press **Run benchmark** to compare the algorithms on this map.")

    st.markdown("---")
    st.markdown("**📈 Scaling experiment** (speed vs. map size; uses smaller parts of the loaded map)")
    if st.button("▶️ Run scaling experiment"):
        table = {}
        with st.spinner("Running..."):
            for frac in (0.3, 0.45, 0.6, 0.8, 1.0):
                try:
                    sub = net if frac == 1.0 else subnetwork(net, net.radius_m * frac)
                except ValueError:
                    continue
                g = apply_traffic(sub, traffic, int(seed))
                rows_s, _ = benchmark(g, 10)
                for r in rows_s:
                    k = f"{r['Algorithm']} + {r['Representation'].replace('Adjacency ', '')}"
                    table.setdefault(k, {})[sub.n] = r["Avg time (ms)"]
        S["scale"] = pd.DataFrame(table).sort_index()
    if "scale" in S:
        st.line_chart(S["scale"])
        st.caption("X-axis: number of junctions. Y-axis: average ms per route.")

    st.markdown(
        """
| | Adjacency List | Adjacency Matrix |
|---|---|---|
| **Memory** | O(V + E) | O(V²) |
| **Dijkstra / A\\*** | O((V + E) log V) | O(V² + E log V) |
| **Finding neighbours** | O(degree) | O(V) |

Road networks are *sparse* (each junction has only 3–4 roads), so the **list** wins clearly and
the matrix becomes impractical on big maps. A\\* adds a straight-line heuristic that steers the
search toward the goal, so it expands fewer junctions.
"""
    )

# ------------------------------------------------------------------ TAB 4
with tab_about:
    st.subheader("📘 About this project")
    st.markdown(
        """
**Problem:** find the fastest ambulance route to a patient and then to the nearest hospital that
offers the required specialty, taking traffic into account.

**How it works**
1. 🌍 Roads and hospitals are downloaded live from **OpenStreetMap** for any area you choose
   (search a place, or press the 📡 current-location button).
2. 🛣️ Junctions become graph nodes and road pieces become edges. Edge weight = travel time =
   length ÷ speed × traffic multiplier. One-way streets are respected.
3. 🌳 Hospitals are stored in an **AVL tree** keyed by specialty (O(log n) lookup).
4. 🧠 **Dijkstra** and **A\\*** compute the fastest path: ambulance → patient → best hospital.
5. ⚡ The performance tab compares both algorithms on **Adjacency List** and **Adjacency Matrix**.

**Honest limitations**
- 🚦 Traffic is **simulated** (congestion hotspots). Free map services do not provide live traffic;
  a paid API (TomTom, Google, HERE) could be plugged into `apply_traffic()` in `graph.py`.
- 🩺 OpenStreetMap rarely lists hospital specialties, so some are guessed from names or demo data
  (shown in the *Specialty source* column).
- Speeds are typical urban values per road type, not measured.

**SDG links:** 🩺 *SDG 3* – faster emergency response saves lives. 🏙️ *SDG 11* – smarter, safer urban mobility.

**Map data © OpenStreetMap contributors.**
"""
    ) 
