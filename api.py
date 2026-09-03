from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
import datetime
import asyncio
import json
import math
import random
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import existing microservices
from wind_load import run_wind_analysis, get_max_safe_wind
from optimize import run_optimization
from weather_service import fetch_weather
from casualty_risk import calculate_wind_chill, frostbite_risk
from swarm_microgrid import ShelterNode, route_swarm_energy, manage_swarm_batteries

app = FastAPI(
    title="DRDO Shelter Simulator API",
    description="Enterprise REST API exposing core physics, logistics, and generative design microservices for Indian Army C2 Integration.",
    version="1.0.0",
    docs_url="/docs", 
    redoc_url="/redoc"
)

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:5173", "http://localhost:3000", "https://drdo.gov.in"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Secure Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# ==========================================
# 1. WIND LOAD & STRUCTURAL ANALYSIS API
# ==========================================
class WindLoadRequest(BaseModel):
    wall_material: str = Field(default="Brick", example="Concrete", max_length=100)
    roof_material: str = Field(default="Polyurethane Panel (PUF)", example="Carbon Fiber Panel", max_length=100)
    wall_area: float = Field(default=40.0, gt=0, le=500.0)
    roof_area: float = Field(default=24.0, gt=0, le=500.0)
    altitude_m: float = Field(default=4500.0, ge=0, le=8848.0)
    hourly_wind_speeds_kmh: List[float] = Field(..., example=[10, 45, 120, 60, 20], max_length=24)

@app.post("/wind-load/analyze", tags=["Structural Engineering"])
@limiter.limit("10/minute")
async def analyze_wind_load(request: Request, req: WindLoadRequest):
    """
    Analyzes the structural safety of a shelter envelope against a series of wind gusts.
    Accounts for altitude-adjusted air density and computes simply-supported beam stress.
    """
    try:
        config = req.model_dump()
        result = run_wind_analysis(config, req.hourly_wind_speeds_kmh)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 2. INVERSE AI GENERATIVE DESIGNER API
# ==========================================
class OptimizerRequest(BaseModel):
    wall_area: float = Field(default=52.0, gt=0, le=500)
    roof_area: float = Field(default=24.0, gt=0, le=500)
    window_area: float = Field(default=4.0, ge=0, le=100)
    door_area: float = Field(default=2.0, ge=0, le=50)
    volume: float = Field(default=60.0, gt=0, le=1000)
    occupants: int = Field(default=5, gt=0, le=100)
    ach: float = Field(default=0.3, ge=0.1, le=5.0)
    initial_temp: float = Field(default=-10.0, ge=-60.0, le=50.0)
    max_weight_kg: float = Field(default=2500.0, gt=0, le=20000.0)
    max_cost_inr: float = Field(default=150000.0, gt=0, le=10000000.0)
    location_name: str = Field(default="DBO (Daulat Beg Oldi)", max_length=100)
    pop_size: int = Field(default=20, ge=10, le=200)
    n_gen: int = Field(default=10, ge=5, le=100)

