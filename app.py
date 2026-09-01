import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from fpdf import FPDF
import base64
from datetime import date as date_type
from physics import (
    calculate_heat_transfer, 
    calculate_solar_gain, 
    calculate_new_temperature,
    calculate_external_surface_temp,
    calculate_metabolic_heat,       
    calculate_ventilation_loss,     
    MATERIALS,
    WALL_MATERIALS,
    ROOF_MATERIALS,
    WINDOW_MATERIALS,
)
from optimize import run_optimization
from solar_terrain import run_terrain_shadow_pipeline

st.set_page_config(page_title="Thermal Shelter Simulator", layout="wide")
st.title("🏔️ Ladakh Thermal Shelter Simulator (SIH26051)")

# Sidebar: Input Parameters
st.sidebar.header("Shelter Configuration")

# Shelter Dimensions
shelter_length = st.sidebar.slider("Length (m)", 2.0, 15.0, 6.0)
shelter_width = st.sidebar.slider("Width (m)", 2.0, 15.0, 4.0)
shelter_height = st.sidebar.slider("Height (m)", 1.5, 5.0, 2.5)



# Calculate areas and volume
wall_area = 2 * (shelter_length + shelter_width) * shelter_height
roof_area = shelter_length * shelter_width
shelter_volume = shelter_length * shelter_width * shelter_height  # NEW: Needed for ventilation

window_area = st.sidebar.slider("Window Area (m²)", 0.0, 10.0, 3.0)
door_area = st.sidebar.slider("Door Area (m²)", 0.0, 5.0, 1.5)

# NEW: Tactical & Biological Inputs
st.sidebar.header("Tactical & Biological")
occupants = st.sidebar.number_input("Number of Troops (Occupancy)", 0, 20, 5)
ach = st.sidebar.slider("Ventilation (Air Changes/Hour)", 0.0, 3.0, 0.5, step=0.1)

# Asphyxiation Warning Logic
if ach < 0.3:
    st.sidebar.error("⚠️ LETHAL HYPOXIA RISK: Ventilation is too low. CO2 buildup imminent.")
elif ach > 1.5:
    st.sidebar.warning("⚠️ SEVERE HEAT LOSS: High ventilation will drain thermal mass.")
else:
    st.sidebar.success("✅ Ventilation in safe operational range.")
# Material Selection
st.sidebar.header("Materials")
wall_material = st.sidebar.selectbox("Wall Material", WALL_MATERIALS, index=1)  # Default: Brick
roof_material = st.sidebar.selectbox("Roof Material", ROOF_MATERIALS, index=2)  # Default: PUF
window_material = st.sidebar.selectbox("Window Material", WINDOW_MATERIALS, index=0)  # Default: Glass (Single Pane)

# Initial Conditions
st.sidebar.header("Initial Conditions")
initial_temp = st.sidebar.slider("Initial Shelter Temperature (°C)", -30.0, 0.0, -5.0)

# Load Weather Data
st.sidebar.header("Weather Data")
weather_file = st.file_uploader("Upload Ladakh Weather CSV", type=["csv"])

if weather_file is None:
    # Load default generated data
    try:
        weather_data = pd.read_csv("ladakh_winter.csv")
        st.sidebar.info("Using generated Ladakh winter data")
    except FileNotFoundError:
        st.error("❌ Please run `python generate_data.py` first!")
        st.stop()
else:
    weather_data = pd.read_csv(weather_file)

# Extract weather columns
hours = weather_data["Hour"].values
outdoor_temps = weather_data["Temperature_C"].values
solar_irradiance_raw = weather_data["Solar_Irradiance_W_m2"].values

# ============ TERRAIN SHADOW MAPPING (Sidebar + Processing) ============
st.sidebar.header("🗺️ Terrain Shadow Mapping")
enable_terrain = st.sidebar.checkbox("Enable Terrain-Aware Solar", value=False)

deploy_lat = st.sidebar.number_input("Latitude (°N)", -90.0, 90.0, 34.1526, format="%.4f")
deploy_lon = st.sidebar.number_input("Longitude (°E)", -180.0, 180.0, 77.5771, format="%.4f")
deploy_date = st.sidebar.date_input("Deployment Date", value=date_type.today())
terrain_radius = st.sidebar.slider("Scan Radius (km)", 1.0, 10.0, 5.0, step=0.5)

# Process terrain shadow if enabled
terrain_result = None
solar_irradiance = solar_irradiance_raw.copy()

