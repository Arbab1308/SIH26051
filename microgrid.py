"""
Tactical Microgrid & Off-Grid Solar Sizer
==========================================
Production-grade engine for sizing autonomous solar+battery microgrids
for military shelters in extreme cold, high-altitude environments.

Accounts for:
  - Hourly heating deficit calculation (Watts gap to maintain target temp)
  - Altitude derating of PV panels (reduced air mass at 3500m+)
  - Cold-weather battery capacity derating (Li-ion loses ~20% at -20°C)
  - Depth-of-Discharge limits (80% usable capacity for cycle life)
  - Round-trip battery efficiency losses (charge/discharge ~92%)
  - Inverter + Balance-of-System (BOS) losses (~85%)
  - Multi-day autonomy sizing (configurable backup days without sun)
  - 24-hour Battery State-of-Charge (SoC) simulation
  - Peak demand analysis for inverter/generator sizing
  - Full system cost estimation (INR)
"""

import numpy as np
from physics import (
    calculate_heat_transfer,
    calculate_solar_gain,
    calculate_metabolic_heat,
    calculate_ventilation_loss,
)


# ─── System Constants ──────────────────────────────────────────────────────────

# Solar PV
PV_EFFICIENCY = 0.20           # 20% — standard monocrystalline panel
PV_ALTITUDE_BOOST = 1.08       # +8% irradiance at 3500m+ due to thinner atmosphere
PV_TEMP_COEFF = -0.004         # -0.4%/°C power loss above 25°C STC
PV_SOILING_FACTOR = 0.95       # 5% loss from dust/snow on panels
PV_COST_PER_M2 = 8000          # INR/m² installed (panels + mounting + wiring)

# Battery (48V LFP — Lithium Iron Phosphate, military-grade)
BATTERY_VOLTAGE = 48.0         # Volts — standard military DC bus
BATTERY_DOD = 0.80             # 80% Depth of Discharge (protect cycle life)
BATTERY_ROUND_TRIP_EFF = 0.92  # 92% round-trip charge/discharge efficiency
BATTERY_COST_PER_KWH = 12000   # INR/kWh installed
BATTERY_COLD_DERATING = {      # Capacity retention vs. ambient temperature
    -30: 0.60,   # 60% capacity at -30°C
    -20: 0.70,   # 70% at -20°C
    -10: 0.80,   # 80% at -10°C
      0: 0.90,   # 90% at 0°C
     10: 0.95,
     25: 1.00,   # 100% at STC (25°C)
}

# Inverter + Balance-of-System
INVERTER_EFFICIENCY = 0.93     # 93% — high-quality pure sine wave inverter
BOS_EFFICIENCY = 0.97          # 97% — wiring, fuses, charge controller losses
SYSTEM_EFFICIENCY = INVERTER_EFFICIENCY * BOS_EFFICIENCY  # ~90.2%
INVERTER_COST_PER_KW = 5000    # INR/kW

# Diesel Generator Fallback (for comparison)
DIESEL_CONSUMPTION_L_PER_KWH = 0.35   # Litres of diesel per kWh generated
DIESEL_COST_PER_LITRE = 120            # INR — military supply chain cost at altitude


# ─── Core Calculations ─────────────────────────────────────────────────────────

def _interpolate_cold_derating(temp_c):
    """
    Interpolate battery capacity derating factor for a given temperature.
    Uses linear interpolation between the defined breakpoints.
    """
    temps = sorted(BATTERY_COLD_DERATING.keys())
    values = [BATTERY_COLD_DERATING[t] for t in temps]

    if temp_c <= temps[0]:
        return values[0]
    if temp_c >= temps[-1]:
        return values[-1]

    for i in range(len(temps) - 1):
        if temps[i] <= temp_c <= temps[i + 1]:
            frac = (temp_c - temps[i]) / (temps[i + 1] - temps[i])
            return values[i] + frac * (values[i + 1] - values[i])

    return values[-1]


