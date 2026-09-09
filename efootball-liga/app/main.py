import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, delete, or_, inspect, text
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import User, Team, Season, Match, Message
from .schemas import TelegramAuth, ResultIn, TeamJoin, SeasonCreate, BanIn, MessageIn
from .auth import telegram_user_from_init_data, make_token, current_user, admin_required
from .services import seed_teams, ensure_active_season, generate_fixtures, standings, public_match
from datetime import datetime
from zoneinfo import ZoneInfo
from .config import settings

Base.metadata.create_all(bind=engine)
migrate_schema()

app = FastAPI(title="eFootball Liga API")

def migrate_schema():
    insp = inspect(engine)
    tables = insp.get_table_names()
    with engine.begin() as conn:
        if "seasons" in tables:
            cols = {c["name"] for c in inspect(engine).get_columns("seasons")}
            if "start_date" not in cols:
                if str(engine.url).startswith("sqlite"):
                    conn.execute(text("ALTER TABLE seasons ADD COLUMN start_date DATE"))
                else:
                    conn.execute(text("ALTER TABLE seasons ADD COLUMN start_date DATE"))
                conn.execute(text("UPDATE seasons SET start_date = CURRENT_DATE WHERE start_date IS NULL"))
        if "matches" in tables:
            cols = {c["name"] for c in inspect(engine).get_columns("matches")}
            if "scheduled_date" not in cols:
                conn.execute(text("ALTER TABLE matches ADD COLUMN scheduled_date DATE"))
                conn.execute(text("UPDATE matches SET scheduled_date = CURRENT_DATE WHERE scheduled_date IS NULL"))
            if "deadline_at" not in cols:
                conn.execute(text("ALTER TABLE matches ADD COLUMN deadline_at TIMESTAMP"))
                if str(engine.url).startswith("sqlite"):
                    conn.execute(text("UPDATE matches SET deadline_at = datetime(scheduled_date || ' 23:30:00') WHERE deadline_at IS NULL"))
                else:
                    conn.execute(text("UPDATE matches SET deadline_at = (scheduled_date::timestamp + interval '23 hours 30 minutes') WHERE deadline_at IS NULL"))

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
def startup():
    from .database import SessionLocal
    db = SessionLocal()
    try:
        seed_teams(db)
        ensure_active_season(db)
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def index():
    with open("app/static/index.html", encoding="utf-8") as f:
        return f.read()

@app.get("/api/health")
def health():
    return {"ok": True, "service": "efootball-liga"}

@app.post("/api/auth/telegram")
def telegram_auth(body: TelegramAuth, db: Session = Depends(get_db)):
    tg = telegram_user_from_init_data(body.init_data)
    tid = str(tg["id"])
    user = db.scalar(select(User).where(User.telegram_id == tid))
    if not user:
        user = User(telegram_id=tid)
        db.add(user)
    user.username = tg.get("username")
    user.first_name = tg.get("first_name")
    user.last_name = tg.get("last_name")
    if settings.telegram_admin_id and tid == str(settings.telegram_admin_id):
        user.role = "ADMIN"
    db.commit(); db.refresh(user)
    return {"token": make_token(user), "user": {"id":user.id,"telegram_id":user.telegram_id,
            "username":user.username,"first_name":user.first_name,"role":user.role,"banned":user.banned}}

