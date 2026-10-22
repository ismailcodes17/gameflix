import re
import time

import httpx

CHART_URL = "https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/"
DETAILS_URL = "https://store.steampowered.com/api/appdetails"
SPY_URL = "https://steamspy.com/api.php?request=top100in2weeks"
SEARCH_URL = "https://store.steampowered.com/api/storesearch/"

ALIASES = {
    "gta": "grand theft auto",
    "rdr": "red dead redemption",
    "cs": "counter-strike",
    "cod": "call of duty",
    "wow": "world of warcraft",
    "lol": "league of legends",
}


_cache = {"at": 0, "games": []}

def header_image(app_id):
    return f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg"


def plain_text(value):
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(text.split())

def store_info(app_id):
    for _ in range(3):
        try:
            with httpx.Client(timeout=12, headers={"User-Agent": "GameFlix/1.0"}) as client:
                details = client.get(DETAILS_URL, params={"appids": app_id})
                if details.status_code == 429:
                    time.sleep(0.8)
                    continue
                details.raise_for_status()
                data = details.json().get(str(app_id), {}).get("data") or {}
                return data.get("name") or "", plain_text(data.get("short_description"))
        except httpx.HTTPError:
            time.sleep(0.4)
    return "", ""


def fill_store_names(games):
    for game in games:
        if game.get("from_store"):
            continue
        name, description = store_info(game["app_id"])
        if name:
            game["name"] = name
            game["short_description"] = description
            game["from_store"] = True
        time.sleep(0.15)


def description_for(app_id):
    try:
        with httpx.Client(timeout=12, headers={"User-Agent": "GameFlix/1.0"}) as client:
            details = client.get(DETAILS_URL, params={"appids": app_id})
            if details.status_code == 429:
                return ""
            details.raise_for_status()
            data = details.json().get(str(app_id), {}).get("data") or {}
    except httpx.HTTPError:
        return ""
    return plain_text(data.get("short_description"))


def load_chart(limit=40):
    if _cache["games"] and time.time() - _cache["at"] < 600:
        return _cache["games"]

    with httpx.Client(timeout=20, headers={"User-Agent": "GameFlix/1.0"}) as client:
        charts = client.get(CHART_URL)
        charts.raise_for_status()
        ranks = charts.json()["response"]["ranks"][:limit]
        catalog = {}
        try:
            spy = client.get(SPY_URL)
            if spy.status_code == 200:
                catalog = spy.json()
        except httpx.HTTPError:
            catalog = {}

    games = []
    for rank in ranks:
        app_id = rank["appid"]
        info = catalog.get(str(app_id), {})
        games.append(
            {
                "app_id": app_id,
                "name": info.get("name") or f"Steam app {app_id}",
                "peak_players": rank["peak_in_game"],
                "rank": rank["rank"],
                "last_week_rank": rank.get("last_week_rank") or 0,
                "image_url": header_image(app_id),
                "short_description": "",
            }
        )
    games.sort(key=lambda game: game["rank"])

    _cache["at"] = time.time()
    _cache["games"] = games
    return games


def search_term(text):
    cleaned = " ".join(text.lower().split())
    for short, full in ALIASES.items():
        if cleaned == short or cleaned.startswith(short + " "):
            return full + cleaned[len(short):]
    return text.strip()


def search_games(text):
    term = search_term(text)
    if len(term) < 2:
        return []
    with httpx.Client(timeout=12, headers={"User-Agent": "GameFlix/1.0"}) as client:
        response = client.get(SEARCH_URL, params={"term": term, "l": "english", "cc": "US"})
        response.raise_for_status()
        items = response.json().get("items") or []
    games = []
    for item in items:
        if item.get("type") != "app":
            continue
        app_id = item["id"]
        games.append(
            {
                "app_id": app_id,
                "name": item.get("name") or f"Steam app {app_id}",
                "image_url": header_image(app_id),
                "peak_players": 0,
                "short_description": "",
            }
        )
        if len(games) == 8:
            break
    return games


def find_game(app_id):
    for game in load_chart():
        if game["app_id"] == app_id:
            if not game["short_description"]:
                game["short_description"] = description_for(app_id)
            return game
    return None


def most_played(limit=12):
    return load_chart()[:limit]


def climbing(limit=12):
    moved = [
        game
        for game in load_chart()
        if game["last_week_rank"] and game["rank"] < game["last_week_rank"]
    ]
    moved.sort(key=lambda game: game["last_week_rank"] - game["rank"], reverse=True)
    return moved[:limit]
    