def calculate_heating_deficit(t_target, outdoor_temps, solar_irradiance,
                              wall_area, wall_r, roof_area, roof_r,
                              window_area, window_r, door_area, door_r,
                              volume, ach, occupants):
    """
    Calculate the exact electrical heating power required (Watts) for each hour
    to maintain the shelter at a strict target temperature.

    The auxiliary heater must supply: Q_aux = max(0, Q_loss - Q_natural_gain)

    Args:
        t_target: Target minimum internal temperature (°C)
        outdoor_temps: numpy array of 24 outdoor temperatures
        solar_irradiance: numpy array of 24 solar irradiance values (W/m²)
        wall_area, wall_r, roof_area, roof_r, etc.: shelter geometry + R-values
        volume: shelter volume (m³)
        ach: air changes per hour
        occupants: number of troops

    Returns:
        dict with:
            'q_aux_hourly': list of 24 floats (Watts per hour)
            'q_loss_hourly': list of 24 floats (total thermal losses)
            'q_gain_hourly': list of 24 floats (natural thermal gains)
            'peak_demand_w': float (maximum instantaneous heater power)
            'total_heating_wh': float (cumulative energy over 24h)
            'total_heating_kwh': float
    """
    q_aux_hourly = []
    q_loss_hourly = []
    q_gain_hourly = []

    for hour in range(24):
        t_out = outdoor_temps[hour]
        solar = solar_irradiance[hour]

        # --- Thermal losses (assuming room is held at t_target) ---
        q_wall = calculate_heat_transfer(t_target, t_out, wall_area, wall_r)
        q_roof = calculate_heat_transfer(t_target, t_out, roof_area, roof_r)
        q_window = calculate_heat_transfer(t_target, t_out, window_area, window_r)
        q_door = calculate_heat_transfer(t_target, t_out, door_area, door_r)
        q_vent = calculate_ventilation_loss(t_target, t_out, volume, ach)

        q_total_loss = q_wall + q_roof + q_window + q_door + q_vent

        # --- Natural heat gains ---
        q_solar = calculate_solar_gain(solar, window_area, absorptivity=0.7)
        q_human = calculate_metabolic_heat(occupants)
        q_total_gain = q_solar + q_human

        # --- Heating deficit: the heater covers the gap ---
        q_aux = max(0.0, q_total_loss - q_total_gain)

        q_aux_hourly.append(q_aux)
        q_loss_hourly.append(q_total_loss)
        q_gain_hourly.append(q_total_gain)

    total_heating_wh = sum(q_aux_hourly)  # Each entry is Watts × 1 hour = Wh

    return {
        "q_aux_hourly": q_aux_hourly,
        "q_loss_hourly": q_loss_hourly,
        "q_gain_hourly": q_gain_hourly,
        "peak_demand_w": max(q_aux_hourly),
        "total_heating_wh": total_heating_wh,
        "total_heating_kwh": total_heating_wh / 1000.0,
    }


def size_solar_array(total_heating_wh, solar_irradiance, avg_outdoor_temp):
    """
    Size the solar PV array (m²) needed to generate enough energy to cover
    the daily heating load, accounting for altitude boost, temperature
    derating, soiling, and system losses.

    Args:
        total_heating_wh: Total daily heating energy required (Wh)
        solar_irradiance: numpy array of 24 hourly irradiance values (W/m²)
        avg_outdoor_temp: Average outdoor temperature for PV temp derating

    Returns:
        dict with:
            'pv_area_m2': required panel area
            'pv_peak_kw': peak array output (kWp)
            'daily_yield_kwh_per_m2': effective energy per m² per day
            'pv_cost_inr': estimated procurement cost
    """
    # Total solar energy available per m² of panel per day (Wh/m²)
    raw_insolation = sum(solar_irradiance)  # Wh/m² (1 W/m² for 1 hour)

    # Apply altitude boost (thinner atmosphere = more direct irradiance)
    altitude_adjusted = raw_insolation * PV_ALTITUDE_BOOST

    # Temperature derating: panels lose efficiency when cold panel temp
    # deviates from STC (25°C). At high altitude, panels are often colder
    # than STC, which actually *helps* — but we model conservatively.
    panel_temp_est = avg_outdoor_temp + 15  # Panel runs ~15°C above ambient
    temp_delta = panel_temp_est - 25.0
    temp_factor = 1.0 + (PV_TEMP_COEFF * temp_delta)
    temp_factor = max(0.5, min(1.2, temp_factor))  # Clamp to sane range

    # Effective energy yield per m²
    effective_per_m2 = (
        altitude_adjusted
        * PV_EFFICIENCY
        * temp_factor
        * PV_SOILING_FACTOR
        * SYSTEM_EFFICIENCY
    )

    # Account for battery round-trip losses (energy stored then retrieved)
    effective_per_m2_net = effective_per_m2 * BATTERY_ROUND_TRIP_EFF

    # Size the array
    if effective_per_m2_net > 0:
        pv_area = total_heating_wh / effective_per_m2_net
    else:
        pv_area = 0.0

    # Peak kilowatt rating (at 1000 W/m² STC)
    pv_peak_kw = pv_area * PV_EFFICIENCY * 1.0  # kWp per m² at STC

    return {
        "pv_area_m2": max(0.0, pv_area),
        "pv_peak_kw": max(0.0, pv_peak_kw),
        "daily_yield_kwh_per_m2": effective_per_m2_net / 1000.0,
        "pv_cost_inr": max(0.0, pv_area) * PV_COST_PER_M2,
    }