if enable_terrain:
    with st.spinner("🛰️ Fetching terrain data & computing shadow mask..."):
        terrain_result = run_terrain_shadow_pipeline(
            lat=deploy_lat,
            lon=deploy_lon,
            date=deploy_date,
            base_irradiance=solar_irradiance_raw,
            radius_km=terrain_radius,
        )
    if terrain_result["status"] == "ok":
        solar_irradiance = terrain_result["modified_irradiance"]
        st.sidebar.success(f"✅ Shadow mapped: {terrain_result['shadowed_hours']} daylight hrs blocked")
    else:
        st.sidebar.error(f"⚠️ {terrain_result.get('error_msg', 'API error')} — using raw solar data")

# ============ SIMULATION ============
st.header("🔬 Simulation Results")

# Get material properties
wall_props = MATERIALS[wall_material]
roof_props = MATERIALS[roof_material]
window_props = MATERIALS[window_material]

# Calculate total thermal mass (simplified: use walls + roof only)
total_mass = (wall_area * wall_props["density"] * 0.2 +  # 20cm thick walls
              roof_area * roof_props["density"] * 0.15)    # 15cm thick roof
total_specific_heat = (wall_props["specific_heat"] + roof_props["specific_heat"]) / 2

# Simulate 24-hour cycle
shelter_temps = [initial_temp]
q_losses = []
q_gains = []
external_wall_temps = []

current_temp = initial_temp

for hour in range(24):
    t_out = outdoor_temps[hour]
    solar = solar_irradiance[hour]
    
    # Calculate how warm the outside wall gets for enemy IR scopes
    t_surf = calculate_external_surface_temp(current_temp, t_out, wall_props["r_value"])
    external_wall_temps.append(t_surf)
    
   
  # Heat transfers calculations
    q_wall = calculate_heat_transfer(current_temp, t_out, wall_area, wall_props["r_value"])
    q_roof = calculate_heat_transfer(current_temp, t_out, roof_area, roof_props["r_value"])
    q_window_loss = calculate_heat_transfer(current_temp, t_out, window_area, window_props["r_value"])
    q_door = calculate_heat_transfer(current_temp, t_out, door_area, 0.1)
    
    # NEW: Ventilation Heat Loss
    q_vent = calculate_ventilation_loss(current_temp, t_out, shelter_volume, ach)
    
    # NEW: Metabolic Heat Gain
    q_human = calculate_metabolic_heat(occupants)
    
    # Calculate total loss and total gain
    q_total_loss = q_wall + q_roof + q_window_loss + q_door + q_vent
    q_solar = calculate_solar_gain(solar, window_area, absorptivity=0.7)
    q_total_gain = q_solar + q_human  # Add human heat to total gain
    
    # Update temperature (Use q_total_gain instead of just q_solar)
    new_temp = calculate_new_temperature(current_temp, q_total_gain, q_total_loss, total_mass, total_specific_heat)
    
    shelter_temps.append(new_temp)
    q_losses.append(q_total_loss)
    q_gains.append(q_total_gain)  # Track total combined gain for the charts
    current_temp = new_temp

shelter_temps = shelter_temps[:-1]  # Remove last point (24h mark already included)

# ============ RESULTS ============
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("🌡️ Min Temp (°C)", f"{min(shelter_temps):.1f}")
with col2:
    st.metric("🔥 Max Temp (°C)", f"{max(shelter_temps):.1f}")
with col3:
    comfort_hours = sum(1 for t in shelter_temps if t >= -10)
    st.metric("😊 Comfort Hours (>-10°C)", f"{comfort_hours}/24")
with col4:
    avg_temp = np.mean(shelter_temps)
    st.metric("📊 Avg Temp (°C)", f"{avg_temp:.1f}")

# ============ INTERACTIVE PLOTLY GRAPHS ============
st.markdown("---")
plot_col1, plot_col2 = st.columns(2)

