import math

def calculate_capacity(area_sqm):
    """
    Capacity (kW) = Area * Module Efficiency
    Assuming modern high-efficiency Mono-PERC modules at 22% efficiency.
    Standard output: 1 sq.m generates ~0.22 kW.
    """
    efficiency = 0.22
    return round(area_sqm * efficiency, 2)

def estimate_solar_irradiance(lat, lon):
    """
    Simulates high-accuracy solar irradiance using latitude regression geometry.
    Average Indian GHI bounds: 4.0 to 6.5 kWh/m2/day depending on latitude.
    """
    base = 5.2 
    lat_factor = (lat - 8) * 0.035 # Lower latitudes (close to equator) have higher insolation
    # Deterministic longitudinal weather variation model
    lon_factor = math.cos(math.radians(lon)) * 0.3 
    
    irradiance = base - lat_factor + lon_factor
    return round(max(3.5, min(irradiance, 6.5)), 2)

def calculate_energy_production(capacity_kw, irradiance, pr_efficiency=0.78):
    """
    Daily Energy (kWh) = Capacity * Solar Irradiance * System Performance Ratio (PR)
    PR accounts for real-world losses: inverter inefficiency, dust, temp degradation.
    """
    daily_energy = capacity_kw * irradiance * pr_efficiency
    monthly_energy = daily_energy * 30.41 # Average days in month
    yearly_energy = daily_energy * 365.25
    return daily_energy, monthly_energy, yearly_energy

def calculate_financials(capacity_kw, monthly_energy):
    """
    Calculate installation cost, monthly savings, and payback period.
    Cost = ₹50,000 per kW
    Electricity rate = ₹7 per unit (kWh)
    """
    installation_cost = capacity_kw * 50000
    monthly_savings = monthly_energy * 7
    yearly_savings = monthly_savings * 12
    
    if yearly_savings > 0:
        payback_years = installation_cost / yearly_savings
    else:
        payback_years = 0
        
    return installation_cost, monthly_savings, yearly_savings, payback_years
