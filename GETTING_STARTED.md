# Shivani Carriers — WhatsApp Driver Tracking
## Complete Getting Started Guide

---

## What's Inside the Bundle

```
shivani_tracker/
├── main.py                        ← App entry point
├── requirements.txt               ← Python dependencies
├── .env.example                   ← Environment config template
├── README.md                      ← Developer reference
└── app/
    ├── config.py                  ← Reads settings from .env
    ├── database.py                ← SQLite/PostgreSQL setup
    ├── routes.py                  ← Webhook + Load API endpoints
    ├── scheduler.py               ← 6-hour follow-up loop
    ├── models/
    │   ├── load.py                ← Core load state table
    │   └── message_log.py        ← Full message audit trail
    └── services/
        ├── whatsapp.py            ← Meta Cloud API sender
        ├── messages.py            ← All driver-facing message strings
        └── flow_engine.py         ← Full 5-stage state machine
```

---

## Prerequisites

Before you begin, make sure you have:

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | https://python.org/downloads |
| Meta Developer Account | https://developers.facebook.com |
| WhatsApp Business Account | Linked to your Meta Developer app |
| ngrok (for local dev) | https://ngrok.com — exposes localhost over HTTPS |

---

## Step 1 — Extract & Set Up Python Environment

```bash
# Unzip the bundle
unzip shivani_tracker_bundle.zip
cd shivani_tracker

# Create a virtual environment
python -m venv venv

# Activate it
# macOS / Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

---

## Step 2 — Get Your Meta / WhatsApp Credentials

### 2a. Create a Meta App
1. Go to https://developers.facebook.com/apps
2. Click **Create App** → Select **Business** → Fill in app name
3. Add the **WhatsApp** product to your app

### 2b. Get Your Phone Number ID
1. In your app dashboard → **WhatsApp** → **API Setup**
2. Copy the **Phone number ID** (looks like: `123456789012345`)

### 2c. Get Your Access Token
1. On the same page, copy the **Temporary access token**
   *(for production, generate a permanent token via System User in Business Manager)*

### 2d. Note Your Verify Token
- This is a string **you choose yourself** — any random phrase
- Example: `shivani_secret_2024`
- You will enter this in both your `.env` file AND the Meta webhook setup

---

## Step 3 — Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Open .env in any text editor and fill in:
```

```ini
# Paste your Phone Number ID from Step 2b
WHATSAPP_PHONE_ID=123456789012345

# Paste your Access Token from Step 2c
WHATSAPP_TOKEN=EAABcde...your_token_here

# Your chosen verify token (must match what you enter in Meta webhook setup)
WHATSAPP_VERIFY_TOKEN=shivani_secret_2024

# The support contact number shown to drivers in all messages
SUPPORT_MOBILE=+91-98765-43210
```

Leave all other values as defaults for now.

---

## Step 4 — Run the Server

```bash
# Start the server (from inside the shivani_tracker folder)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Initialising database...
INFO:     Starting 6-hour follow-up scheduler...
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The SQLite database file `shivani_tracking.db` is created automatically.

---

## Step 5 — Expose Your Server via HTTPS

Meta requires an HTTPS webhook URL. Use ngrok for local development:

```bash
# In a NEW terminal window:
ngrok http 8000
```

You'll get a URL like:
```
Forwarding   https://abc123.ngrok-free.app → http://localhost:8000
```

Copy the `https://...` URL — you'll need it in the next step.

---

## Step 6 — Register the Webhook with Meta

1. Go to your Meta app → **WhatsApp** → **Configuration**
2. Under **Webhook**, click **Edit**
3. Fill in:
   - **Callback URL**: `https://abc123.ngrok-free.app/webhook`
   - **Verify token**: same value as `WHATSAPP_VERIFY_TOKEN` in your `.env`
4. Click **Verify and Save**
5. Under **Webhook fields**, click **Manage** and subscribe to **messages**

If verification succeeds, your server is correctly connected.

---

## Step 7 — Create Your First Load (Test)

Use any API client (curl, Postman, or your dispatch system) to create a load:

```bash
curl -X POST http://localhost:8000/webhook/loads \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_no": "MH-12-AB-1234",
    "from_location": "Mumbai",
    "to_location": "Pune",
    "bilty_no": "BL-2024-001",
    "bilty_date": "25/06/2024",
    "driver_whatsapp": "+919876543210",
    "load_out_time": "2024-06-25T10:00:00"
  }'
```

The driver will automatically receive a WhatsApp confirmation message
**6 hours after** the `load_out_time` you provide.

To test immediately, set `load_out_time` to a time in the past
(e.g. 7 hours ago) — the scheduler picks it up within 60 seconds.

---

## Step 8 — Test the Full Flow

1. Send the load creation request (Step 7)
2. Wait up to 60 seconds for the driver confirmation message to arrive
3. Reply **Yes** on the driver's WhatsApp
4. The main status menu appears
5. Select any stage and walk through the questions

To manually close a load at any time:
```bash
curl -X POST http://localhost:8000/webhook/loads/1/close
```

---

## Flow at a Glance

```
[Trigger: load_out + 6h]
        ↓
  Driver Confirmation
   Yes ↓       ↓ No → "Thank you" → END
        ↓
  ┌─ Main Menu (repeats every 6h) ──────────────────────┐
  │  1. Enroute                                         │
  │  2. Reached unloading point                        │
  │  3. Unloading started                              │
  │  4. Unloaded, POD not received                     │
  │  5. Unloaded + POD received  ──→ LOAD CLOSED       │
  └─────────────────────────────────────────────────────┘
```

**Anti-redundancy**: If a driver jumps from Stage 1 to Stage 4,
the system fetches stored data and asks only the missing fields.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/webhook` | Meta webhook verification |
| `POST` | `/webhook` | Inbound WhatsApp messages |
| `POST` | `/webhook/loads` | Create a new load |
| `POST` | `/webhook/loads/{id}/close` | Manually close a load |

Interactive API docs available at: `http://localhost:8000/docs`

---

## Going to Production

### Switch to PostgreSQL
```ini
# In .env:
DATABASE_URL=postgresql+asyncpg://user:password@localhost/shivani_db
```
```bash
pip install asyncpg
```

### Use a permanent Meta access token
1. In Meta Business Manager → **System Users** → Create a system user
2. Assign your WhatsApp app with `whatsapp_business_messaging` permission
3. Generate a permanent token and put it in `WHATSAPP_TOKEN`

### Run with gunicorn
```bash
pip install gunicorn
gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### WhatsApp Message Templates
The first outbound message to a driver requires a pre-approved template
(to open a new 24-hour conversation window).

Create a template in **Meta Business Manager → Message Templates**:
- **Name**: `driver_confirmation`
- **Category**: Utility
- **Body**: `Are you the driver for vehicle {{1}} travelling from {{2}} to {{3}}?`
- **Buttons**: Quick Reply — `Yes` | `No`

Once approved (usually 1–2 hours), update `trigger_load()` in
`app/services/flow_engine.py` to call `send_template()` instead of `send_buttons()`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Webhook verification fails | Check `WHATSAPP_VERIFY_TOKEN` matches exactly in `.env` and Meta dashboard |
| Messages not sending | Verify `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_ID` are correct |
| Driver not receiving trigger | Check `load_out_time` is in the past; scheduler polls every 60s |
| "No active load" in logs | Driver's WhatsApp number must match `driver_whatsapp` in E.164 format (`+91...`) |
| 24-hour window error | Use a pre-approved template for first outbound message (see above) |

---

*Shivani Carriers — Driver Tracking System v1.0*
