"""
Inverse AI Generative Designer — NSGA-II Multi-Objective Shelter Optimizer
Uses pymoo to evolve optimal shelter blueprints across 3 objectives:
  f1: Minimize Total Deployment Weight (kg)
  f2: Minimize Total Material Cost (INR)
  f3: Maximize Minimum Internal Temperature (°C)  → minimized as -min_temp

Decision Variables (5 integer-encoded genes):
  x[0] = Wall material index
  x[1] = Roof material index
  x[2] = Window material index
  x[3] = Orientation (0-35 → maps to 0°-350° in steps of 10°)
  x[4] = Shape (0=Box, 1=Dome)

Subject to constraints:
  g1: Weight  < max_weight   (default 2500 kg)
  g2: Cost    < max_cost     (default 150000 INR)
  g3: Max IR Glow < max_glow (default 0.5 °C)
"""

import numpy as np
from pymoo.core.problem import Problem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.optimize import minimize as pymoo_minimize

from physics import (
    MATERIALS,
    WALL_MATERIALS,
    ROOF_MATERIALS,
    WINDOW_MATERIALS,
    calculate_heat_transfer,
    calculate_solar_gain,
    calculate_new_temperature,
    calculate_external_surface_temp,
    calculate_metabolic_heat,
    calculate_ventilation_loss,
    calculate_ground_conduction,
    get_effective_window_r_value,
    calculate_pcm_specific_heat,
)
from solar_terrain import calculate_azimuth_factor
from supply_chain import get_available_materials, get_delivered_cost

# Shape definitions for area calculations
SHAPE_TYPES = ['box', 'dome']


def simulate_shelter(wall_name, roof_name, window_name,
                     wall_area, roof_area, window_area, door_area,
                     shelter_volume, occupants, ach,
                     outdoor_temps, solar_irradiance, initial_temp=-5.0,
                     orientation=180, shape='box', night_shutters=True,
                     floor_r_value=2.0, floor_area=24.0,
                     sun_azimuths=None):
    """
    Run the full 24-hour thermal simulation for a given material combination.
    Returns a dict with: min_temp, max_temp, total_weight, total_cost, max_ir_glow, shelter_temps
    """
    wall_props = MATERIALS[wall_name]
    roof_props = MATERIALS[roof_name]
    window_props = MATERIALS[window_name]

    # Shape modifier: dome has ~25% less surface area for same volume
    shape_area_factor = 0.75 if shape == 'dome' else 1.0
    effective_wall_area = wall_area * shape_area_factor
    effective_roof_area = roof_area * shape_area_factor

    # Weight calculations (20cm walls, 15cm roof, 1cm windows)
    wall_weight = effective_wall_area * wall_props["density"] * 0.20
    roof_weight = effective_roof_area * roof_props["density"] * 0.15
    window_weight = window_area * window_props["density"] * 0.01
    total_weight = wall_weight + roof_weight + window_weight

    # Cost calculations (using base cost if location not provided)
    total_cost = (
        wall_weight * wall_props["cost_per_kg"]
        + roof_weight * roof_props["cost_per_kg"]
        + window_weight * window_props["cost_per_kg"]
    )

    # Thermal mass
    total_mass = (
        effective_wall_area * wall_props["density"] * 0.2
        + effective_roof_area * roof_props["density"] * 0.15
    )
    base_specific_heat = (wall_props["specific_heat"] + roof_props["specific_heat"]) / 2

    # Check PCM
    has_pcm = "pcm_transition_temp" in wall_props

    # 24-hour simulation loop
    current_temp = initial_temp
    shelter_temps = []
    external_wall_temps = []

    for hour in range(24):
        t_out = outdoor_temps[hour]
        solar = solar_irradiance[hour]

        # PCM specific heat modulation
        if has_pcm:
            total_specific_heat = calculate_pcm_specific_heat(
                base_specific_heat, current_temp,
                transition_temp=wall_props["pcm_transition_temp"],
                active_cp=wall_props.get("pcm_active_cp", 14000.0)
            )
        else:
            total_specific_heat = base_specific_heat

        # IR stealth: external surface temperature
        t_surf = calculate_external_surface_temp(current_temp, t_out, wall_props["r_value"])
        external_wall_temps.append(t_surf)

        # Night shutters
        effective_window_r = get_effective_window_r_value(
            window_props["r_value"], solar, night_shutters_enabled=night_shutters
        )

        # Heat losses
        q_wall = calculate_heat_transfer(current_temp, t_out, effective_wall_area, wall_props["r_value"])
        q_roof = calculate_heat_transfer(current_temp, t_out, effective_roof_area, roof_props["r_value"])
        q_window = calculate_heat_transfer(current_temp, t_out, window_area, effective_window_r)
        q_door = calculate_heat_transfer(current_temp, t_out, door_area, 0.1)
        q_ground = calculate_ground_conduction(current_temp, floor_area, floor_r_value)
        q_vent = calculate_ventilation_loss(current_temp, t_out, shelter_volume, ach)

        q_total_loss = q_wall + q_roof + q_window + q_door + q_ground + q_vent

        # Heat gains with azimuth factor
        q_solar_raw = calculate_solar_gain(solar, window_area, absorptivity=0.7)
        if sun_azimuths is not None and solar > 0:
            azimuth_factor = calculate_azimuth_factor(sun_azimuths[hour], orientation)
            q_solar = q_solar_raw * azimuth_factor
        else:
            # Simplified: south-facing bonus at midday
            if 10 <= hour <= 14 and 135 <= orientation <= 225:
                q_solar = q_solar_raw
            elif solar > 0:
                q_solar = q_solar_raw * 0.6
            else:
                q_solar = q_solar_raw

        q_human = calculate_metabolic_heat(occupants)
        q_total_gain = q_solar + q_human

        # Temperature update
        new_temp = calculate_new_temperature(
            current_temp, q_total_gain, q_total_loss, total_mass, total_specific_heat
        )
        shelter_temps.append(new_temp)
        current_temp = new_temp

    # IR glow: max difference between wall surface and ambient
    max_ir_glow = max(
        surf - amb for surf, amb in zip(external_wall_temps, outdoor_temps)
    )

    return {
        "min_temp": min(shelter_temps),
        "max_temp": max(shelter_temps),
        "total_weight": total_weight,
        "total_cost": total_cost,
        "max_ir_glow": max_ir_glow,
        "shelter_temps": shelter_temps,
        "wall": wall_name,
        "roof": roof_name,
        "window": window_name,
        "orientation": orientation,
        "shape": shape,
        "night_shutters": night_shutters,
    }


