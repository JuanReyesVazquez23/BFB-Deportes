"""
Lógica del bracket de postemporada MLB (formato de 12 equipos, vigente desde 2022).

Este módulo es PURO: recibe los JSON crudos de la MLB Stats API (schedule y
standings) y devuelve el bracket ya armado. No hace llamadas de red ni toca la
base de datos, así que se puede probar sin levantar el servidor
(ver backend/tests/test_postseason_service.py).

Estructura fija del cuadro, por liga (AL y NL):

    Wild Card (mejor de 3):   #3 vs #6      #4 vs #5
    Divisional (mejor de 5):  #2 vs ganador(3/6)   #1 vs ganador(4/5)
    Campeonato (mejor de 7):  ganador DS_A vs ganador DS_B
    Serie Mundial (mejor de 7): campeón AL vs campeón NL

Los "sembrados" (#1..#6) se calculan desde las posiciones de temporada
regular: los 3 líderes de división son #1-#3 (por récord) y los 3 comodines
son #4-#6. Los juegos reales de la postemporada se ubican en su casilla del
cuadro por los equipos que participan, y los ganadores avanzan solos a la
siguiente ronda, aun cuando esa serie todavía no tenga juegos programados.
"""
from __future__ import annotations

from datetime import datetime, timezone

AL_LEAGUE_ID = 103
NL_LEAGUE_ID = 104
_LEAGUE_BY_ID = {AL_LEAGUE_ID: "AL", NL_LEAGUE_ID: "NL"}

# gameType de la MLB Stats API -> ronda.
_ROUND_BY_GAME_TYPE = {"F": "WC", "D": "DS", "L": "CS", "W": "WS"}
# Respaldo por descripción si por algún motivo gameType no viniera.
_ROUND_BY_DESCRIPTION = (
    ("wild card", "WC"),
    ("division", "DS"),
    ("championship", "CS"),
    ("world series", "WS"),
)
BEST_OF = {"WC": 3, "DS": 5, "CS": 7, "WS": 7}

# Ids fijos de equipos MLB -> (abreviatura, color primario). Sirven de respaldo
# cuando la API no trae la abreviatura y para colorear el cuadro.
TEAM_META: dict[str, tuple[str, str]] = {
    "108": ("LAA", "#BA0021"),
    "109": ("AZ", "#A71930"),
    "110": ("BAL", "#DF4601"),
    "111": ("BOS", "#BD3039"),
    "112": ("CHC", "#0E3386"),
    "113": ("CIN", "#C6011F"),
    "114": ("CLE", "#00385D"),
    "115": ("COL", "#33006F"),
    "116": ("DET", "#0C2340"),
    "117": ("HOU", "#EB6E1F"),
    "118": ("KC", "#004687"),
    "119": ("LAD", "#005A9C"),
    "120": ("WSH", "#AB0003"),
    "121": ("NYM", "#002D72"),
    "133": ("ATH", "#003831"),
    "134": ("PIT", "#FDB827"),
    "135": ("SD", "#2F241D"),
    "136": ("SEA", "#0C2C56"),
    "137": ("SF", "#FD5A1E"),
    "138": ("STL", "#C41E3A"),
    "139": ("TB", "#092C5C"),
    "140": ("TEX", "#003278"),
    "141": ("TOR", "#134A8E"),
    "142": ("MIN", "#002B5C"),
    "143": ("PHI", "#E81828"),
    "144": ("ATL", "#CE1141"),
    "145": ("CWS", "#27251F"),
    "146": ("MIA", "#00A3E0"),
    "147": ("NYY", "#0C2340"),
    "158": ("MIL", "#12284B"),
}
_DEFAULT_COLOR = "#3d3d43"


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _tid(value) -> str | None:
    """Normaliza un id de equipo a str (o None si no es válido)."""
    n = _int_or_none(value)
    return str(n) if n else None


def _round_of(game: dict) -> str | None:
    by_type = _ROUND_BY_GAME_TYPE.get(str(game.get("gameType") or "").upper())
    if by_type:
        return by_type
    desc = (game.get("seriesDescription") or "").lower()
    for needle, round_key in _ROUND_BY_DESCRIPTION:
        if needle in desc:
            return round_key
    return None