with plot_col1:
    # Plot 1: Temperature Comparison
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=hours, y=outdoor_temps, mode='lines+markers', name='Outside Temp', line=dict(color='#3498db')))
    fig1.add_trace(go.Scatter(x=hours, y=shelter_temps, mode='lines+markers', name='Shelter Temp', line=dict(color='#e74c3c')))
    fig1.add_hline(y=-10, line_dash="dash", line_color="#2ecc71", annotation_text="Comfort Threshold (-10°C)", annotation_position="bottom right")
    fig1.update_layout(title="Temperature Profile: 24-Hour Cycle", xaxis_title="Hour of Day", yaxis_title="Temperature (°C)", hovermode="x unified")
    st.plotly_chart(fig1, use_container_width=True)

    # Plot 3: Solar Irradiance (with terrain shadow overlay if enabled)
    fig3 = go.Figure()
    if enable_terrain and terrain_result and terrain_result["status"] == "ok":
        # Show original as faded background
        fig3.add_trace(go.Scatter(x=hours, y=solar_irradiance_raw, mode='lines',
                                   name='Original (No Shadow)', line=dict(color='#f39c12', dash='dot', width=1),
                                   fillcolor='rgba(243, 156, 18, 0.05)', fill='tozeroy'))
        # Show terrain-modified as solid
        fig3.add_trace(go.Scatter(x=hours, y=solar_irradiance, mode='lines+markers',
                                   name='Terrain-Modified', line=dict(color='#e74c3c', width=3),
                                   fillcolor='rgba(231, 76, 60, 0.2)', fill='tozeroy'))
        fig3.update_layout(title="🗺️ Solar Radiation (Terrain Shadow Applied)",
                           xaxis_title="Hour of Day", yaxis_title="Solar Irradiance (W/m²)",
                           hovermode="x unified")
    else:
        fig3.add_trace(go.Scatter(x=hours, y=solar_irradiance, mode='lines+markers',
                                   name='Solar Irradiance', fill='tozeroy',
                                   line=dict(color='#f39c12'), fillcolor='rgba(243, 156, 18, 0.2)'))
        fig3.update_layout(title="Solar Radiation Profile", xaxis_title="Hour of Day",
                           yaxis_title="Solar Irradiance (W/m²)", hovermode="x unified")
    st.plotly_chart(fig3, use_container_width=True)

