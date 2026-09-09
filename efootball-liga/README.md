# eFootball Liga — Telegram Mini App v2

To'liq ishlaydigan bitta Render Web Service:
- 20 ta jamoa
- 20 ta o'yinchi, har jamoaga faqat 1 o'yinchi
- Telegram Mini App orqali avtomatik Telegram ID
- Telegram initData serverda HMAC bilan tekshiriladi
- 19 tur, jami 190 ta o'yin
- Natija kiritish/tahrirlash
- Avtomatik ochko, GF, GA, GD, o'rin
- 1/2/3-o'rin
- Admin panel
- Ban/unban
- Jamoani boshqarish
- Mavsum yaratish/faollashtirish/tugatish/reset
- PostgreSQL
- Render uchun tayyor

## Render
Root Directory: `efootball-liga`
Build: `pip install -r requirements.txt`
Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Environment:
DATABASE_URL = PostgreSQL Internal/External URL
SECRET_KEY = uzun random string
TELEGRAM_BOT_TOKEN = @BotFather bergan token
TELEGRAM_ADMIN_ID = sizning Telegram numeric ID

Mini App URL:
https://SIZNING-RENDER-DOMENINGIZ.onrender.com/

Muhim: bot tokenni kodga yozmang.

## Yangi jadval qoidasi
- Har kuni 2 ta tur: masalan 1-tur va 2-tur birinchi kun, 3-tur va 4-tur ikkinchi kun.
- Har kun uchun deadline: 23:30 (Asia/Tashkent).
- Oddiy ishtirokchi deadline'dan keyin natija kirita/o'zgartira olmaydi.
- Admin deadline'dan keyin ham tuzatishi mumkin.

## Mini App chat
- `Chat` bo'limida ishtirokchilar bir-biriga Mini App ichida shaxsiy xabar yuboradi.
- Telegram profiliga o'tish shart emas.
- Xabarlar PostgreSQL'da saqlanadi.
- O'qilganlik holati mavjud.
- Admin xabarni moderatsiya uchun o'chira oladi.
