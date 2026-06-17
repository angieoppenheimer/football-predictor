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
        self.match_data = pd.DataFrame()

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

    def load_competition_data(self, league_id, season):
        url = "fixtures"
        params = {"league": league_id, "season": season}
        data = self._get(url, params=params)
        
        if not data or "response" not in data or not data["response"]:
            return False

        matches = []
        for item in data["response"]:
            fixture = item["fixture"]
            if fixture["status"]["short"] != "FT":
                continue
                
            teams = item["teams"]
            goals = item["goals"]
            home_goals = goals["home"]
            away_goals = goals["away"]
            
            if home_goals is None or away_goals is None:
                continue

            m = {
                "Date": fixture["date"][:10],
                "HomeTeamID": teams["home"]["id"],
                "AwayTeamID": teams["away"]["id"],
                "HomeTeam": teams["home"]["name"],
                "AwayTeam": teams["away"]["name"],
                "HomeGoals": home_goals,
                "AwayGoals": away_goals,
            }
            if m["HomeGoals"] > m["AwayGoals"]:
                m["Result"] = "1"
            elif m["HomeGoals"] < m["AwayGoals"]:
                m["Result"] = "2"
            else:
                m["Result"] = "X"
            m["Under/Over 2.5"] = "Over" if (m["HomeGoals"] + m["AwayGoals"]) >= 3 else "Under"
            m["BTTS"] = "Yes" if (m["HomeGoals"] > 0 and m["AwayGoals"] > 0) else "No"
            matches.append(m)

        if not matches:
            self.match_data = pd.DataFrame()
            self.team_data = {}
            return True

        self.match_data = pd.DataFrame(matches)
        self._process_team_data()
        return True

    def _process_team_data(self):
        self.team_data = {}
        if self.match_data.empty:
            return

        team_ids = set(self.match_data["HomeTeamID"].tolist() + self.match_data["AwayTeamID"].tolist())
        for team_id in team_ids:
            home_matches = self.match_data[self.match_data["HomeTeamID"] == team_id]
            away_matches = self.match_data[self.match_data["AwayTeamID"] == team_id]
            
            team_name = ""
            if not home_matches.empty:
                team_name = home_matches.iloc[0]["HomeTeam"]
            elif not away_matches.empty:
                team_name = away_matches.iloc[0]["AwayTeam"]
            else:
                team_name = f"Team_{team_id}"

            home_wins = len(home_matches[home_matches["Result"] == "1"])
            home_draws = len(home_matches[home_matches["Result"] == "X"])
            home_losses = len(home_matches[home_matches["Result"] == "2"])
            away_wins = len(away_matches[away_matches["Result"] == "2"])
            away_draws = len(away_matches[away_matches["Result"] == "X"])
            away_losses = len(away_matches[away_matches["Result"] == "1"])

            home_goals_scored = home_matches["HomeGoals"].sum()
            home_goals_conceded = home_matches["AwayGoals"].sum()
            away_goals_scored = away_matches["AwayGoals"].sum()
            away_goals_conceded = away_matches["HomeGoals"].sum()

            home_overs = len(home_matches[home_matches["Under/Over 2.5"] == "Over"])
            away_overs = len(away_matches[away_matches["Under/Over 2.5"] == "Over"])
            home_btts = len(home_matches[home_matches["BTTS"] == "Yes"])
            away_btts = len(away_matches[away_matches["BTTS"] == "Yes"])

            all_matches = pd.concat([home_matches.assign(is_home=True), away_matches.assign(is_home=False)]).sort_values(by="Date", ascending=False)
            recent_matches = all_matches.head(5)

            recent_points = 0
            for _, m in recent_matches.iterrows():
                if m["is_home"] and m["Result"] == "1": recent_points += 3
                elif not m["is_home"] and m["Result"] == "2": recent_points += 3
                elif m["Result"] == "X": recent_points += 1

            self.team_data[team_name] = {
                "id": team_id,
                "home_matches": len(home_matches),
                "away_matches": len(away_matches),
                "home_wins": home_wins, "home_draws": home_draws, "home_losses": home_losses,
                "away_wins": away_wins, "away_draws": away_draws, "away_losses": away_losses,
                "home_goals_scored": home_goals_scored, "home_goals_conceded": home_goals_conceded,
                "away_goals_scored": away_goals_scored, "away_goals_conceded": away_goals_conceded,
                "home_overs": home_overs, "away_overs": away_overs,
                "home_btts": home_btts, "away_btts": away_btts,
                "recent_form": recent_points,
                "total_points": (home_wins + away_wins) * 3 + (home_draws + away_draws),
            }

    def load_upcoming_matches(self, league_id, season, date_from, date_to):
        url = "fixtures"
        params = {"league": league_id, "season": season, "from": date_from, "to": date_to}
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
        if home_team not in self.team_data or away_team not in self.team_data:
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

        home_data = self.team_data[home_team]
        away_data = self.team_data[away_team]

        min_home_matches = max(1, home_data["home_matches"])
        min_away_matches = max(1, away_data["away_matches"])

        prob_1 = home_data["home_wins"] / min_home_matches * 0.4
        prob_x = home_data["home_draws"] / min_home_matches * 0.3
        prob_2 = away_data["away_wins"] / min_away_matches * 0.4

        prob_1 += (home_data["recent_form"] / 15) * 0.2 - (away_data["recent_form"] / 15) * 0.1
        prob_2 += (away_data["recent_form"] / 15) * 0.2 - (home_data["recent_form"] / 15) * 0.1

        points_diff = home_data["total_points"] - away_data["total_points"]
        table_factor = min(0.2, max(-0.2, points_diff / 30))
        prob_1 += table_factor
        prob_2 -= table_factor

        probabilities = {
            "1": max(0.1, min(0.8, prob_1)),
            "X": max(0.1, min(0.6, prob_x)),
            "2": max(0.1, min(0.7, prob_2)),
        }
        total = sum(probabilities.values())
        for key in probabilities: probabilities[key] /= total

        expected_goals = (
            (home_data["home_goals_scored"] / min_home_matches) + (away_data["away_goals_conceded"] / min_away_matches)
            + (away_data["away_goals_scored"] / min_away_matches) + (home_data["home_goals_conceded"] / min_home_matches)
        ) / 2

        prob_over = ((home_data["home_overs"] / min_home_matches) + (away_data["away_overs"] / min_away_matches)) / 2
        prob_btts = ((home_data["home_btts"] / min_home_matches) + (away_data["away_btts"] / min_away_matches)) / 2

        return {
            "HomeTeam": home_team,
            "AwayTeam": away_team,
            "Prediction_1X2": max(probabilities, key=probabilities.get),
            "Probability_1": round(probabilities["1"] * 100, 1),
            "Probability_X": round(probabilities["X"] * 100, 1),
            "Probability_2": round(probabilities["2"] * 100, 1),
            "Over_Under_2.5": "Over" if prob_over > 0.5 or expected_goals > 2.5 else "Under",
            "Probability_Over": round(prob_over * 100, 1),
            "BTTS": "Yes" if prob_btts > 0.5 else "No",
            "Probability_BTTS": round(prob_btts * 100, 1),
            "Expected_Goals": round(expected_goals, 1)
        }

