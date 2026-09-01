import math

"""
Service for calculating structural wind load and stress on shelter materials.
Uses principles of structural engineering and simply-supported beam models.
"""

MATERIAL_STRUCTURAL = {
    # Walls
    "Concrete":              {"tensile_mpa": 3.5,   "compressive_mpa": 30,  "thickness_m": 0.20},
    "Brick":                 {"tensile_mpa": 1.5,   "compressive_mpa": 15,  "thickness_m": 0.20},
    "Wood":                  {"tensile_mpa": 40.0,  "compressive_mpa": 25,  "thickness_m": 0.10},
    "Polyurethane Panel (PUF)": {"tensile_mpa": 0.35,  "compressive_mpa": 0.2, "thickness_m": 0.10},
    "Aerogel Composite":     {"tensile_mpa": 0.8,   "compressive_mpa": 1.5, "thickness_m": 0.05},
    "Kevlar Sandwich Panel": {"tensile_mpa": 3600.0,"compressive_mpa": 350, "thickness_m": 0.02},
    "Carbon Fiber Panel":    {"tensile_mpa": 3500.0,"compressive_mpa": 570, "thickness_m": 0.01},
    "Stone Wool (Rockwool)": {"tensile_mpa": 0.05,  "compressive_mpa": 0.1, "thickness_m": 0.15},
    "EPS Foam (Thermocol)":  {"tensile_mpa": 0.15,  "compressive_mpa": 0.1, "thickness_m": 0.15},
    "XPS Foam (Extruded)":   {"tensile_mpa": 0.30,  "compressive_mpa": 0.25,"thickness_m": 0.10},
    "Fiberglass Batt":       {"tensile_mpa": 0.02,  "compressive_mpa": 0.02,"thickness_m": 0.15},
    "Mud Brick (Adobe)":     {"tensile_mpa": 0.5,   "compressive_mpa": 5.0, "thickness_m": 0.30},
    "Steel Sheet (Corrugated)": {"tensile_mpa": 400.0, "compressive_mpa": 250, "thickness_m": 0.002},
    "Aluminium Composite":   {"tensile_mpa": 150.0, "compressive_mpa": 100, "thickness_m": 0.005},
    "Bamboo Composite":      {"tensile_mpa": 100.0, "compressive_mpa": 50,  "thickness_m": 0.05},
    "HDPE Fabric (Heavy Duty)": {"tensile_mpa": 25.0,  "compressive_mpa": 10,  "thickness_m": 0.005},
    "Nomex Honeycomb":       {"tensile_mpa": 50.0,  "compressive_mpa": 40,  "thickness_m": 0.05},
    
    # Windows
    "Glass (Single Pane)":   {"tensile_mpa": 40.0,  "compressive_mpa": 1000,"thickness_m": 0.006},
    "Glass (Double Pane)":   {"tensile_mpa": 40.0,  "compressive_mpa": 1000,"thickness_m": 0.012},
    "Polycarbonate Sheet":   {"tensile_mpa": 60.0,  "compressive_mpa": 80,  "thickness_m": 0.005},
}

def calculate_wind_force(wind_speed_kmh, area_m2, drag_coeff=1.3, altitude_m=4500):
    """
    Calculates the total wind force in Newtons.
    F = 0.5 * rho * v^2 * A * Cd
    rho (air density) decreases with altitude.
    """
    # Standard atmosphere approximation for density
    # Sea level ~ 1.225 kg/m^3
    rho = max(0.4, 1.225 * math.exp(-0.00012 * altitude_m))
    
    v_ms = wind_speed_kmh / 3.6
    force = 0.5 * rho * (v_ms ** 2) * area_m2 * drag_coeff
    return force

def calculate_material_stress(force_newtons, area_m2, thickness_m, span_m=3.0):
    """
    Calculates bending stress on the material panel.
    Assuming simply supported beam model for panels.
    Stress (MPa) = 0.75 * Pressure * (Span / Thickness)^2 / 1,000,000
    """
    if thickness_m <= 0 or area_m2 <= 0:
        return float('inf')
        
    pressure_pa = force_newtons / area_m2
    stress_pa = 0.75 * pressure_pa * ((span_m / thickness_m) ** 2)
    stress_mpa = stress_pa / 1_000_000.0
    return stress_mpa

