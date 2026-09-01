"""
Swarm Microgrid & Virtual Power Plant Service
Manages predictive energy routing and battery balancing across a cluster of multiple shelters.
"""

import math

class ShelterNode:
    def __init__(self, id, initial_temp, battery_capacity_wh=50000, initial_soc=100.0, health_cycles=0):
        self.id = f"Shelter_{id}"
        self.current_temp = initial_temp
        self.battery_capacity = battery_capacity_wh
        self.soc = initial_soc  # State of Charge (0-100)
        self.health_cycles = health_cycles
        self.is_isolated = False
        self.status = "Healthy"
        
        # Physical mock attributes for prediction
        self.heat_loss_rate = 150  # Watts per degree delta T
        
    def predict_temperature(self, t_out_next_2h, passive_solar_gain):
        """Predicts temperature 2 hours ahead without active heating."""
        # Simple lumped capacitance mock for 2 hours (dt = 7200s)
        # Using a cooling curve approach
        future_temp = self.current_temp
        for t_out in t_out_next_2h: # assume array of 2 hourly temps
            delta = future_temp - t_out
            loss_watts = delta * self.heat_loss_rate
            net_watts = passive_solar_gain - loss_watts
            # Assume 1 degree change per 1000W net over an hour (mock thermal mass)
            future_temp += (net_watts / 1000.0) 
        return future_temp

    def calculate_deficit(self, predicted_temp, target_temp=5.0):
        """Calculates power needed to reach target temp."""
        if predicted_temp >= target_temp:
            return 0
        # Watts required to offset the drop
        return (target_temp - predicted_temp) * self.heat_loss_rate

def route_swarm_energy(shelters, solar_irradiance, t_out_next_2h, current_time):
    """
    Predictive Energy Routing Algorithm (Feature 1)
    """
    # 1. Calculate available solar power
    # 50 panels * 400W peak = 20kW peak array. 
    # Assume 1000 W/m2 is 100% capacity.
    array_peak_w = 20000
    efficiency = 0.90 * 0.95 # DC-DC and Charging losses
    solar_ratio = max(0, min(1.0, solar_irradiance / 1000.0))
    net_available_power = array_peak_w * solar_ratio * efficiency
    
    routing_matrix = {
        "timestamp": current_time,
        "solar_available": round(net_available_power, 1),
        "allocation": {},
        "strategy": "",
        "risk_level": "Low"
    }
    
    # 2. Forecast Demand Per Shelter
    demands = []
    for s in shelters:
        if s.is_isolated:
            routing_matrix["allocation"][s.id] = 0
            continue
            
        passive_solar = solar_irradiance * 4.0 * 0.7 # 4m2 window
        pred_t = s.predict_temperature(t_out_next_2h, passive_solar)
        deficit = s.calculate_deficit(pred_t)
        demands.append({"shelter": s, "deficit": deficit, "pred_t": pred_t})
        
    # Sort by coldest predicted temperature (priority 1)
    demands.sort(key=lambda x: x["pred_t"])
    
    total_demand = sum(d["deficit"] for d in demands)
    remaining_power = net_available_power
    
    # 3. Allocate Power
    if remaining_power >= total_demand:
        routing_matrix["strategy"] = "Full Predictive Heating"
        for d in demands:
            s_id = d["shelter"].id
            routing_matrix["allocation"][s_id] = round(d["deficit"], 1)
            remaining_power -= d["deficit"]
        routing_matrix["allocation"]["Reserve_battery"] = round(remaining_power, 1)
        routing_matrix["risk_level"] = "Low - All shelters heated ✅"
    else:
        routing_matrix["strategy"] = "Rationed Priority Routing"
        # 70% to coldest, 20% to 2nd, 10% to rest
        
        if len(demands) > 0:
            coldest = demands[0]
            alloc = min(remaining_power * 0.7, coldest["deficit"])
            routing_matrix["allocation"][coldest["shelter"].id] = round(alloc, 1)
            remaining_power -= alloc
            
        if len(demands) > 1:
            second = demands[1]
            alloc = min(remaining_power * (20/30), second["deficit"]) # relative to remaining
            routing_matrix["allocation"][second["shelter"].id] = round(alloc, 1)
            remaining_power -= alloc
            
        # Distribute rest to 3-10
        dist_count = len(demands) - 2
        if dist_count > 0:
            per_shelter = remaining_power / dist_count
            for i in range(2, len(demands)):
                routing_matrix["allocation"][demands[i]["shelter"].id] = round(per_shelter, 1)
                
        routing_matrix["allocation"]["Reserve_battery"] = 0
        routing_matrix["risk_level"] = "Medium - Rationed Mode ⚠️"
        
    return routing_matrix

def manage_swarm_batteries(shelters, hour_of_day):
    """
    Swarm Battery Management (Virtual Power Plant) (Feature 2)
    """
    fleet_status = {
        "total_capacity_kwh": 0,
        "usable_capacity_kwh": 0,
        "current_charge_kwh": 0,
        "batteries_healthy": 0,
        "predicted_failures": [],
        "active_discharge_pool": []
    }
    
    # 1. Health Monitoring & Isolation
    for s in shelters:
        # Check thresholds
        if s.health_cycles > 8000 and not s.is_isolated:
            s.status = "EOL - Failing Battery"
            s.is_isolated = True
            fleet_status["predicted_failures"].append(f"{s.id} EOL in 10 days")
            
        if not s.is_isolated:
            fleet_status["total_capacity_kwh"] += (s.battery_capacity / 1000.0)
            fleet_status["current_charge_kwh"] += ((s.battery_capacity * s.soc / 100.0) / 1000.0)
            fleet_status["batteries_healthy"] += 1
            
    fleet_status["usable_capacity_kwh"] = fleet_status["total_capacity_kwh"] * 0.8 # 80% DoD
    
    # 2. Discharge Sequencing (Virtual Power Plant)
    healthy_shelters = [s for s in shelters if not s.is_isolated]
    
    # Sort by cycles (wear leveling)
    healthy_shelters.sort(key=lambda x: x.health_cycles, reverse=True) # Oldest first
    
    if 0 <= hour_of_day < 6:
        # Deep cold: Use oldest batteries to balance wear
        active = healthy_shelters[:3]
        fleet_status["active_discharge_pool"] = [s.id for s in active]
    elif 6 <= hour_of_day < 12:
        # Solar peak: No discharge, all charging
        fleet_status["active_discharge_pool"] = []
    elif 12 <= hour_of_day < 18:
        # Moderate solar: Use youngest batteries
        youngest = sorted(healthy_shelters, key=lambda x: x.health_cycles)
        active = youngest[:4]
        fleet_status["active_discharge_pool"] = [s.id for s in active]
    else:
        # Night survival: Gradual switch, priority order (coldest)
        healthy_shelters.sort(key=lambda x: x.current_temp)
        active = healthy_shelters[:5]
        fleet_status["active_discharge_pool"] = [s.id for s in active]
        
    # 3. Parallel Balancing (Simulation)
    # If a battery is >80% and another is <30%, we would route power.
    soc_list = [s.soc for s in healthy_shelters]
    if soc_list:
        max_soc_s = max(healthy_shelters, key=lambda x: x.soc)
        min_soc_s = min(healthy_shelters, key=lambda x: x.soc)
        if max_soc_s.soc > 80 and min_soc_s.soc < 30:
            fleet_status["balancing_action"] = f"Rerouting DC power from {max_soc_s.id} (80%+) to {min_soc_s.id} (<30%)"
    
    return fleet_status
