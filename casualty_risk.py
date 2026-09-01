"""
Service for predicting cold casualty risk (hypothermia and frostbite) 
based on NATO STANAG 2895 cold weather operational guidelines.
"""

def calculate_wind_chill(temp_c, wind_kmh):
    """
    Calculates Wind Chill Temperature (WCT).
    Formula from Joint Action Group for Temperature Indices.
    Valid for temps <= 10C and wind > 4.8 km/h.
    """
    if temp_c > 10.0 or wind_kmh <= 4.8:
        return temp_c
        
    wct = 13.12 + 0.6215 * temp_c - 11.37 * (wind_kmh ** 0.16) + 0.3965 * temp_c * (wind_kmh ** 0.16)
    return wct

def frostbite_risk(wind_chill_c):
    """
    Returns time to frostbite for exposed skin based on wind chill.
    """
    if wind_chill_c > -15:
        return {"risk": "Low", "time_min": float('inf'), "msg": "Low risk for > 30 mins"}
    elif wind_chill_c > -27:
        return {"risk": "Moderate", "time_min": 30, "msg": "Frostbite in 30 mins"}
    elif wind_chill_c > -35:
        return {"risk": "High", "time_min": 10, "msg": "Frostbite in 10 mins"}
    elif wind_chill_c > -45:
        return {"risk": "Severe", "time_min": 5, "msg": "Frostbite in 5 mins"}
    else:
        return {"risk": "Extreme", "time_min": 2, "msg": "Frostbite in < 2 mins"}

def daily_hypothermia_risk(min_temp, avg_temp, is_wet=False, inactive=True):
    """
    Calculates daily % risk of hypothermia for personnel inside the shelter.
    """
    # Base risk determined by minimum temperature experienced
    base_risk = 0.0
    
    if min_temp >= 5.0:
        base_risk = 0.0
    elif min_temp >= 0.0:
        base_risk = 2.0
    elif min_temp >= -5.0:
        base_risk = 5.0
    elif min_temp >= -10.0:
        base_risk = 15.0
    elif min_temp >= -20.0:
        base_risk = 40.0
    else:
        base_risk = 80.0
        
    # Modifiers
    if is_wet:
        base_risk += 20.0
    if inactive:
        base_risk += 15.0
        
    # Thermal recovery (if average is much higher than min)
    if avg_temp > 5.0:
        base_risk *= 0.5
        
    return min(100.0, max(0.0, base_risk))

def assess_casualty_risk_multi_day(daily_results, occupants=5):
    """
    Calculates cumulative risk over the 30-day deployment.
    """
    cumulative_risk = 0.0
    high_risk_days = 0
    
    for day in daily_results:
        daily_risk = daily_hypothermia_risk(day["min_temp"], day["avg_temp"], inactive=True)
        # Probability of NOT getting hypothermia
        prob_safe = 1.0 - (daily_risk / 100.0)
        # Cumulative probability of getting hypothermia
        cumulative_risk = 1.0 - ((1.0 - cumulative_risk) * prob_safe)
        
        if daily_risk > 10.0:
            high_risk_days += 1
            
    final_risk_pct = cumulative_risk * 100.0
    
    status = "SAFE"
    if final_risk_pct > 25.0:
        status = "CRITICAL RISK"
    elif final_risk_pct > 5.0:
        status = "WARNING"
        
    return {
        "cumulative_risk_pct": round(final_risk_pct, 1),
        "high_risk_days_count": high_risk_days,
        "status": status
    }
