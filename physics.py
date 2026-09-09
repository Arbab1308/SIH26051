import math
from functools import lru_cache

# ─── Ground / Permafrost Constants ─────────────────────────────────────────────
GROUND_TEMP_PERMAFROST = -15.0  # °C — Ladakh frozen ground temperature
DEFAULT_FLOOR_R_VALUE = 0.5     # m²K/W — bare concrete on permafrost

@lru_cache(maxsize=None)
def calculate_heat_transfer(t_inside, t_outside, area, r_value):
    """
    Calculates the heat loss (or gain) through a surface via conduction.
    Formula: Q = Area * ΔT / R-value
    Returns: Heat transfer in Watts (Joules/second)
    """
    if r_value <= 0:
        return 0
    return (t_inside - t_outside) * area / r_value
@lru_cache(maxsize=None)
def calculate_solar_gain(solar_irradiance, window_area, absorptivity=0.7):
    """
    Calculates the heat gained from the sun entering the shelter.
    Formula: Q = Irradiance * Area * Absorptivity
    Returns: Heat gain in Watts
    """
    return solar_irradiance * window_area * absorptivity


# ─── Ground Conduction (Permafrost) ────────────────────────────────────────────
@lru_cache(maxsize=None)
def calculate_ground_conduction(t_inside, floor_area, floor_r_value=None,
                                 ground_temp=GROUND_TEMP_PERMAFROST):
    """
    Calculates heat lost downward through the floor into frozen permafrost.
    Formula: Q = floor_area × (T_inside − T_ground) / R_floor
    Default T_ground = −15°C (Ladakh permafrost).
    Returns: Heat loss in Watts (positive = heat escaping downward)
    """
    if floor_r_value is None:
        floor_r_value = DEFAULT_FLOOR_R_VALUE
    if floor_r_value <= 0:
        return 0.0
    delta_t = t_inside - ground_temp
    if delta_t <= 0:
        return 0.0  # Ground is warmer than shelter — no loss
    return delta_t * floor_area / floor_r_value


# ─── Night Shutters ────────────────────────────────────────────────────────────
NIGHT_SHUTTER_R_BOOST = 2.5  # m²K/W added when insulated thermal blankets deployed

def get_effective_window_r_value(base_r_value, solar_irradiance,
                                  night_shutters_enabled=True):
    """
    Returns the effective window R-value. During nighttime (solar irradiance = 0)
    with shutters enabled, troops pull down insulated thermal blankets adding
    R = 2.5 m²K/W to the window.
    """
    if night_shutters_enabled and solar_irradiance <= 0:
        return base_r_value + NIGHT_SHUTTER_R_BOOST
    return base_r_value


# ─── Phase Change Materials (PCM) ──────────────────────────────────────────────
def calculate_pcm_specific_heat(base_cp, current_temp, transition_temp=18.0,
                                 active_cp=14000.0, bandwidth=2.0):
    """
    Modulates the specific heat capacity for Phase Change Materials (bio-wax).
    When shelter temperature is within ±bandwidth of the transition temperature,
    the effective cp spikes dramatically (simulating latent heat absorption/release).

    Args:
        base_cp: Normal specific heat capacity (J/kg·K)
        current_temp: Current shelter temperature (°C)
        transition_temp: PCM melting/freezing point (default 18°C)
        active_cp: Elevated cp during phase transition (default 14000 J/kg·K)
        bandwidth: Half-width of the transition zone (default ±2°C)

    Returns: Effective specific heat in J/kg·K
    """
    if abs(current_temp - transition_temp) <= bandwidth:
        return active_cp
    return base_cp

def calculate_new_temperature(t_current, q_gain, q_loss, mass, specific_heat, dt_seconds=3600):
    """
    Calculates the new internal temperature after 1 hour (3600 seconds).
    Formula: ΔT = (Net Heat * Time) / (Mass * Specific Heat)
    Returns: New temperature in °C
    """
    # Net heat in Watts (Joules/second)
    q_net = q_gain - q_loss 
    
    # Total energy transferred over the time period (dt_seconds)
    total_energy_joules = q_net * dt_seconds
    
    # Thermal capacity of the shelter
    thermal_mass = mass * specific_heat
    
    if thermal_mass == 0:
        return t_current
        
    delta_t = total_energy_joules / thermal_mass
    return t_current + delta_t

