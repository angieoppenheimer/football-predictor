import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# COMPETITION LEGEND
# ---------------------------------------------------------------------------
# Codes verified against the official football-data.org documentation (v4).
# The FREE plan includes ONLY these 12 competitions, with basic data
# (results, fixtures, league tables) and 10 requests/minute.
# Other competitions exist in the catalog (/competitions endpoint) but
# require a paid plan to actually query their data.
FREE_COMPETITIONS = {
    "CL":  "UEFA Champions League",
    "PL":  "Premier League (England)",
    "PD":  "La Liga (Spain)",
    "BL1": "Bundesliga (Germany)",
    "SA":  "Serie A (Italy)",
    "FL1": "Ligue 1 (France)",
    "DED": "Eredivisie (Netherlands)",
    "PPL": "Primeira Liga (Portugal)",
    "ELC": "Championship (England, 2nd tier)",
    "BSA": "Brasileirão Série A (Brazil)",
    "WC":  "FIFA World Cup",
    "EC":  "UEFA European Championship",
}

def print_competition_legend():
    print("\n=== COMPETITIONS AVAILABLE ON THE FREE PLAN ===")
    for code, name in FREE_COMPETITIONS.items():
        print(f"  {code:5s} -> {name}")
    print("\n=== OTHER EXISTING COMPETITIONS (require a paid plan) ===")
    for code, name in PAID_COMPETITIONS_NOTE.items():
        print(f"  {code:5s} -> {name}")
    print("\nNote: the full, official list can always be checked live")
    print("with a GET /v4/competitions call (see get_live_competitions).")
    print("=" * 55)


class RateLimiter:
    """Limits API calls so as not to exceed the free plan's limit
    (10 requests/minute). Sleeps automatically when needed."""

    def __init__(self, requests_per_minute=10):
        self.min_interval = 60.0 / requests_per_minute
        self._last_call = 0.0

    def wait(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()


class APIError(Exception):
    """Dedicated exception for football-data.org API errors."""
    pass


class FootballPredictor:

    def __init__(self, api_token, requests_per_minute=10):
        if not api_token:
            raise ValueError(
                "Missing API token. Set the FOOTBALL_DATA_TOKEN environment "
                "variable, or pass the token explicitly."
            )
        self.api_token = api_token
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {"X-Auth-Token": self.api_token}
        self.team_data = {}
        self.match_data = pd.DataFrame()
        self.id_to_name = {}
        self.name_to_id = {}
        self._rate_limiter = RateLimiter(requests_per_minute)

    # ------------------------------------------------------------------
    # Centralized HTTP call with rate limiting and error handling
    # ------------------------------------------------------------------
    def _get(self, url, params=None):
        self._rate_limiter.wait()
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
        except requests.RequestException as e:
            raise APIError(f"Connection error: {e}") from e

        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
            raise APIError(
                "Rate limit exceeded. Try again later or increase the "
                "interval between calls."
            )
        if response.status_code == 403:
            raise APIError(
                "Access denied (403): this competition or resource is not "
                "available on your plan (likely requires a paid plan)."
            )
        if response.status_code == 404:
            raise APIError("Resource not found (404): check the code you used.")
        raise APIError(f"API error {response.status_code}: {response.text[:200]}")

    # ------------------------------------------------------------------
    # Competitions
    # ------------------------------------------------------------------
    def get_live_competitions(self):
        """Fetches the full, live list of competitions known to the
        account (useful to check what's actually available)."""
        data = self._get(f"{self.base_url}/competitions")
        return {comp["code"]: comp["name"] for comp in data.get("competitions", [])}

    def validate_competition_code(self, competition_code):
        if competition_code not in FREE_COMPETITIONS:
            message = (
                f"The code '{competition_code}' is not among the free-plan "
                f"competitions. Valid codes: {', '.join(FREE_COMPETITIONS)}."
            )
            if competition_code in PAID_COMPETITIONS_NOTE:
                message += " (This code exists but requires a paid plan.)"
            raise ValueError(message)

    # ------------------------------------------------------------------
    # Loading historical data
    # ------------------------------------------------------------------
    def load_competition_data(self, competition_code, season=None):
        self.validate_competition_code(competition_code)

        if not season:
            current_year = datetime.now().year
            season = current_year if datetime.now().month > 7 else current_year - 1

        self._load_teams(competition_code, season)
        self._load_matches(competition_code, season)
        self._process_team_data()
        print(f"Data for competition {competition_code}, season {season}, loaded successfully.")
        return True

    def _load_teams(self, competition_code, season):
        url = f"{self.base_url}/competitions/{competition_code}/teams"
        params = {"season": season} if season else None
        data = self._get(url, params=params)

        self.id_to_name = {team["id"]: team["name"] for team in data["teams"]}
        self.name_to_id = {team["name"]: team["id"] for team in data["teams"]}

    def _load_matches(self, competition_code, season):
        url = f"{self.base_url}/competitions/{competition_code}/matches"
        params = {"season": season} if season else None
        data = self._get(url, params=params)

        matches = []
        for match in data["matches"]:
            if match["status"] != "FINISHED":
                continue
            home_goals = match["score"]["fullTime"]["home"]
            away_goals = match["score"]["fullTime"]["away"]
            if home_goals is None or away_goals is None:
                continue  # incomplete data, skip

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
        print(f"Loaded {len(matches)} completed matches.")

    def _process_team_data(self):
        self.team_data = {}
        if self.match_data.empty:
            print("Warning: no completed matches found for this season/competition.")
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

            all_matches = pd.concat(
                [home_matches.assign(is_home=True), away_matches.assign(is_home=False)]
            ).sort_values(by="Date", ascending=False)
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
                "id": team_id,
                "home_matches": len(home_matches),
                "away_matches": len(away_matches),
                "home_wins": home_wins,
                "home_draws": home_draws,
                "home_losses": home_losses,
                "away_wins": away_wins,
                "away_draws": away_draws,
                "away_losses": away_losses,
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

    # ------------------------------------------------------------------
    # Upcoming matches
    # ------------------------------------------------------------------
    def load_upcoming_matches(self, competition_code, date_from=None, date_to=None):
        self.validate_competition_code(competition_code)

        if not date_from:
            date_from = datetime.now().strftime("%Y-%m-%d")
        if not date_to:
            date_to = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        url = f"{self.base_url}/matches"
        params = {
            "competitions": competition_code,
            "dateFrom": date_from,
            "dateTo": date_to,
        }
        data = self._get(url, params=params)

        upcoming_matches = []
        for match in data["matches"]:
            home_id = match["homeTeam"]["id"]
            away_id = match["awayTeam"]["id"]
            if home_id in self.id_to_name and away_id in self.id_to_name:
                upcoming_matches.append({
                    "Date": match["utcDate"][:10],
                    "Time": match["utcDate"][11:16],
                    "HomeTeamID": home_id,
                    "AwayTeamID": away_id,
                    "HomeTeam": self.id_to_name[home_id],
                    "AwayTeam": self.id_to_name[away_id],
                })
        return upcoming_matches

    def print_matches(self, matches):
        if not matches:
            print("\nNo matches found in the selected period.")
            return
        print("\n=== UPCOMING MATCHES ===")
        for m in matches:
            print(f"{m['Date']} {m['Time']} - {m['HomeTeam']} vs {m['AwayTeam']}")
        print("========================")

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict_match(self, home_team, away_team):
        if home_team not in self.team_data or away_team not in self.team_data:
            return {"error": "One or both teams are not present in the data"}

        home_data = self.team_data[home_team]
        away_data = self.team_data[away_team]

        min_home_matches = max(1, home_data["home_matches"])
        min_away_matches = max(1, away_data["away_matches"])

        # Warn if the sample is very small (e.g. start of season)
        small_sample = home_data["home_matches"] < 3 or away_data["away_matches"] < 3

        # Base 1X2 probabilities
        prob_1 = home_data["home_wins"] / min_home_matches * 0.4
        prob_x = home_data["home_draws"] / min_home_matches * 0.3
        prob_2 = away_data["away_wins"] / min_away_matches * 0.4

        # Adjust for recent form
        home_form = home_data["recent_form"] / 15
        away_form = away_data["recent_form"] / 15
        prob_1 += home_form * 0.2 - away_form * 0.1
        prob_2 += away_form * 0.2 - home_form * 0.1

        # Adjust for points-table gap
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
            "Over/Under_2.5": over_under,
            "Probability_Over": round(prob_over * 100, 1),
            "BTTS": btts,
            "Probability_BTTS": round(prob_btts * 100, 1),
            "Expected_Goals": round(expected_goals, 1),
        }
        if small_sample:
            result["Warning"] = "Very small match sample: estimate is unreliable."
        return result


