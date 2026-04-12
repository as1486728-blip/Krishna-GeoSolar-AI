# SunMap AI - Data Calculation Logic

Yeh file detail me explain karti hai ki SunMap AI application me data (jaise Solar Capacity, Energy Production, aur Financial Savings) kis basis pe calculate aur dikhaya jaata hai.

---

## 1. Solar System Capacity (Kitne kW ka system lagega?)

**File:** `utils.py -> calculate_capacity(area_sqm)`

**Logic:**
Application assume karti hai ki **1 kW (Kilowatt)** solar panel setup karne ke liye average **10 square meters** ki chhat (roof area) chahiye hoti hai.

*   **Formula:** `Capacity (kW) = Area (sq.m) / 10`
*   **Example:** Agar map par select kiya gaya area 150 sq.m hai, toh system capacity hogi: `150 / 10 = 15 kW`.

---

## 2. Solar Irradiance (Suraj ki Roshni kitni milegi?)

**File:** `utils.py -> estimate_solar_irradiance(lat, lon)`

**Logic:**
Kyunki abhi app kisi paid/live Weather API ka use nahi kar raha hai, isliye suraj ki roshni yaani Solar Irradiance (`kWh/m²/day`) ko **simulate (approximate)** kiya gaya hai Map par select ki gayi location (Latitude & Longitude) ke basis par.

*   **Base Value:** India ka average irradiance approx `4.5` se `5` hota hai. App ek ideal base `4.8` lekar chalti hai.
*   **Latitude Factor:** Equator (South India side) ke paas dhoop zyada milti hai aur thodi constant hoti hai. Isliye agar latitude badhega (North India ki taraf jayenge), toh app formula se thoda irradiance kam kar deta hai.
    *   `lat_factor = (lat - 8) * 0.02`
*   **Longitude Factor:** Yeh sirf ek chhota sa random variation add karne ke liye use hota hai taaki data thoda aur natural/real lage.
    *   `lon_factor = math.sin(lon) * 0.2`
*   **Final Formula:** `Irradiance = 4.8 - lat_factor + lon_factor`
*   **Limitation:** Resulting Irradiance ki value humesha `4.0` se `6.0` ke andar limit ki gayi hai taaki galat/unrealistic numbers print na ho jayein.

---

## 3. Daily Energy Production (Ek din me kitni unit bijli banegi?)

App ke paas daily energy calculate karne ke 2 methods hain:

### Method A: Deterministic/Mathematical Math (Standard)
**File:** `utils.py -> calculate_energy_production()`

*   **Logic:** Yeh ek physics-based calculation hai jo Capacity ko Irradiance ke sath multiply karta hai.
*   **Efficiency Factor:** Solar panels kabhi 100% bijli nahi banate kyunki wire me loss hota hai, panel pe dhool hoti hai, ya inverter efficiency hoti hai. Isliye app **80% (0.80)** efficiency maankar chalti hai.
*   **Formula:** `Daily Energy (kWh ya Units) = Capacity * Irradiance * 0.80`

### Method B: Machine Learning (AI) Prediction
**File:** `ml_model.py -> predict_energy()`

*   **Logic:** System ke paas ek AI Model (Random Forest Regressor) hai jo automatic ek synthetic data file (`data/synthetic_solar_data.csv`) banata hai jisme hazaaro samples hote hain.
*   In samples me weather ke random fluctuations aur noise add kiye jaate hain.
*   Jab aap map pe location select karte hain, toh yeh AI Model aapke map coordinates ko padh kar apna intelligent guess deta hai ki Daily Energy kitni predict ki ja sakti hai, jo kabhi normal mathematical formula se slightly behatar estimate de sakti hai by accounting for weather unpredictability.

---

## 4. Financial Calculations (Cost aur Bachat)

**File:** `utils.py -> calculate_financials()`

Ye calculations bilkul simple assumptions par aadharit hain:

1.  **Installation Cost (Lagane ka kharcha):**
    *   App maanti hai ki 1 kW solar lagane ka base kharcha India me ₹50,000 lagta hai.
    *   **Formula:** `Total Cost = Capacity (kW) * 50,000`
2.  **Monthly & Yearly Savings (Kitna bill bachega):**
    *   App assume karti hai ki aap apne Grid/Electricity provider ko **₹7 per Unit** de rahe hain. 
    *   **Formula:** `Monthly Bachat = Monthly Energy Generated * ₹7`
    *   **Formula:** `Yearly Bachat = Monthly Bachat * 12`
3.  **Payback Period (ROI):**
    *   Jo paisa lagaya, wo kitne time me wapas aayega panel free bijli dekar?
    *   **Formula:** `Years to Payback = Total Installation Cost / Yearly Bachat`

---

## Summary (Aage kya kar sakte hain?)

Agar app ko real-world scenarios me zyada accurate banana hai, toh aap inme se kuch changes kar sakte hain:
1.  **Irradiance**: *NASA POWER API* ya *OpenWeatherMap API* integrate kar sakte hain asli weather sunlight data lene ke liye.
2.  **Electric Rate Input**: ₹7/unit ki jagah user se puch sakte hain ki unka bill kitna per unit aata hai.
3.  **Cost Adjustment**: Installation cost state ke hisaab se vary kar sakti hai, jise add kiya ja sakta hai.