@lru_cache(maxsize=None)
def calculate_convection_coefficient(wind_speed_kmh=50.0):
    """
    Calculates the external convective heat transfer coefficient (h_ext) in W/m²K
    based on outdoor wind speed using McAdams/Jurges forced convection correlation.
    Formula: 
      - v <= 5 m/s: h_ext = 5.7 + 3.8 * v
      - v > 5 m/s:  h_ext = 7.6 * (v ** 0.78)
    Ladakh winter winds (40-60 km/h = 11-17 m/s) -> h_ext ≈ 40-60 W/m²K.
    """
    v_ms = wind_speed_kmh / 3.6
    if v_ms <= 0:
        return 25.0
    elif v_ms <= 5.0:
        h_conv = 5.7 + 3.8 * v_ms
    else:
        h_conv = 7.6 * (v_ms ** 0.78)
    return max(25.0, float(h_conv))

@lru_cache(maxsize=None)
def calculate_external_surface_temp(t_inside, t_outside, r_value, h_ext=45.0):
    """
    Estimates the external surface temperature of the wall for IR stealth.
    Formula derived from steady-state heat flux: q = h_ext * (T_surf - T_out)
    h_ext = Convective heat transfer coefficient of winter wind.
    Default h_ext = 45 W/m²K (corresponding to Ladakh winter winds of 50-60 km/h).
    """
    if r_value <= 0:
        return t_outside
    
    # Calculate how warm the outside of the wall gets due to escaping heat
    t_surf = t_outside + (t_inside - t_outside) / (r_value * h_ext)
    return t_surf

# --- Material Database (Expanded for AI Optimizer) ---
# Values: [R-Value (m²K/W), Density (kg/m³), Specific Heat (J/kg·K), Cost (INR/kg)]
MATERIALS = {
    # === WALL MATERIALS ===
    "Concrete":                     {"r_value": 0.20, "density": 2400, "specific_heat": 840,  "cost_per_kg": 5},
    "Brick":                        {"r_value": 0.30, "density": 1900, "specific_heat": 840,  "cost_per_kg": 4},
    "Wood":                         {"r_value": 1.00, "density": 600,  "specific_heat": 1200, "cost_per_kg": 40},
    "Polyurethane Panel (PUF)":     {"r_value": 5.00, "density": 50,   "specific_heat": 1400, "cost_per_kg": 250},
    "Aerogel Composite":            {"r_value": 10.0, "density": 120,  "specific_heat": 1000, "cost_per_kg": 1800},
    "Kevlar Sandwich Panel":        {"r_value": 2.50, "density": 180,  "specific_heat": 1100, "cost_per_kg": 3500},
    "Carbon Fiber Panel":           {"r_value": 1.80, "density": 160,  "specific_heat": 800,  "cost_per_kg": 4000},
    "Stone Wool (Rockwool)":        {"r_value": 3.80, "density": 100,  "specific_heat": 840,  "cost_per_kg": 80},
    "EPS Foam (Thermocol)":         {"r_value": 3.50, "density": 25,   "specific_heat": 1300, "cost_per_kg": 120},
    "XPS Foam (Extruded)":          {"r_value": 4.20, "density": 35,   "specific_heat": 1350, "cost_per_kg": 150},
    "Fiberglass Batt":              {"r_value": 3.20, "density": 12,   "specific_heat": 700,  "cost_per_kg": 90},
    "Mud Brick (Adobe)":            {"r_value": 0.40, "density": 1500, "specific_heat": 900,  "cost_per_kg": 2},
    "Steel Sheet (Corrugated)":     {"r_value": 0.05, "density": 7800, "specific_heat": 500,  "cost_per_kg": 55},
    "Aluminium Composite":          {"r_value": 0.10, "density": 2700, "specific_heat": 900,  "cost_per_kg": 180},
    "Bamboo Composite":             {"r_value": 0.90, "density": 400,  "specific_heat": 1100, "cost_per_kg": 25},
    "HDPE Fabric (Heavy Duty)":     {"r_value": 0.60, "density": 150,  "specific_heat": 1800, "cost_per_kg": 200},
    "Nomex Honeycomb":              {"r_value": 2.00, "density": 48,   "specific_heat": 1200, "cost_per_kg": 5500},
    # === WINDOW / GLAZING MATERIALS ===
    "Glass (Single Pane)":          {"r_value": 0.15, "density": 2500, "specific_heat": 750,  "cost_per_kg": 60},
    "Glass (Double Pane)":          {"r_value": 0.35, "density": 2500, "specific_heat": 750,  "cost_per_kg": 120},
    "Polycarbonate Sheet":          {"r_value": 0.28, "density": 1200, "specific_heat": 1200, "cost_per_kg": 250},
    # === PHASE CHANGE MATERIALS (PCM) ===
    "PCM Bio-Wax Lining":           {"r_value": 1.20, "density": 850,  "specific_heat": 2100, "cost_per_kg": 350,
                                      "pcm_transition_temp": 18.0, "pcm_latent_heat": 200000, "pcm_active_cp": 14000},
}