@app.get("/api/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    team = db.scalar(select(Team).where(Team.player_id == user.id))
    return {"id":user.id,"telegram_id":user.telegram_id,"username":user.username,
            "first_name":user.first_name,"role":user.role,"banned":user.banned,
            "team": {"id":team.id,"name":team.name,"short":team.short_name} if team else None}

@app.get("/api/teams")
def teams(db: Session = Depends(get_db)):
    data=[]
    for t in db.scalars(select(Team).order_by(Team.id)):
        p=t.player
        data.append({"id":t.id,"name":t.name,"short":t.short_name,
                     "player": (p.username or p.first_name or "Nomsiz") if p else None})
    return data

@app.post("/api/join")
def join(body: TeamJoin, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "ADMIN" and user.banned:
        raise HTTPException(403,"Bloklangan")
    if db.scalar(select(Team).where(Team.player_id == user.id)):
        raise HTTPException(400,"Siz allaqachon jamoa tanlagansiz")
    team=db.get(Team, body.team_id)
    if not team: raise HTTPException(404,"Jamoa topilmadi")
    if team.player_id: raise HTTPException(409,"Bu jamoa band")
    team.player_id=user.id
    db.commit()
    return {"ok":True,"team":{"id":team.id,"name":team.name}}

@app.get("/api/seasons")
def seasons(db: Session = Depends(get_db)):
    return [{"id":s.id,"name":s.name,"active":s.active} for s in db.scalars(select(Season).order_by(Season.id.desc()))]

@app.get("/api/standings")
def get_standings(season_id: int|None = None, db: Session = Depends(get_db)):
    season = db.get(Season, season_id) if season_id else ensure_active_season(db)
    if not season: raise HTTPException(404,"Mavsum topilmadi")
    return {"season":{"id":season.id,"name":season.name,"active":season.active},"standings":standings(db,season.id)}

@app.get("/api/matches")
def matches(season_id: int|None=None, round_no: int|None=None, db: Session=Depends(get_db)):
    season=db.get(Season,season_id) if season_id else ensure_active_season(db)
    q=select(Match).where(Match.season_id==season.id).order_by(Match.round_no,Match.id)
    if round_no: q=q.where(Match.round_no==round_no)
    return [public_match(db,m) for m in db.scalars(q)]

@app.post("/api/matches/{match_id}/result")
def result(match_id:int, body:ResultIn, user:User=Depends(current_user), db:Session=Depends(get_db)):
    m=db.get(Match,match_id)
    if not m: raise HTTPException(404,"O'yin topilmadi")
    h=db.get(Team,m.home_team_id); a=db.get(Team,m.away_team_id)
    allowed = user.role=="ADMIN" or user.id in [h.player_id,a.player_id]
    if not allowed: raise HTTPException(403,"Faqat o'yin ishtirokchilari yoki admin natija kiritadi")
    if user.banned: raise HTTPException(403,"Bloklangansiz")
    if user.role != "ADMIN" and datetime.utcnow() > m.deadline_at:
        raise HTTPException(403,"Bu tur uchun deadline 23:30 da tugagan")
    m.home_goals=body.home_goals; m.away_goals=body.away_goals; m.note=body.note; m.played=True
    db.commit()
    return public_match(db,m)


@app.get("/api/chat/users")
def chat_users(user: User = Depends(current_user), db: Session = Depends(get_db)):
    users = list(db.scalars(select(User).where(User.id != user.id, User.banned == False).order_by(User.username, User.first_name)))
    return [{"id":u.id,"username":u.username,"first_name":u.first_name} for u in users]

@app.get("/api/chat/{other_id}")
def chat_history(other_id:int, user:User=Depends(current_user), db:Session=Depends(get_db)):
    other=db.get(User,other_id)
    if not other: raise HTTPException(404,"Foydalanuvchi topilmadi")
    msgs=list(db.scalars(select(Message).where(
        or_((Message.sender_id==user.id)&(Message.receiver_id==other_id),
            (Message.sender_id==other_id)&(Message.receiver_id==user.id))
    ).order_by(Message.created_at, Message.id)))
    now=datetime.utcnow()
    for m in msgs:
        if m.receiver_id==user.id and not m.read_at:
            m.read_at=now
    db.commit()
    return [{"id":m.id,"sender_id":m.sender_id,"receiver_id":m.receiver_id,"text":m.text,
             "created_at":m.created_at.isoformat()} for m in msgs if not m.deleted]

@app.post("/api/chat/send")
def chat_send(body:MessageIn, user:User=Depends(current_user), db:Session=Depends(get_db)):
    if user.banned: raise HTTPException(403,"Bloklangansiz")
    receiver=db.get(User,body.receiver_id)
    if not receiver or receiver.id==user.id: raise HTTPException(404,"Qabul qiluvchi topilmadi")
    if receiver.banned: raise HTTPException(403,"Bu foydalanuvchi bloklangan")
    m=Message(sender_id=user.id, receiver_id=receiver.id, text=body.text.strip())
    db.add(m); db.commit(); db.refresh(m)
    return {"ok":True,"id":m.id}

@app.get("/api/chat/unread/count")
def unread_count(user:User=Depends(current_user), db:Session=Depends(get_db)):
    return {"count":len(list(db.scalars(select(Message).where(Message.receiver_id==user.id, Message.read_at==None, Message.deleted==False))))}

@app.delete("/api/admin/chat/{message_id}")
def admin_delete_message(message_id:int, _:User=Depends(admin_required), db:Session=Depends(get_db)):
    m=db.get(Message,message_id)
    if not m: raise HTTPException(404,"Xabar topilmadi")
    m.deleted=True; db.commit()
    return {"ok":True}

@app.get("/api/admin/users")
def admin_users(_:User=Depends(admin_required), db:Session=Depends(get_db)):
    return [{"id":u.id,"telegram_id":u.telegram_id,"username":u.username,"first_name":u.first_name,
             "role":u.role,"banned":u.banned} for u in db.scalars(select(User).order_by(User.id.desc()))]

@app.post("/api/admin/users/{uid}/ban")
def ban_user(uid:int, body:BanIn, _:User=Depends(admin_required), db:Session=Depends(get_db)):
    u=db.get(User,uid)
    if not u: raise HTTPException(404,"User topilmadi")
    if u.role=="ADMIN" and body.banned: raise HTTPException(400,"Admin bloklanmaydi")
    u.banned=body.banned
    db.commit()
    return {"ok":True}

@app.post("/api/admin/season")
def create_season(body:SeasonCreate, _:User=Depends(admin_required), db:Session=Depends(get_db)):
    if db.scalar(select(Season).where(Season.name==body.name)): raise HTTPException(409,"Bu nom bor")
    for s in db.scalars(select(Season)): s.active=False
    s=Season(name=body.name,active=True); db.add(s); db.commit(); db.refresh(s)
    generate_fixtures(db,s)
    return {"id":s.id,"name":s.name,"active":s.active}

@app.post("/api/admin/season/{sid}/activate")
def activate_season(sid:int, _:User=Depends(admin_required), db:Session=Depends(get_db)):
    s=db.get(Season,sid)
    if not s: raise HTTPException(404,"Mavsum topilmadi")
    for x in db.scalars(select(Season)): x.active=False
    s.active=True; db.commit()
    return {"ok":True}

@app.delete("/api/admin/season/{sid}")
def delete_season(sid:int, _:User=Depends(admin_required), db:Session=Depends(get_db)):
    s=db.get(Season,sid)
    if not s: raise HTTPException(404,"Mavsum topilmadi")
    if s.active: raise HTTPException(400,"Faol mavsumni o'chirib bo'lmaydi")
    db.delete(s); db.commit()
    return {"ok":True}

@app.post("/api/admin/reset-season/{sid}")
def reset_season(sid:int, _:User=Depends(admin_required), db:Session=Depends(get_db)):
    s=db.get(Season,sid)
    if not s: raise HTTPException(404,"Mavsum topilmadi")
    for m in db.scalars(select(Match).where(Match.season_id==sid)):
        m.home_goals=None; m.away_goals=None; m.played=False; m.note=None
    db.commit()
    return {"ok":True}

@app.get("/api/admin/summary")
def admin_summary(_:User=Depends(admin_required), db:Session=Depends(get_db)):
    s=ensure_active_season(db)
    return {"users":len(list(db.scalars(select(User)))),"teams":len(list(db.scalars(select(Team)))),
            "matches":len(list(db.scalars(select(Match).where(Match.season_id==s.id)))),
            "played":len(list(db.scalars(select(Match).where(Match.season_id==s.id,Match.played==True))))}