@app.post("/optimize/generate-blueprints", tags=["Generative AI"])
@limiter.limit("5/minute")
async def generate_blueprints(request: Request, req: OptimizerRequest):
    """
    Runs the NSGA-II Genetic Algorithm to evolve the optimal shelter blueprints.
    Automatically filters out materials that are unavailable at the target deployment zone.
    """
    try:
        # Mocking synthetic weather for the API endpoint speed
        weather_res = fetch_weather(35.0, 77.0, datetime.date.today(), num_days=1, use_api=False)
        outdoor_temps = [h["temperature_c"] for h in weather_res["hourly_data"]][:24]
        solar_irradiance = [h["solar_irradiance_wm2"] for h in weather_res["hourly_data"]][:24]

        blueprints = run_optimization(
            wall_area=req.wall_area, roof_area=req.roof_area, window_area=req.window_area, door_area=req.door_area,
            shelter_volume=req.volume, occupants=req.occupants, ach=req.ach,
            outdoor_temps=outdoor_temps, solar_irradiance=solar_irradiance, initial_temp=req.initial_temp,
            max_weight=req.max_weight_kg, max_cost=req.max_cost_inr, location_name=req.location_name,
            pop_size=req.pop_size, n_gen=req.n_gen
        )
        return {"status": "success", "blueprints_found": len(blueprints), "data": blueprints[:3]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 3. CASUALTY RISK & MEDICAL API
# ==========================================
class CasualtyRequest(BaseModel):
    ambient_temp_c: float = Field(..., example=-30.0, ge=-80.0, le=50.0)
    wind_speed_kmh: float = Field(..., example=60.0, ge=0.0, le=200.0)

@app.post("/casualty/frostbite-risk", tags=["Medical Intelligence"])
@limiter.limit("20/minute")
async def predict_frostbite(request: Request, req: CasualtyRequest):
    """
    Predicts the exact time to frostbite for exposed skin using NATO STANAG 2895 Wind Chill metrics.
    """
    try:
        wct = calculate_wind_chill(req.ambient_temp_c, req.wind_speed_kmh)
        risk = frostbite_risk(wct)
        return {
            "status": "success",
            "data": {
                "input_temp_c": req.ambient_temp_c,
                "input_wind_kmh": req.wind_speed_kmh,
                "effective_wind_chill_c": round(wct, 2),
                "frostbite_assessment": risk
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 4. SWARM MICROGRID API
# ==========================================
class SwarmRequest(BaseModel):
    solar_irradiance: float = Field(..., example=800.0, ge=0.0)
    outdoor_temps_2h: List[float] = Field(..., example=[-20.0, -22.0])
    current_hour: int = Field(..., example=14, ge=0, le=23)

@app.post("/swarm/manage-fleet", tags=["Microgrid Operations"])
@limiter.limit("10/minute")
async def manage_swarm_fleet(request: Request, req: SwarmRequest):
    """
    Executes Predictive Energy Routing and Virtual Power Plant (VPP) battery balancing
    across a decentralized swarm of 10 tactical shelters.
    """
    try:
        # Generate 10 shelters with varying states to demonstrate the algorithm
        shelters = [
            ShelterNode(1, initial_temp=-5.0, initial_soc=30, health_cycles=6000), # Cold, low batt
            ShelterNode(2, initial_temp=2.0, initial_soc=85, health_cycles=1000),  # Warm, high batt
            ShelterNode(3, initial_temp=-1.0, initial_soc=50, health_cycles=4000),
            ShelterNode(4, initial_temp=4.0, initial_soc=90, health_cycles=500),
            ShelterNode(5, initial_temp=-8.0, initial_soc=20, health_cycles=7000), # Very cold
            ShelterNode(6, initial_temp=5.0, initial_soc=100, health_cycles=200),
            ShelterNode(7, initial_temp=1.0, initial_soc=45, health_cycles=8500),  # Failing battery
            ShelterNode(8, initial_temp=-2.0, initial_soc=60, health_cycles=3000),
            ShelterNode(9, initial_temp=3.0, initial_soc=75, health_cycles=1500),
            ShelterNode(10, initial_temp=6.0, initial_soc=95, health_cycles=100),
        ]
        
        routing = route_swarm_energy(shelters, req.solar_irradiance, req.outdoor_temps_2h, f"{req.current_hour}:00 IST")
        vpp_status = manage_swarm_batteries(shelters, req.current_hour)
        
        return {
            "status": "success",
            "data": {
                "energy_routing_matrix": routing,
                "virtual_power_plant_status": vpp_status
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ==========================================
# 5. WEBSOCKET TELEMETRY STREAM
# ==========================================
@app.websocket("/telemetry")
async def telemetry_stream(websocket: WebSocket):
    """
    Streams live simulation telemetry to the 3D visualization frontend
    at 1 Hz (1 JSON payload per second).
    """
    await websocket.accept()
    hour = 0
    try:
        while True:
            day = hour // 24
            hour_of_day = hour % 24
            # Synthetic diurnal cycle
            base_temp = -25 + 5 * math.sin((day / 30) * math.pi)
            diurnal = 8 * math.sin(((hour_of_day - 6) / 24) * 2 * math.pi)
            outside_temp = round(base_temp + diurnal + random.uniform(-1.5, 1.5), 1)
            solar = max(0, round(800 * math.sin(((hour_of_day - 7) / 10) * math.pi) * random.uniform(0.6, 1.0))) if 7 <= hour_of_day <= 17 else 0
            wind = round(20 + 30 * random.random() + (15 if hour_of_day > 18 else 0))
            shelter_temp = round(outside_temp + 18 + solar / 200 - wind / 40, 1)
            stress = round(min(1.0, 0.1 + day * 0.025 + (0.2 if wind > 50 else 0)), 2)
            failures = []
            if day >= 7 and stress > 0.6:
                failures.append('concrete_crack')
            if day >= 15 and stress > 0.8:
                failures.append('steel_corrosion')

            payload = {
                "timestamp": datetime.datetime.now().isoformat(),
                "day": day,
                "hour": hour_of_day,
                "shelter_temp": shelter_temp,
                "outside_temp": outside_temp,
                "solar_irradiance": solar,
                "wind_speed": wind,
                "battery_soc": max(5, round(100 - day * 2.5 - (10 if hour_of_day > 18 else 0) + solar / 50)),
                "power_demand": round(3000 + abs(shelter_temp) * 100 + wind * 20),
                "material_stress": stress,
                "failures": failures,
            }
            await websocket.send_text(json.dumps(payload))
            hour = (hour + 1) % 720
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
