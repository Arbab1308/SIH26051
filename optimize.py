"""
Inverse AI Generative Designer — NSGA-II Multi-Objective Shelter Optimizer
Uses pymoo to evolve optimal shelter blueprints across 3 objectives:
  f1: Minimize Total Deployment Weight (kg)
  f2: Minimize Total Material Cost (INR)
  f3: Maximize Minimum Internal Temperature (°C)  → minimized as -min_temp

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
)


def simulate_shelter(wall_name, roof_name, window_name,
                     wall_area, roof_area, window_area, door_area,
                     shelter_volume, occupants, ach,
                     outdoor_temps, solar_irradiance, initial_temp=-5.0):
    """
    Run the full 24-hour thermal simulation for a given material combination.
    Returns a dict with: min_temp, max_temp, total_weight, total_cost, max_ir_glow, shelter_temps
    """
    wall_props = MATERIALS[wall_name]
    roof_props = MATERIALS[roof_name]
    window_props = MATERIALS[window_name]

    # Weight calculations (20cm walls, 15cm roof, 1cm windows)
    wall_weight = wall_area * wall_props["density"] * 0.20
    roof_weight = roof_area * roof_props["density"] * 0.15
    window_weight = window_area * window_props["density"] * 0.01
    total_weight = wall_weight + roof_weight + window_weight

    # Cost calculations
    total_cost = (
        wall_weight * wall_props["cost_per_kg"]
        + roof_weight * roof_props["cost_per_kg"]
        + window_weight * window_props["cost_per_kg"]
    )

    # Thermal mass
    total_mass = (
        wall_area * wall_props["density"] * 0.2
        + roof_area * roof_props["density"] * 0.15
    )
    total_specific_heat = (wall_props["specific_heat"] + roof_props["specific_heat"]) / 2

    # 24-hour simulation loop
    current_temp = initial_temp
    shelter_temps = []
    external_wall_temps = []

    for hour in range(24):
        t_out = outdoor_temps[hour]
        solar = solar_irradiance[hour]

        # IR stealth: external surface temperature
        t_surf = calculate_external_surface_temp(current_temp, t_out, wall_props["r_value"])
        external_wall_temps.append(t_surf)

        # Heat losses
        q_wall = calculate_heat_transfer(current_temp, t_out, wall_area, wall_props["r_value"])
        q_roof = calculate_heat_transfer(current_temp, t_out, roof_area, roof_props["r_value"])
        q_window = calculate_heat_transfer(current_temp, t_out, window_area, window_props["r_value"])
        q_door = calculate_heat_transfer(current_temp, t_out, door_area, 0.1)
        q_vent = calculate_ventilation_loss(current_temp, t_out, shelter_volume, ach)

        q_total_loss = q_wall + q_roof + q_window + q_door + q_vent

        # Heat gains
        q_solar = calculate_solar_gain(solar, window_area, absorptivity=0.7)
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
    }


class ShelterOptProblem(Problem):
    """
    NSGA-II Multi-Objective Problem for shelter design.

    Decision Variables (integer-encoded):
      x[0] = wall material index    (0 to len(WALL_MATERIALS)-1)
      x[1] = roof material index    (0 to len(ROOF_MATERIALS)-1)
      x[2] = window material index  (0 to len(WINDOW_MATERIALS)-1)

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
                 max_weight=2500, max_cost=150000, max_glow=0.5):

        n_wall = len(WALL_MATERIALS)
        n_roof = len(ROOF_MATERIALS)
        n_window = len(WINDOW_MATERIALS)

        super().__init__(
            n_var=3,
            n_obj=3,
            n_ieq_constr=3,
            xl=np.array([0, 0, 0]),
            xu=np.array([n_wall - 1, n_roof - 1, n_window - 1]),
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

    def _evaluate(self, X, out, *args, **kwargs):
        F = np.zeros((X.shape[0], 3))
        G = np.zeros((X.shape[0], 3))

        for i, x in enumerate(X):
            wall_idx = int(np.clip(x[0], 0, len(WALL_MATERIALS) - 1))
            roof_idx = int(np.clip(x[1], 0, len(ROOF_MATERIALS) - 1))
            win_idx = int(np.clip(x[2], 0, len(WINDOW_MATERIALS) - 1))

            result = simulate_shelter(
                wall_name=WALL_MATERIALS[wall_idx],
                roof_name=ROOF_MATERIALS[roof_idx],
                window_name=WINDOW_MATERIALS[win_idx],
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
            )

            # Objectives (all minimized)
            F[i, 0] = result["total_weight"]
            F[i, 1] = result["total_cost"]
            F[i, 2] = -result["min_temp"]  # Negate: minimizing = maximizing warmth

            # Constraints (g <= 0 is feasible)
            G[i, 0] = result["total_weight"] - self.max_weight
            G[i, 1] = result["total_cost"] - self.max_cost
            G[i, 2] = result["max_ir_glow"] - self.max_glow

        out["F"] = F
        out["G"] = G


def run_optimization(wall_area, roof_area, window_area, door_area,
                     shelter_volume, occupants, ach,
                     outdoor_temps, solar_irradiance, initial_temp,
                     max_weight=2500, max_cost=150000, max_glow=0.5,
                     pop_size=100, n_gen=50, seed=42):
    """
    Execute the NSGA-II optimization and return the top Pareto-optimal blueprints.

    Returns:
        list[dict]: Top blueprints sorted by minimum internal temperature (warmest first).
                    Each dict contains: wall, roof, window, total_weight, total_cost,
                    min_temp, max_ir_glow, comfort_hours.
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

            wall_name = WALL_MATERIALS[wall_idx]
            roof_name = ROOF_MATERIALS[roof_idx]
            window_name = WINDOW_MATERIALS[win_idx]

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
            )

            comfort_hours = sum(1 for t in result["shelter_temps"] if t >= -10)

            blueprints.append({
                "wall": wall_name,
                "roof": roof_name,
                "window": window_name,
                "total_weight": result["total_weight"],
                "total_cost": result["total_cost"],
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
        key = (bp["wall"], bp["roof"], bp["window"])
        if key not in seen:
            seen.add(key)
            unique_blueprints.append(bp)

    return unique_blueprints