with plot_col2:
    # Plot 2: Heat Gains vs Losses
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=hours, y=q_gains, name='Solar Gain', marker_color='#f1c40f'))
    fig2.add_trace(go.Bar(x=hours, y=[-q for q in q_losses], name='Heat Loss', marker_color='#00cec9'))
    fig2.update_layout(title="Heat Gains vs Losses", xaxis_title="Hour of Day", yaxis_title="Heat Transfer (W)", barmode='relative', hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

    # Plot 4: Comfort Analysis
    fig4 = go.Figure()
    comfort = [1 if t >= -10 else 0 for t in shelter_temps]
    colors = ['#2ecc71' if c else '#e74c3c' for c in comfort]
    hover_texts = [f"Hour {h}: {t:.1f}°C (Comfortable)" if c else f"Hour {h}: {t:.1f}°C (Cold)" for h, t, c in zip(hours, shelter_temps, comfort)]
    fig4.add_trace(go.Bar(x=hours, y=[1]*24, marker_color=colors, hoverinfo="text", hovertext=hover_texts, showlegend=False))
    fig4.update_layout(title="Comfort Hours (Green = Comfortable, Red = Cold)", xaxis_title="Hour of Day", yaxis_title="Comfort Status", yaxis=dict(tickvals=[0, 1], ticktext=["Cold", "Comfortable"]))
    st.plotly_chart(fig4, use_container_width=True)

# ============ TERRAIN SHADOW ANALYSIS SECTION ============
if enable_terrain and terrain_result and terrain_result["status"] == "ok":
    st.markdown("---")
    st.header("🗺️ Topographical Shadow Analysis")
    st.caption(f"GPS: {deploy_lat}°N, {deploy_lon}°E | Date: {deploy_date} | Scan Radius: {terrain_radius} km")

    shadow_col1, shadow_col2, shadow_col3 = st.columns(3)
    with shadow_col1:
        st.metric("🏔️ Site Elevation", f"{terrain_result['terrain_data']['site_elevation']:,.0f} m")
    with shadow_col2:
        st.metric("🌑 Shadow Hours (Daylight)", f"{terrain_result['shadowed_hours']}")
    with shadow_col3:
        solar_loss_pct = 0
        raw_total = solar_irradiance_raw.sum()
        if raw_total > 0:
            solar_loss_pct = ((raw_total - solar_irradiance.sum()) / raw_total) * 100
        st.metric("☀️ Solar Energy Lost", f"{solar_loss_pct:.1f}%")

    # Sun Path vs Horizon Angle chart
    shadow_data = terrain_result["shadow_mask"]
    sun_pos = terrain_result["sun_positions"]

    fig_shadow = go.Figure()

    # Sun altitude curve
    fig_shadow.add_trace(go.Scatter(
        x=hours, y=sun_pos["altitudes"],
        mode='lines+markers', name='Sun Altitude',
        line=dict(color='#f39c12', width=3),
        marker=dict(size=6),
    ))

    # Horizon angle at sun's azimuth
    fig_shadow.add_trace(go.Scatter(
        x=hours, y=shadow_data["horizon_at_sun"],
        mode='lines', name='Terrain Horizon',
        line=dict(color='#e74c3c', width=2, dash='dash'),
        fill='tozeroy', fillcolor='rgba(231, 76, 60, 0.1)',
    ))

    # Shade the blocked hours
    for h in range(24):
        if shadow_data["is_shadowed"][h] and sun_pos["altitudes"][h] > 0:
            fig_shadow.add_vrect(
                x0=h - 0.5, x1=h + 0.5,
                fillcolor="rgba(0, 0, 0, 0.15)", layer="below",
                line_width=0,
            )

    fig_shadow.add_hline(y=0, line_dash="solid", line_color="gray",
                          annotation_text="Geometric Horizon (0°)")
    fig_shadow.update_layout(
        title="Sun Path vs Mountain Horizon (Shaded = Blocked by Terrain)",
        xaxis_title="Hour of Day", yaxis_title="Angle (degrees)",
        hovermode="x unified", height=400,
    )
    st.plotly_chart(fig_shadow, use_container_width=True)

    # Shadow hour indicator bar
    fig_shadow_bar = go.Figure()
    shadow_colors = []
    shadow_hover = []
    for h in range(24):
        alt = sun_pos["altitudes"][h]
        if alt <= 0:
            shadow_colors.append('#1a1a2e')  # Night
            shadow_hover.append(f"Hour {h}: Night (Sun below horizon)")
        elif shadow_data["is_shadowed"][h]:
            shadow_colors.append('#c0392b')  # Shadow
            shadow_hover.append(f"Hour {h}: ⛰️ SHADOWED (Sun {alt:.1f}° < Horizon {shadow_data['horizon_at_sun'][h]:.1f}°)")
        else:
            shadow_colors.append('#f1c40f')  # Sunlit
            shadow_hover.append(f"Hour {h}: ☀️ Sunlit (Sun {alt:.1f}°)")

    fig_shadow_bar.add_trace(go.Bar(
        x=hours, y=[1]*24, marker_color=shadow_colors,
        hoverinfo='text', hovertext=shadow_hover, showlegend=False,
    ))
    fig_shadow_bar.update_layout(
        title="Shadow Timeline (Yellow=Sun, Red=Mountain Shadow, Dark=Night)",
        xaxis_title="Hour of Day", yaxis_visible=False, height=200,
    )
    st.plotly_chart(fig_shadow_bar, use_container_width=True)

# ============ MILITARY LOGISTICS & AIRLIFT ENGINE ============
st.markdown("---")
st.header("🚁 Logistics & Airlift Feasibility")

# 1. Calculate Weights (assuming 20cm walls, 15cm roof, 1cm glass windows)
wall_weight = wall_area * wall_props["density"] * 0.20
roof_weight = roof_area * roof_props["density"] * 0.15
window_weight = window_area * window_props["density"] * 0.01

total_deployment_weight = wall_weight + roof_weight + window_weight

# 2. Calculate Procurement Cost
total_cost_inr = (
    (wall_weight * wall_props["cost_per_kg"]) + 
    (roof_weight * roof_props["cost_per_kg"]) + 
    (window_weight * window_props["cost_per_kg"])
)

# 3. Helicopter Feasibility Logic (Indian Air Force Assets)
airlift_status = ""
airlift_color = ""

if total_deployment_weight <= 1500:
    airlift_status = "✅ HAL Dhruv (ALH) - Light Transport"
    airlift_color = "normal"
elif total_deployment_weight <= 4000:
    airlift_status = "⚠️ Mi-17 V5 - Medium Transport"
    airlift_color = "off"
elif total_deployment_weight <= 10000:
    airlift_status = "🚨 CH-47 Chinook - Heavy Lift Required"
    airlift_color = "inverse"
else:
    airlift_status = "❌ AIRLIFT IMPOSSIBLE: Requires Road Transport (Convoy)"
    airlift_color = "inverse"

# Display Logistics Metrics
log1, log2, log3 = st.columns(3)

with log1:
    st.metric("⚖️ Total Shelter Weight", f"{total_deployment_weight:,.0f} kg")
with log2:
    st.metric("💰 Est. Material Cost", f"₹ {total_cost_inr:,.0f}")
with log3:
    st.info(f"**Airlift Requirement:**\n\n{airlift_status}")
    
    # ============ TACTICAL THERMAL STEALTH ============
st.markdown("---")
st.header("🎯 Tactical Thermal Stealth (IR Signature)")

# Calculate the maximum temperature difference between the wall and the outside air
max_temp_diff = max([surf - amb for surf, amb in zip(external_wall_temps, outdoor_temps)])

stealth_col1, stealth_col2 = st.columns([2, 1])

with stealth_col1:
    if max_temp_diff < 0.5:
        st.success("🟢 EXCELLENT: Thermal signature is nearly invisible to enemy IR scopes.")
    elif max_temp_diff < 2.0:
        st.warning("🟡 MODERATE: Slight thermal blooming visible on high-res IR drones.")
    else:
        st.error("🔴 DANGER: High IR signature detected. Shelter is a glowing target.")

with stealth_col2:
    st.metric("Max External Wall Heat Glow", f"+{max_temp_diff:.2f} °C", delta_color="inverse")

st.caption("Military Note: If the external wall is more than 0.5°C warmer than the ambient air, it can be detected by thermal imaging.")

# ============ AI AUTO-DESIGNER (NSGA-II) ============
st.markdown("---")
st.header("🧬 Inverse AI Generative Designer")
st.caption("Uses NSGA-II (Non-dominated Sorting Genetic Algorithm II) to evolve optimal shelter material blueprints across 5,000+ permutations.")

# Constraint sliders in the sidebar
st.sidebar.header("🧬 AI Auto-Designer")
ai_max_weight = st.sidebar.slider("Max Payload (kg)", 500, 10000, 2500, step=100)
ai_max_cost = st.sidebar.slider("Max Budget (INR)", 10000, 500000, 150000, step=5000)
ai_max_glow = st.sidebar.slider("Max IR Glow (°C)", 0.1, 3.0, 0.5, step=0.1)
ai_pop_size = st.sidebar.select_slider("Population Size", options=[50, 100, 150, 200], value=100)
ai_n_gen = st.sidebar.select_slider("Generations", options=[25, 50, 75, 100], value=50)

run_ai = st.button("🚀 Run AI Optimizer", type="primary", use_container_width=True)

if run_ai:
    with st.spinner(f"Evolving {ai_pop_size * ai_n_gen:,} shelter permutations via NSGA-II..."):
        blueprints = run_optimization(
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
            max_weight=ai_max_weight,
            max_cost=ai_max_cost,
            max_glow=ai_max_glow,
            pop_size=ai_pop_size,
            n_gen=ai_n_gen,
        )

    if not blueprints:
        st.error("❌ No feasible blueprints found. Try relaxing your constraints (increase budget or payload limit).")
    else:
        st.success(f"✅ Found {len(blueprints)} Pareto-optimal blueprint(s). Showing top 3:")
        top_blueprints = blueprints[:3]

        # Summary comparison table
        summary_data = []
        for i, bp in enumerate(top_blueprints):
            summary_data.append({
                "Rank": f"#{i+1}",
                "Wall": bp["wall"],
                "Roof": bp["roof"],
                "Window": bp["window"],
                "Weight (kg)": f"{bp['total_weight']:,.0f}",
                "Cost (INR)": f"₹{bp['total_cost']:,.0f}",
                "Min Temp (°C)": f"{bp['min_temp']:.1f}",
                "IR Glow (°C)": f"+{bp['max_ir_glow']:.2f}",
                "Comfort Hrs": f"{bp['comfort_hours']}/24",
            })

        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

        # Detailed expanders for each blueprint
        for i, bp in enumerate(top_blueprints):
            medal = ["🥇", "🥈", "🥉"][i]
            with st.expander(f"{medal} Blueprint #{i+1}: {bp['wall']} + {bp['roof']} + {bp['window']}"):
                bp_col1, bp_col2, bp_col3, bp_col4 = st.columns(4)
                with bp_col1:
                    st.metric("⚖️ Weight", f"{bp['total_weight']:,.0f} kg")
                with bp_col2:
                    st.metric("💰 Cost", f"₹{bp['total_cost']:,.0f}")
                with bp_col3:
                    st.metric("🌡️ Min Temp", f"{bp['min_temp']:.1f}°C")
                with bp_col4:
                    st.metric("🎯 IR Glow", f"+{bp['max_ir_glow']:.2f}°C")

                # Temperature profile chart for this blueprint
                fig_bp = go.Figure()
                fig_bp.add_trace(go.Scatter(
                    x=list(range(24)), y=outdoor_temps.tolist(),
                    mode='lines', name='Outside',
                    line=dict(color='#3498db', dash='dot')
                ))
                fig_bp.add_trace(go.Scatter(
                    x=list(range(24)), y=bp["shelter_temps"],
                    mode='lines+markers', name=f'Blueprint #{i+1}',
                    line=dict(color='#e74c3c', width=3)
                ))
                fig_bp.add_hline(y=-10, line_dash="dash", line_color="#2ecc71",
                                 annotation_text="Comfort Threshold")
                fig_bp.update_layout(
                    title=f"24h Thermal Profile — Blueprint #{i+1}",
                    xaxis_title="Hour", yaxis_title="Temperature (°C)",
                    hovermode="x unified", height=350
                )
                st.plotly_chart(fig_bp, use_container_width=True)

                # Airlift feasibility for this blueprint
                if bp["total_weight"] <= 1500:
                    st.info("🚁 **Airlift:** HAL Dhruv (ALH) — Light Transport")
                elif bp["total_weight"] <= 4000:
                    st.warning("🚁 **Airlift:** Mi-17 V5 — Medium Transport")
                elif bp["total_weight"] <= 10000:
                    st.error("🚁 **Airlift:** CH-47 Chinook — Heavy Lift")
                else:
                    st.error("❌ **Airlift:** IMPOSSIBLE — Road Convoy Required")

# ============ CONFIGURATION SUMMARY ============
st.markdown("---")
st.header("📋 Configuration Summary")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Shelter Dimensions")
    st.write(f"- **Length:** {shelter_length} m")
    st.write(f"- **Width:** {shelter_width} m")
    st.write(f"- **Height:** {shelter_height} m")
    st.write(f"- **Wall Area:** {wall_area:.1f} m²")
    st.write(f"- **Roof Area:** {roof_area:.1f} m²")
    st.write(f"- **Window Area:** {window_area} m²")
    st.write(f"- **Door Area:** {door_area} m²")

with col2:
    st.subheader("Material Properties")
    st.write(f"- **Walls:** {wall_material} (R={wall_props['r_value']})")
    st.write(f"- **Roof:** {roof_material} (R={roof_props['r_value']})")
    st.write(f"- **Windows:** {window_material} (R={window_props['r_value']})")
    st.write(f"- **Total Thermal Mass:** {total_mass:.0f} kg")

# Export Results
st.header("📥 Export Results")
results_df = pd.DataFrame({
    "Hour": hours,
    "Outside_Temp_C": outdoor_temps,
    "Shelter_Temp_C": shelter_temps,
    "Solar_Irradiance_W_m2": solar_irradiance,
    "Heat_Loss_W": q_losses,
    "Solar_Gain_W": q_gains
})

csv = results_df.to_csv(index=False)
st.download_button(label="Download Results as CSV", data=csv, file_name="shelter_simulation_results.csv", mime="text/csv")

# ============  TACTICAL PDF EXPORTER 
import os
import matplotlib.pyplot as plt
from fpdf import FPDF

class TacticalDossierPDF(FPDF):
    def header(self):
        # Dark Slate Banner
        self.set_fill_color(30, 41, 59)
        self.rect(0, 0, 210, 16, 'F')
        self.set_font("Arial", 'B', 9)
        self.set_text_color(255, 255, 255)  # FIXED
        self.cell(0, 6, "RESTRICTED // DRDO HIGH-ALTITUDE FIELD SIMULATION // TACTICAL DOSSIER", 0, 1, 'C')
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Arial", 'I', 8)
        self.set_text_color(148, 163, 184)  # FIXED
        self.cell(0, 8, f"Page {self.page_no()} | DRDO SIH26051 Tactical Thermal Simulation Engine", 0, 0, 'C')

def create_dossier_charts(hours, outdoor_temps, shelter_temps, q_gains, q_losses, terrain_enabled=False, terrain_res=None):
    """Generates high-resolution 300 DPI analytical charts for the PDF dossier."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2), dpi=300)
    
    # --- Chart 1: Thermal Trajectory ---
    ax1.plot(hours, outdoor_temps, label="Ambient Air", color="#3b82f6", linestyle="--", linewidth=1.5)
    ax1.plot(hours, shelter_temps, label="Shelter Interior", color="#ef4444", linewidth=2.5)
    ax1.axhline(y=-10, color="#10b981", linestyle=":", linewidth=1.5, label="Comfort Baseline (-10 C)")
    ax1.set_title("24-Hour Thermal Survival Curve", fontsize=10, fontweight="bold", pad=8)
    ax1.set_xlabel("Hour of Day (00:00 - 23:00)", fontsize=8)
    ax1.set_ylabel("Temperature (deg C)", fontsize=8)
    ax1.set_xlim(0, 23)
    ax1.grid(True, linestyle="--", alpha=0.4)
    ax1.legend(fontsize=7, loc="lower left")

    # --- Chart 2: Dynamic Energy Balance ---
    ax2.bar(hours - 0.2, q_gains, width=0.4, label="Heat Gain (Solar+Troops)", color="#f59e0b", alpha=0.85)
    ax2.bar(hours + 0.2, [-q for q in q_losses], width=0.4, label="Heat Loss (Envelope+Vent)", color="#06b6d4", alpha=0.85)
    ax2.axhline(y=0, color="#64748b", linewidth=0.8)
    ax2.set_title("Dynamic Heat Transfer Balance (Watts)", fontsize=10, fontweight="bold", pad=8)
    ax2.set_xlabel("Hour of Day (00:00 - 23:00)", fontsize=8)
    ax2.set_ylabel("Power Transfer (W)", fontsize=8)
    ax2.set_xlim(-0.5, 23.5)
    ax2.grid(True, linestyle="--", alpha=0.4)
    ax2.legend(fontsize=7, loc="upper right")

    plt.tight_layout()
    chart_filename = "temp_dossier_chart.png"
    plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return chart_filename

def generate_pdf_report():
    pdf = TacticalDossierPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_text_color(30, 41, 59)  # FIXED
    
    # Document Header Title
    pdf.set_font("Arial", 'B', 15)
    pdf.cell(0, 8, "TACTICAL SHELTER THERMAL ASSESSMENT DOSSIER", ln=True)
    pdf.set_font("Arial", '', 8.5)
    pdf.set_text_color(100, 116, 139)  # FIXED
    pdf.cell(0, 4, f"Theatre: Ladakh High Altitude (34.15N, 77.58E) | Date: {deploy_date} | Alt: ~4,500m ASL", ln=True)
    pdf.ln(3)

    # Status KPI Callout Box
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.rect(10, 31, 190, 16, 'DF')
    pdf.set_xy(14, 33)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.set_text_color(15, 23, 42)  # FIXED
    
    clean_airlift = airlift_status.replace('✅','').replace('⚠️','').replace('🚨','').replace('❌','').strip()
    stealth_str = "OPTIMAL (INVISIBLE)" if max_temp_diff < 0.5 else ("MODERATE BLOOM" if max_temp_diff < 2.0 else "HIGH SIGNATURE (ALERT)")
    
    pdf.cell(90, 5, f"LOGISTICS PAYLOAD: {total_deployment_weight:,.0f} kg ({clean_airlift})", 0, 0)
    pdf.cell(90, 5, f"IR STEALTH RATING: {stealth_str} (+{max_temp_diff:.2f} C)", 0, 1)
    
    pdf.set_xy(14, 39)
    pdf.set_font("Arial", '', 8.5)
    pdf.cell(90, 5, f"THERMAL SURVIVAL: Min {min(shelter_temps):.1f} C | Max {max(shelter_temps):.1f} C | Avg {avg_temp:.1f} C", 0, 0)
    
    # Shadow text fallback safely
    shadow_txt = "Disabled"
    if enable_terrain and terrain_result and terrain_result.get('status') == 'ok':
        shadow_txt = f"{terrain_result['shadowed_hours']} hrs blocked"
    pdf.cell(90, 5, f"TERRAIN SHADOW MAPPING: {shadow_txt}", 0, 1)
    pdf.ln(6)

    # --- Section 1: Specifications & Physical Configuration ---
    pdf.set_font("Arial", 'B', 10)
    pdf.set_text_color(15, 23, 42)  # FIXED
    pdf.cell(0, 6, "1. Structural Specifications & Biological Heat Matrix", ln=True)
    
    pdf.set_fill_color(226, 232, 240)
    pdf.set_font("Arial", 'B', 7.5)
    pdf.cell(48, 5, "STRUCTURAL PARAMETER", 1, 0, 'L', True)
    pdf.cell(47, 5, "CONFIGURATION", 1, 0, 'C', True)
    pdf.cell(48, 5, "TACTICAL PARAMETER", 1, 0, 'L', True)
    pdf.cell(47, 5, "SPECIFICATION", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 7.5)
    pdf.cell(48, 4.5, "Dimensions (L x W x H)", 1, 0, 'L')
    pdf.cell(47, 4.5, f"{shelter_length:.1f}m x {shelter_width:.1f}m x {shelter_height:.1f}m", 1, 0, 'C')
    pdf.cell(48, 4.5, "Active Occupants (Troops)", 1, 0, 'L')
    pdf.cell(47, 4.5, f"{occupants} Personnel ({occupants*100} W Load)", 1, 1, 'C')

    pdf.cell(48, 4.5, "Total Envelope Volume", 1, 0, 'L')
    pdf.cell(47, 4.5, f"{shelter_volume:.1f} m3", 1, 0, 'C')
    pdf.cell(48, 4.5, "Ventilation Rate (ACH)", 1, 0, 'L')
    pdf.cell(47, 4.5, f"{ach:.1f} Air Changes/Hour", 1, 1, 'C')

    pdf.cell(48, 4.5, "Wall Envelope Material", 1, 0, 'L')
    pdf.cell(47, 4.5, f"{wall_material[:22]} (R={wall_props['r_value']})", 1, 0, 'C')
    pdf.cell(48, 4.5, "Roof Insulation System", 1, 0, 'L')
    pdf.cell(47, 4.5, f"{roof_material[:22]} (R={roof_props['r_value']})", 1, 1, 'C')

    pdf.cell(48, 4.5, "Glazing Area & Type", 1, 0, 'L')
    pdf.cell(47, 4.5, f"{window_area:.1f} m2 ({window_material[:18]})", 1, 0, 'C')
    pdf.cell(48, 4.5, "Est. Procurement Cost", 1, 0, 'L')
    pdf.cell(47, 4.5, f"INR {total_cost_inr:,.0f}", 1, 1, 'C')
    pdf.ln(4)

    # --- Section 2: High-Resolution Thermal Curves ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "2. High-Altitude Thermal Dynamics & Heat Flux Curves", ln=True)
    
    # Render and insert the chart
    chart_path = create_dossier_charts(hours, outdoor_temps, shelter_temps, q_gains, q_losses)
    pdf.image(chart_path, x=10, y=pdf.get_y(), w=190)
    pdf.ln(78)

    # --- Section 3: Field Engineering Assessment & Sign-Off ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "3. Tactical Survivability & Deployment Assessment", ln=True)
    pdf.set_font("Arial", '', 8)
    
    narrative = (
        f"Under simulated -20.0 C Ladakh operational conditions, the structure maintained an average interior temperature "
        f"of {avg_temp:.1f} C with {comfort_hours}/24 hours above the -10.0 C survival baseline. Total thermal envelope "
        f"mass stands at {total_mass:,.0f} kg with a combined deployment weight of {total_deployment_weight:,.0f} kg, "
        f"validating deployment feasibility under: {clean_airlift}. "
        f"Envelope external thermal differential is +{max_temp_diff:.2f} C relative to ambient, fulfilling "
        f"thermal stealth parameters classified as '{stealth_str}'."
    )
    pdf.multi_cell(0, 4.5, narrative)
    pdf.ln(4)

    # Sign-off box
    pdf.set_font("Arial", 'I', 7.5)
    pdf.cell(95, 5, "Engineering Officer Sign-Off: ________________________", 0, 0, 'L')
    pdf.cell(95, 5, "Document Auth: DRDO-DGRE-SIM-2026-T1", 0, 1, 'R')

    # Cleanup temporary image file
    if os.path.exists(chart_path):
        os.remove(chart_path)

    return pdf.output(dest="S").encode("latin-1")

# Streamlit UI Trigger
st.markdown("---")
st.header("📄 Tactical Mission Dossier (PDF)")
st.caption("Generates a formal, unclassified military deployment dossier with embedded high-resolution 300-DPI charts.")

pdf_bytes = generate_pdf_report()

st.download_button(
    label="📥 Download Tactical Dossier (with Embedded High-Res Charts)",
    data=pdf_bytes,
    file_name=f"DRDO_Tactical_Dossier_{shelter_length}x{shelter_width}m.pdf",
    mime="application/pdf",
    use_container_width=True
)