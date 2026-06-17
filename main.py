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
        self.team_stats = {}

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException:
            return None

    def load_competition_data(self, league_code):
        self.team_stats = {}
        endpoint = f"competitions/{league_code}/matches"
        data = self._get(endpoint, params={"status": "FINISHED"})
        
        if not data or "matches" not in data or not data["matches"]:
            return

        for match in data["matches"]:
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]
            
            if not home or not away:
                continue

            for team in [home, away]:
                if team not in self.team_stats:
                    self.team_stats[team] = {
                        "matches": 0, "wins": 0, "draws": 0, "losses": 0,
                        "goals_scored": 0, "goals_conceded": 0, "overs": 0, "btts": 0
                    }

            score = match.get("score", {}).get("fullTime", {})
            gh = score.get("home")
            ga = score.get("away")
            
            if gh is None or ga is None:
                continue

            self.team_stats[home]["matches"] += 1
            self.team_stats[away]["matches"] += 1
            self.team_stats[home]["goals_scored"] += gh
            self.team_stats[home]["goals_conceded"] += ga
            self.team_stats[away]["goals_scored"] += ga
            self.team_stats[away]["goals_conceded"] += gh

            if gh > ga:
                self.team_stats[home]["wins"] += 1
                self.team_stats[away]["losses"] += 1
            elif gh < ga:
                self.team_stats[away]["wins"] += 1
                self.team_stats[home]["losses"] += 1
            else:
                self.team_stats[home]["draws"] += 1
                self.team_stats[away]["draws"] += 1

            if (gh + ga) >= 3:
                self.team_stats[home]["overs"] += 1
                self.team_stats[away]["overs"] += 1
            if gh > 0 and ga > 0:
                self.team_stats[home]["btts"] += 1
                self.team_stats[away]["btts"] += 1

    def load_upcoming_matches(self, league_code):
        endpoint = f"competitions/{league_code}/matches"
        data = self._get(endpoint)
        
        if not data or "matches" not in data or not data["matches"]:
            return []

        upcoming_matches = []
        for match in data["matches"]:
            if match["status"] not in ["TIMED", "SCHEDULED"]:
                continue
            upcoming_matches.append({
                "Date": match["utcDate"][:10],
                "Time": match["utcDate"][11:16],
                "HomeTeam": match["homeTeam"]["name"],
                "AwayTeam": match["awayTeam"]["name"],
            })
        return upcoming_matches

    def predict_match(self, home_team, away_team):
        if home_team not in self.team_stats or away_team not in self.team_stats:
            return {
                "HomeTeam": home_team, "AwayTeam": away_team, "Prediction_1X2": "X",
                "Probability_1": 33.3, "Probability_X": 33.4, "Probability_2": 33.3,
                "Over_Under_2.5": "Under", "Probability_Over": 50.0, "BTTS": "No", "Probability_BTTS": 50.0
            }

        home = self.team_stats[home_team]
        away = self.team_stats[away_team]

        m_home = max(1, home["matches"])
        m_away = max(1, away["matches"])

        prob_1 = (home["wins"] / m_home) * 0.5 + (away["losses"] / m_away) * 0.1
        prob_x = (home["draws"] / m_home) * 0.3 + (away["draws"] / m_away) * 0.1
        prob_2 = (away["wins"] / m_away) * 0.5 + (home["losses"] / m_home) * 0.1

        raw_probs = {"1": prob_1, "X": prob_x, "2": prob_2}
        total = sum(raw_probs.values()) if sum(raw_probs.values()) > 0 else 1
        
        probs = {k: max(0.1, v / total) for k, v in raw_probs.items()}
        new_total = sum(probs.values())
        for k in probs: probs[k] = round((probs[k] / new_total) * 100, 1)

        p_over = ((home["overs"] / m_home) + (away["overs"] / m_away)) / 2
        p_btts = ((home["btts"] / m_home) + (away["btts"] / m_away)) / 2

        return {
            "HomeTeam": home_team,
            "AwayTeam": away_team,
            "Prediction_1X2": max(probs, key=probs.get),
            "Probability_1": probs["1"],
            "Probability_X": probs["X"],
            "Probability_2": probs["2"],
            "Over_Under_2.5": "Over" if p_over > 0.5 else "Under",
            "Probability_Over": round(p_over * 100, 1),
            "BTTS": "Yes" if p_btts > 0.5 else "No",
            "Probability_BTTS": round(p_btts * 100, 1)
        }

if __name__ == "__main__":
    API_KEY = os.environ.get("API_FOOTBALL_KEY")
    if not API_KEY:
        sys.exit(1)

    predictor = FootballPredictor(API_KEY)
    output_base_dir = "data"
    os.makedirs(output_base_dir, exist_ok=True)

    readme_content = "# Football Predictions Dashboard\n\n"
    readme_content += f"Last updated: _{datetime.utcnow().isoformat()[:-7]}Z (UTC)_\n\n"
    readme_content += "Automated predictive analytics pipeline updating every 24 hours.\n\n"

    all_predictions_count = 0

    for code, name in COMPETITIONS.items():
        # Delay di 3 secondi per non superare il rate limit (10 richieste/min) del piano Free
        time.sleep(3)
        print(f"Processing real analytics for {name} ({code})...")
            
        predictor.load_competition_data(code)
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

        with open(os.path.join(output_base_dir, f"{code}.json"), "w", encoding="utf-8") as f:
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
    
    print("Pipeline executed successfully with analytics engine engaged.")
