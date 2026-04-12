import math

def calculate_capacity(area_sqm):
    """
    Capacity (kW) = Area / 10
    Assuming 1 kW requires approx 10 sq.m area.
    """
    return area_sqm / 10.0

def estimate_solar_irradiance(lat, lon):
    """
    Estimates solar irradiance based on latitude. 
    This is a simulation since we don't have a live API key.
    Indian average is ~ 4-5 kWh/m2/day.
    We will add some slight deterministic variation based on lat/lon.
    """
    # Simple simulation: 
    # Closer to equator (lower lat in India) typically gets steadier irradiance.
    # Let's say base is 4.5, subtract a tiny factor for higher latitudes (up to 35 deg in India).
    base = 4.8 
    lat_factor = (lat - 8) * 0.02 # Assuming India's southern tip is ~8 deg.
    # Just to add some pseudo-randomness using lon
    lon_factor = math.sin(lon) * 0.2 
    
    irradiance = base - lat_factor + lon_factor
    # Clamp within 4 to 6 for realism
    return max(4.0, min(irradiance, 6.0))

def calculate_energy_production(capacity_kw, irradiance, efficiency=0.80):
    """
    Daily Energy (kWh) = Capacity * Solar Irradiance * Efficiency Factor
    """
    daily_energy = capacity_kw * irradiance * efficiency
    monthly_energy = daily_energy * 30
    yearly_energy = daily_energy * 365
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
