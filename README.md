# 🪔 Spice Garden – Indian Restaurant Web App

A full-stack restaurant booking application built with FastAPI, SQLite, modern HTML/CSS, and an AI chatbot powered by the Claude API.

---

## 📁 Project Structure

```
restaurant/
├── main.py                  # FastAPI app – all routes, logic, and /chat endpoint
├── requirements.txt
├── restaurant_users.db      # Auto-created on first run
├── restaurant_bookings.db   # Auto-created on first run
├── templates/
│   ├── base.html            # Shared layout, background, fonts, chat widget
│   ├── index.html           # Page 1 – Home + all modals
│   ├── booking.html         # Page 2 – Make / modify a booking
│   ├── summary.html         # Page 3 – Booking summary + confirm/modify/cancel
│   └── confirmation.html    # Page 4 – Booking confirmed
└── static/
    ├── css/style.css        # Complete styling incl. chat widget
    └── js/app.js            # Shared JS incl. chatbot logic
```

---

## 🚀 Setup & Run

```bash
cd restaurant
pip install -r requirements.txt
```

### 1. Set your Anthropic API key (required for the chatbot)

Get a key from [console.anthropic.com](https://console.anthropic.com), then set it as an environment variable:

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

**macOS / Linux:**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

> The app works fine **without** a key — every page still functions normally. Only the chat widget will show a friendly "not configured" message instead of replying.

### 2. Run the server

```bash
uvicorn main:app --reload --port 8000
```

Open: http://localhost:8000

---

## 🤖 AI Chatbot ("Spice Bot")

A floating chat button (bottom-right, on every page) lets guests ask questions and get live answers from Claude.

**What it can do:**
- Answer questions about the menu, prices, and ingredients
- Recommend dishes (spicy/mild/vegetarian/sweet, etc.)
- Explain how to book, modify, or cancel a reservation
- Stay on-topic — redirects unrelated questions back to the restaurant

**How it works:**
- `POST /chat` in `main.py` calls the Claude API (`anthropic` Python SDK)
- The system prompt is built dynamically from the live `MENU` dictionary, so the bot is always accurate
- Conversation history (last 10 turns) is kept client-side in JavaScript and sent with each request — no server-side session storage needed
- Default model: `claude-haiku-4-5-20251001` (fast and cost-efficient for an FAQ-style assistant). To use a more capable model, change `CHAT_MODEL` in `main.py`, e.g. to `claude-sonnet-4-6`.

**Cost control tips:**
- `CHAT_MAX_TOKENS` (default 400) caps each reply's length
- `CHAT_HISTORY_LIMIT` (default 10) caps how much past conversation is resent each turn

---

## 🗄️ Database Schemas

### users (restaurant_users.db)
| Column        | Type    | Notes                  |
|---------------|---------|------------------------|
| user_id       | INTEGER | Primary key, auto-inc  |
| login_id      | TEXT    | Email or phone, unique |
| customer_name | TEXT    | Full name              |
| password      | TEXT    | SHA-256 hashed         |
| created_at    | TEXT    | Auto timestamp         |

### bookings (restaurant_bookings.db)
| Column        | Type    | Notes                      |
|---------------|---------|----------------------------|
| booking_id    | INTEGER | Primary key, auto-inc      |
| user_login    | TEXT    | FK → users.login_id        |
| booking_name  | TEXT    | Name on reservation        |
| booking_time  | TEXT    | e.g. "7:00 PM"             |
| booking_date  | TEXT    | ISO date "2026-02-15"      |
| menu          | TEXT    | JSON: {"Dish": qty, ...}   |
| table_for     | INTEGER | Number of guests           |
| user_reviews  | TEXT    | Optional review            |
| total_amount  | REAL    | Calculated total in ₹      |
| created_at    | TEXT    | Auto timestamp             |

---

## 🎨 Changing the Background Image

In `static/css/style.css`:
```css
:root {
  --bg-image: url('https://images.unsplash.com/photo-...');
}
```
Replace with any image URL or `/static/images/your-photo.jpg`.

---

## 📧 Email Configuration

In `main.py`, find `send_confirmation_email()` and uncomment the SMTP block, filling in a Gmail address and an [App Password](https://myaccount.google.com/apppasswords).

---

## 🔐 Security Notes

- Passwords are SHA-256 hashed with a salt (upgrade to bcrypt for production)
- Sessions stored in HTTP-only cookies (1-day expiry)
- Booking modify/cancel routes verify ownership before any write
- Never commit your `ANTHROPIC_API_KEY` to version control — keep it as an environment variable
- For production: use HTTPS and move all secrets to environment variables / a `.env` file