# --- Integer-Indexed Material Lookup for Genetic Algorithm ---
MATERIAL_LIST = list(MATERIALS.keys())

# Materials suitable for walls (index -> name)
WALL_MATERIALS = [
    "Concrete", "Brick", "Wood", "Polyurethane Panel (PUF)",
    "Aerogel Composite", "Kevlar Sandwich Panel", "Carbon Fiber Panel",
    "Stone Wool (Rockwool)", "EPS Foam (Thermocol)", "XPS Foam (Extruded)",
    "Fiberglass Batt", "Mud Brick (Adobe)", "Steel Sheet (Corrugated)",
    "Aluminium Composite", "Bamboo Composite", "HDPE Fabric (Heavy Duty)",
    "Nomex Honeycomb",
    "PCM Bio-Wax Lining",
]

# Materials suitable for roofs (index -> name)
ROOF_MATERIALS = [
    "Concrete", "Wood", "Polyurethane Panel (PUF)", "Steel Sheet (Corrugated)",
    "EPS Foam (Thermocol)", "XPS Foam (Extruded)", "Fiberglass Batt",
    "Aluminium Composite", "Carbon Fiber Panel", "Nomex Honeycomb",
    "Stone Wool (Rockwool)", "Kevlar Sandwich Panel",
]

# Materials suitable for windows / glazing (index -> name)
WINDOW_MATERIALS = [
    "Glass (Single Pane)", "Glass (Double Pane)", "Polycarbonate Sheet",
]

@lru_cache(maxsize=None)
def calculate_metabolic_heat(occupants, watts_per_person=175):
    """
    Calculates the internal heat generated by human bodies.
    Default watts_per_person = 175W (Soldiers under high-altitude cold stress generate 150W-200W).
    Formula: Q = Number of people * Watts per person
    """
    return occupants * watts_per_person
@lru_cache(maxsize=None)
def calculate_ventilation_loss(t_inside, t_outside, volume, ach):
    """
    Calculates heat loss due to air exchange (ventilation).
    ACH = Air Changes per Hour
    Formula: Q = (ACH * Volume / 3600) * Air_Density * Air_Specific_Heat * ΔT
    """
    if t_inside <= t_outside:
        return 0
        
    # Standard values for high altitude (Ladakh ~4500m)
    air_density = 0.77  # kg/m^3 (thinner air at high altitude)
    air_specific_heat = 1005  # J/kg·K
    
    # Calculate cubic meters of air moved per second
    volume_per_second = (ach * volume) / 3600
    
    # Calculate heat lost to warming up the cold incoming air
    return volume_per_second * air_density * air_specific_heat * (t_inside - t_outside)