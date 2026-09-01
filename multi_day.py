import numpy as np
from datetime import timedelta
from weather_service import fetch_weather
from solar_terrain import run_terrain_shadow_pipeline
from wind_load import run_wind_analysis
from failure_modes import MaterialDegradationTracker
from casualty_risk import assess_casualty_risk_multi_day
from physics import (
    calculate_heat_transfer,
    calculate_solar_gain,
    calculate_new_temperature,
    calculate_external_surface_temp,
    calculate_metabolic_heat,
    calculate_ventilation_loss,
    calculate_convection_coefficient,
    MATERIALS
)

def _simulate_single_day(config, weather_day, start_temp, solar_irradiance, day_idx):
    """
    Simulate a single 24-hour cycle.
    """
    wall_props = MATERIALS[config["wall_material"]]
    roof_props = MATERIALS[config["roof_material"]]
    window_props = MATERIALS[config["window_material"]]
    
    wall_area = config["wall_area"]
    roof_area = config["roof_area"]
    window_area = config["window_area"]
    door_area = config["door_area"]
    shelter_volume = config["volume"]
    ach = config["ach"]
    occupants = config["occupants"]
    metabolic_watts = config.get("metabolic_watts", 175) # Configurable
    
    # Calculate thermal mass
    total_mass = (wall_area * wall_props["density"] * 0.2 + 
                  roof_area * roof_props["density"] * 0.15)
    total_specific_heat = (wall_props["specific_heat"] + roof_props["specific_heat"]) / 2.0
    
    current_temp = start_temp
    
    hourly_temps = []
    hourly_outdoor = []
    hypo_hours = 0
    comfort_hours = 0
    heating_kwh = 0.0
    target_temp = config.get("target_temp", 5.0)
    
    for hour in range(24):
        # Extract hour data from weather_day
        # weather_day is a list of 24 dicts
        w_hour = weather_day[hour]
        t_out = w_hour["temperature_c"]
        wind_speed = w_hour["wind_speed_kmh"]
        solar = solar_irradiance[hour]
        
        hourly_outdoor.append(t_out)
        
        # Convection based on wind
        h_ext = calculate_convection_coefficient(wind_speed)
        t_surf = calculate_external_surface_temp(current_temp, t_out, wall_props["r_value"], h_ext)
        
        # Heat transfers
        q_wall = calculate_heat_transfer(current_temp, t_out, wall_area, wall_props["r_value"])
        q_roof = calculate_heat_transfer(current_temp, t_out, roof_area, roof_props["r_value"])
        q_window_loss = calculate_heat_transfer(current_temp, t_out, window_area, window_props["r_value"])
        q_door = calculate_heat_transfer(current_temp, t_out, door_area, 0.1)
        q_vent = calculate_ventilation_loss(current_temp, t_out, shelter_volume, ach)
        
        q_human = calculate_metabolic_heat(occupants, watts_per_person=metabolic_watts)
        q_solar = calculate_solar_gain(solar, window_area, absorptivity=0.7)
        
        q_total_loss = q_wall + q_roof + q_window_loss + q_door + q_vent
        q_total_gain = q_solar + q_human
        
        # Auxiliary heating if temp drops below target
        q_aux = 0
        if current_temp < target_temp:
            # Need to add enough heat to reach target temp (simplified to offset loss)
            # A true thermostat would calculate required energy to raise temp
            q_aux = max(0, q_total_loss - q_total_gain)
            heating_kwh += (q_aux / 1000.0) # W to kWh for 1 hour
            q_total_gain += q_aux
            
        current_temp = calculate_new_temperature(
            current_temp, q_total_gain, q_total_loss, total_mass, total_specific_heat
        )
        
        hourly_temps.append(current_temp)
        
        if current_temp < -20.0:
            hypo_hours += 1
        if current_temp >= target_temp:
            comfort_hours += 1
            
    min_temp = min(hourly_temps)
    max_temp = max(hourly_temps)
    avg_temp = sum(hourly_temps) / 24.0
    
    # Check freeze-thaw
    freeze_thaw = False
    if min(hourly_outdoor) < -10 and max(hourly_outdoor) > -5:
        freeze_thaw = True
        
    return {
        "day_idx": day_idx,
        "hourly_temps": hourly_temps,
        "hourly_outdoor": hourly_outdoor,
        "min_temp": min_temp,
        "max_temp": max_temp,
        "avg_temp": avg_temp,
        "hypothermia_hours": hypo_hours,
        "comfort_hours": comfort_hours,
        "daily_delta_t": max_temp - min_temp,
        "freeze_thaw_event": freeze_thaw,
        "heating_kwh": heating_kwh,
        "end_temp": current_temp
    }


def run_multi_day_simulation(config, num_days=30, use_api=False):
    """
    Orchestrates the multi-day simulation by fetching weather, running terrain 
    shadow pipeline daily, and computing physics and wind loads.
    """
    lat = config["lat"]
    lon = config["lon"]
    start_date = config["start_date"]
    
    weather_resp = fetch_weather(lat, lon, start_date, num_days, use_api=use_api)
    all_weather_data = weather_resp["hourly_data"]
    
    daily_results = []
    current_temp = config.get("initial_temp", -5.0)
    
    # Initialize Failure Mode Tracker
    degradation_tracker = MaterialDegradationTracker(config["wall_material"], config["roof_material"])
    
    # Track overall metrics
    total_hypo = 0
    total_heating = 0
    wind_analysis_results = []
    
    for day in range(num_days):
        day_date = start_date + timedelta(days=day)
        
        # Extract 24h weather for this day
        start_idx = day * 24
        end_idx = start_idx + 24
        day_weather = all_weather_data[start_idx:end_idx]
        
        # Terrain Shadow mapping for this specific day
        raw_irradiance = np.array([h["solar_irradiance_wm2"] for h in day_weather])
        
        terrain_result = run_terrain_shadow_pipeline(
            lat=lat, lon=lon, date=day_date, 
            base_irradiance=raw_irradiance,
            radius_km=config.get("terrain_radius_km", 5.0),
            diffuse_fraction=config.get("diffuse_fraction", 0.10)
        )
        
        solar_irradiance = terrain_result["modified_irradiance"]
        
        # Physics simulation for 1 day
        day_res = _simulate_single_day(config, day_weather, current_temp, solar_irradiance, day)
        current_temp = day_res["end_temp"]
        
        # Wind load analysis
        wind_speeds = [h["wind_speed_kmh"] for h in day_weather]
        wind_res = run_wind_analysis(config, wind_speeds)
        day_res["wind_analysis"] = wind_res
        
        # Update trackers
        total_hypo += day_res["hypothermia_hours"]
        total_heating += day_res["heating_kwh"]
        wind_analysis_results.append(wind_res)
        
        # Track Material Degradation
        degradation_tracker.update(day_res, day)
        
        daily_results.append(day_res)
        
    casualty_res = assess_casualty_risk_multi_day(daily_results, config.get("occupants", 5))
        
    return {
        "status": "ok",
        "weather_source": weather_resp["source"],
        "num_days": num_days,
        "daily_results": daily_results,
        "summary": {
            "total_hypothermia_hours": total_hypo,
            "total_heating_kwh": total_heating,
            "avg_min_temp": sum(d["min_temp"] for d in daily_results) / num_days,
            "avg_max_temp": sum(d["max_temp"] for d in daily_results) / num_days,
            "max_wind_kmh": max(w["max_wind_kmh"] for w in wind_analysis_results)
        },
        "casualty_risk": casualty_res,
        "material_failures": degradation_tracker.get_failures()
    }