def _game_status(game: dict) -> str:
    status = game.get("status") or {}
    detailed = (status.get("detailedState") or "").lower()
    if "postponed" in detailed or "cancel" in detailed:
        return "postponed"
    abstract = (status.get("abstractGameState") or "").lower()
    if abstract == "final" or "final" in detailed or "game over" in detailed:
        return "final"
    if abstract == "live" or "progress" in detailed or "review" in detailed:
        return "live"
    return "scheduled"


def _logo(team_id: str, logos: dict[str, str | None]) -> str:
    return logos.get(team_id) or f"https://www.mlbstatic.com/team-logos/{team_id}.svg"


# --------------------------------------------------------------------------
# Sembrados (seeds) desde las posiciones de temporada regular
# --------------------------------------------------------------------------
def compute_seeds(standings: dict | None) -> dict[str, dict]:
    """
    Devuelve {team_id: {"league": "AL"|"NL", "seed": 1..6, "name": str}}.

    Solo incluye los 6 clasificados por liga. Si las posiciones faltan o están
    incompletas, devuelve lo que se pueda (el armado del bracket tolera eso).
    """
    if not standings:
        return {}

    by_league: dict[str, list[dict]] = {"AL": [], "NL": []}
    for record in standings.get("records", []) or []:
        league = _LEAGUE_BY_ID.get(_int_or_none((record.get("league") or {}).get("id")))
        if not league:
            continue
        by_league[league].extend(record.get("teamRecords", []) or [])

    def _rank(tr: dict, key: str) -> int:
        n = _int_or_none(tr.get(key))
        return n if n is not None else 10**6

    def _pct(tr: dict) -> float:
        try:
            return float(tr.get("winningPercentage") or 0)
        except (TypeError, ValueError):
            return 0.0

    seeds: dict[str, dict] = {}
    for league, teams in by_league.items():
        winners = [
            tr for tr in teams
            if tr.get("divisionLeader") is True or _int_or_none(tr.get("divisionRank")) == 1
        ]
        winner_ids = {_tid((tr.get("team") or {}).get("id")) for tr in winners}
        wildcards = [
            tr for tr in teams
            if _tid((tr.get("team") or {}).get("id")) not in winner_ids
            and _int_or_none(tr.get("wildCardRank")) is not None
        ]
        winners.sort(key=lambda tr: (_rank(tr, "leagueRank"), -_pct(tr)))
        wildcards.sort(key=lambda tr: (_rank(tr, "wildCardRank"), -_pct(tr)))

        for idx, tr in enumerate(winners[:3]):
            _put_seed(seeds, tr, league, idx + 1)
        for idx, tr in enumerate(wildcards[:3]):
            _put_seed(seeds, tr, league, idx + 4)
    return seeds


def _put_seed(seeds: dict, team_record: dict, league: str, seed: int) -> None:
    team = team_record.get("team") or {}
    tid = _tid(team.get("id"))
    if tid:
        seeds[tid] = {"league": league, "seed": seed, "name": team.get("name") or ""}


