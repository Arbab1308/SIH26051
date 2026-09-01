import os
import matplotlib.pyplot as plt
from fpdf import FPDF
import pandas as pd

class TacticalDossierPDF(FPDF):
    def header(self):
        # Dark Slate Banner
        self.set_fill_color(30, 41, 59)
        self.rect(0, 0, 210, 16, 'F')
        self.set_font("Arial", 'B', 9)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, "RESTRICTED // DRDO HIGH-ALTITUDE FIELD SIMULATION // TACTICAL DOSSIER", 0, 1, 'C')
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Arial", 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 8, f"Page {self.page_no()} | DRDO SIH26051 Tactical Thermal Simulation Engine", 0, 0, 'C')


def create_multi_day_chart(daily_results, save_path="multi_day_temp.png"):
    days = [d["day_idx"] + 1 for d in daily_results]
    min_temps = [d["min_temp"] for d in daily_results]
    max_temps = [d["max_temp"] for d in daily_results]
    
    fig, ax = plt.subplots(figsize=(8, 3.5), dpi=300)
    ax.plot(days, max_temps, label="Daily Max Temp", color="#ef4444", linewidth=2)
    ax.plot(days, min_temps, label="Daily Min Temp", color="#3b82f6", linewidth=2)
    ax.axhline(y=5.0, color="#10b981", linestyle="--", linewidth=1.5, label="Survival Target (5°C)")
    ax.axhline(y=-20.0, color="#8b5cf6", linestyle=":", linewidth=1.5, label="Hypothermia Risk (-20°C)")
    
    ax.set_title("30-Day Simulation Thermal Trajectory", fontsize=10, fontweight="bold", pad=8)
    ax.set_xlabel("Day of Deployment", fontsize=8)
    ax.set_ylabel("Temperature (°C)", fontsize=8)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(fontsize=7, loc="lower right")
    
    plt.tight_layout()
    plt.savefig(save_path, bbox_inches='tight', facecolor="white")
    plt.close()
    return save_path

def generate_multi_day_pdf(multi_res, config, scenario_name, supply_location, total_weight, total_cost, airlift_status):
    pdf = TacticalDossierPDF()
    pdf.add_page()
    
    sum_data = multi_res.get("summary", {})
    casualty = multi_res.get("casualty_risk", {})
    failures = multi_res.get("material_failures", [])
    
    # Title
    pdf.set_y(18)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, f"OPERATION DOSSIER: {scenario_name.upper()}", 0, 1)
    
    # Exec summary
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(51, 65, 85)
    
    hypo_risk = casualty.get('cumulative_risk_pct', 0)
    casualty_status = casualty.get('status', 'UNKNOWN')
    
    pdf.multi_cell(0, 5, f"Executive Summary: A {multi_res['num_days']}-day simulation was conducted for {scenario_name}. The thermal envelope maintained an average minimum of {sum_data.get('avg_min_temp',0):.1f}°C. Hypothermia risk is classified as {casualty_status} ({hypo_risk}% cumulative risk). Peak structural wind load experienced was {sum_data.get('max_wind_kmh', 0):.1f} km/h.")
    pdf.ln(5)
    
    # 1. Structural & Supply Chain
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "1. Supply Chain & Logistics Assessment", ln=True)
    
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, f"Deployment Hub: {supply_location} | Airlift Mode: {airlift_status}", ln=True)
    pdf.cell(0, 5, f"Estimated Material Cost: INR {total_cost:,.0f} | Total Deployment Weight: {total_weight:,.0f} kg", ln=True)
    pdf.ln(2)
    
    # 2. Material Failures
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 6, "2. Material Degradation Forecast", ln=True)
    pdf.set_font("Arial", '', 9)
    if not failures:
        pdf.cell(0, 5, "No critical material failures detected over the simulation period.", ln=True)
    else:
        for f in failures:
            pdf.set_text_color(220, 38, 38)
            pdf.cell(0, 5, f"Day {f['day']} - {f['material']}: {f['mode']} (Cause: {f['cause']})", ln=True)
            pdf.set_text_color(51, 65, 85)
            pdf.cell(0, 5, f"Mitigation: {f['recommendation']}", ln=True)
    pdf.ln(5)
    
    # 3. Chart
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "3. Thermal Trajectory", ln=True)
    
    chart_path = create_multi_day_chart(multi_res['daily_results'])
    pdf.image(chart_path, x=15, y=pdf.get_y(), w=180)
    pdf.ln(75)
    
    # Sign-off box
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(95, 5, "Commander Sign-Off: ________________________", 0, 0, 'L')
    pdf.cell(95, 5, "Auth: DRDO-DGRE-SIM-2026-T1", 0, 1, 'R')

    if os.path.exists(chart_path):
        os.remove(chart_path)

    return pdf.output(dest="S").encode("latin-1")