def size_battery_bank(total_heating_kwh, avg_outdoor_temp, autonomy_days=1.5):
    """
    Size the 48V LFP battery bank, accounting for cold-weather derating,
    depth-of-discharge limits, and multi-day autonomy.

    Args:
        total_heating_kwh: Daily heating load (kWh)
        avg_outdoor_temp: Average outdoor temperature (°C) for cold derating
        autonomy_days: Number of days the battery must sustain without sun

    Returns:
        dict with:
            'battery_kwh_gross': total gross capacity needed
            'battery_kwh_usable': usable capacity after DoD + derating
            'battery_ah_48v': Amp-hours at 48V
            'cold_derating_factor': applied capacity penalty
            'battery_cost_inr': estimated procurement cost
    """
    cold_factor = _interpolate_cold_derating(avg_outdoor_temp)

    # Energy the battery must deliver (accounting for autonomy)
    energy_needed_kwh = total_heating_kwh * autonomy_days

    # Gross capacity = needed / (DoD × cold_derating × round_trip_eff)
    if BATTERY_DOD * cold_factor * BATTERY_ROUND_TRIP_EFF > 0:
        gross_kwh = energy_needed_kwh / (
            BATTERY_DOD * cold_factor * BATTERY_ROUND_TRIP_EFF
        )
    else:
        gross_kwh = 0.0

    # Convert to Amp-hours at 48V
    ah_48v = (gross_kwh * 1000.0) / BATTERY_VOLTAGE

    return {
        "battery_kwh_gross": gross_kwh,
        "battery_kwh_usable": energy_needed_kwh,
        "battery_ah_48v": ah_48v,
        "cold_derating_factor": cold_factor,
        "battery_cost_inr": gross_kwh * BATTERY_COST_PER_KWH,
    }


def simulate_battery_soc(q_aux_hourly, solar_irradiance, pv_area_m2,
                          battery_kwh_gross, avg_outdoor_temp):
    """
    Simulate the battery State-of-Charge (SoC) over a 24-hour cycle.
    Starts at 100% SoC. Solar charges during daytime, heater discharges.

    Args:
        q_aux_hourly: list of 24 heater demands (Watts)
        solar_irradiance: numpy array of 24 irradiance values (W/m²)
        pv_area_m2: installed PV area (m²)
        battery_kwh_gross: total gross battery capacity (kWh)
        avg_outdoor_temp: for temperature derating

    Returns:
        dict with:
            'soc_hourly': list of 25 floats (SoC % from hour 0 to 24)
            'min_soc': minimum SoC reached (%)
            'solar_gen_hourly': list of 24 PV generation values (Wh)
            'surplus_hourly': list of 24 surplus/deficit values (Wh, positive = surplus)
    """
    cold_factor = _interpolate_cold_derating(avg_outdoor_temp)
    usable_capacity_wh = battery_kwh_gross * 1000.0 * BATTERY_DOD * cold_factor

    # Panel temp estimation for derating
    panel_temp_est = avg_outdoor_temp + 15
    temp_delta = panel_temp_est - 25.0
    temp_factor = 1.0 + (PV_TEMP_COEFF * temp_delta)
    temp_factor = max(0.5, min(1.2, temp_factor))

    # Start at 100% SoC
    current_energy_wh = usable_capacity_wh
    soc_hourly = [100.0]
    solar_gen_hourly = []
    surplus_hourly = []

    for hour in range(24):
        # PV generation this hour
        pv_gen = (
            solar_irradiance[hour]
            * pv_area_m2
            * PV_EFFICIENCY
            * PV_ALTITUDE_BOOST
            * temp_factor
            * PV_SOILING_FACTOR
            * SYSTEM_EFFICIENCY
        )  # Watts × 1 hour = Wh

        # Heater consumption this hour (accounting for inverter losses)
        heater_draw = q_aux_hourly[hour] / SYSTEM_EFFICIENCY  # Wh from battery

        # Net energy flow: positive = charging, negative = discharging
        net_flow = pv_gen - heater_draw
        surplus_hourly.append(net_flow)
        solar_gen_hourly.append(pv_gen)

        # Update battery (clamp to 0–100% usable)
        current_energy_wh += net_flow * BATTERY_ROUND_TRIP_EFF if net_flow > 0 else net_flow
        current_energy_wh = max(0.0, min(usable_capacity_wh, current_energy_wh))

        soc_pct = (current_energy_wh / usable_capacity_wh * 100.0) if usable_capacity_wh > 0 else 0.0
        soc_hourly.append(soc_pct)

    return {
        "soc_hourly": soc_hourly,
        "min_soc": min(soc_hourly),
        "solar_gen_hourly": solar_gen_hourly,
        "surplus_hourly": surplus_hourly,
    }


