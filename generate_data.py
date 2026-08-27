
import pandas as pd
import numpy as np

def generate_ladakh_winter_day():
    hours = np.arange(24)
    
    # FIXED: Plus sign ensures 2 PM (Hour 14) is the warmest (-5°C) and 2 AM is the coldest (-20°C)
    temp = -12.5 + 7.5 * np.cos((hours - 14) * (2 * np.pi / 24))
    
    # Solar Irradiance: Sunrise 7 AM, peaks noon ~1000 W/m², sunset 5 PM
    solar = np.zeros(24)
    daytime = (hours >= 7) & (hours <= 17)
    solar[daytime] = 1000 * np.sin((hours[daytime] - 7) * (np.pi / 10))
    
    # Humidity (optional but realistic)
    humidity = np.random.uniform(30, 60, 24)
    
    df = pd.DataFrame({
        "Hour": hours,
        "Temperature_C": np.round(temp, 1),
        "Solar_Irradiance_W_m2": np.round(solar, 1),
        "Humidity_Percent": np.round(humidity, 1)
    })
    
    df.to_csv("ladakh_winter.csv", index=False)
    print("✓ ladakh_winter.csv generated successfully!")

if __name__ == "__main__":
    generate_ladakh_winter_day()