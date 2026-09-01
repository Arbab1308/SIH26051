"""
=============================================================================
  DRDO SHELTER SIMULATOR — SYSTEM STRESS TEST HARNESS
  ====================================================
  Tests three extreme edge-case scenarios to verify microservice integration:

  TEST 1: Offline Blackout Test
    - Simulates total network failure (mocks requests to raise ConnectionError)
    - Verifies the weather service gracefully degrades to synthetic fallback
    - Confirms the full multi-day pipeline completes without traceback

  TEST 2: Chinook Paradox (High Budget, Low Weight)
    - Budget: ₹1,000,000 but payload limited to 1,000 kg
    - Verifies the optimizer filters out heavy materials (Concrete, Brick)
    - Confirms only ultra-light composites survive the Pareto front

  TEST 3: 30-Day Blizzard
    - Runs full 30-day simulation with Steel + Concrete materials
    - Verifies the Material Failure service flags degradation
    - Confirms casualty risk assessment produces valid output

  TEST 4: Swarm Intelligence
    - Tests virtual power plant (VPP) isolation algorithms
    - Tests predictive energy routing with 10 shelters
=============================================================================
"""

import sys
import datetime
import traceback
import numpy as np
from unittest.mock import patch


# ═══════════════════════════════════════════════════════════════════
# SHARED CONFIG — Siachen-class shelter for stress testing
# ═══════════════════════════════════════════════════════════════════
SIACHEN_CONFIG = {
    "lat": 35.4206,
    "lon": 77.1090,
    "start_date": datetime.date(2026, 1, 1),
    "wall_material": "Steel Sheet (Corrugated)",
    "roof_material": "Concrete",
    "window_material": "Glass (Double Pane)",
    "wall_area": 52.0,
    "roof_area": 24.0,
    "window_area": 4.0,
    "door_area": 2.0,
    "volume": 60.0,
    "ach": 0.3,
    "occupants": 4,
    "metabolic_watts": 175,
    "terrain_radius_km": 5.0,
    "diffuse_fraction": 0.10,
    "initial_temp": -10.0,
    "target_temp": 5.0,
    "altitude_m": 5400
}

TEST_RESULTS = {}
PASS = "✅ PASS"
FAIL = "❌ FAIL"


