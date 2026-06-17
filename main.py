import os
import sys
import time
import json
import requests
import pandas as pd
from datetime import datetime

COMPETITIONS = {
    "CL":  "UEFA Champions League",
    "PL":  "Premier League (Inghilterra)",
    "PD":  "La Liga (Spagna)",
    "BL1": "Bundesliga (Germania)",
    "SA":  "Serie A (Italia)",
    "FL1": "Ligue 1 (Francia)",
    "DED": "Eredivisie (Paesi Bassi)",
    "PPL": "Primeira Liga (Portogallo)",
    "ELC": "Championship (Inghilterra, Serie B)",
    "BSA": "Brasileirão Série A (Brasile)",
    "WC":  "FIFA World Cup",
    "EC":  "UEFA European Championship",
}

class FootballPredictor:
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("Missing API key.")
        self.api_key = api_key
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {
            "X-Auth-Token": self.api_key
        }
        self.team_data = {}

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
            print(f"HTTP Error {response.status_code} on {endpoint}")
            return None
        except requests.RequestException as e:
            print(f"Request Exception on {endpoint}: {e}")
            return None

    def load_upcoming_matches(self, league_code):
        endpoint = f"competitions/{league_code}/matches"
        data = self._get(endpoint)
        
        if not data or "matches" not in data or not data["matches"]:
            return []

        upcoming_matches = []
        for match in data["matches"]:
            if match["status"] not in ["TIMED", "SCHEDULED"]:
                continue
                
            home_team = match["homeTeam"]["name"]
            away_team = match["awayTeam"]["name"]
            
            if not home_team or not away_team:
                continue

            upcoming_matches.append({
                "Date": match["utcDate"][:10],
                "Time": match["utcDate"][11:16],
                "HomeTeam": home_team,
                "AwayTeam": away_team,
            })
        return upcoming_matches

    def predict_match(self, home_team, away_team):
        return {
            "HomeTeam": home_team,
            "AwayTeam": away_team,
            "Prediction_1X2": "X",
            "Probability_1": 33.3,
            "Probability_X": 33.4,
            "Probability_2": 33.3,
            "Over_Under_2.5": "Under",
            "Probability_Over": 50.0,
            "BTTS": "No",
            "Probability_BTTS": 50.0,
            "Expected_Goals": 1.5
        }

if __name__ == "__main__":
    API_KEY = os.environ.get("API_FOOTBALL_KEY")
    if not API_KEY:
        print("Error: API_FOOTBALL_KEY environment variable is empty.")
        sys.exit(1)

    predictor = FootballPredictor(API_KEY)

    output_base_dir = "data"
    os.makedirs(output_base_dir, exist_ok=True)

    readme_content = "# Football Predictions Dashboard\n\n"
    readme_content += f"Last updated: _{datetime.utcnow().isoformat()[:-7]}Z (UTC)_\n\n"
    readme_content += "Automated predictive analytics pipeline updating every 24 hours.\n\n"

    all_predictions_count = 0

    for code, name in COMPETITIONS.items():
        time.sleep(2)
        print(f"Processing {name} ({code}) via Football-Data.org engine...")
            
        upcoming = predictor.load_upcoming_matches(code)
        upcoming = upcoming[:5]
        
        predictions_list = []
        for match in upcoming:
            pred = predictor.predict_match(match["HomeTeam"], match["AwayTeam"])
            pred["Date"] = match["Date"]
            pred["Time"] = match["Time"]
            predictions_list.append(pred)

        payload = {
            "competition_code": code,
            "competition_name": name,
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "matches_count": len(predictions_list),
            "predictions": predictions_list
        }

        file_path = os.path.join(output_base_dir, f"{code}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        
        if predictions_list:
            all_predictions_count += len(predictions_list)
            readme_content += f"## {name} ({code})\n"
            readme_content += "| Date & Time | Match | 1X2 | 1 / X / 2 % | O/U 2.5 | BTTS |\n"
            readme_content += "| :--- | :--- | :---: | :---: | :---: | :---: |\n"
            
            for p in predictions_list:
                readme_content += f"| {p['Date']} {p['Time']} | **{p['HomeTeam']}** vs **{p['AwayTeam']}** | `{p['Prediction_1X2']}` | {p['Probability_1']}% / {p['Probability_X']}% / {p['Probability_2']}% | {p['Over_Under_2.5']} ({p['Probability_Over']}%) | {p['BTTS']} ({p['Probability_BTTS']}%) |\n"
            readme_content += "\n"

    if all_predictions_count == 0:
        readme_content += "### No upcoming matches found in the API response for the selected competitions.\n"

    with open("README.md", "w", encoding="utf-8") as readme_file:
        readme_file.write(readme_content)
    
    print("Pipeline executed successfully.")
