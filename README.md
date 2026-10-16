# 🚑 Optimized Route Planner for Emergency Vehicles (Real-World Map)
SDG 3 (Good Health & Well-being) · SDG 11 (Sustainable Cities)

Works on a **real map of any city** (default: Rajahmundry) using free OpenStreetMap data.
No API key needed.

## Files (put ALL of them in the root of your GitHub repo)
| File | Purpose |
|---|---|
| `app.py` | Streamlit app: real map, current-location button, tabs |
| `osm.py` | Place search + downloads roads/hospitals from OpenStreetMap |
| `graph.py` | Road graph, traffic simulation, Adjacency List + Matrix |
| `algorithms.py` | Dijkstra, A*, nearest hospital, benchmark |
| `avl_tree.py` | AVL tree (hospitals by specialty) |
| `hospitals.py` | Hospital data + AVL builder |
| `requirements.txt` | Packages to install |

## Run locally
```
pip install -r requirements.txt
streamlit run app.py
```

## Get a Streamlit web link (free)
1. Create a **public** GitHub repository and upload all 7 files (not inside a sub-folder).
2. Go to https://share.streamlit.io and sign in with GitHub.
3. **Create app** → pick your repo → branch `main` → main file `app.py` → **Deploy**.
4. Open the link on your phone/laptop. Press the 📡 button and tap **Allow** to use your current location.

## How to use
1. Search an area (e.g. `Rajahmundry`) **or** press 📡 current location → *Center map on my location*.
2. Click **Load road map & hospitals** (takes 10–40 s the first time).
3. Click on the map to place the 🚑 ambulance and the 🆘 patient (switch with the radio button),
   or use landmark search / current location.
4. Choose the specialty needed, traffic level, algorithm and graph type.
5. See the fastest route, ETA, hospital ranking, AVL tree and the performance comparison.

## Notes
- Location access needs HTTPS: the Streamlit link and `localhost` both work.
- Traffic is **simulated** (free services give no live traffic). A paid traffic API can be added in `apply_traffic()`.
- If OpenStreetMap servers are busy, press **Use offline demo city**.
- Map radius 1–4 km. The adjacency matrix is disabled above 2500 junctions (V² memory).
- Map data © OpenStreetMap contributors.
