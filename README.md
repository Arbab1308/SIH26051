# 🏔️ DRDO Ladakh Thermal Shelter Simulator (SIH26051)

An interactive, high-performance thermal simulation tool designed for the defense research of tactical shelters in high-altitude, extreme cold weather conditions (e.g., Ladakh at ~4500m). 

This project simulates 24-hour thermodynamic performance, solar radiation gain, metabolic heat from occupants, and ventilation heat loss. It also features a military logistics engine for airlift feasibility and an infrared (IR) signature stealth analyzer.

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

*   `app.py`: The main Streamlit application containing the UI, plotting logic, logistics calculators, AI optimizer integration, and report exporters.
*   `physics.py`: The core thermodynamic library implementing heat transfer (conduction, solar radiation, metabolic heat, ventilation loss), thermal signature equations, and the expanded 20-material database with integer-indexed lookup tables.
*   `optimize.py`: The **Inverse AI Generative Designer** — a multi-objective NSGA-II optimizer (via `pymoo`) that evolves optimal shelter material blueprints across 3 objectives and 3 constraints.
*   `generate_data.py`: A helper script simulating weather conditions (ambient temp, solar irradiance, humidity) for a winter day in Ladakh.
*   `ladakh_winter.csv`: The default generated weather dataset.
*   `requirements.txt`: Python package dependencies (including `pymoo` for the AI optimizer).
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
    *   Uses the `pymoo` multi-objective optimization framework to evolve optimal shelter material combinations.
    *   **3 Objectives**: Minimize weight, minimize cost, maximize minimum internal temperature.
    *   **3 Constraints**: Max payload (kg), max budget (INR), max IR glow (°C) — all configurable via sidebar sliders.
    *   Evaluates **5,000+ shelter permutations** (100 population × 50 generations) using the full 24-hour thermal simulation loop.
    *   Displays **Top 3 Pareto-optimal Blueprints** with comparison tables, expandable detail cards, and per-blueprint thermal profile charts.

---

## 🔒 Security & Secrecy Audit

*   **API Keys & Secrets**: The codebase has been scanned and contains no API keys, credentials, or private credentials. It runs entirely locally on local calculation engines.
*   **Git Security**: A `.gitignore` file has been added to prevent local environment variables (`.env`), python cache (`__pycache__`), virtual environments (`venv/`), and PDF report downloads from being committed or pushed to Github.

---

## 📄 License & Copyright

© 2026 Arbab1308. All rights reserved.
This project is developed for the Smart India Hackathon (SIH26051). Unauthorized copying, distribution, or modification of this software is subject to copyright protection.