def print_betting_slip(predictor, matches):
    print("\n=== MATCH PREDICTIONS ===")
    for match in matches:
        prediction = predictor.predict_match(match["HomeTeam"], match["AwayTeam"])
        if "error" in prediction:
            print(f"{match['Date']} {match['Time']} - {match['HomeTeam']} vs {match['AwayTeam']}: {prediction['error']}")
            print("----------------------------")
            continue
        print(f"{match['Date']} {match['Time']} - {prediction['HomeTeam']} vs {prediction['AwayTeam']}")
        print(f"1X2 prediction: {prediction['Prediction_1X2']} "
              f"({prediction['Probability_1']}% - {prediction['Probability_X']}% - {prediction['Probability_2']}%)")
        print(f"Over/Under 2.5: {prediction['Over/Under_2.5']} ({prediction['Probability_Over']}%)")
        print(f"BTTS: {prediction['BTTS']} ({prediction['Probability_BTTS']}%)")
        print(f"Expected goals: {prediction['Expected_Goals']}")
        if "Warning" in prediction:
            print(f"⚠ {prediction['Warning']}")
        print("----------------------------")


if __name__ == "__main__":
    # The token is read from a .env file (not committed, not shared),
    # never written here in plain text. Create a ".env" file in the same
    # folder with a line like: FOOTBALL_DATA_TOKEN=your_token_here
    API_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not API_TOKEN:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith("FOOTBALL_DATA_TOKEN="):
                        API_TOKEN = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        break

    print_competition_legend()

    if not API_TOKEN:
        print("\nError: FOOTBALL_DATA_TOKEN not set (env var or .env file).")
        raise SystemExit(1)

    competition_code = "CL"   # see legend above
    date_from = "2026-09-15"
    date_to = "2026-09-15"

    try:
        predictor = FootballPredictor(API_TOKEN)
        predictor.load_competition_data(competition_code)
        matches = predictor.load_upcoming_matches(competition_code, date_from, date_to)
        predictor.print_matches(matches)
        print_betting_slip(predictor, matches)
    except (APIError, ValueError) as e:
        print(f"\nError: {e}")
