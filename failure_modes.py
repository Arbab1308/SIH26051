"""
Service for detecting long-term material degradation and failure modes.
Monitors daily thermal stresses, freeze-thaw cycles, and humidity exposure.
"""

class MaterialDegradationTracker:
    def __init__(self, wall_material, roof_material):
        self.materials = [wall_material, roof_material]
        
        # Cumulative stress counters
        self.counters = {
            "freeze_thaw_cycles": 0,
            "high_humidity_days": 0,
            "extreme_cold_days": 0,
            "high_delta_t_days": 0
        }
        
        self.active_warnings = []
        self.detected_failures = []
        
    def update(self, day_weather, day_idx):
        """
        Update degradation counters based on a single day's weather and thermal performance.
        day_weather is a dictionary from the multi_day simulation containing min/max temps, etc.
        """
        min_temp = day_weather["min_temp"]
        max_temp = day_weather["max_temp"]
        avg_temp = day_weather["avg_temp"]
        delta_t = day_weather["daily_delta_t"]
        
        # We estimate internal humidity loosely based on outdoor humidity + occupants
        # In a real model, this would be computed by physics engine
        avg_humidity = sum(day_weather["hourly_outdoor"]) / 24.0 if "hourly_outdoor" in day_weather else 50.0
        
        # Update physical stress counters
        if day_weather.get("freeze_thaw_event", False):
            self.counters["freeze_thaw_cycles"] += 1
            
        if avg_humidity > 75.0:
            self.counters["high_humidity_days"] += 1
            
        if min_temp < -20.0:
            self.counters["extreme_cold_days"] += 1
            
        if delta_t > 25.0:
            self.counters["high_delta_t_days"] += 1
            
        # Check specific material failure thresholds
        self._check_concrete_failures(day_idx)
        self._check_puf_failures(day_idx)
        self._check_steel_failures(day_idx)
        self._check_wood_failures(day_idx)
        
    def _check_concrete_failures(self, day_idx):
        if "Concrete" in self.materials:
            if self.counters["high_delta_t_days"] >= 5:
                self._add_failure("Concrete", "Thermal Cracking", day_idx, 
                                  "High thermal swings (>25°C) caused structural micro-cracking.",
                                  "Apply expansion joint coating or thermal break.")
                
    def _check_puf_failures(self, day_idx):
        if "Polyurethane Panel (PUF)" in self.materials:
            if self.counters["high_humidity_days"] >= 3:
                self._add_failure("Polyurethane Panel (PUF)", "Delamination", day_idx,
                                  "High persistent humidity compromised panel adhesive.",
                                  "Install internal vapor barrier membrane.")
                                  
    def _check_steel_failures(self, day_idx):
        if "Steel Sheet (Corrugated)" in self.materials:
            if self.counters["freeze_thaw_cycles"] >= 8:
                self._add_failure("Steel Sheet (Corrugated)", "Freeze-Thaw Corrosion", day_idx,
                                  "Repeated freezing/thawing breached anti-rust coating.",
                                  "Use hot-dip galvanized steel or apply zinc-rich primer.")
                                  
    def _check_wood_failures(self, day_idx):
        if "Wood" in self.materials:
            if self.counters["high_humidity_days"] >= 5 and self.counters["extreme_cold_days"] >= 2:
                self._add_failure("Wood", "Moisture Rot / Freeze Expansion", day_idx,
                                  "Moisture absorbed into wood matrix expanded during freeze.",
                                  "Use pressure-treated lumber and seal end-grains.")
                
    def _add_failure(self, material, mode, day_idx, cause, recommendation):
        # Prevent duplicate failure logging for the same mode
        for f in self.detected_failures:
            if f["material"] == material and f["mode"] == mode:
                return
                
        failure = {
            "day": day_idx + 1,
            "material": material,
            "mode": mode,
            "cause": cause,
            "recommendation": recommendation
        }
        self.detected_failures.append(failure)
        
    def get_failures(self):
        return self.detected_failures
