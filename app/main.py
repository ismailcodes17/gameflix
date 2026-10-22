from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_conn
from app.steam import climbing, fill_store_names, find_game, most_played, search_games, store_info

app = FastAPI()
base = Path(__file__).parent
templates = Jinja2Templates(directory=str(base / "templates"))
app.mount("/static", StaticFiles(directory=str(base / "static")), name="static")

def remember_game(app_id, name, peak_players, image_url, short_description):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO games (app_id, name, peak_players, image_url, short_description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (app_id) DO UPDATE SET
                name = EXCLUDED.name,
                peak_players = EXCLUDED.peak_players,
                image_url = EXCLUDED.image_url,
                short_description = EXCLUDED.short_description
            """,
            (app_id, name, peak_players, image_url, short_description),
        )
    
def _batch(count: int) -> int:
    count = max(5, min(count, 40))
    if count % 5:
        count += 5 - (count % 5)
    return min(count, 40)


@app.get("/")
def home(request: Request, hot: int = 5, up: int = 5):
    error = None
    games = []
    rising = []
    hot_total = 0
    up_total = 0
    hot = _batch(hot)
    up = _batch(up)
    try:
        chart = most_played(40)
        moved = climbing(40)
        hot_total = len(chart)
        up_total = len(moved)
        games = chart[:hot]
        rising = moved[:up]
        fill_store_names(games + rising)
    except Exception:
        error = "Steam did not answer. Wait a few seconds and refresh."
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "games": games,
            "rising": rising,
            "error": error,
            "hot": hot,
            "up": up,
            "hot_total": hot_total,
            "up_total": up_total,
        },
    )    

@app.get("/search")
def search(request: Request, q: str = ""):
    games = []
    if len(q.strip()) >= 2:
        try:
            games = search_games(q)
        except Exception:
            games = []
    return templates.TemplateResponse(request, "search_results.html", {"games": games, "q": q})


@app.get("/saved")
def saved(request: Request):
    with get_conn() as conn:
        games = conn.execute(
            """
            SELECT games.*, saved_games.added_at
            FROM saved_games
            JOIN games ON games.app_id = saved_games.app_id
            ORDER BY saved_games.added_at DESC
            """
        ).fetchall()
    return templates.TemplateResponse(request, "saved.html", {"games": games})
    
@app.post("/saved")
def save_game(
    app_id: int = Form(),
    name: str = Form(),
    peak_players: int = Form(),
    image_url: str = Form(),
    short_description: str = Form(""),
):
    remember_game(app_id, name, peak_players, image_url, short_description)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO saved_games (app_id) VALUES (%s) ON CONFLICT (app_id) DO NOTHING ",
            (app_id,),
        )
    return RedirectResponse("/saved", status_code=303)


@app.post("/saved/{app_id}/remove")
def remove_saved(app_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM saved_games WHERE app_id = %s", (app_id,))
    return RedirectResponse("/saved", status_code=303)

@app.get("/games/{app_id}")
def game_page(request: Request, app_id: int):
    listed = None
    try:
        listed = find_game(app_id)
    except Exception:
        listed = None
    with get_conn() as conn:
        stored = conn.execute("SELECT * FROM games WHERE app_id = %s", (app_id,)).fetchone()
        thoughts = []
        if stored is not None:
            thoughts = conn.execute(
                "SELECT * FROM thoughts WHERE app_id = %s ORDER BY created_at DESC",
                (app_id,),
            ).fetchall()
    if stored is None and listed is None:
        name, description = store_info(app_id)
        if not name:
            return RedirectResponse("/", status_code=303)
        listed = {
            "app_id": app_id,
            "name": name,
            "peak_players": 0,
            "image_url": f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
            "short_description": description,
        }
    game = dict(stored or listed)
    if listed:
        game["short_description"] = listed.get("short_description") or game.get("short_description") or ""
    return templates.TemplateResponse(
        request,
        "game.html",
        {"game": game, "thoughts": thoughts, "saved": stored is not None},
    )

@app.post("/games/{app_id}/thoughts")
def add_thought(
    app_id: int,
    friend_name: str = Form(),
    rating: int = Form(),
    comment: str= Form(),
):
    friend_name = friend_name.strip()
    comment = comment.strip()
    if friend_name and comment and 1 <= rating <= 5:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO thoughts (app_id, friend_name, rating, comment)
                VALUES (%s, %s, %s, %s)
                """,
                (app_id, friend_name, rating, comment),

            )
            
        return RedirectResponse(f"/games/{app_id}", status_code=303)
    
@app.get("/about")
def about (request: Request):
    return templates.TemplateResponse(request, "about.html", {})