from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
from .models import Season, Team, Match

TEAM_NAMES = [
    ("Real Madrid","RMA"), ("Barcelona","BAR"), ("Manchester City","MCI"),
    ("Liverpool","LIV"), ("Arsenal","ARS"), ("Manchester United","MUN"),
    ("Chelsea","CHE"), ("Bayern Munich","BAY"), ("PSG","PSG"),
    ("Inter Milan","INT"), ("AC Milan","ACM"), ("Juventus","JUV"),
    ("Napoli","NAP"), ("Atletico Madrid","ATM"), ("Borussia Dortmund","BVB"),
    ("Bayer Leverkusen","LEV"), ("Tottenham","TOT"), ("Newcastle","NEW"),
    ("Benfica","BEN"), ("Ajax","AJA")
]

def seed_teams(db: Session):
    if db.scalar(select(Team).limit(1)):
        return
    for name, short in TEAM_NAMES:
        db.add(Team(name=name, short_name=short))
    db.commit()

def ensure_active_season(db: Session):
    season = db.scalar(select(Season).where(Season.active == True).order_by(Season.id.desc()))
    if season:
        return season
    season = Season(name="1-mavsum", active=True, start_date=__import__("datetime").date.today())
    db.add(season)
    db.commit()
    db.refresh(season)
    generate_fixtures(db, season)
    return season

def generate_fixtures(db: Session, season: Season):
    db.execute(delete(Match).where(Match.season_id == season.id))
    teams = list(db.scalars(select(Team).order_by(Team.id)))
    if len(teams) != 20:
        raise ValueError("Jamoalar soni aynan 20 bo'lishi kerak")
    ids = [t.id for t in teams]
    n = len(ids)
    # Circle method: 19 rounds x 10 matches.
    for r in range(n - 1):
        for i in range(n // 2):
            a = ids[i]
            b = ids[n - 1 - i]
            if (r + i) % 2:
                a, b = b, a
            match_date = season.start_date + timedelta(days=r // 2)
            deadline = datetime.combine(match_date, time(23, 30), tzinfo=ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
            db.add(Match(season_id=season.id, round_no=r + 1,
                         home_team_id=a, away_team_id=b,
                         scheduled_date=match_date, deadline_at=deadline))
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    db.commit()

def standings(db: Session, season_id: int):
    teams = list(db.scalars(select(Team).order_by(Team.id)))
    rows = {t.id: {"team_id": t.id, "team": t.name, "short_name": t.short_name,
                   "player": None, "played":0, "wins":0, "draws":0, "losses":0,
                   "gf":0, "ga":0, "gd":0, "points":0} for t in teams}
    for t in teams:
        if t.player:
            rows[t.id]["player"] = t.player.username or t.player.first_name or "Nomsiz"
    matches = list(db.scalars(select(Match).where(Match.season_id == season_id, Match.played == True)))
    for m in matches:
        h, a = rows[m.home_team_id], rows[m.away_team_id]
        hg, ag = m.home_goals, m.away_goals
        h["played"] += 1; a["played"] += 1
        h["gf"] += hg; h["ga"] += ag
        a["gf"] += ag; a["ga"] += hg
        if hg > ag:
            h["wins"] += 1; h["points"] += 3; a["losses"] += 1
        elif hg < ag:
            a["wins"] += 1; a["points"] += 3; h["losses"] += 1
        else:
            h["draws"] += 1; a["draws"] += 1
            h["points"] += 1; a["points"] += 1
    for x in rows.values():
        x["gd"] = x["gf"] - x["ga"]
    return sorted(rows.values(), key=lambda x: (-x["points"], -x["gd"], -x["gf"], x["team"]))

def public_match(db, m: Match):
    h, a = db.get(Team, m.home_team_id), db.get(Team, m.away_team_id)
    return {"id":m.id,"round":m.round_no,"home":{"id":h.id,"name":h.name,"short":h.short_name},
            "away":{"id":a.id,"name":a.name,"short":a.short_name},
            "home_goals":m.home_goals,"away_goals":m.away_goals,"played":m.played,"note":m.note,"scheduled_date":str(m.scheduled_date),"deadline_at":m.deadline_at.isoformat()}
