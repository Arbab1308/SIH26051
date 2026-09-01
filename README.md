# 🏔️ DRDO Ladakh Thermal Shelter Simulator (SIH26051)

An interactive, high-performance thermal simulation tool designed for the defense research of tactical shelters in high-altitude, extreme cold weather conditions (e.g., Ladakh at ~4500m). 

This project simulates 24-hour thermodynamic performance, solar radiation gain, metabolic heat from occupants, and ventilation heat loss. It features a military logistics engine for airlift feasibility, an infrared (IR) signature stealth analyzer, an **AI-powered NSGA-II generative designer**, **real-time topographical shadow mapping** using live terrain data, and a **tactical microgrid & off-grid solar sizer** for autonomous power deployment.

---

## 🚀 Quick Startup & Running Guide

This application is built on **Python 3.13**. Follow these steps to set up and run the simulator locally on your machine.

### Prerequisites
- **Python 3.13.x** installed. You can verify your version by running:
  ```bash
  python --version
  ```

### 1. Clone the Repository
Clone the project to your local machine:
```bash
git clone https://github.com/Arbab1308/SIH26051.git
cd drdo-shelter-sim
```

### 2. Set Up a Virtual Environment (Recommended)
Set up a clean environment to avoid package conflicts:

*   **On Windows (PowerShell):**
    ```powershell
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    ```
*   **On Windows (CMD):**
    ```cmd
    python -m venv venv
    .\venv\Scripts\activate.bat
    ```
*   **On macOS/Linux:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

### 3. Install Dependencies
Install all the required python packages using the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

### 4. Generate the Weather Data
The simulator requires weather profile input. Run the weather generator script to generate the default Ladakh winter day dataset (`ladakh_winter.csv`):
```bash
python generate_data.py
```

