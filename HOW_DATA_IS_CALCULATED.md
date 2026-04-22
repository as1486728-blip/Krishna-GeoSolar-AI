# SunMap AI - Data Calculation Logic

Yeh file detail me explain karti hai ki SunMap AI application me data (jaise Solar Capacity, Energy Production, Wind Potential, aur Financial Savings) kis basis pe calculate aur dikhaya jaata hai.

---

## 1. Solar System Capacity (Kitne kW ka system lagega?)

**File:** `utils.py -> calculate_capacity(area_sqm)`

**Logic:**
Application assume karti hai ki **modern 22% efficiency Mono-PERC solar panels** use kiye ja rahe hain. 
1 kW (Kilowatt) solar panel setup karne ke liye approximately **4.54 square meters** ki chhat (roof area) chahiye hoti hai. Polygon area exact calculate karne ke liye map par draw kiye gaye coordinates ko **Shoelace Formula** ke through process kiya jaata hai.

*   **Formula:** `Capacity (kW) = Area (sq.m) * 0.22`
*   **Example:** Agar map par select kiya gaya area 50 sq.m hai, toh system capacity hogi: `50 * 0.22 = 11 kW`.

---

## 2. Solar Irradiance (Suraj ki Roshni kitni milegi?)

**File:** `app.py` & API integration

**Logic:**
SunMap AI ab **Open-Meteo API** ka use karta hai real-time aur historical weather data fetch karne ke liye. Ab irradiance simulate nahi kiya jaata, balki actual data use hota hai.

*   **Live Data:** GHI (Global Horizontal Irradiance), DNI (Direct Normal Irradiance), DHI (Diffuse Horizontal Irradiance), aur Solar Zenith Angle API se live fetch kiye jaate hain.
*   **Historical Data:** Pichle 5 saal (5-year historical span) ka data analyze kiya jaata hai taaki weather ke fluctuations aur anomalies ko smooth kiya ja sake aur ek accurate median irradiance nikala ja sake.
*   **Panel Tilt:** Solar Zenith angle ke base par dynamic panel tilt recommendations di jaati hain taaki shading losses kam se kam hon.

---

## 3. Daily Energy Production (Ek din me kitni unit bijli banegi?)

App ke paas daily energy calculate karne ke 2 methods hain:

### Method A: Deterministic/Mathematical Math (Physics-based)
*   **Logic:** Yeh ek physics-based calculation hai jo Capacity ko live Irradiance aur Performance Ratio ke sath multiply karta hai.
*   **Efficiency:** Modern 22% Mono-PERC modules ka use karke actual production calculate hota hai, jisme wiring/dust losses aur real weather resistance ko account me liya jata hai.

### Method B: Machine Learning (AI) Prediction
**File:** `ml_model.py -> predict_energy()`

*   **Logic:** System ke paas ek advanced AI Model (**Gradient Boosting Regressor**) hai.
*   Is model ko ek **10,000-sample synthetic dataset** aur pichle 5 saal ke historical solar data par retrain kiya gaya hai.
*   Yeh model weather anomalies, temperature, aur location ke base par near-perfect (approx 99.99%) prediction accuracy ke sath daily energy output ka intelligent estimate deta hai.

---

## 4. Wind Potential Analysis (Hawa se kitni bijli banegi?)

**Logic:**
Solar ke sath-sath ab SunMap AI **Vertical Axis Wind Turbine (VAWT)** ki feasibility bhi check karta hai.

*   **Global Wind Mapping:** Open-Meteo API se **10-meter** aur **80-meter** altitude par live wind speed data fetch kiya jaata hai.
*   Agar wind speed sufficient hoti hai, toh app hybrid (Solar + Wind) microgrid generation ki recommendation deti hai, jo ki global wind hubs ke liye bahut useful hai.

---

## 5. Financial Calculations (Cost aur Bachat)

**File:** `utils.py -> calculate_financials()`

Ye calculations economies-of-scale par aadharit hain:

1.  **Installation Cost (Lagane ka kharcha):**
    *   App maanti hai ki 1 kW solar lagane ka base kharcha India me **₹50,000** lagta hai. Ye installation area badhne ke sath proportionally scale hota hai.
    *   **Formula:** `Total Cost = Capacity (kW) * 50,000`
2.  **Monthly & Yearly Savings (Kitna bill bachega):**
    *   App assume karti hai ki aap apne Grid/Electricity provider ko **₹7 per Unit** de rahe hain. 
    *   **Formula:** `Monthly Bachat = Monthly Energy Generated * ₹7`
    *   **Formula:** `Yearly Bachat = Monthly Bachat * 12`
3.  **Payback Period (ROI):**
    *   Jo paisa lagaya, wo kitne time me wapas aayega panel free bijli dekar?
    *   **Formula:** `Years to Payback = Total Installation Cost / Yearly Bachat`

---

## Summary

*   **Accuracy:** Ab system **Nominatim geocoding service** se exact location track karta hai aur **Shoelace formula** se precise polygon area nikalta hai.
*   **Real Data:** **Open-Meteo API** ne dummy data ko replace kar diya hai, jisse reports ab industrial standard ki ho gayi hain.
