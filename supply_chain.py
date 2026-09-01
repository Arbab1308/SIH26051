"""
Service for managing supply chain constraints based on Indian Army deployment locations.
"""
from functools import lru_cache

DEPLOYMENT_LOCATIONS = {
    "Leh Cantonment": {
        "lat": 34.1526, "lon": 77.5771, "altitude_m": 3524,
        "supply_tier": "A",
        "transport_mode": "Road + Air",
        "lead_time_base_days": 1,
    },
    "Khardung La Pass": {
        "lat": 34.2817, "lon": 77.6025, "altitude_m": 5359,
        "supply_tier": "B",
        "transport_mode": "Road only (seasonal)",
        "lead_time_base_days": 3,
    },
    "DBO (Daulat Beg Oldi)": {
        "lat": 35.3889, "lon": 77.8469, "altitude_m": 5065,
        "supply_tier": "C",
        "transport_mode": "C-130J airlift only",
        "lead_time_base_days": 15,
    },
    "Siachen Base Camp": {
        "lat": 35.4206, "lon": 77.1090, "altitude_m": 5400,
        "supply_tier": "D",
        "transport_mode": "Helicopter + porter",
        "lead_time_base_days": 30,
    },
    "Pangong Tso (South Bank)": {
        "lat": 33.7595, "lon": 78.6466, "altitude_m": 4250,
        "supply_tier": "B",
        "transport_mode": "Road (seasonal Nov-Apr closed)",
        "lead_time_base_days": 5,
    },
}

# Base materials data, mapping material name to a supply chain definition
# Format: "Material Name": {"base_cost": INR/kg, "tier_availability": ["A", "B", "C", "D"]}
MATERIAL_SUPPLY = {
    "Concrete": {"base_cost": 5, "tier_availability": ["A", "B", "C"]},
    "Brick": {"base_cost": 4, "tier_availability": ["A", "B"]},
    "Wood": {"base_cost": 40, "tier_availability": ["A", "B", "C"]},
    "Polyurethane Panel (PUF)": {"base_cost": 250, "tier_availability": ["A", "B", "C"]},
    "Aerogel Composite": {"base_cost": 1800, "tier_availability": ["A"]},
    "Kevlar Sandwich Panel": {"base_cost": 3500, "tier_availability": ["A"]},
    "Carbon Fiber Panel": {"base_cost": 4000, "tier_availability": ["A"]},
    "Stone Wool (Rockwool)": {"base_cost": 80, "tier_availability": ["A", "B", "C"]},
    "EPS Foam (Thermocol)": {"base_cost": 120, "tier_availability": ["A", "B", "C"]},
    "XPS Foam (Extruded)": {"base_cost": 150, "tier_availability": ["A", "B", "C"]},
    "Fiberglass Batt": {"base_cost": 90, "tier_availability": ["A", "B", "C"]},
    "Mud Brick (Adobe)": {"base_cost": 2, "tier_availability": ["A"]},
    "Steel Sheet (Corrugated)": {"base_cost": 55, "tier_availability": ["A", "B", "C", "D"]},
    "Aluminium Composite": {"base_cost": 180, "tier_availability": ["A", "B", "C"]},
    "Bamboo Composite": {"base_cost": 25, "tier_availability": ["A", "B"]},
    "HDPE Fabric (Heavy Duty)": {"base_cost": 200, "tier_availability": ["A", "B", "C", "D"]},
    "Nomex Honeycomb": {"base_cost": 5500, "tier_availability": ["A"]},
    
    # Windows
    "Glass (Single Pane)": {"base_cost": 60, "tier_availability": ["A", "B", "C"]},
    "Glass (Double Pane)": {"base_cost": 120, "tier_availability": ["A", "B", "C"]},
    "Polycarbonate Sheet": {"base_cost": 250, "tier_availability": ["A", "B", "C", "D"]},
}
@lru_cache(maxsize=None)
def get_location(name):
    """Returns deployment location info or default to Leh if not found."""
    return DEPLOYMENT_LOCATIONS.get(name, DEPLOYMENT_LOCATIONS["Leh Cantonment"])
@lru_cache(maxsize=None)
def get_available_materials(location_name):
    """Returns a list of material names available at the given location tier."""
    loc = get_location(location_name)
    tier = loc["supply_tier"]
    available = []
    for mat, props in MATERIAL_SUPPLY.items():
        if tier in props["tier_availability"]:
            available.append(mat)
    return available
@lru_cache(maxsize=None)
def get_delivered_cost(material, location_name):
    """
    Calculates the delivered cost of a material based on location tier logistics markup.
    Tier A: +0% (Base cost)
    Tier B: +20% (Road transport up pass)
    Tier C: +50% (Airlift)
    Tier D: +150% (Heli/Porter)
    """
    loc = get_location(location_name)
    tier = loc["supply_tier"]
    
    if material not in MATERIAL_SUPPLY or tier not in MATERIAL_SUPPLY[material]["tier_availability"]:
        return float('inf') # Material unavailable
        
    base = MATERIAL_SUPPLY[material]["base_cost"]
    
    markup = 0.0
    if tier == "B": markup = 0.20
    elif tier == "C": markup = 0.50
    elif tier == "D": markup = 1.50
    
    return base * (1 + markup)

def get_lead_time(material, location_name):
    """Returns estimated lead time in days for a material to reach the location."""
    loc = get_location(location_name)
    tier = loc["supply_tier"]
    
    if material not in MATERIAL_SUPPLY or tier not in MATERIAL_SUPPLY[material]["tier_availability"]:
        return -1 # Unavailable
        
    base_lead = loc["lead_time_base_days"]
    
    # High tech materials take longer to source even at base
    if material in ["Aerogel Composite", "Kevlar Sandwich Panel", "Nomex Honeycomb"]:
        base_lead += 14
        
    return base_lead