### 5. Run the Streamlit Application
Launch the web interface locally:
```bash
streamlit run app.py
```
After running, the application will be hosted locally. Open your browser and navigate to:
👉 **[http://localhost:8501](http://localhost:8501)**

---

## 🛠️ Project Architecture & Files

*   `app.py`: The main Streamlit application containing the UI, plotting logic, logistics calculators, AI optimizer integration, terrain shadow visualization, microgrid dashboard, and report exporters.
*   `physics.py`: The core thermodynamic library implementing heat transfer (conduction, solar radiation, metabolic heat, ventilation loss), thermal signature equations, and the expanded 20-material database with integer-indexed lookup tables.
*   `optimize.py`: The **Inverse AI Generative Designer** — a multi-objective NSGA-II optimizer (via `pymoo`) that evolves optimal shelter material blueprints across 3 objectives and 3 constraints.
*   `solar_terrain.py`: The **Real-Time Topographical Shadow Mapping** module — uses `pysolar` for astronomical sun positioning and the Open-Elevation API for terrain data, then applies ray-casting to compute shadow masks.
*   `microgrid.py`: The **Tactical Microgrid & Off-Grid Solar Sizer** — calculates hourly heating deficits, sizes PV arrays with altitude/temperature derating, sizes LFP battery banks with cold-weather derating, simulates 24h battery SoC, and compares against diesel fallback costs.
*   `generate_data.py`: A helper script simulating weather conditions (ambient temp, solar irradiance, humidity) for a winter day in Ladakh.
*   `ladakh_winter.csv`: The default generated weather dataset.
*   `requirements.txt`: Python package dependencies (including `pymoo`, `pysolar`).
*   `.gitignore`: Prevents temporary cache, virtual environments (`venv`), and sensitive environment files from being tracked by Git.

---

## 💡 Simulation Features

1.  **Shelter Configuration**: Dynamic sliders to configure dimensions (length, width, height, window/door areas).
2.  **Tactical & Biological Inputs**:
    *   **Troops Count**: Accounts for metabolic heat output (~100W per person).
    *   **Ventilation Rate**: Slider for Air Changes per Hour (ACH) with built-in safety alerts (e.g., *Asphyxiation / Hypoxia warning* if ventilation is too low (< 0.3 ACH) or *Severe heat loss warning* if too high (> 1.5 ACH)).
3.  **Material Selection Database**: 20 real-world military insulation and construction materials (Aerogel, Kevlar, Carbon Fiber, PUF, Rockwool, Nomex, HDPE, etc.) with exact R-Values, density, specific heat capacities, and cost metrics.
4.  **Stealth (IR Signature) Assessment**: Automatically evaluates whether the external wall surface temperature will exceed ambient temperature enough to bloom on enemy thermal imaging / infrared scopes.
5.  **Logistics Engine**: Weighs the shelter materials and calculates transport feasibility using Indian Air Force (IAF) aircraft assets (HAL Dhruv, Mi-17 V5, CH-47 Chinook).
6.  **Tactical Exporters**:
    *   Download raw simulation metrics as a `.csv` file.
    *   Generate and download a formal **Commanding Officer's Dossier** as a PDF containing deployment specs and stealth ratings.
7.  **🧬 Inverse AI Generative Designer (NSGA-II)**:
    Instead of hardcoding material choices, this feature uses a Genetic Algorithm to evolve the perfect shelter using `pymoo`, a standard Python framework for multi-objective optimization.
    *   **Phase 1.1: Dependency & Search Space Setup**
        *   Installed `pymoo` optimization engine.
        *   Expanded the `MATERIALS` dictionary in `physics.py` to include 20 different material choices for walls, roofs, and windows (e.g., Aerogel, Kevlar, Carbon Fiber, standard fabrics).
        *   Mapped each material to an integer index so the algorithm can genetically mutate arrays of integers representing a "shelter blueprint."
    *   **Phase 1.2: The Fitness Evaluation Function**
        *   Created `optimize.py` script containing the optimization engine.
        *   Defined a custom problem class inheriting from `pymoo.core.problem.Problem`.
        *   Set objectives: $f_1$ (Minimize Total Weight), $f_2$ (Minimize Total Cost), and $f_3$ (Maximize Minimum Internal Temperature).
        *   Set constraints: $g_1$ (Weight < Max Payload), $g_2$ (Cost < Max Budget), and $g_3$ (Max External Glow < Max IR Glow).
        *   The fitness function runs the 24-hour thermodynamic simulator (`calculate_new_temperature` loop) for every genetic mutation to evaluate its survivability.
    *   **Phase 1.3: Algorithm Execution & UI Integration**
        *   Initializes the NSGA-II algorithm with a configurable population size (default 100) and generations (default 50) for 5,000+ total permutations.
        *   Integrated an "AI Auto-Designer" sidebar section in `app.py`.
        *   Provided sliders for the user to set their hard constraints (Max Budget, Max Payload).
        *   Triggers the `pymoo` engine via a button click and displays the "Top 3 Optimal Blueprints" using Streamlit's expanders, dataframe tables, and temperature curves.

8.  **🗺️ Real-Time Topographical Shadow Mapping**:
    To execute immediate, real-time data analysis based on physical terrain, this feature replaces the standard solar curve with a dynamic API fetching and shadow computation pipeline.
    *   **Phase 2.1: Real-Time Sun Positioning**
        *   Installed the astronomical calculation library `pysolar`.
        *   Inputs the exact deployment GPS coordinates (Latitude, Longitude) and the current real-time date.
        *   Calculates the Sun's exact Altitude (angle above horizon) and Azimuth (compass direction) for every hour of the 24-hour cycle.
    *   **Phase 2.2: Live Topographical Data Ingestion**
        *   Uses the Open-Elevation API to fetch live elevation profiles.
        *   Queries a radial pattern (36 azimuth angles × 6 distance rings = 216 sample points) in a 5-kilometer radius around the deployment coordinates.
    *   **Phase 2.3: Shadow Masking (Ray-Casting Algorithm)**
        *   Calculates the "Horizon Angle" of the surrounding mountains using trigonometry: $\theta_{horizon} = \arctan(\text{Mountain Height relative to deployment site} / \text{Distance to Mountain})$.
        *   Compares the Sun's Altitude against the Terrain Horizon Angle for each hour.
        *   If `Sun_Altitude < Mountain_Horizon_Angle`, the shelter is in a topographical shadow.
    *   **Phase 2.4: Irradiance Curve Modification**
        *   Applies a shadow mask multiplier (0.1) to the solar irradiance array for shadowed hours, accounting only for diffuse sky radiation and eliminating direct sunlight.
        *   Passes the modified solar irradiance profile into the existing thermodynamic engine to instantly reflect the massive heat loss caused by mountain shadows.

9.  **⚡ Tactical Microgrid & Off-Grid Solar Sizer**:
    Even with perfect insulation, shelters at -25°C need active heating. This feature eliminates diesel dependency by sizing a fully autonomous solar+battery microgrid.
    *   **Phase 3.1: Heating Deficit Calculation**
        *   For each hour, calculates the exact electrical heating power (Watts) required to maintain the shelter at a configurable target temperature (e.g., +5°C).
        *   Formula: $Q_{aux} = \max(0, Q_{loss} - Q_{natural\_gain})$ — the heater covers whatever the insulation, sun, and body heat cannot.
        *   Identifies **peak demand** (coldest hour) for inverter sizing.
    *   **Phase 3.2: Solar PV Array Sizing**
        *   Sizes the panel area (m²) with production-grade derating factors:
            *   **Altitude boost**: +8% irradiance at 3500m+ due to thinner atmosphere.
            *   **Temperature coefficient**: -0.4%/°C from STC (25°C) — cold panels actually perform *better*.
            *   **Soiling factor**: 5% loss from dust/snow.
            *   **System efficiency**: Inverter (93%) × BOS wiring losses (97%) = 90.2% net.
            *   **Battery round-trip**: 92% charge/discharge efficiency.
    *   **Phase 3.3: Battery Bank Sizing (48V LFP)**
        *   Sizes a Lithium Iron Phosphate (LFP) battery bank with:
            *   **Cold-weather derating curve**: 60% capacity at -30°C, 70% at -20°C, scaling to 100% at 25°C.
            *   **Depth-of-Discharge (DoD)**: 80% usable capacity to protect cycle life.
            *   **Multi-day autonomy**: Configurable backup days (default 1.5 days without sun).
    *   **Phase 3.4: 24-Hour Battery SoC Simulation**
        *   Simulates battery State-of-Charge from midnight to midnight.
        *   Models solar charging during daytime and heater discharge overnight.
        *   Flags CRITICAL (<20%), LOW (<50%), or HEALTHY minimum SoC levels.
    *   **Phase 3.5: Diesel Fallback Comparison**
        *   Calculates the diesel generator equivalent: litres/day, daily cost, and 30-day savings.
        *   Demonstrates the economic and logistical case for solar autonomy.
    *   **Visualizations**: Heater Demand vs Solar Generation chart, Battery SoC simulation curve, Thermal Energy Balance breakdown, System Cost donut chart (PV/Battery/Inverter).
---

## 🔒 Security & Secrecy Audit

*   **API Keys & Secrets**: The codebase contains no API keys, tokens, or private credentials. The only external API used (**Open-Elevation**) is completely free, open-source, and requires no authentication.
*   **Git Security**: A `.gitignore` file prevents local environment variables (`.env`), python cache (`__pycache__`), virtual environments (`venv/`), and PDF report downloads from being committed or pushed to Github.
*   **Internet Requirement**: The Terrain Shadow Mapping feature requires an internet connection to fetch live elevation data. All other features work fully offline.

---

## 📄 License & Copyright

© 2026 Arbab1308. All rights reserved.
This project is developed for the Smart India Hackathon (SIH26051). Unauthorized copying, distribution, or modification of this software is subject to copyright protection.