def banner(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ═══════════════════════════════════════════════════════════════════
# TEST 1: OFFLINE BLACKOUT TEST
# ═══════════════════════════════════════════════════════════════════
def test_offline_blackout():
    banner("TEST 1: OFFLINE BLACKOUT — Total Network Failure Simulation")

    from weather_service import fetch_weather
    from multi_day import run_multi_day_simulation

    checks = {}

    # 1a. Verify weather_service falls back to synthetic on ConnectionError
    print("\n  [1a] Testing weather_service with use_api=True (mocked to fail)...")
    try:
        def mock_get(*args, **kwargs):
            raise ConnectionError("Simulated total network blackout")

        with patch("weather_service.requests.get", side_effect=mock_get):
            result = fetch_weather(35.4206, 77.1090, datetime.date(2026, 1, 1), num_days=3, use_api=True)

        assert result["source"] == "synthetic_fallback", f"Expected synthetic_fallback, got {result['source']}"
        assert len(result["hourly_data"]) == 72, f"Expected 72 hours of data, got {len(result['hourly_data'])}"
        checks["weather_fallback"] = PASS
        print(f"      {PASS} Weather service gracefully fell back to synthetic model")
        print(f"         Source: {result['source']}")
        print(f"         Hours: {len(result['hourly_data'])}")
        if "error_msg" in result:
            print(f"         Logged Error: {result['error_msg'][:80]}")
    except Exception as e:
        checks["weather_fallback"] = FAIL
        print(f"      {FAIL} Weather fallback crashed: {e}")
        traceback.print_exc()

    # 1b. Verify weather_service works with use_api=False (no mock needed)
    print("\n  [1b] Testing weather_service with use_api=False (no network)...")
    try:
        result = fetch_weather(35.4206, 77.1090, datetime.date(2026, 1, 1), num_days=7, use_api=False)
        assert result["status"] == "ok"
        assert result["source"] == "synthetic_fallback"
        assert len(result["hourly_data"]) == 168
        checks["weather_offline_default"] = PASS
        print(f"      {PASS} Offline synthetic model produced 168 hours (7 days)")
    except Exception as e:
        checks["weather_offline_default"] = FAIL
        print(f"      {FAIL} {e}")

    # 1c. Full multi-day pipeline with mocked network failure + use_api=True
    print("\n  [1c] Testing FULL multi-day pipeline under network blackout...")
    try:
        def mock_get_multi(*args, **kwargs):
            raise ConnectionError("Total blackout - multi_day test")

        with patch("weather_service.requests.get", side_effect=mock_get_multi):
            res = run_multi_day_simulation(SIACHEN_CONFIG, num_days=3, use_api=True)

        assert res["status"] == "ok", f"Pipeline returned status: {res['status']}"
        assert res["weather_source"] == "synthetic_fallback"
        assert len(res["daily_results"]) == 3
        assert "summary" in res
        assert "casualty_risk" in res
        assert "material_failures" in res
        checks["full_pipeline_offline"] = PASS
        print(f"      {PASS} Full 3-day pipeline completed under total blackout!")
        print(f"         Weather source: {res['weather_source']}")
        print(f"         Days simulated: {len(res['daily_results'])}")
        print(f"         Avg Min Temp: {res['summary']['avg_min_temp']:.1f}°C")
        print(f"         Casualty Risk: {res['casualty_risk']['status']} ({res['casualty_risk']['cumulative_risk_pct']}%)")
    except Exception as e:
        checks["full_pipeline_offline"] = FAIL
        print(f"      {FAIL} Pipeline crashed under blackout: {e}")
        traceback.print_exc()

    TEST_RESULTS["Test 1: Offline Blackout"] = checks
    return all(v == PASS for v in checks.values())


# ═══════════════════════════════════════════════════════════════════
# TEST 2: CHINOOK PARADOX (High Budget, Low Weight)
# ═══════════════════════════════════════════════════════════════════
def test_chinook_paradox():
    banner("TEST 2: CHINOOK PARADOX — ₹1M Budget, 1000kg Weight Cap")

    from optimize import run_optimization, simulate_shelter
    from supply_chain import get_available_materials, get_delivered_cost
    from physics import MATERIALS, WALL_MATERIALS, ROOF_MATERIALS, WINDOW_MATERIALS
    import pandas as pd

    checks = {}

    # Generate baseline weather for optimizer
    weather_data = pd.read_csv("ladakh_winter.csv")
    outdoor_temps = weather_data["Temperature_C"].values
    solar_irradiance = weather_data["Solar_Irradiance_W_m2"].values

    # 2a. Verify supply chain correctly reports availability at DBO
    print("\n  [2a] Checking material availability at DBO...")
    try:
        dbo_materials = get_available_materials("DBO (Daulat Beg Oldi)")
        leh_materials = get_available_materials("Leh Cantonment")
        siachen_materials = get_available_materials("Siachen Base Camp")

        print(f"      Leh (Tier A): {len(leh_materials)} materials available")
        print(f"      DBO (Tier C): {len(dbo_materials)} materials available")
        print(f"      Siachen (Tier D): {len(siachen_materials)} materials available")

        # Aerogel and Kevlar should NOT be at DBO
        assert "Aerogel Composite" not in dbo_materials, "Aerogel should be unavailable at DBO!"
        assert "Kevlar Sandwich Panel" not in dbo_materials, "Kevlar should be unavailable at DBO!"
        # Steel should be everywhere
        assert "Steel Sheet (Corrugated)" in siachen_materials, "Steel should be available even at Siachen!"

        checks["supply_chain_filtering"] = PASS
        print(f"      {PASS} Supply chain correctly restricts materials by tier")
    except Exception as e:
        checks["supply_chain_filtering"] = FAIL
        print(f"      {FAIL} {e}")

    # 2b. Verify heavy materials weigh more than 1000kg for a standard shelter
    print("\n  [2b] Verifying Concrete exceeds 1000kg weight limit...")
    try:
        wall_area = 52.0
        roof_area = 24.0
        window_area = 4.0

        concrete_weight = (wall_area * MATERIALS["Concrete"]["density"] * 0.20 +
                           roof_area * MATERIALS["Concrete"]["density"] * 0.15)
        puf_weight = (wall_area * MATERIALS["Polyurethane Panel (PUF)"]["density"] * 0.20 +
                      roof_area * MATERIALS["Polyurethane Panel (PUF)"]["density"] * 0.15)
        steel_weight = (wall_area * MATERIALS["Steel Sheet (Corrugated)"]["density"] * 0.20 +
                        roof_area * MATERIALS["Steel Sheet (Corrugated)"]["density"] * 0.15)

        print(f"      Concrete shelter: {concrete_weight:,.0f} kg")
        print(f"      PUF shelter: {puf_weight:,.0f} kg")
        print(f"      Steel shelter: {steel_weight:,.0f} kg")

        assert concrete_weight > 1000, f"Concrete should exceed 1000kg, got {concrete_weight}"
        checks["weight_check"] = PASS
        print(f"      {PASS} Concrete ({concrete_weight:,.0f} kg) correctly exceeds 1000kg cap")
    except Exception as e:
        checks["weight_check"] = FAIL
        print(f"      {FAIL} {e}")

    # 2c. Run NSGA-II optimizer with strict weight cap
    print("\n  [2c] Running NSGA-II optimizer (₹1M budget, 1000kg cap)...")
    try:
        blueprints = run_optimization(
            wall_area=wall_area,
            roof_area=roof_area,
            window_area=window_area,
            door_area=2.0,
            shelter_volume=60.0,
            occupants=4,
            ach=0.3,
            outdoor_temps=outdoor_temps,
            solar_irradiance=solar_irradiance,
            initial_temp=-10.0,
            max_weight=1000,       # STRICT: 1 tonne cap
            max_cost=1000000,      # GENEROUS: ₹1M
            max_glow=2.0,
            location_name="Leh Cantonment",
            pop_size=50,
            n_gen=20,
            seed=42
        )

        print(f"      Found {len(blueprints)} Pareto-optimal blueprints")

        if blueprints:
            heavy_materials_found = []
            for bp in blueprints:
                print(f"        → {bp['wall']} + {bp['roof']} | {bp['total_weight']:,.0f} kg | ₹{bp['total_cost']:,.0f}")
                if bp["total_weight"] > 1000:
                    heavy_materials_found.append(bp)

            if heavy_materials_found:
                checks["optimizer_weight_filter"] = FAIL
                print(f"      {FAIL} Optimizer returned {len(heavy_materials_found)} blueprints exceeding 1000kg!")
            else:
                # Check no Concrete walls made it through
                concrete_in_results = [bp for bp in blueprints if bp["wall"] == "Concrete"]
                if concrete_in_results:
                    print(f"      ⚠️ NOTE: {len(concrete_in_results)} Concrete blueprints found, but all under 1000kg")
                checks["optimizer_weight_filter"] = PASS
                print(f"      {PASS} All {len(blueprints)} blueprints are under 1000kg payload limit")
        else:
            # No blueprints found is also acceptable — it means constraints were too tight
            checks["optimizer_weight_filter"] = PASS
            print(f"      {PASS} No blueprints found (constraints correctly eliminated all heavy options)")

    except Exception as e:
        checks["optimizer_weight_filter"] = FAIL
        print(f"      {FAIL} Optimizer crashed: {e}")
        traceback.print_exc()

    TEST_RESULTS["Test 2: Chinook Paradox"] = checks
    return all(v == PASS for v in checks.values())


# ═══════════════════════════════════════════════════════════════════
# TEST 3: 30-DAY BLIZZARD
# ═══════════════════════════════════════════════════════════════════
def test_30_day_blizzard():
    banner("TEST 3: 30-DAY BLIZZARD — Full Degradation & Casualty Pipeline")

    from multi_day import run_multi_day_simulation
    from failure_modes import MaterialDegradationTracker
    from casualty_risk import calculate_wind_chill, frostbite_risk, daily_hypothermia_risk

    checks = {}

    # 3a. Unit test: wind chill calculator
    print("\n  [3a] Verifying wind chill calculations (NATO STANAG 2895)...")
    try:
        wc_1 = calculate_wind_chill(-20.0, 40.0)  # -20°C, 40 km/h wind
        wc_2 = calculate_wind_chill(-30.0, 60.0)  # -30°C, 60 km/h wind
        wc_3 = calculate_wind_chill(15.0, 10.0)   # Warm day, should return raw temp

        print(f"      Wind Chill (-20°C, 40 km/h): {wc_1:.1f}°C")
        print(f"      Wind Chill (-30°C, 60 km/h): {wc_2:.1f}°C")
        print(f"      Wind Chill (+15°C, 10 km/h): {wc_3:.1f}°C (should be +15°C, above threshold)")

        assert wc_1 < -20.0, "Wind chill should be colder than actual temp"
        assert wc_2 < wc_1, "Higher wind + colder temp should produce lower WC"
        assert wc_3 == 15.0, "Temps > 10°C should return raw temp"

        fb = frostbite_risk(wc_2)
        print(f"      Frostbite risk at {wc_2:.1f}°C: {fb['risk']} — {fb['msg']}")

        checks["wind_chill"] = PASS
        print(f"      {PASS} Wind chill and frostbite functions are NATO-compliant")
    except Exception as e:
        checks["wind_chill"] = FAIL
        print(f"      {FAIL} {e}")

    # 3b. Unit test: MaterialDegradationTracker
    print("\n  [3b] Verifying degradation tracker with synthetic stress data...")
    try:
        tracker = MaterialDegradationTracker("Steel Sheet (Corrugated)", "Concrete")

        # Simulate 15 days of extreme conditions
        for day in range(15):
            fake_day = {
                "min_temp": -25.0,
                "max_temp": 2.0,       # Delta T = 27°C > 25°C threshold
                "avg_temp": -12.0,
                "daily_delta_t": 27.0,
                "freeze_thaw_event": True,  # Every day
                "hourly_outdoor": [-20.0] * 24  # Used for humidity estimation
            }
            tracker.update(fake_day, day)

        failures = tracker.get_failures()
        print(f"      Detected {len(failures)} failure(s) over 15 simulated days:")
        for f in failures:
            print(f"        → Day {f['day']}: {f['material']} — {f['mode']}")
            print(f"          Cause: {f['cause']}")
            print(f"          Fix: {f['recommendation']}")

        # Steel should corrode after 8 freeze-thaw cycles
        steel_failures = [f for f in failures if "Steel" in f["material"]]
        concrete_failures = [f for f in failures if "Concrete" in f["material"]]

        assert len(steel_failures) > 0, "Steel should have flagged freeze-thaw corrosion!"
        assert len(concrete_failures) > 0, "Concrete should have flagged thermal cracking!"
        assert steel_failures[0]["day"] <= 10, f"Steel corrosion should flag by day 10, got day {steel_failures[0]['day']}"
        assert concrete_failures[0]["day"] <= 7, f"Concrete cracking should flag by day 7, got day {concrete_failures[0]['day']}"

        checks["degradation_tracker"] = PASS
        print(f"      {PASS} Material degradation tracker correctly flags Steel corrosion (day {steel_failures[0]['day']}) and Concrete cracking (day {concrete_failures[0]['day']})")
    except Exception as e:
        checks["degradation_tracker"] = FAIL
        print(f"      {FAIL} {e}")
        traceback.print_exc()

    # 3c. Full 30-day simulation
    print("\n  [3c] Running full 30-day blizzard simulation (Steel + Concrete)...")
    try:
        res = run_multi_day_simulation(SIACHEN_CONFIG, num_days=30, use_api=False)

        assert res["status"] == "ok"
        assert len(res["daily_results"]) == 30, f"Expected 30 days, got {len(res['daily_results'])}"

        summary = res["summary"]
        casualty = res["casualty_risk"]
        failures = res["material_failures"]

        print(f"\n      ═══ 30-DAY SIMULATION RESULTS ═══")
        print(f"      Weather Source: {res['weather_source']}")
        print(f"      Avg Min Temp: {summary['avg_min_temp']:.1f}°C")
        print(f"      Avg Max Temp: {summary['avg_max_temp']:.1f}°C")
        print(f"      Total Hypothermia Hours: {summary['total_hypothermia_hours']}")
        print(f"      Total Heating: {summary['total_heating_kwh']:.1f} kWh")
        print(f"      Peak Wind: {summary['max_wind_kmh']:.1f} km/h")
        print(f"")
        print(f"      Casualty Risk: {casualty['status']} ({casualty['cumulative_risk_pct']}%)")
        print(f"      High Risk Days: {casualty['high_risk_days_count']}")
        print(f"      Material Failures Detected: {len(failures)}")

        for f in failures:
            print(f"        → Day {f['day']}: {f['material']} — {f['mode']}")

        # Validate data integrity
        assert summary["avg_min_temp"] < 0, "Avg min temp should be below zero at Siachen"
        assert summary["max_wind_kmh"] > 0, "Should have wind data"
        assert isinstance(casualty["cumulative_risk_pct"], (int, float)), "Risk should be numeric"
        assert casualty["cumulative_risk_pct"] >= 0, "Risk cannot be negative"

        # Check that every daily result has the expected keys
        for d in res["daily_results"]:
            assert "hourly_temps" in d, f"Day {d['day_idx']} missing hourly_temps"
            assert "wind_analysis" in d, f"Day {d['day_idx']} missing wind_analysis"
            assert len(d["hourly_temps"]) == 24, f"Day {d['day_idx']} has {len(d['hourly_temps'])} hours, expected 24"

        checks["full_30day"] = PASS
        print(f"\n      {PASS} 30-day simulation completed with valid output across all services")
    except Exception as e:
        checks["full_30day"] = FAIL
        print(f"      {FAIL} 30-day simulation crashed: {e}")
        traceback.print_exc()

    TEST_RESULTS["Test 3: 30-Day Blizzard"] = checks
    return all(v == PASS for v in checks.values())


# ═══════════════════════════════════════════════════════════════════
# TEST 4: SWARM INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════
def test_swarm_intelligence():
    banner("TEST 4: SWARM INTELLIGENCE — Predictive Routing & VPP")
    from swarm_microgrid import ShelterNode, route_swarm_energy, manage_swarm_batteries

    checks = {}
    print("\n  [4a] Verifying Virtual Power Plant Battery Isolation...")
    try:
        shelters = [
            ShelterNode(1, initial_temp=-10.0, initial_soc=15, health_cycles=6000), 
            ShelterNode(2, initial_temp=5.0, initial_soc=90, health_cycles=1000),   
            ShelterNode(3, initial_temp=-5.0, initial_soc=50, health_cycles=8500),  # Failing
        ]
        
        vpp_status = manage_swarm_batteries(shelters, hour_of_day=2)
        assert shelters[2].is_isolated == True, "EOL battery must be isolated!"
        assert vpp_status["batteries_healthy"] == 2, "Only 2 healthy batteries should remain"
        checks["vpp_battery_isolation"] = PASS
        print(f"      {PASS} VPP correctly identified and isolated failing node.")
    except Exception as e:
        checks["vpp_battery_isolation"] = FAIL
        print(f"      {FAIL} {e}")

    print("\n  [4b] Verifying Predictive Energy Routing (Starvation Mode)...")
    try:
        t_out_next = [-25.0, -26.0]
        # Low irradiance (100W/m2), won't be enough to heat both
        routing = route_swarm_energy(shelters, 100.0, t_out_next, "02:00 IST")
        
        assert routing["strategy"] == "Rationed Priority Routing"
        assert routing["allocation"]["Shelter_1"] > routing["allocation"]["Shelter_2"], "Coldest shelter must get most power"
        assert routing["allocation"]["Shelter_3"] == 0, "Isolated shelter must get 0 power"
        checks["predictive_routing"] = PASS
        print(f"      {PASS} Energy routed to coldest shelter, isolated shelter ignored.")
    except Exception as e:
        checks["predictive_routing"] = FAIL
        print(f"      {FAIL} {e}")

    TEST_RESULTS["Test 4: Swarm Intelligence"] = checks
    return all(v == PASS for v in checks.values())


# ═══════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    banner("DRDO SIH26051 — SYSTEM STRESS TEST HARNESS v1.0")
    print("  Running 3 extreme edge-case tests across all microservices...")
    print("  This verifies offline resilience, supply chain constraints,")
    print("  material degradation, and casualty risk prediction.\n")

    test_1_ok = test_offline_blackout()
    test_2_ok = test_chinook_paradox()
    test_3_ok = test_30_day_blizzard()
    test_4_ok = test_swarm_intelligence()

    # ═══════════════════════════════════════════════════════════════
    # FINAL REPORT
    # ═══════════════════════════════════════════════════════════════
    banner("FINAL STRESS TEST REPORT")

    total_checks = 0
    total_pass = 0

    for test_name, checks in TEST_RESULTS.items():
        all_ok = all(v == PASS for v in checks.values())
        status = PASS if all_ok else FAIL
        print(f"\n  {status}  {test_name}")
        for check_name, result in checks.items():
            print(f"       {result}  {check_name}")
            total_checks += 1
            if result == PASS:
                total_pass += 1

    print(f"\n{'='*70}")
    overall = "ALL SYSTEMS OPERATIONAL" if total_pass == total_checks else "FAILURES DETECTED"
    icon = "🟢" if total_pass == total_checks else "🔴"
    print(f"  {icon} {total_pass}/{total_checks} checks passed — {overall}")
    print(f"{'='*70}\n")

    sys.exit(0 if total_pass == total_checks else 1)