def calculate_diesel_fallback(total_heating_kwh):
    """
    Calculate diesel generator requirements for comparison.
    Shows the operational cost the solar microgrid replaces.

    Returns:
        dict with diesel_litres_per_day, diesel_cost_per_day, diesel_cost_30_days
    """
    litres = total_heating_kwh * DIESEL_CONSUMPTION_L_PER_KWH
    daily_cost = litres * DIESEL_COST_PER_LITRE

    return {
        "diesel_litres_per_day": litres,
        "diesel_cost_per_day": daily_cost,
        "diesel_cost_30_days": daily_cost * 30,
    }


# ─── Full Pipeline ─────────────────────────────────────────────────────────────

def run_microgrid_analysis(t_target, outdoor_temps, solar_irradiance,
                           wall_area, wall_r, roof_area, roof_r,
                           window_area, window_r, door_area, door_r,
                           volume, ach, occupants, autonomy_days=1.5):
    """
    Execute the complete microgrid sizing pipeline.

    1. Calculate hourly heating deficit
    2. Size the solar PV array
    3. Size the battery bank
    4. Simulate 24h battery SoC
    5. Compute diesel fallback for comparison
    6. Estimate total system cost

    Returns:
        dict with all sub-results merged, plus:
            'inverter_kw': recommended inverter size
            'inverter_cost_inr': inverter cost
            'total_system_cost_inr': PV + battery + inverter
            'diesel_savings_30d': monthly savings vs diesel
    """
    avg_temp = float(np.mean(outdoor_temps))

    # 1. Heating deficit
    deficit = calculate_heating_deficit(
        t_target, outdoor_temps, solar_irradiance,
        wall_area, wall_r, roof_area, roof_r,
        window_area, window_r, door_area, door_r,
        volume, ach, occupants,
    )

    # 2. Solar PV sizing
    pv = size_solar_array(
        deficit["total_heating_wh"], solar_irradiance, avg_temp
    )

    # 3. Battery sizing
    battery = size_battery_bank(
        deficit["total_heating_kwh"], avg_temp, autonomy_days
    )

    # 4. SoC simulation
    soc = simulate_battery_soc(
        deficit["q_aux_hourly"], solar_irradiance,
        pv["pv_area_m2"], battery["battery_kwh_gross"], avg_temp,
    )

    # 5. Diesel fallback
    diesel = calculate_diesel_fallback(deficit["total_heating_kwh"])

    # 6. Inverter sizing (20% headroom above peak demand)
    inverter_kw = (deficit["peak_demand_w"] / 1000.0) * 1.20
    inverter_cost = inverter_kw * INVERTER_COST_PER_KW

    # Total system cost
    total_cost = pv["pv_cost_inr"] + battery["battery_cost_inr"] + inverter_cost

    return {
        **deficit,
        **pv,
        **battery,
        **soc,
        **diesel,
        "autonomy_days": autonomy_days,
        "avg_outdoor_temp": avg_temp,
        "inverter_kw": inverter_kw,
        "inverter_cost_inr": inverter_cost,
        "total_system_cost_inr": total_cost,
        "diesel_savings_30d": diesel["diesel_cost_30_days"],
    }
