from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, hashlib, json, os
from datetime import date, timedelta
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Anthropic SDK for the AI chatbot — pip install anthropic
import anthropic

app = FastAPI(title="Spice Garden")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB_USER = "restaurant_users.db"
DB_BOOKING = "restaurant_bookings.db"

# ─── DB INIT ────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_USER)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            login_id   TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            password   TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit(); conn.close()

    conn = sqlite3.connect(DB_BOOKING)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_login   TEXT NOT NULL,
            booking_name TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            menu         TEXT,
            table_for    INTEGER NOT NULL,
            user_reviews TEXT,
            total_amount REAL DEFAULT 0,
            created_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit(); conn.close()

init_db()

# ─── HELPERS ────────────────────────────────────────────────────────────────

def hash_password(pw: str) -> str:
    salt = "restaurant_secret_2026"
    return hashlib.sha256((pw + salt).encode()).hexdigest()

def get_user(login_id: str):
    conn = sqlite3.connect(DB_USER)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE login_id=?", (login_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_session_user(request: Request):
    return request.cookies.get("session_user")

def get_session_name(request: Request):
    return request.cookies.get("session_name")

def get_user_bookings(login_id: str):
    conn = sqlite3.connect(DB_BOOKING)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM bookings WHERE user_login=? ORDER BY created_at DESC",
        (login_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_booking_by_id(booking_id: int):
    conn = sqlite3.connect(DB_BOOKING)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM bookings WHERE booking_id=?", (booking_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_reviews():
    conn = sqlite3.connect(DB_BOOKING)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT booking_name, user_reviews, created_at, user_login FROM bookings "
        "WHERE user_reviews IS NOT NULL AND user_reviews != '' "
        "ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

MENU = {
    "Starters": {
        "Veg Samosa": 80, "Paneer Tikka": 280, "Aloo Tikki": 120,
        "Onion Bhaji": 150, "Soya Chhap": 320
    },
    "Main Course": {
        "Butter Paneer Masala": 420, "Paneer Kadai": 400,
        "Dal Makhani": 360, "Chole Masala": 300, "Malai Kofta": 480
    },
    "Breads": {
        "Plain Naan": 40, "Butter Naan": 55, "Garlic Naan": 70,
        "Tandoori Roti": 35, "Lachha Paratha": 80
    },
    "Desserts": {
        "Gulab Jamun": 120, "Rasmalai": 150, "Kheer": 110, "Kulfi": 130
    },
    "Drinks": {
        "Masala Chai": 40, "Mango Lassi": 120, "Sweet Lassi": 100,
        "Fresh Lime Soda": 90, "Soft Drinks": 60
    }
}

TIME_SLOTS = [
    "11:00 AM","11:30 AM","12:00 PM","12:30 PM","1:00 PM","1:30 PM",
    "2:00 PM","2:30 PM","3:00 PM","3:30 PM","4:00 PM","4:30 PM",
    "5:00 PM","5:30 PM","6:00 PM","6:30 PM","7:00 PM","7:30 PM",
    "8:00 PM","8:30 PM","9:00 PM","9:30 PM","10:00 PM","10:30 PM","11:00 PM"
]

# ─── ROUTES ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = get_session_user(request)
    name = get_session_name(request)
    reviews = get_all_reviews()
    return templates.TemplateResponse("index.html", {
        "request": request, "user": user, "name": name,
        "reviews": reviews, "menu": MENU
    })

@app.post("/register")
async def register(
    login_id: str = Form(...),
    customer_name: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    if password != confirm_password:
        return JSONResponse({"success": False, "error": "Passwords do not match"})
    if len(password) < 6:
        return JSONResponse({"success": False, "error": "Password must be at least 6 characters"})
    if get_user(login_id):
        return JSONResponse({"success": False, "error": "User already registered with this email/phone"})
    try:
        conn = sqlite3.connect(DB_USER)
        conn.execute(
            "INSERT INTO users (login_id, customer_name, password) VALUES (?,?,?)",
            (login_id.strip(), customer_name.strip(), hash_password(password))
        )
        conn.commit(); conn.close()
        response = JSONResponse({"success": True, "redirect": "/booking"})
        response.set_cookie("session_user", login_id.strip(), httponly=True, max_age=86400)
        response.set_cookie("session_name", customer_name.strip(), httponly=True, max_age=86400)
        return response
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/login")
async def login(login_id: str = Form(...), password: str = Form(...)):
    user = get_user(login_id.strip())
    if not user:
        return JSONResponse({"success": False, "error": "User not found. Please register first."})
    if user["password"] != hash_password(password):
        return JSONResponse({"success": False, "error": "Incorrect password. Please try again."})
    response = JSONResponse({"success": True, "redirect": "/booking"})
    response.set_cookie("session_user", login_id.strip(), httponly=True, max_age=86400)
    response.set_cookie("session_name", user["customer_name"], httponly=True, max_age=86400)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("session_user")
    response.delete_cookie("session_name")
    return response

@app.get("/booking", response_class=HTMLResponse)
async def booking_page(request: Request):
    user = get_session_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    name = get_session_name(request)
    past_bookings = get_user_bookings(user)
    today = date.today()
    max_date = today + timedelta(days=30)
    return templates.TemplateResponse("booking.html", {
        "request": request, "user": user, "name": name,
        "past_bookings": past_bookings,
        "menu": MENU, "time_slots": TIME_SLOTS,
        "min_date": today.isoformat(),
        "max_date": max_date.isoformat()
    })

@app.post("/booking/submit")
async def submit_booking(
    request: Request,
    booking_name: str = Form(...),
    table_for: int = Form(...),
    booking_date: str = Form(...),
    booking_time: str = Form(...),
    menu_json: str = Form("{}"),
    total_amount: float = Form(0)
):
    user = get_session_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not logged in"})
    try:
        conn = sqlite3.connect(DB_BOOKING)
        cursor = conn.execute(
            "INSERT INTO bookings (user_login, booking_name, booking_time, booking_date, menu, table_for, total_amount) VALUES (?,?,?,?,?,?,?)",
            (user, booking_name, booking_time, booking_date, menu_json, table_for, total_amount)
        )
        booking_id = cursor.lastrowid
        conn.commit(); conn.close()
        return JSONResponse({"success": True, "redirect": f"/summary/{booking_id}"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/booking/modify/{booking_id}", response_class=HTMLResponse)
async def modify_booking_page(request: Request, booking_id: int):
    user = get_session_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    name = get_session_name(request)
    booking = get_booking_by_id(booking_id)
    if not booking or booking["user_login"] != user:
        return RedirectResponse("/booking", status_code=302)
    past_bookings = get_user_bookings(user)
    today = date.today()
    max_date = today + timedelta(days=30)
    menu_data = json.loads(booking["menu"]) if booking["menu"] else {}
    return templates.TemplateResponse("booking.html", {
        "request": request, "user": user, "name": name,
        "past_bookings": past_bookings,
        "menu": MENU, "time_slots": TIME_SLOTS,
        "min_date": today.isoformat(),
        "max_date": max_date.isoformat(),
        "edit_booking": booking,
        "edit_menu": menu_data
    })

@app.post("/booking/modify/{booking_id}")
async def modify_booking_submit(
    request: Request,
    booking_id: int,
    booking_name: str = Form(...),
    table_for: int = Form(...),
    booking_date: str = Form(...),
    booking_time: str = Form(...),
    menu_json: str = Form("{}"),
    total_amount: float = Form(0)
):
    user = get_session_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not logged in"})
    booking = get_booking_by_id(booking_id)
    if not booking or booking["user_login"] != user:
        return JSONResponse({"success": False, "error": "Not allowed"})
    try:
        conn = sqlite3.connect(DB_BOOKING)
        conn.execute(
            "UPDATE bookings SET booking_name=?, table_for=?, booking_date=?, booking_time=?, menu=?, total_amount=? WHERE booking_id=?",
            (booking_name, table_for, booking_date, booking_time, menu_json, total_amount, booking_id)
        )
        conn.commit(); conn.close()
        return JSONResponse({"success": True, "redirect": f"/summary/{booking_id}"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/booking/cancel/{booking_id}")
async def cancel_booking(request: Request, booking_id: int):
    user = get_session_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not logged in"})
    booking = get_booking_by_id(booking_id)
    if not booking or booking["user_login"] != user:
        return JSONResponse({"success": False, "error": "Not allowed"})
    try:
        conn = sqlite3.connect(DB_BOOKING)
        conn.execute("DELETE FROM bookings WHERE booking_id=?", (booking_id,))
        conn.commit(); conn.close()
        return JSONResponse({"success": True, "message": "Booking cancelled"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/summary/{booking_id}", response_class=HTMLResponse)
async def summary_page(request: Request, booking_id: int):
    user = get_session_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    name = get_session_name(request)
    booking = get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(404, "Booking not found")
    menu_data = json.loads(booking["menu"]) if booking["menu"] else {}
    return templates.TemplateResponse("summary.html", {
        "request": request, "user": user, "name": name,
        "booking": booking, "menu_data": menu_data, "menu_prices": MENU
    })

@app.post("/booking/confirm/{booking_id}")
async def confirm_booking(request: Request, booking_id: int):
    user = get_session_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not logged in"})
    booking = get_booking_by_id(booking_id)
    if not booking:
        return JSONResponse({"success": False, "error": "Booking not found"})
    try:
        send_confirmation_email(user, booking)
    except Exception:
        pass
    return JSONResponse({"success": True, "redirect": f"/confirmation/{booking_id}"})

@app.get("/confirmation/{booking_id}", response_class=HTMLResponse)
async def confirmation_page(request: Request, booking_id: int):
    user = get_session_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    name = get_session_name(request)
    booking = get_booking_by_id(booking_id)
    menu_data = json.loads(booking["menu"]) if booking["menu"] else {}
    return templates.TemplateResponse("confirmation.html", {
        "request": request, "user": user, "name": name,
        "booking": booking, "menu_data": menu_data
    })

@app.post("/add-review")
async def add_review(
    request: Request,
    review_text: str = Form(...),
    booking_id: Optional[int] = Form(None)
):
    user = get_session_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Not logged in"})
    name = get_session_name(request)
    conn = sqlite3.connect(DB_BOOKING)
    if booking_id:
        conn.execute("UPDATE bookings SET user_reviews=? WHERE booking_id=? AND user_login=?",
                     (review_text, booking_id, user))
    else:
        conn.execute(
            "INSERT INTO bookings (user_login, booking_name, booking_time, booking_date, table_for, user_reviews) VALUES (?,?,?,?,?,?)",
            (user, name, "N/A", date.today().isoformat(), 1, review_text)
        )
    conn.commit(); conn.close()
    return JSONResponse({"success": True})

def send_confirmation_email(to_email: str, booking: dict):
    if "@" not in to_email:
        return
    menu_data = json.loads(booking["menu"]) if booking["menu"] else {}
    menu_str = ", ".join([f"{item} x{qty}" for item, qty in menu_data.items()])
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🍛 Booking Confirmed - Spice Garden"
    msg["From"] = "noreply@spicegarden.com"
    msg["To"] = to_email
    body = f"""
Dear {booking['booking_name']},

Your table has been successfully booked!

📅 Date: {booking['booking_date']}
⏰ Time: {booking['booking_time']}
👥 Guests: {booking['table_for']}
🍽️ Menu: {menu_str or 'Not selected'}
💰 Total: ₹{booking['total_amount']:.0f}

We look forward to serving you!

Warm regards,
Spice Garden Team
"""
    msg.attach(MIMEText(body, "plain"))
    # Configure SMTP here for real sending:
    # with smtplib.SMTP("smtp.gmail.com", 587) as s:
    #     s.starttls(); s.login("your@email.com", "app_password")
    #     s.sendmail(msg["From"], to_email, msg.as_string())


# ══════════════════════════════════════════════════════════════════════════
# AI CHATBOT — powered by the Claude API (Anthropic)
# ══════════════════════════════════════════════════════════════════════════

# The client automatically reads the ANTHROPIC_API_KEY environment variable.
# Set it before starting the server, e.g.:
#   Windows (PowerShell):  $env:ANTHROPIC_API_KEY="sk-ant-..."
#   macOS/Linux:            export ANTHROPIC_API_KEY="sk-ant-..."
try:
    claude_client = anthropic.Anthropic()
except Exception:
    claude_client = None

CHAT_MODEL = "claude-haiku-4-5-20251001"   # fast + low-cost, ideal for a restaurant FAQ assistant
CHAT_MAX_TOKENS = 400
CHAT_HISTORY_LIMIT = 10   # how many past turns to send back for context (keeps cost low)

def build_system_prompt() -> str:
    """Builds the chatbot's instructions, including the live menu, so it always
    has accurate, up-to-date information about Spice Garden."""
    menu_lines = []
    for category, items in MENU.items():
        dish_list = ", ".join(f"{dish} (₹{price})" for dish, price in items.items())
        menu_lines.append(f"{category}: {dish_list}")
    menu_text = "\n".join(menu_lines)

    return f"""You are "Spice Bot", the friendly virtual assistant for Spice Garden, an Indian restaurant.

RESTAURANT INFO:
- Cuisine: Authentic Indian cuisine
- Opening hours: 11:00 AM to 11:00 PM, every day
- Table bookings: available for the next 30 days, in 30-minute time slots
- Guests per booking: 1 to 12 people
- Bookings require a free account (register with email or phone number)

FULL MENU (prices in Indian Rupees ₹):
{menu_text}

YOUR JOB:
- Answer questions about the menu, prices, ingredients, spice levels, and dietary suitability (most dishes are vegetarian unless named otherwise; mention if something likely contains dairy or gluten, but recommend the guest confirm allergies with staff).
- Recommend dishes based on what the guest is in the mood for (e.g., spicy, mild, vegetarian, sweet, drinks).
- Explain how to book a table: register/login → go to the Booking page → pick date, time, guest count → optionally pre-order dishes → review summary → confirm.
- Explain how to modify or cancel an existing booking (via the booking page sidebar, Edit/Cancel buttons).
- Be warm, concise, and conversational — like a friendly host, not a generic chatbot. Use at most 2–3 short paragraphs.
- If asked something unrelated to the restaurant, politely redirect the conversation back to Spice Garden.
- You cannot directly create or modify bookings yourself — always guide the guest to use the website's Booking page for that.
- Never invent menu items or prices that are not listed above."""


@app.post("/chat")
async def chat(request: Request):
    if claude_client is None:
        return JSONResponse({
            "success": False,
            "reply": "Sorry, the chat assistant isn't configured yet. Please set the ANTHROPIC_API_KEY environment variable and restart the server."
        })

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"success": False, "reply": "Invalid request."})

    user_message = (payload.get("message") or "").strip()
    history = payload.get("history") or []   # [{role: "user"|"assistant", content: "..."}]

    if not user_message:
        return JSONResponse({"success": False, "reply": "Please type a message."})

    # Keep only the most recent turns to control token usage
    trimmed_history = history[-CHAT_HISTORY_LIMIT:]

    messages = [{"role": m["role"], "content": m["content"]} for m in trimmed_history
                if m.get("role") in ("user", "assistant") and m.get("content")]
    messages.append({"role": "user", "content": user_message})

    try:
        response = claude_client.messages.create(
            model=CHAT_MODEL,
            max_tokens=CHAT_MAX_TOKENS,
            system=build_system_prompt(),
            messages=messages
        )
        reply_text = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        if not reply_text:
            reply_text = "I'm not sure how to answer that — could you rephrase?"
        return JSONResponse({"success": True, "reply": reply_text})

    except Exception as e:
        return JSONResponse({
            "success": False,
            "reply": "Sorry, I'm having trouble connecting right now. Please try again in a moment, or browse the Menu and Booking pages directly."
        })
