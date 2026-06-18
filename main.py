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
        self.id_to_name = {}
        self.match_data = pd.DataFrame()

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
            print(f"HTTP Error {response.status_code} on {endpoint}: {response.text[:300]}")
            return None
        except requests.RequestException as e:
            print(f"Request Exception on {endpoint}: {e}")
            return None

    # ------------------------------------------------------------------
    # Historical data loading
    # ------------------------------------------------------------------
    def load_competition_data(self, league_code, season=None):
        """Loads finished matches for the competition and builds the
        per-team stats that predict_match relies on."""
        params = {"season": season} if season else None
        data = self._get(f"competitions/{league_code}/matches", params=params)

        if not data or "matches" not in data:
            print(f"  [debug] load_competition_data({league_code}): no data / no 'matches' key in response.")
            self.match_data = pd.DataFrame()
            self.team_data = {}
            return False

        print(f"  [debug] load_competition_data({league_code}): API returned {len(data['matches'])} total matches.")

        matches = []
        id_to_name = {}
        for match in data["matches"]:
            if match["status"] != "FINISHED":
                continue
            home_goals = match["score"]["fullTime"]["home"]
            away_goals = match["score"]["fullTime"]["away"]
            if home_goals is None or away_goals is None:
                continue

            home_id = match["homeTeam"]["id"]
            away_id = match["awayTeam"]["id"]
            id_to_name[home_id] = match["homeTeam"]["name"]
            id_to_name[away_id] = match["awayTeam"]["name"]

            m = {
                "Date": match["utcDate"][:10],
                "HomeTeamID": home_id,
                "AwayTeamID": away_id,
                "HomeTeam": match["homeTeam"]["name"],
                "AwayTeam": match["awayTeam"]["name"],
                "HomeGoals": home_goals,
                "AwayGoals": away_goals,
            }
            if home_goals > away_goals:
                m["Result"] = "1"
            elif home_goals < away_goals:
                m["Result"] = "2"
            else:
                m["Result"] = "X"
            m["Under/Over 2.5"] = "Over" if (home_goals + away_goals) >= 3 else "Under"
            m["BTTS"] = "Yes" if (home_goals > 0 and away_goals > 0) else "No"
            matches.append(m)

        print(f"  [debug] load_competition_data({league_code}): {len(matches)} matches are FINISHED with a final score.")

        self.id_to_name = id_to_name
        self.match_data = pd.DataFrame(matches)
        self._process_team_data()
        print(f"  [debug] load_competition_data({league_code}): team_data has stats for {len(self.team_data)} teams.")
        return True

    def _process_team_data(self):
        """Aggregates self.match_data into per-team season stats:
        home/away record, goals scored/conceded, over/btts rates,
        recent form (last 5), and total league points."""
        self.team_data = {}
        if self.match_data.empty:
            return

        team_ids = set(
            self.match_data["HomeTeamID"].tolist() + self.match_data["AwayTeamID"].tolist()
        )
        for team_id in team_ids:
            team_name = self.id_to_name.get(team_id, f"ID_{team_id}")
            home_matches = self.match_data[self.match_data["HomeTeamID"] == team_id]
            away_matches = self.match_data[self.match_data["AwayTeamID"] == team_id]

            home_wins = len(home_matches[home_matches["Result"] == "1"])
            home_draws = len(home_matches[home_matches["Result"] == "X"])
            away_wins = len(away_matches[away_matches["Result"] == "2"])
            away_draws = len(away_matches[away_matches["Result"] == "X"])

            home_goals_scored = home_matches["HomeGoals"].sum()
            home_goals_conceded = home_matches["AwayGoals"].sum()
            away_goals_scored = away_matches["AwayGoals"].sum()
            away_goals_conceded = away_matches["HomeGoals"].sum()

            home_overs = len(home_matches[home_matches["Under/Over 2.5"] == "Over"])
            away_overs = len(away_matches[away_matches["Under/Over 2.5"] == "Over"])
            home_btts = len(home_matches[home_matches["BTTS"] == "Yes"])
            away_btts = len(away_matches[away_matches["BTTS"] == "Yes"])

            all_matches = pd.concat([
                home_matches.assign(is_home=True),
                away_matches.assign(is_home=False)
            ]).sort_values(by="Date", ascending=False)
            recent_matches = all_matches.head(5)

            recent_points = 0
            for _, m in recent_matches.iterrows():
                if m["is_home"] and m["Result"] == "1":
                    recent_points += 3
                elif not m["is_home"] and m["Result"] == "2":
                    recent_points += 3
                elif m["Result"] == "X":
                    recent_points += 1

            total_points = (home_wins + away_wins) * 3 + (home_draws + away_draws)

            self.team_data[team_name] = {
                "home_matches": len(home_matches),
                "away_matches": len(away_matches),
                "home_wins": home_wins,
                "home_draws": home_draws,
                "away_wins": away_wins,
                "away_draws": away_draws,
                "home_goals_scored": home_goals_scored,
                "home_goals_conceded": home_goals_conceded,
                "away_goals_scored": away_goals_scored,
                "away_goals_conceded": away_goals_conceded,
                "home_overs": home_overs,
                "away_overs": away_overs,
                "home_btts": home_btts,
                "away_btts": away_btts,
                "recent_form": recent_points,
                "total_points": total_points,
            }

    def load_upcoming_matches(self, league_code):
        endpoint = f"competitions/{league_code}/matches"
        data = self._get(endpoint)

        if not data or "matches" not in data or not data["matches"]:
            print(f"  [debug] load_upcoming_matches({league_code}): no data / empty 'matches' in response.")
            return []

        # Diagnostic: show what statuses the API is actually returning,
        # so we can see if the filter below is the thing eating the matches.
        status_counts = {}
        for match in data["matches"]:
            status_counts[match["status"]] = status_counts.get(match["status"], 0) + 1
        print(f"  [debug] load_upcoming_matches({league_code}): {len(data['matches'])} total matches, status breakdown: {status_counts}")

        upcoming_matches = []
        for match in data["matches"]:
            if match["status"] not in ["TIMED", "SCHEDULED"]:
                continue

            home_team = match["homeTeam"]["name"]
            away_team = match["awayTeam"]["name"]

            if not home_team or not away_team:
                continue

            # The "season" the match belongs to, per the API's own season
            # object — this is what we need to align the historical-stats
            # call to, not a guess based on today's date.
            season_year = None
            season_obj = match.get("season")
            if season_obj and season_obj.get("startDate"):
                season_year = int(season_obj["startDate"][:4])

            upcoming_matches.append({
                "Date": match["utcDate"][:10],
                "Time": match["utcDate"][11:16],
                "HomeTeam": home_team,
                "AwayTeam": away_team,
                "SeasonYear": season_year,
            })

        print(f"  [debug] load_upcoming_matches({league_code}): {len(upcoming_matches)} matches kept after status filter.")
        return upcoming_matches

    # ------------------------------------------------------------------
    # Real prediction formula
    # ------------------------------------------------------------------
    def predict_match(self, home_team, away_team):
        if home_team not in self.team_data or away_team not in self.team_data:
            return {
                "HomeTeam": home_team,
                "AwayTeam": away_team,
                "Prediction_1X2": "N/A",
                "Probability_1": None,
                "Probability_X": None,
                "Probability_2": None,
                "Over_Under_2.5": "N/A",
                "Probability_Over": None,
                "BTTS": "N/A",
                "Probability_BTTS": None,
                "Expected_Goals": None,
                "Warning": "Insufficient historical data for one or both teams.",
            }

        home_data = self.team_data[home_team]
        away_data = self.team_data[away_team]

        min_home_matches = max(1, home_data["home_matches"])
        min_away_matches = max(1, away_data["away_matches"])
        small_sample = home_data["home_matches"] < 3 or away_data["away_matches"] < 3

        # Base 1X2 probabilities
        prob_1 = home_data["home_wins"] / min_home_matches * 0.4
        prob_x = home_data["home_draws"] / min_home_matches * 0.3
        prob_2 = away_data["away_wins"] / min_away_matches * 0.4

        # Recent form adjustment
        home_form = home_data["recent_form"] / 15
        away_form = away_data["recent_form"] / 15
        prob_1 += home_form * 0.2 - away_form * 0.1
        prob_2 += away_form * 0.2 - home_form * 0.1

        # Table position adjustment
        points_diff = home_data["total_points"] - away_data["total_points"]
        table_factor = min(0.2, max(-0.2, points_diff / 30))
        prob_1 += table_factor
        prob_2 -= table_factor

        # Clamp and normalize
        probabilities = {
            "1": max(0.1, min(0.8, prob_1)),
            "X": max(0.1, min(0.6, prob_x)),
            "2": max(0.1, min(0.7, prob_2)),
        }
        total = sum(probabilities.values())
        for key in probabilities:
            probabilities[key] /= total

        predicted_result = max(probabilities, key=probabilities.get)

        # Over/Under
        avg_home_goals_scored = home_data["home_goals_scored"] / min_home_matches
        avg_away_goals_conceded = away_data["away_goals_conceded"] / min_away_matches
        avg_away_goals_scored = away_data["away_goals_scored"] / min_away_matches
        avg_home_goals_conceded = home_data["home_goals_conceded"] / min_home_matches
        expected_goals = (
            avg_home_goals_scored + avg_away_goals_conceded
            + avg_away_goals_scored + avg_home_goals_conceded
        ) / 2

        prob_over_home = home_data["home_overs"] / min_home_matches
        prob_over_away = away_data["away_overs"] / min_away_matches
        prob_over = (prob_over_home + prob_over_away) / 2
        over_under = "Over" if prob_over > 0.5 or expected_goals > 2.5 else "Under"

        # BTTS
        prob_btts_home = home_data["home_btts"] / min_home_matches
        prob_btts_away = away_data["away_btts"] / min_away_matches
        prob_btts = (prob_btts_home + prob_btts_away) / 2
        btts = "Yes" if prob_btts > 0.5 else "No"

        result = {
            "HomeTeam": home_team,
            "AwayTeam": away_team,
            "Prediction_1X2": predicted_result,
            "Probability_1": round(probabilities["1"] * 100, 1),
            "Probability_X": round(probabilities["X"] * 100, 1),
            "Probability_2": round(probabilities["2"] * 100, 1),
            "Over_Under_2.5": over_under,
            "Probability_Over": round(prob_over * 100, 1),
            "BTTS": btts,
            "Probability_BTTS": round(prob_btts * 100, 1),
            "Expected_Goals": round(expected_goals, 1),
        }
        if small_sample:
            result["Warning"] = "Small match sample: estimate may be unreliable."
        return result


