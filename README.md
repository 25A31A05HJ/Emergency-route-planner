# 🚑 Optimized Route Planner for Emergency Vehicles (Real-World Map)

> **A high-performance Python application designed to optimize and find the fastest routes to critical care facilities using OpenStreetMap data and advanced algorithms.** 🚑💨

---

## 🚀 Live Demo
Experience the project live in action! Click the link below:
🔗 **[https://emergency-route-planner-pm5tmobwukpceq45dog34y.streamlit.app/]** 
---

## 📌 Project Overview
During medical emergencies, every second counts. This project leverages real-world geospatial data to build highly efficient routing maps. 🎯 By combining **custom graph networks** with **self-balancing AVL search trees**, the system handles massive maps seamlessly to connect patients to nearby hospitals in optimal time. ⏳

---

## 📁 Repository Architecture & File Blueprint

Here is what each file in this repository handles:

*   **`app.py`** 🖥️ — The central command station. It runs the main application interface and coordinates the mapping workflow.
*   **`osm.py`** 🗺️ — OpenStreetMap processor. Extracts structural road networks, coordinates, and geographic milestones from raw OSM files.
*   **`graph.py`** 🕸️ — Graph structure engine. Turns geographic data into mathematical nodes (intersections) and edges (roads).
*   **`algorithms.py`** ⚙️ — The routing core. Houses optimized shortest-path algorithms (like Dijkstra or A*) tuned for speed.
*   **`hospitals.py`** 🏥 — Healthcare registry. Manages information, capacities, locations, and search indices for care facilities.
*   **`avl_tree.py`** 🌲 — Data optimizer. A self-balancing binary search tree built to ensure lightning-fast spatial queries.
*   **`requirements.txt`** 📦 — Dependency locker. Contains all the necessary Python libraries required to spin up the project.

---

## 🛠️ Local Installation & Setup

Get this project running on your computer in four easy steps:

1. **Clone the repository** 👥
   ```bash
   git clone https://github.com
   cd emergency-route-planner
   ```

2. **Create a virtual sandbox environment** 🍦
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install all required packages** 📥
   ```bash
   pip install -r requirements.txt
   ```

4. **Fire up the app** 🔥
   ```bash
   python app.py
   ```

---

## 🛠️ Technologies Used
*   **Language:** Python 🐍
*   **Data Structures:** Graphs 🕸️ & AVL Trees 🌲
*   **Mapping Data:** OpenStreetMap API 🌍

---

### 👩‍💻 Credits & Attribution
✨ **Developed by:** Veera Purnima Venkata  
🏛️ **Institution:** Pragati Engineering College  
💻 **Department:** Computer Science & Engineering  
