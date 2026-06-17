import os
import sys
import time
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

FREE_COMPETITIONS = {
    "CL": "UEFA Champions League",
    "PL": "Premier League (England)",
    "PD": "La Liga (Spain)",
    "BL1": "Bundesliga (Germany)",
    "SA": "Serie A (Italy)",
    "FL1": "Ligue 1 (France)",
    "DED": "Eredivisie (Netherlands)",
    "PPL": "Primeira Liga (Portugal)",
    "ELC": "Championship (England, 2nd tier)",
    "BSA": "Brasileirão Série A (Brazil)"
}

class RateLimiter:
    def __init__(self, requests_per_minute=10):
        self.min_interval = 60.0 / requests_per_minute
        self._last_call = 0.0

    def wait(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()

class APIError(Exception):
    pass

class FootballPredictor:
    def __init__(self, api_token, requests_per_minute=10):
        if not api_token:
            raise ValueError("Missing API token.")
        self.api_token = api_token
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {"X-Auth-Token": self.api_token}
        self.team_data = {}
        self.match_data = pd.DataFrame()
        self.id_to_name = {}
        self.name_to_id = {}
        self._rate_limiter = RateLimiter(requests_per_minute)

    def _get(self, url, params=None):
        self._rate_limiter.wait()
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
        except requests.RequestException as e:
            raise APIError(f"Connection error: {e}") from e

        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
            time.sleep(60)
            return self._get(url, params)
        if response.status_code in [403, 404]:
            return None
        raise APIError(f"API error {response.status_code}: {response.text[:200]}")

    def load_competition_data(self, competition_code, season=None):
        if not season:
            current_year = datetime.now().year
            season = current_year if datetime.now().month > 7 else current_year - 1

        if not self._load_teams(competition_code, season):
            return False
        if not self._load_matches(competition_code, season):
            return False
        self._process_team_data()
        return True

    def _load_teams(self, competition_code, season):
        url = f"{self.base_url}/competitions/{competition_code}/teams"
        data = self._get(url, params={"season": season})
        if not data or "teams" not in data:
            return False
        self.id_to_name = {team["id"]: team["name"] for team in data["teams"]}
        self.name_to_id = {team["name"]: team["id"] for team in data["teams"]}
        return True

    def _load_matches(self, competition_code, season):
        url = f"{self.base_url}/competitions/{competition_code}/matches"
        data = self._get(url, params={"season": season})
        if not data or "matches" not in data:
            return False

        matches = []
        for match in data["matches"]:
            if match["status"] != "FINISHED":
                continue
            home_goals = match["score"]["fullTime"]["home"]
            away_goals = match["score"]["fullTime"]["away"]
            if home_goals is None or away_goals is None:
                continue

            m = {
                "Date": match["utcDate"][:10],
                "HomeTeamID": match["homeTeam"]["id"],
                "AwayTeamID": match["awayTeam"]["id"],
                "HomeTeam": self.id_to_name.get(match["homeTeam"]["id"], "Unknown"),
                "AwayTeam": self.id_to_name.get(match["awayTeam"]["id"], "Unknown"),
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

        self.match_data = pd.DataFrame(matches)
        return True

    def _process_team_data(self):
        self.team_data = {}
        if self.match_data.empty:
            return

        team_ids = set(self.match_data["HomeTeamID"].tolist() + self.match_data["AwayTeamID"].tolist())
        for team_id in team_ids:
            team_name = self.id_to_name.get(team_id, f"ID_{team_id}")
            home_matches = self.match_data[self.match_data["HomeTeamID"] == team_id]
            away_matches = self.match_data[self.match_data["AwayTeamID"] == team_id]

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

        def load_upcoming_matches(self, competition_code, date_from, date_to):
            url = f"{self.base_url}/matches"
            params = {"competitions": competition_code, "dateFrom": date_from, "dateTo": date_to}
            data = self._get(url, params=params)
            
            if not data or "matches" not in data:
                return []

            upcoming_matches = []
            for match in data["matches"]:
                home_id = match["homeTeam"]["id"]
                away_id = match["awayTeam"]["id"]
                if home_id in self.id_to_name and away_id in self.id_to_name:
                    upcoming_matches.append({
                        "Date": match["utcDate"][:10],
                        "Time": match["utcDate"][11:16],
                        "HomeTeam": self.id_to_name[home_id],
                        "AwayTeam": self.id_to_name[away_id],
                    })
            return upcoming_matches

        def predict_match(self, home_team, away_team):
            if home_team not in self.team_data or away_team not in self.team_data:
                return {"error": "Missing team analytics profile"}

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
    API_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not API_TOKEN:
        sys.exit(1)

    predictor = FootballPredictor(API_TOKEN)

    today = datetime.now()
    date_from = today.strftime("%Y-%m-%d")
    date_to = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    output_base_dir = "data"
    os.makedirs(output_base_dir, exist_ok=True)

    readme_content = "# Football Predictions Dashboard\n\n"
    readme_content += f"Last updated: _{datetime.utcnow().isoformat()[:-7]}Z (UTC)_\n\n"
    readme_content += "Automated predictive analytics pipeline updating every 24 hours.\n\n"

    all_predictions_count = 0

    for code, name in FREE_COMPETITIONS.items():
        if not predictor.load_competition_data(code):
            continue
            
        upcoming = predictor.load_upcoming_matches(code, date_from, date_to)
        
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