# --------------------------------------------------------------------------
# Series crudas desde el schedule
# --------------------------------------------------------------------------
def _collect_raw_series(schedule: dict) -> tuple[dict, dict, dict]:
    """
    Agrupa los juegos por (ronda, par de equipos).

    Devuelve (series, team_info, team_league_hint):
      - series: {(round, frozenset(ids)): {...juegos, victorias, ganador...}}
      - team_info: {team_id: {"name", "abbreviation"}}
      - team_league_hint: {team_id: "AL"|"NL"} sacado del objeto team hidratado
    """
    series: dict = {}
    team_info: dict[str, dict] = {}
    league_hint: dict[str, str] = {}

    for day in schedule.get("dates", []) or []:
        for game in day.get("games", []) or []:
            round_key = _round_of(game)
            if not round_key:
                continue
            teams = game.get("teams") or {}
            home, away = teams.get("home") or {}, teams.get("away") or {}
            home_team, away_team = home.get("team") or {}, away.get("team") or {}
            home_id, away_id = _tid(home_team.get("id")), _tid(away_team.get("id"))
            if not home_id or not away_id or home_id == away_id:
                continue  # juego con equipos aún por definir

            for tid, team in ((home_id, home_team), (away_id, away_team)):
                info = team_info.setdefault(tid, {"name": "", "abbreviation": ""})
                info["name"] = info["name"] or team.get("name") or ""
                info["abbreviation"] = (
                    info["abbreviation"] or team.get("abbreviation") or TEAM_META.get(tid, ("", ""))[0]
                )
                hint = _LEAGUE_BY_ID.get(_int_or_none((team.get("league") or {}).get("id")))
                if hint:
                    league_hint[tid] = hint

            key = (round_key, frozenset((home_id, away_id)))
            entry = series.get(key)
            if entry is None:
                entry = {
                    "round": round_key,
                    "ids": (home_id, away_id),
                    "best_of": BEST_OF[round_key],
                    "games": [],
                    "wins": {home_id: 0, away_id: 0},
                }
                series[key] = entry
            games_in_series = _int_or_none(game.get("gamesInSeries"))
            if games_in_series in (3, 5, 7):
                entry["best_of"] = games_in_series

            entry["games"].append(
                {
                    "id": game.get("gamePk"),
                    "game_number": _int_or_none(game.get("seriesGameNumber")),
                    "date": game.get("gameDate"),
                    "status": _game_status(game),
                    "home_id": home_id,
                    "away_id": away_id,
                    "home_abbreviation": team_info[home_id]["abbreviation"],
                    "away_abbreviation": team_info[away_id]["abbreviation"],
                    "home_score": home.get("score"),
                    "away_score": away.get("score"),
                }
            )

    for entry in series.values():
        entry["games"].sort(key=lambda g: (g["date"] or "", g["game_number"] or 0))
        for g in entry["games"]:
            hs, aws = g["home_score"], g["away_score"]
            if g["status"] != "final" or hs is None or aws is None or hs == aws:
                continue
            entry["wins"][g["home_id"] if hs > aws else g["away_id"]] += 1
        needed = entry["best_of"] // 2 + 1
        entry["winner_id"] = next((tid for tid, w in entry["wins"].items() if w >= needed), None)
        if entry["winner_id"]:
            # Juegos "si es necesario" que ya no se jugaron: no se muestran.
            entry["games"] = [g for g in entry["games"] if g["status"] in ("final", "live")]
    return series, team_info, league_hint


