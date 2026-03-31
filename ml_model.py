import os
import pandas as pd
import numpy as np
import random
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import pickle

import utils

class SolarMLModel:
    def __init__(self, data_path="data/synthetic_solar_data.csv", model_path="data/rf_model.pkl"):
        self.data_path = data_path
        self.model_path = model_path
        self.model = None

    def generate_synthetic_data(self, num_samples=2000):
        """
        Creates synthetic dataset based on math formulas with slight variations
        to represent AI predicting energy.
        """
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        
        data = []
        for _ in range(num_samples):
            # Typical India lat/lon
            lat = random.uniform(8.0, 35.0)
            lon = random.uniform(68.0, 97.0)
            area = random.uniform(20.0, 500.0) # Roof size in sqm
            irradiance = utils.estimate_solar_irradiance(lat, lon)
            
            capacity = utils.calculate_capacity(area)
            # Add some noise to realism for AI to learn
            base_efficiency = random.uniform(0.70, 0.85)
            
            daily_energy_base = capacity * irradiance * base_efficiency
            daily_energy = max(0, daily_energy_base + np.random.normal(0, 0.5)) # Noise
            
            # Target output is daily energy
            data.append([lat, lon, area, irradiance, daily_energy])
            
        df = pd.DataFrame(data, columns=["Latitude", "Longitude", "Area_sqm", "Irradiance", "Daily_Energy_kWh"])
        df.to_csv(self.data_path, index=False)
        return df

    def train_model(self):
        """
        Trains Random Forest regressor on the dataset.
        """
        if not os.path.exists(self.data_path):
            self.generate_synthetic_data()
            
        df = pd.read_csv(self.data_path)
        
        X = df[["Latitude", "Longitude", "Area_sqm", "Irradiance"]]
        y = df["Daily_Energy_kWh"]
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)
        
        # Save model
        with open(self.model_path, "wb") as f:
            pickle.dump(self.model, f)
            
        return self.model.score(X_test, y_test)

    def load_model(self):
        if self.model is None:
            if not os.path.exists(self.model_path):
                self.train_model()
            with open(self.model_path, "rb") as f:
                self.model = pickle.load(f)
        return self.model

    def predict_energy(self, lat, lon, area, irradiance):
        """
        Given the inputs, predicts the Daily Energy using ML.
        """
        model = self.load_model()
        X_pred = pd.DataFrame([[lat, lon, area, irradiance]], 
                               columns=["Latitude", "Longitude", "Area_sqm", "Irradiance"])
        return model.predict(X_pred)[0]
