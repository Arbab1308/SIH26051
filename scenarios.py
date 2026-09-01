import datetime

"""
Service for loading predefined Indian Army deployment scenarios.
"""

SCENARIOS = {
    "Leh Cantonment Winter": {
        "description": "Standard high-altitude baseline. Moderate cold, full supply chain.",
        "lat": 34.1526,
        "lon": 77.5771,
        "altitude_m": 3524,
        "start_date": datetime.date(2026, 1, 15),
        "wall_material": "Brick",
        "roof_material": "Polyurethane Panel (PUF)",
        "window_material": "Glass (Double Pane)",
        "occupants": 8,
        "diffuse_fraction": 0.10,
        "ach": 0.5
    },
    "Khardung La Storm": {
        "description": "Extreme altitude and high wind stress scenario.",
        "lat": 34.2817,
        "lon": 77.6025,
        "altitude_m": 5359,
        "start_date": datetime.date(2026, 2, 10),
        "wall_material": "Concrete",
        "roof_material": "Carbon Fiber Panel",
        "window_material": "Polycarbonate Sheet",
        "occupants": 5,
        "diffuse_fraction": 0.15,
        "ach": 0.3
    },
    "DBO Forward Base (Logistics Limited)": {
        "description": "Remote forward base relying on airlift. Supply chain constraints active.",
        "lat": 35.3889,
        "lon": 77.8469,
        "altitude_m": 5065,
        "start_date": datetime.date(2026, 12, 1),
        "wall_material": "Polyurethane Panel (PUF)",
        "roof_material": "Polyurethane Panel (PUF)",
        "window_material": "Polycarbonate Sheet",
        "occupants": 10,
        "diffuse_fraction": 0.05,
        "ach": 0.4
    },
    "Siachen Glacier (Extreme Cold)": {
        "description": "The highest battlefield. Extreme cold and no road access.",
        "lat": 35.4206,
        "lon": 77.1090,
        "altitude_m": 5400,
        "start_date": datetime.date(2026, 1, 1),
        "wall_material": "Aerogel Composite",
        "roof_material": "Aerogel Composite",
        "window_material": "Glass (Double Pane)",
        "occupants": 4,
        "diffuse_fraction": 0.10,
        "ach": 0.2
    },
    "Pangong Tso Border (High Humidity/Wind)": {
        "description": "Lake-side deployment with higher humidity and wind-chill.",
        "lat": 33.7595,
        "lon": 78.6466,
        "altitude_m": 4250,
        "start_date": datetime.date(2026, 1, 20),
        "wall_material": "Fiberglass Batt",
        "roof_material": "Polyurethane Panel (PUF)",
        "window_material": "Glass (Single Pane)",
        "occupants": 6,
        "diffuse_fraction": 0.12,
        "ach": 0.6
    }
}

def get_scenario_names():
    return list(SCENARIOS.keys())

def get_scenario(name):
    return SCENARIOS.get(name, SCENARIOS["Leh Cantonment Winter"])