if __name__ == "__main__":
    API_KEY = os.environ.get("API_FOOTBALL_KEY")
    if not API_KEY:
        print("Error: API_FOOTBALL_KEY environment variable is empty.")
        sys.exit(1)

    predictor = FootballPredictor(API_KEY)

    readme_content = "# Football Predictions Dashboard\n\n"
    readme_content += f"Last updated: _{datetime.utcnow().isoformat()[:-7]}Z (UTC)_\n\n"
    readme_content += "Automated predictive analytics pipeline updating every 24 hours.\n\n"

    all_predictions_count = 0

    MIN_FINISHED_MATCHES_FOR_STATS = 20  # rough floor: enough games for the
    # per-team aggregation to mean anything (a handful of matchdays across
    # the league, not just 1-2 games for a couple of teams).

    for code, name in COMPETITIONS.items():
        time.sleep(2)
        print(f"Processing {name} ({code}) via Football-Data.org engine...")

        # 1) Fetch upcoming matches first — this tells us which season
        #    the API currently considers "active" for this competition,
        #    which near a season changeover (the API treats a season as
        #    active up to 30 days before it starts) is NOT necessarily
        #    the season with enough finished matches to compute stats.
        upcoming = predictor.load_upcoming_matches(code)
        upcoming = upcoming[:5]

        upcoming_season_year = None
        for m in upcoming:
            if m.get("SeasonYear"):
                upcoming_season_year = m["SeasonYear"]
                break

        # 2) Load historical stats for that season. If it doesn't have
        #    enough finished matches yet (e.g. brand new season with 0-1
        #    matchdays played), fall back to the previous season so the
        #    model has something real to compute from.
        loaded = predictor.load_competition_data(code, season=upcoming_season_year)
        finished_count = len(predictor.match_data) if not predictor.match_data.empty else 0

        if not loaded or finished_count < MIN_FINISHED_MATCHES_FOR_STATS:
            fallback_season = (upcoming_season_year - 1) if upcoming_season_year else None
            print(f"  [debug] Only {finished_count} finished matches for season={upcoming_season_year}; "
                  f"falling back to season={fallback_season} for stats.")
            time.sleep(2)
            loaded = predictor.load_competition_data(code, season=fallback_season)
            if not loaded:
                print(f"  Warning: could not load historical data for {code} even with fallback season.")

        time.sleep(2)

        predictions_list = []
        for match in upcoming:
            pred = predictor.predict_match(match["HomeTeam"], match["AwayTeam"])
            pred["Date"] = match["Date"]
            pred["Time"] = match["Time"]
            predictions_list.append(pred)

        if predictions_list:
            all_predictions_count += len(predictions_list)
            readme_content += f"## {name} ({code})\n"
            readme_content += "| Date & Time | Match | 1X2 | 1 / X / 2 % | O/U 2.5 | BTTS |\n"
            readme_content += "| :--- | :--- | :---: | :---: | :---: | :---: |\n"

            for p in predictions_list:
                if p["Probability_1"] is None:
                    readme_content += f"| {p['Date']} {p['Time']} | **{p['HomeTeam']}** vs **{p['AwayTeam']}** | N/A | insufficient data | — | — |\n"
                else:
                    readme_content += f"| {p['Date']} {p['Time']} | **{p['HomeTeam']}** vs **{p['AwayTeam']}** | `{p['Prediction_1X2']}` | {p['Probability_1']}% / {p['Probability_X']}% / {p['Probability_2']}% | {p['Over_Under_2.5']} ({p['Probability_Over']}%) | {p['BTTS']} ({p['Probability_BTTS']}%) |\n"
            readme_content += "\n"

    if all_predictions_count == 0:
        readme_content += "### No upcoming matches found in the API response for the selected competitions.\n"

    with open("README.md", "w", encoding="utf-8") as readme_file:
        readme_file.write(readme_content)

    print("Pipeline executed successfully.")
