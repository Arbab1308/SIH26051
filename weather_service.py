import math
import datetime
import requests
import numpy as np

def _generate_synthetic_weather(lat, lon, start_date, num_days, base_elevation=3500):
    """
    Generates synthetic weather for offline fallback based on Ladakh climate model.
    Produces deterministic but realistic diurnal and day-to-day variations.
    """
    # Deterministic generation for reproducibility based on location and date
    seed = int((abs(lat) + abs(lon) + start_date.timetuple().tm_yday) * 1000) % (2**32 - 1)
    np.random.seed(seed)
    
    hourly_data = []
    month = start_date.month
    
    # Base temps by month for Leh (~3500m)
    month_base_temps = {
        1: -12, 2: -9, 3: -3, 4: 4, 5: 8, 6: 12,
        7: 15, 8: 14, 9: 10, 10: 3, 11: -3, 12: -9
    }
    base_temp = month_base_temps.get(month, 0)
    
    for day in range(num_days):
        # Day to day variation
        day_base = base_temp + np.random.normal(0, 3.0) 
        
        # Diurnal swing
        diurnal_range = 12 if month in [12, 1, 2] else 15
        
        # Cloud cover (winter is clearer in Ladakh)
        cloud_base = 15 if month in [12, 1, 2] else 40
        cloud_day = max(0, min(100, cloud_base + np.random.normal(0, 15)))
        
        for hour in range(24):
            # Temp curve (lowest at 5 AM, highest at 2 PM / 14:00)
            temp_variation = -math.cos((hour - 5) * math.pi / 12) * (diurnal_range / 2)
            hour_temp = day_base + temp_variation
            
            # Wind (Weibull-like, stronger in afternoon)
            wind_base = 15 + np.random.normal(0, 5) # Base 15 km/h
            wind_diurnal = math.sin(max(0, hour - 8) * math.pi / 12) * 20 if 8 <= hour <= 20 else 0
            wind_speed = max(0, wind_base + wind_diurnal + np.random.normal(0, 5))
            
            # Very strong wind events (storms) - 5% chance per hour
            if np.random.random() < 0.05:
                wind_speed += np.random.uniform(20, 40)
            
            # Humidity
            rh = max(10, min(90, 40 + np.random.normal(0, 10) - (hour_temp * 0.5)))
            
            # Solar Irradiance raw (0 at night, peak at noon)
            solar = 0
            if 6 < hour < 18:
                # Max irradiance around 1000 W/m2 at zenith, reduced by cloud cover
                clear_sky_solar = max(0, math.sin((hour - 6) * math.pi / 12) * 1000)
                cloud_transmittance = 1.0 - (cloud_day / 100.0) * 0.75 # Clouds block up to 75%
                solar = clear_sky_solar * cloud_transmittance
                
            hourly_data.append({
                "day_idx": day,
                "hour": hour,
                "temperature_c": round(float(hour_temp), 1),
                "wind_speed_kmh": round(float(wind_speed), 1),
                "humidity_pct": round(float(rh), 1),
                "cloud_cover_pct": round(float(cloud_day), 1),
                "solar_irradiance_wm2": round(float(solar), 1)
            })
            
    return hourly_data

def fetch_weather(lat, lon, start_date, num_days=1, use_api=False):
    """
    Fetches weather data. 
    Tries Open-Meteo API (free, no key needed) first if use_api=True.
    Falls back gracefully to synthetic high-altitude model.
    """
    if use_api:
        try:
            # Open-Meteo API for real-time/forecast data
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,cloud_cover,direct_radiation"
                f"&timezone=auto&forecast_days={num_days}"
            )
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            hourly_data = []
            for i in range(num_days * 24):
                if i >= len(data["hourly"]["time"]):
                    break
                hourly_data.append({
                    "day_idx": i // 24,
                    "hour": i % 24,
                    "temperature_c": data["hourly"]["temperature_2m"][i],
                    "wind_speed_kmh": data["hourly"]["wind_speed_10m"][i],
                    "humidity_pct": data["hourly"]["relative_humidity_2m"][i],
                    "cloud_cover_pct": data["hourly"]["cloud_cover"][i],
                    "solar_irradiance_wm2": data["hourly"]["direct_radiation"][i]
                })
            return {
                "status": "ok",
                "source": "open_meteo_api",
                "hourly_data": hourly_data
            }
        except Exception as e:
            # Fallback to synthetic if API fails or no internet
            return {
                "status": "warning",
                "source": "synthetic_fallback",
                "error_msg": str(e),
                "hourly_data": _generate_synthetic_weather(lat, lon, start_date, num_days)
            }
            
    # Default to synthetic if API not requested
    return {
        "status": "ok",
        "source": "synthetic_fallback",
        "hourly_data": _generate_synthetic_weather(lat, lon, start_date, num_days)
    }