class ShelterOptProblem(Problem):
    """
    NSGA-II Multi-Objective Problem for shelter design.

    Decision Variables (5 integer-encoded genes):
      x[0] = wall material index    (0 to len(WALL_MATERIALS)-1)
      x[1] = roof material index    (0 to len(ROOF_MATERIALS)-1)
      x[2] = window material index  (0 to len(WINDOW_MATERIALS)-1)
      x[3] = orientation index      (0 to 35 → 0° to 350° in 10° steps)
      x[4] = shape index            (0=Box, 1=Dome)

    Objectives (all minimized):
      f1 = total_weight
      f2 = total_cost
      f3 = -min_temp  (negated so minimizing it maximizes warmth)

    Inequality Constraints (g <= 0 means feasible):
      g1 = total_weight - max_weight
      g2 = total_cost   - max_cost
      g3 = max_ir_glow  - max_glow
    """

    def __init__(self, wall_area, roof_area, window_area, door_area,
                 shelter_volume, occupants, ach,
                 outdoor_temps, solar_irradiance, initial_temp,
                 max_weight=2500, max_cost=150000, max_glow=0.5,
                 location_name="Leh Cantonment",
                 floor_area=24.0, floor_r_value=2.0,
                 night_shutters=True):

        n_wall = len(WALL_MATERIALS)
        n_roof = len(ROOF_MATERIALS)
        n_window = len(WINDOW_MATERIALS)
        n_orientation = 36   # 0-35 → 0°-350° in 10° steps
        n_shapes = len(SHAPE_TYPES)  # 0=box, 1=dome

        super().__init__(
            n_var=5,
            n_obj=3,
            n_ieq_constr=3,
            xl=np.array([0, 0, 0, 0, 0]),
            xu=np.array([n_wall - 1, n_roof - 1, n_window - 1,
                         n_orientation - 1, n_shapes - 1]),
            vtype=int,
        )

        # Store shelter geometry & conditions
        self.wall_area = wall_area
        self.roof_area = roof_area
        self.window_area = window_area
        self.door_area = door_area
        self.shelter_volume = shelter_volume
        self.occupants = occupants
        self.ach = ach
        self.outdoor_temps = outdoor_temps
        self.solar_irradiance = solar_irradiance
        self.initial_temp = initial_temp

        # Constraint bounds
        self.max_weight = max_weight
        self.max_cost = max_cost
        self.max_glow = max_glow
        self.location_name = location_name
        self.available_mats = get_available_materials(location_name)

        # New passive physics config
        self.floor_area = floor_area
        self.floor_r_value = floor_r_value
        self.night_shutters = night_shutters

    def _evaluate(self, X, out, *args, **kwargs):
        F = np.zeros((X.shape[0], 3))
        G = np.zeros((X.shape[0], 3))

        for i, x in enumerate(X):
            wall_idx = int(np.clip(x[0], 0, len(WALL_MATERIALS) - 1))
            roof_idx = int(np.clip(x[1], 0, len(ROOF_MATERIALS) - 1))
            win_idx = int(np.clip(x[2], 0, len(WINDOW_MATERIALS) - 1))
            orient_idx = int(np.clip(x[3], 0, 35))
            shape_idx = int(np.clip(x[4], 0, len(SHAPE_TYPES) - 1))

            wall_name = WALL_MATERIALS[wall_idx]
            roof_name = ROOF_MATERIALS[roof_idx]
            window_name = WINDOW_MATERIALS[win_idx]
            orientation = orient_idx * 10  # 0°, 10°, 20°, ... 350°
            shape = SHAPE_TYPES[shape_idx]

            result = simulate_shelter(
                wall_name=wall_name,
                roof_name=roof_name,
                window_name=window_name,
                wall_area=self.wall_area,
                roof_area=self.roof_area,
                window_area=self.window_area,
                door_area=self.door_area,
                shelter_volume=self.shelter_volume,
                occupants=self.occupants,
                ach=self.ach,
                outdoor_temps=self.outdoor_temps,
                solar_irradiance=self.solar_irradiance,
                initial_temp=self.initial_temp,
                orientation=orientation,
                shape=shape,
                night_shutters=self.night_shutters,
                floor_r_value=self.floor_r_value,
                floor_area=self.floor_area,
            )
            
            # Recalculate cost with delivered cost (shape-adjusted areas)
            shape_area_factor = 0.75 if shape == 'dome' else 1.0
            wall_weight = self.wall_area * shape_area_factor * MATERIALS[wall_name]["density"] * 0.20
            roof_weight = self.roof_area * shape_area_factor * MATERIALS[roof_name]["density"] * 0.15
            window_weight = self.window_area * MATERIALS[window_name]["density"] * 0.01
            
            delivered_cost = (
                wall_weight * get_delivered_cost(wall_name, self.location_name) +
                roof_weight * get_delivered_cost(roof_name, self.location_name) +
                window_weight * get_delivered_cost(window_name, self.location_name)
            )

            # Objectives (all minimized)
            F[i, 0] = result["total_weight"]
            F[i, 1] = delivered_cost
            F[i, 2] = -result["min_temp"]  # Negate: minimizing = maximizing warmth
            
            # Infinite cost if unavailable
            if wall_name not in self.available_mats or roof_name not in self.available_mats or window_name not in self.available_mats:
                F[i, 1] = float('inf')

            # Constraints (g <= 0 is feasible)
            G[i, 0] = result["total_weight"] - self.max_weight
            G[i, 1] = delivered_cost - self.max_cost
            G[i, 2] = result["max_ir_glow"] - self.max_glow

        out["F"] = F
        out["G"] = G