def get_max_safe_wind(material_name, span_m=3.0, drag_coeff=1.3, altitude_m=4500):
    """
    Finds the maximum safe wind speed (km/h) for a given material before Factor of Safety (FoS) < 1.5.
    """
    if material_name not in MATERIAL_STRUCTURAL:
        return 100.0 # Default if unknown
        
    props = MATERIAL_STRUCTURAL[material_name]
    ultimate_tensile = props["tensile_mpa"]
    thickness = props["thickness_m"]
    
    # Max allowable stress (FoS = 1.5)
    max_stress_mpa = ultimate_tensile / 1.5
    max_stress_pa = max_stress_mpa * 1_000_000.0
    
    if span_m <= 0 or thickness <= 0:
        return 0.0
        
    max_pressure = max_stress_pa / (0.75 * ((span_m / thickness) ** 2))
    
    rho = max(0.4, 1.225 * math.exp(-0.00012 * altitude_m))
    
    if rho <= 0 or drag_coeff <= 0:
        return float('inf')
        
    v_ms_squared = max_pressure / (0.5 * rho * drag_coeff)
    if v_ms_squared <= 0:
        return 0.0
        
    v_ms = math.sqrt(v_ms_squared)
    v_kmh = v_ms * 3.6
    return v_kmh

def run_wind_analysis(shelter_config, hourly_wind_speeds):
    """
    Runs wind analysis for a given set of wind speeds over the simulation.
    Returns peak stress, warnings, and safety factors.
    """
    wall_mat = shelter_config.get("wall_material", "Brick")
    roof_mat = shelter_config.get("roof_material", "Polyurethane Panel (PUF)")
    
    wall_area = shelter_config.get("wall_area", 40)
    roof_area = shelter_config.get("roof_area", 24)
    altitude = shelter_config.get("altitude_m", 4500)
    
    wall_safe_wind = get_max_safe_wind(wall_mat, span_m=3.0, drag_coeff=1.3, altitude_m=altitude)
    roof_safe_wind = get_max_safe_wind(roof_mat, span_m=3.0, drag_coeff=0.8, altitude_m=altitude)
    
    max_wind_experienced = max(hourly_wind_speeds) if hourly_wind_speeds else 0
    
    warnings = []
    status = "Safe"
    
    if max_wind_experienced >= wall_safe_wind:
        warnings.append(f"Wall material ({wall_mat}) failure risk! Safe limit: {wall_safe_wind:.1f} km/h")
        status = "Failure Risk"
    elif max_wind_experienced >= wall_safe_wind * 0.8:
        warnings.append(f"Wall material ({wall_mat}) approaching wind limit ({wall_safe_wind:.1f} km/h)")
        if status == "Safe": status = "Marginal"
        
    if max_wind_experienced >= roof_safe_wind:
        warnings.append(f"Roof material ({roof_mat}) failure risk! Safe limit: {roof_safe_wind:.1f} km/h")
        status = "Failure Risk"
    elif max_wind_experienced >= roof_safe_wind * 0.8:
        warnings.append(f"Roof material ({roof_mat}) approaching wind limit ({roof_safe_wind:.1f} km/h)")
        if status == "Safe": status = "Marginal"
        
    # Calculate peak stress for the max wind
    wall_props = MATERIAL_STRUCTURAL.get(wall_mat, {"tensile_mpa": 1.0, "thickness_m": 0.1})
    roof_props = MATERIAL_STRUCTURAL.get(roof_mat, {"tensile_mpa": 1.0, "thickness_m": 0.1})
    
    wall_force = calculate_wind_force(max_wind_experienced, wall_area, 1.3, altitude)
    wall_stress = calculate_material_stress(wall_force, wall_area, wall_props["thickness_m"], 3.0)
    
    roof_force = calculate_wind_force(max_wind_experienced, roof_area, 0.8, altitude)
    roof_stress = calculate_material_stress(roof_force, roof_area, roof_props["thickness_m"], 3.0)
    
    return {
        "max_wind_kmh": round(max_wind_experienced, 1),
        "wall_safe_limit_kmh": round(wall_safe_wind, 1),
        "roof_safe_limit_kmh": round(roof_safe_wind, 1),
        "peak_wall_stress_mpa": round(wall_stress, 3),
        "peak_roof_stress_mpa": round(roof_stress, 3),
        "status": status,
        "warnings": warnings
    }