if __name__ == "__main__":
    API_KEY = os.environ.get("API_FOOTBALL_KEY")
    if not API_KEY:
        print("Error: API_FOOTBALL_KEY environment variable is empty.")
        sys.exit(1)

    predictor = FootballPredictor(API_KEY)

    today = datetime.now()
    date_from = today.strftime("%Y-%m-%d")
    date_to = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    output_base_dir = "data"
    os.makedirs(output_base_dir, exist_ok=True)

    readme_content = "# Football Predictions Dashboard\n\n"
    readme_content += f"Last updated: _{datetime.utcnow().isoformat()[:-7]}Z (UTC)_\n\n"
    readme_content += "Automated predictive analytics pipeline updating every 24 hours.\n\n"

    all_predictions_count = 0

    for code, name in COMPETITIONS.items():
        time.sleep(1)
        
        current_season = today.year
        print(f"Processing {name} (ID: {code}) for season {current_season}...")
        
        if not predictor.load_competition_data(code, current_season):
            print(f"Skipping {name}: Failed to initialize competition structure.")
            continue
            
        upcoming = predictor.load_upcoming_matches(code, current_season, date_from, date_to)
        
        predictions_list = []
        for match in upcoming:
            pred = predictor.predict_match(match["HomeTeam"], match["AwayTeam"])
            if "error" not in pred:
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
        readme_content += "### No upcoming matches scheduled for the next 7 days across all active leagues.\n"

    with open("README.md", "w", encoding="utf-8") as readme_file:
        readme_file.write(readme_content)
    
    print("Pipeline executed successfully.")