def run_optimization(wall_area, roof_area, window_area, door_area,
                     shelter_volume, occupants, ach,
                     outdoor_temps, solar_irradiance, initial_temp,
                     max_weight=2500, max_cost=150000, max_glow=0.5,
                     location_name="Leh Cantonment",
                     pop_size=100, n_gen=50, seed=42,
                     floor_area=24.0, floor_r_value=2.0,
                     night_shutters=True):
    """
    Execute the NSGA-II optimization and return the top Pareto-optimal blueprints.
    Now evolves 5 genes: wall, roof, window, orientation (0-350°), shape (box/dome).

    Returns:
        list[dict]: Top blueprints sorted by minimum internal temperature (warmest first).
                    Each dict contains: wall, roof, window, orientation, shape,
                    total_weight, total_cost, min_temp, max_ir_glow, comfort_hours.
    """
    problem = ShelterOptProblem(
        wall_area=wall_area,
        roof_area=roof_area,
        window_area=window_area,
        door_area=door_area,
        shelter_volume=shelter_volume,
        occupants=occupants,
        ach=ach,
        outdoor_temps=outdoor_temps,
        solar_irradiance=solar_irradiance,
        initial_temp=initial_temp,
        max_weight=max_weight,
        max_cost=max_cost,
        max_glow=max_glow,
        location_name=location_name,
        floor_area=floor_area,
        floor_r_value=floor_r_value,
        night_shutters=night_shutters,
    )

    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=IntegerRandomSampling(),
        crossover=SBX(prob=0.9, eta=3.0, vtype=float, repair=RoundingRepair()),
        mutation=PM(eta=3.0, vtype=float, repair=RoundingRepair()),
        eliminate_duplicates=True,
    )

    res = pymoo_minimize(
        problem,
        algorithm,
        termination=("n_gen", n_gen),
        seed=seed,
        verbose=False,
    )

    # Decode the Pareto front results into readable blueprints
    blueprints = []

    if res.X is not None:
        # Handle both single-solution and multi-solution cases
        solutions = res.X if res.X.ndim == 2 else res.X.reshape(1, -1)
        objectives = res.F if res.F.ndim == 2 else res.F.reshape(1, -1)

        for x, f in zip(solutions, objectives):
            wall_idx = int(np.clip(x[0], 0, len(WALL_MATERIALS) - 1))
            roof_idx = int(np.clip(x[1], 0, len(ROOF_MATERIALS) - 1))
            win_idx = int(np.clip(x[2], 0, len(WINDOW_MATERIALS) - 1))
            orient_idx = int(np.clip(x[3], 0, 35))
            shape_idx = int(np.clip(x[4], 0, len(SHAPE_TYPES) - 1))

            wall_name = WALL_MATERIALS[wall_idx]
            roof_name = ROOF_MATERIALS[roof_idx]
            window_name = WINDOW_MATERIALS[win_idx]
            orientation = orient_idx * 10
            shape = SHAPE_TYPES[shape_idx]

            # Re-simulate for full details
            result = simulate_shelter(
                wall_name=wall_name,
                roof_name=roof_name,
                window_name=window_name,
                wall_area=wall_area,
                roof_area=roof_area,
                window_area=window_area,
                door_area=door_area,
                shelter_volume=shelter_volume,
                occupants=occupants,
                ach=ach,
                outdoor_temps=outdoor_temps,
                solar_irradiance=solar_irradiance,
                initial_temp=initial_temp,
                orientation=orientation,
                shape=shape,
                night_shutters=night_shutters,
                floor_r_value=floor_r_value,
                floor_area=floor_area,
            )

            comfort_hours = sum(1 for t in result["shelter_temps"] if t >= -10)

            shape_area_factor = 0.75 if shape == 'dome' else 1.0
            wall_weight = wall_area * shape_area_factor * MATERIALS[wall_name]["density"] * 0.20
            roof_weight = roof_area * shape_area_factor * MATERIALS[roof_name]["density"] * 0.15
            window_weight = window_area * MATERIALS[window_name]["density"] * 0.01
            
            delivered_cost = (
                wall_weight * get_delivered_cost(wall_name, location_name) +
                roof_weight * get_delivered_cost(roof_name, location_name) +
                window_weight * get_delivered_cost(window_name, location_name)
            )

            blueprints.append({
                "wall": wall_name,
                "roof": roof_name,
                "window": window_name,
                "orientation": orientation,
                "shape": shape,
                "night_shutters": night_shutters,
                "total_weight": result["total_weight"],
                "total_cost": delivered_cost,
                "min_temp": result["min_temp"],
                "max_temp": result["max_temp"],
                "max_ir_glow": result["max_ir_glow"],
                "comfort_hours": comfort_hours,
                "shelter_temps": result["shelter_temps"],
            })

    # Sort by warmest minimum temperature (best survival), deduplicate
    seen = set()
    unique_blueprints = []
    for bp in sorted(blueprints, key=lambda b: b["min_temp"], reverse=True):
        key = (bp["wall"], bp["roof"], bp["window"], bp["orientation"], bp["shape"])
        if key not in seen:
            seen.add(key)
            unique_blueprints.append(bp)

    return unique_blueprints
