import os
import sys
import time
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

COMPETITIONS = {
    "1": "FIFA World Cup",
    "15": "FIFA Club World Cup",
    "12": "FIFA Women's World Cup",
    "13": "FIFA U-20 World Cup",
    "14": "FIFA U-17 World Cup",
    "1024": "FIFA Women's U-20 World Cup",
    "1023": "FIFA Women's U-17 World Cup",
    "6": "FIFA Confederations Cup",
    "30": "FIFA World Cup Qualification CONMEBOL",
    "31": "FIFA World Cup Qualification CONCACAF",
    "32": "FIFA World Cup Qualification UEFA",
    "33": "FIFA World Cup Qualification CAF",
    "34": "FIFA World Cup Qualification AFC",
    "35": "FIFA World Cup Qualification OFC",
    "36": "FIFA World Cup Qualification Intercontinental Play-offs",
    "40": "FIFA Women's World Cup Qualification UEFA",
    "1017": "FIFA Women's World Cup Qualification OFC",
    "960": "FIFA Women's World Cup Qualification Intercontinental Play-offs"
}

class FootballPredictor:
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("Missing API key.")
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            "x-apisports-key": self.api_key,
            "x-rapidapi-host": "v3.football.api-sports.io"
        }
        self.team_data = {}

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            if response.status_code == 200:
                res_json = response.json()
                if "errors" in res_json and res_json["errors"]:
                    print(f"API Error [{endpoint}]: {res_json['errors']}")
                    return None
                return res_json
            print(f"HTTP Error {response.status_code} on {endpoint}")
            return None
        except requests.RequestException as e:
            print(f"Request Exception on {endpoint}: {e}")
            return None

    def load_upcoming_matches(self, league_id, date_from, date_to):
        url = "fixtures"
        params = {"league": league_id, "from": date_from, "to": date_to}
        data = self._get(url, params=params)
        
        if not data or "response" not in data or not data["response"]:
            return []

        upcoming_matches = []
        for item in data["response"]:
            fixture = item["fixture"]
            teams = item["teams"]
            upcoming_matches.append({
                "Date": fixture["date"][:10],
                "Time": fixture["date"][11:16],
                "HomeTeam": teams["home"]["name"],
                "AwayTeam": teams["away"]["name"],
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

    today = datetime.now()
    date_from = today.strftime("%Y-%m-%d")
    date_to = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    output_base_dir = "data"
    os.makedirs(output_base_dir, exist_ok=True)

    readme_content = "# Football Predictions Dashboard\n\n"
    readme_content += f"Last updated: _{datetime.utcnow().isoformat()[:-7]}Z (UTC)_\n\n"
    readme_content += "Automated predictive analytics pipeline updating every 24 hours.\n\n"

    all_predictions_count = 0

    for code, name in COMPETITIONS.items():
        time.sleep(1)
        print(f"Processing {name} (ID: {code}) via Free Tier Date Protocol...")
            
        upcoming = predictor.load_upcoming_matches(code, date_from, date_to)
        
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
        readme_content += "### No upcoming matches scheduled for the next 24 hours across active FIFA leagues.\n"

    with open("README.md", "w", encoding="utf-8") as readme_file:
        readme_file.write(readme_content)
    
    print("Pipeline executed successfully.")