# --------------------------------------------------------------------------
# Armado del bracket
# --------------------------------------------------------------------------
def build_bracket(
    schedule: dict,
    standings: dict | None = None,
    logos: dict[str, str | None] | None = None,
    season: int | None = None,
) -> dict:
    logos = logos or {}
    seeds = compute_seeds(standings)
    raw_series, team_info, league_hint = _collect_raw_series(schedule)
    active = bool(raw_series)

    for tid, info in seeds.items():
        entry = team_info.setdefault(tid, {"name": "", "abbreviation": TEAM_META.get(tid, ("", ""))[0]})
        entry["name"] = entry["name"] or info["name"]
        entry["abbreviation"] = entry["abbreviation"] or TEAM_META.get(tid, ("", ""))[0]

    def league_of(tid: str) -> str | None:
        return (seeds.get(tid) or {}).get("league") or league_hint.get(tid)

    seeds_available = all(
        sum(1 for s in seeds.values() if s["league"] == lg) == 6 for lg in ("AL", "NL")
    )

    payload = {
        "season": season,
        "postseason_active": active,
        "seeds_available": seeds_available,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stale": False,
        "al": [],
        "nl": [],
        "world_series": None,
        "champion": None,
    }
    if not active:
        return payload

    used: set = set()

    def pick(round_key: str, league: str | None, ids: list[str | None], single: bool = False):
        """Busca la serie real que corresponde a una casilla del cuadro."""
        wanted = {i for i in ids if i}
        candidates = [
            (key, s) for key, s in raw_series.items()
            if s["round"] == round_key and key not in used
            and (league is None or league_of(s["ids"][0]) == league or league_of(s["ids"][1]) == league)
        ]
        candidates.sort(key=lambda kv: kv[1]["games"][0]["date"] or "")
        for key, s in candidates:
            if wanted & set(s["ids"]):
                used.add(key)
                return s
        # Sin sembrados no se puede casar por equipo: se asigna por orden de fecha.
        # En CS/WS solo existe una serie por liga, así que también aplica.
        if candidates and (single or not seeds_available):
            key, s = candidates[0]
            used.add(key)
            return s
        return None

    def team_entry(tid: str | None, series: dict | None) -> dict | None:
        if not tid:
            return None
        info = team_info.get(tid, {})
        winner = series.get("winner_id") if series else None
        return {
            "id": tid,
            "name": info.get("name", ""),
            "abbreviation": info.get("abbreviation") or TEAM_META.get(tid, ("", ""))[0],
            "logo_url": _logo(tid, logos),
            "color": TEAM_META.get(tid, ("", _DEFAULT_COLOR))[1],
            "seed": (seeds.get(tid) or {}).get("seed"),
            "wins": series["wins"].get(tid, 0) if series else 0,
            "is_winner": bool(winner and winner == tid),
            "eliminated": bool(winner and winner != tid),
        }

    def make_series(slot: str, league: str | None, round_key: str, projected: list[str | None], raw: dict | None) -> dict:
        ordered: list[str | None] = [None, None]
        if raw:
            actual = list(raw["ids"])
            for i, pid in enumerate(projected):
                if pid in actual:
                    ordered[i] = pid
            remaining = [x for x in actual if x not in ordered]
            if round_key == "WS":
                remaining.sort(key=lambda x: league_of(x) != "AL")
            for i in range(2):
                if ordered[i] is None and remaining:
                    ordered[i] = remaining.pop(0)
        else:
            ordered = list(projected)

        if not raw:
            status = "pending"
        elif raw["winner_id"]:
            status = "final"
        elif any(g["status"] == "live" for g in raw["games"]):
            status = "live"
        elif any(g["status"] == "final" for g in raw["games"]):
            status = "in_progress"
        else:
            status = "scheduled"

        return {
            "id": f"{league}_{slot}" if league else slot,
            "slot": slot,
            "round": round_key,
            "league": league,
            "best_of": raw["best_of"] if raw else BEST_OF[round_key],
            "status": status,
            "teams": [team_entry(t, raw) for t in ordered],
            "winner_id": raw["winner_id"] if raw else None,
            "games": raw["games"] if raw else [],
        }

    champions: dict[str, str | None] = {}
    for league in ("AL", "NL"):
        by_seed = {s["seed"]: tid for tid, s in seeds.items() if s["league"] == league}
        s1, s2, s3, s4, s5, s6 = (by_seed.get(n) for n in range(1, 7))

        wc_a_raw = pick("WC", league, [s3, s6])
        wc_b_raw = pick("WC", league, [s4, s5])
        wc_a = make_series("WC_A", league, "WC", [s6, s3], wc_a_raw)
        wc_b = make_series("WC_B", league, "WC", [s5, s4], wc_b_raw)

        ds_a_raw = pick("DS", league, [s2])
        ds_b_raw = pick("DS", league, [s1])
        ds_a = make_series("DS_A", league, "DS", [wc_a["winner_id"], s2], ds_a_raw)
        ds_b = make_series("DS_B", league, "DS", [wc_b["winner_id"], s1], ds_b_raw)

        cs_raw = pick("CS", league, [ds_a["winner_id"], ds_b["winner_id"]], single=True)
        cs = make_series("CS", league, "CS", [ds_a["winner_id"], ds_b["winner_id"]], cs_raw)

        champions[league] = cs["winner_id"]
        payload["al" if league == "AL" else "nl"] = [wc_a, wc_b, ds_a, ds_b, cs]

    ws_raw = pick("WS", None, [champions["AL"], champions["NL"]], single=True)
    ws = make_series("WS", None, "WS", [champions["AL"], champions["NL"]], ws_raw)
    payload["world_series"] = ws
    if ws["winner_id"]:
        winner = next((t for t in ws["teams"] if t and t["id"] == ws["winner_id"]), None)
        payload["champion"] = winner
    return payload


def has_live_game(payload: dict) -> bool:
    series = (payload.get("al") or []) + (payload.get("nl") or [])
    if payload.get("world_series"):
        series.append(payload["world_series"])
    return any(s.get("status") == "live" for s in series)
