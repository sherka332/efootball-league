from .database import Base, engine, SessionLocal
from .services import seed_teams, ensure_active_season
Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    seed_teams(db)
    ensure_active_season(db)
finally:
    db.close()
