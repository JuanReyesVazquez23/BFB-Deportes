"""
Pruebas de la lógica del bracket de postemporada (sin red, sin servidor).

Ejecutar desde backend/:
    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.postseason_service import build_bracket, compute_seeds, has_live_game  # noqa: E402

# Sembrados de la imagen de referencia (Panorama de la Postemporada 2026).
AL = {1: 139, 2: 114, 3: 117, 4: 147, 5: 111, 6: 145}  # TB, CLE, HOU, NYY, BOS, CWS
NL = {1: 158, 2: 119, 3: 144, 4: 135, 5: 112, 6: 143}  # MIL, LAD, ATL, SD, CHC, PHI
NAMES = {
    139: "Tampa Bay Rays", 114: "Cleveland Guardians", 117: "Houston Astros",
    147: "New York Yankees", 111: "Boston Red Sox", 145: "Chicago White Sox",
    158: "Milwaukee Brewers", 119: "Los Angeles Dodgers", 144: "Atlanta Braves",
    135: "San Diego Padres", 112: "Chicago Cubs", 143: "Philadelphia Phillies",
}
LEAGUE_OF = {**{t: 103 for t in AL.values()}, **{t: 104 for t in NL.values()}}


def _record(tid, seed, extra=None):
    """teamRecord de /standings. Seeds 1-3 = líderes de división; 4-6 = comodines."""
    rec = {
        "team": {"id": tid, "name": NAMES[tid]},
        "divisionRank": "1" if seed <= 3 else "2",
        "divisionLeader": seed <= 3,
        "leagueRank": str(seed),
        "wildCardRank": "-" if seed <= 3 else str(seed - 3),
        "winningPercentage": f"{0.650 - seed * 0.02:.3f}",
    }
    rec.update(extra or {})
    return rec


def make_standings():
    records = []
    for league_id, seeds in ((103, AL), (104, NL)):
        # Mezclados a propósito: el orden de entrada no debe importar.
        teams = [_record(tid, seed) for seed, tid in sorted(seeds.items(), reverse=True)]
        # Más equipos que no clasifican (no deben recibir sembrado).
        teams.append({
            "team": {"id": 9000 + league_id, "name": "No clasifica"},
            "divisionRank": "3", "divisionLeader": False, "leagueRank": "9",
            "wildCardRank": "4", "winningPercentage": "0.480",
        })
        records.append({"league": {"id": league_id}, "teamRecords": teams})
    return {"records": records}


_pk = [1000]


def game(round_type, home, away, num, status="Final", hs=None, aws=None, in_series=None):
    _pk[0] += 1
    abstract = {"Final": "Final", "In Progress": "Live", "Scheduled": "Preview", "Postponed": "Preview"}[status]
    return {
        "gamePk": _pk[0],
        "gameType": round_type,
        "gameDate": f"2026-10-{num + 1:02d}T20:00:00Z" if round_type != "W" else f"2026-10-{num + 20:02d}T20:00:00Z",
        "seriesGameNumber": num,
        "gamesInSeries": in_series or {"F": 3, "D": 5, "L": 7, "W": 7}[round_type],
        "status": {"abstractGameState": abstract, "detailedState": status},
        "teams": {
            "home": {"team": {"id": home, "name": NAMES[home], "league": {"id": LEAGUE_OF[home]}}, "score": hs},
            "away": {"team": {"id": away, "name": NAMES[away], "league": {"id": LEAGUE_OF[away]}}, "score": aws},
        },
    }


def schedule(*games):
    return {"dates": [{"games": list(games)}]}


def find(payload, side, slot):
    series = payload[side] if side in ("al", "nl") else None
    return next(s for s in series if s["slot"] == slot)


def team_ids(series):
    return [t["id"] if t else None for t in series["teams"]]


class SeedsTest(unittest.TestCase):
    def test_seeds_por_liga(self):
        seeds = compute_seeds(make_standings())
        for seed, tid in AL.items():
            self.assertEqual(seeds[str(tid)]["seed"], seed)
            self.assertEqual(seeds[str(tid)]["league"], "AL")
        for seed, tid in NL.items():
            self.assertEqual(seeds[str(tid)]["seed"], seed)
            self.assertEqual(seeds[str(tid)]["league"], "NL")
        self.assertNotIn("9103", seeds)  # equipo que no clasifica
        self.assertEqual(len(seeds), 12)

    def test_sin_standings(self):
        self.assertEqual(compute_seeds(None), {})
        self.assertEqual(compute_seeds({}), {})


class BracketTest(unittest.TestCase):
    def test_sin_juegos_es_inactivo(self):
        p = build_bracket({"dates": []}, make_standings(), season=2026)
        self.assertFalse(p["postseason_active"])
        self.assertEqual(p["al"], [])
        self.assertIsNone(p["world_series"])

    def test_estructura_completa_y_proyeccion(self):
        # Solo se han programado los Wild Card; el resto debe proyectarse.
        g = [
            game("F", AL[3], AL[6], 1, "Scheduled"),
            game("F", AL[4], AL[5], 1, "Scheduled"),
            game("F", NL[3], NL[6], 1, "Scheduled"),
            game("F", NL[4], NL[5], 1, "Scheduled"),
        ]
        p = build_bracket(schedule(*g), make_standings(), season=2026)
        self.assertTrue(p["postseason_active"])
        self.assertTrue(p["seeds_available"])
        for side in ("al", "nl"):
            self.assertEqual([s["slot"] for s in p[side]], ["WC_A", "WC_B", "DS_A", "DS_B", "CS"])
        wc_a = find(p, "al", "WC_A")
        self.assertEqual(team_ids(wc_a), ["145", "117"])  # #6 CWS arriba, #3 HOU abajo (como la imagen)
        self.assertEqual([t["seed"] for t in wc_a["teams"]], [6, 3])
        self.assertEqual(find(p, "al", "WC_B")["teams"][0]["seed"], 5)
        self.assertEqual(wc_a["status"], "scheduled")
        self.assertEqual(wc_a["best_of"], 3)
        ds_a, ds_b = find(p, "al", "DS_A"), find(p, "al", "DS_B")
        self.assertEqual(team_ids(ds_a), [None, "114"])  # CLE #2 espera al ganador de 3/6
        self.assertEqual(team_ids(ds_b), [None, "139"])  # TB #1 espera al ganador de 4/5
        self.assertEqual(ds_a["status"], "pending")
        self.assertEqual(ds_a["best_of"], 5)
        self.assertEqual(find(p, "nl", "DS_A")["teams"][1]["abbreviation"], "LAD")
        self.assertEqual(find(p, "nl", "DS_B")["teams"][1]["abbreviation"], "MIL")
        ws = p["world_series"]
        self.assertEqual(ws["status"], "pending")
        self.assertEqual(team_ids(ws), [None, None])

    def test_ganador_avanza_y_conteo_de_victorias(self):
        g = [
            # AL WC_A: HOU barre a CWS 2-0 (jugador local alterna)
            game("F", AL[3], AL[6], 1, "Final", 5, 2),
            game("F", AL[3], AL[6], 2, "Final", 3, 1),
            game("F", AL[3], AL[6], 3, "Scheduled"),  # juego "si es necesario": debe ocultarse
            # AL WC_B: 1-1, el 3.º en vivo
            game("F", AL[4], AL[5], 1, "Final", 2, 4),
            game("F", AL[4], AL[5], 2, "Final", 6, 3),
            game("F", AL[4], AL[5], 3, "In Progress", 1, 0),
            # NL WC_A: PHI gana 2-1
            game("F", NL[3], NL[6], 1, "Final", 1, 2),
            game("F", NL[3], NL[6], 2, "Final", 4, 0),
            game("F", NL[3], NL[6], 3, "Final", 2, 5),
            # AL DS_A: HOU (ganador WC) vs CLE ya programado
            game("D", AL[2], AL[3], 1, "Final", 3, 4),
        ]
        p = build_bracket(schedule(*g), make_standings(), season=2026)

        wc_a = find(p, "al", "WC_A")
        self.assertEqual(wc_a["status"], "final")
        self.assertEqual(wc_a["winner_id"], "117")
        self.assertEqual({t["id"]: t["wins"] for t in wc_a["teams"]}, {"145": 0, "117": 2})
        self.assertTrue(wc_a["teams"][1]["is_winner"])
        self.assertTrue(wc_a["teams"][0]["eliminated"])
        self.assertEqual(len(wc_a["games"]), 2, "el juego 3 no jugado debe ocultarse")

        wc_b = find(p, "al", "WC_B")
        self.assertEqual(wc_b["status"], "live")
        self.assertEqual({t["id"]: t["wins"] for t in wc_b["teams"]}, {"111": 1, "147": 1})
        self.assertIsNone(wc_b["winner_id"])

        ds_a = find(p, "al", "DS_A")
        self.assertEqual(team_ids(ds_a), ["117", "114"])  # HOU avanzó a la posición de arriba
        self.assertEqual(ds_a["status"], "in_progress")
        self.assertEqual({t["id"]: t["wins"] for t in ds_a["teams"]}, {"117": 1, "114": 0})

        ds_b = find(p, "al", "DS_B")
        self.assertEqual(team_ids(ds_b), [None, "139"])  # WC_B sin decidir

        nl_wc_a = find(p, "nl", "WC_A")
        self.assertEqual(nl_wc_a["winner_id"], "143")
        self.assertEqual(team_ids(find(p, "nl", "DS_A")), ["143", "119"])
        self.assertTrue(has_live_game(p))

    def test_postemporada_completa_con_campeon(self):
        def sweep(rt, winner, loser, n, winner_home=True):
            out = []
            for i in range(1, n + 1):
                h, a = (winner, loser) if winner_home else (loser, winner)
                hs, aws = (4, 1) if winner_home else (1, 4)
                out.append(game(rt, h, a, i, "Final", hs, aws))
            return out

        g = []
        # AL: HOU, NYY avanzan; DS: HOU(en 3), TB(en 3); CS: TB
        g += sweep("F", AL[3], AL[6], 2) + sweep("F", AL[4], AL[5], 2)
        g += sweep("D", AL[3], AL[2], 3) + sweep("D", AL[1], AL[4], 3)
        g += sweep("L", AL[1], AL[3], 4)
        # NL: LAD, MIL llegan
        g += sweep("F", NL[3], NL[6], 2) + sweep("F", NL[5], NL[4], 2)
        g += sweep("D", NL[2], NL[3], 3) + sweep("D", NL[1], NL[5], 3)
        g += sweep("L", NL[2], NL[1], 4)
        # WS: LAD gana 4-1 a TB
        g += sweep("W", NL[2], AL[1], 4)
        g.append(game("W", AL[1], NL[2], 5, "Final", 3, 2))  # TB gana el 5.º -> LAD 4-1 final
        # (añadir un juego más de TB no cambia: LAD ya tenía 4)
        p = build_bracket(schedule(*g), make_standings(), season=2026)

        ws = p["world_series"]
        self.assertEqual(ws["status"], "final")
        self.assertEqual(ws["winner_id"], "119")
        self.assertEqual(team_ids(ws), ["139", "119"])  # AL a la izquierda, NL a la derecha
        self.assertEqual(p["champion"]["abbreviation"], "LAD")
        self.assertEqual(team_ids(find(p, "al", "CS")), ["117", "139"])  # ganador DS_A arriba, DS_B abajo
        self.assertEqual(find(p, "al", "CS")["winner_id"], "139")
        self.assertEqual(find(p, "nl", "CS")["winner_id"], "119")
        self.assertFalse(has_live_game(p))

    def test_sin_standings_degrada_sin_romperse(self):
        g = [
            game("F", AL[3], AL[6], 1, "Final", 3, 1),
            game("F", NL[3], NL[6], 1, "Final", 3, 1),
        ]
        p = build_bracket(schedule(*g), None, season=2026)
        self.assertTrue(p["postseason_active"])
        self.assertFalse(p["seeds_available"])
        # Las ligas se detectan por el objeto team hidratado del schedule.
        self.assertEqual(len(p["al"]), 5)
        self.assertEqual(len(p["nl"]), 5)
        wc_a = find(p, "al", "WC_A")
        self.assertEqual(sorted(team_ids(wc_a)), ["117", "145"])
        self.assertTrue(all(t["logo_url"].startswith("https://www.mlbstatic.com/team-logos/") for t in wc_a["teams"]))

    def test_juego_con_equipos_por_definir_se_ignora(self):
        bad = game("D", AL[2], AL[3], 1, "Scheduled")
        bad["teams"]["away"]["team"] = {}
        p = build_bracket(schedule(bad), make_standings(), season=2026)
        self.assertFalse(p["postseason_active"])

    def test_logo_de_bd_tiene_prioridad(self):
        g = [game("F", AL[3], AL[6], 1, "Scheduled")]
        p = build_bracket(schedule(*g), make_standings(), {"117": "https://cdn.example/hou.svg"}, season=2026)
        wc_a = find(p, "al", "WC_A")
        logos = {t["id"]: t["logo_url"] for t in wc_a["teams"]}
        self.assertEqual(logos["117"], "https://cdn.example/hou.svg")
        self.assertEqual(logos["145"], "https://www.mlbstatic.com/team-logos/145.svg")


if __name__ == "__main__":
    unittest.main()
