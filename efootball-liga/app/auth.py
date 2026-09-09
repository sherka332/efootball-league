import hashlib, hmac, time
from urllib.parse import parse_qsl
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User

ALGORITHM = "HS256"

def telegram_user_from_init_data(init_data: str):
    if not settings.telegram_bot_token:
        raise HTTPException(500, "TELEGRAM_BOT_TOKEN sozlanmagan")
    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))
        received = data.pop("hash", None)
        if not received:
            raise ValueError("hash yo'q")
        auth_date = int(data.get("auth_date", "0"))
        if abs(time.time() - auth_date) > 86400:
            raise ValueError("initData muddati o'tgan")
        check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
        secret = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received):
            raise ValueError("hash noto'g'ri")
        import json
        tg = json.loads(data["user"])
        return tg
    except Exception as e:
        raise HTTPException(401, f"Telegram autentifikatsiyasi xato: {e}")

def make_token(user: User):
    return jwt.encode({"sub": str(user.id), "role": user.role}, settings.secret_key, algorithm=ALGORITHM)

def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token kerak")
    try:
        payload = jwt.decode(authorization[7:], settings.secret_key, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(401, "Token noto'g'ri")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "Foydalanuvchi topilmadi")
    if user.banned:
        raise HTTPException(403, "Siz bloklangansiz")
    return user

def admin_required(user: User = Depends(current_user)):
    if user.role != "ADMIN":
        raise HTTPException(403, "Faqat admin")
    return user
