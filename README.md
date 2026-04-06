# Shivani Carriers — WhatsApp Driver Tracking Backend

A Python/FastAPI backend that drives the full WhatsApp driver tracking flow
via **Meta WhatsApp Cloud API**.

---

## Architecture Overview

```
Meta Cloud API
      │  webhook POST
      ▼
FastAPI  (/webhook)
      │
      ▼
Flow Engine  ─── State Machine (5 stages)
      │
      ▼
SQLite DB  (one row per load, full state stored)
      │
      ▼
Scheduler  ─── 6-hour follow-up loop
```

---

## Project Structure

```
shivani_tracker/
├── main.py                    # FastAPI app + lifespan
├── requirements.txt
├── .env.example               # Copy to .env and fill in values
└── app/
    ├── config.py              # All settings from env vars
    ├── database.py            # Async SQLAlchemy setup
    ├── routes.py              # Webhook + Load management endpoints
    ├── scheduler.py           # 6-hour follow-up scheduler
    ├── models/
    │   ├── base.py
    │   ├── load.py            # Core per-load state table
    │   └── message_log.py     # Full audit trail
    └── services/
        ├── whatsapp.py        # Meta Cloud API sender (text/buttons/list)
        ├── messages.py        # Message catalog (all user-facing strings)
        └── flow_engine.py     # Full state machine — all 5 stages
```

---

## Quick Start

### 1. Install dependencies
```bash
cd shivani_tracker
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — fill in WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, SUPPORT_MOBILE
```

### 3. Run the server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Expose via HTTPS (Meta requires HTTPS)
```bash
# Development: use ngrok
ngrok http 8000
# Copy the https URL e.g. https://abc123.ngrok.io
```

### 5. Configure Meta Webhook
- Go to Meta Developer Console → Your App → WhatsApp → Configuration
- Webhook URL: `https://your-domain.com/webhook`
- Verify Token: same as `WHATSAPP_VERIFY_TOKEN` in your `.env`
- Subscribe to: `messages`

---

## API Endpoints

### POST `/webhook/loads` — Create a new load
Called by your dispatch system when a truck is loaded.

```json
{
  "vehicle_no": "MH-12-AB-1234",
  "from_location": "Mumbai",
  "to_location": "Pune",
  "bilty_no": "BL-2024-001",
  "bilty_date": "25/06/2024",
  "driver_whatsapp": "+919876543210",
  "load_out_time": "2024-06-25T10:00:00"
}
```

The driver will automatically receive a confirmation message 6 hours after `load_out_time`.

### POST `/webhook/loads/{load_id}/close` — Manually close a load
Stops all follow-ups for a load. Use when backend team manually closes.

### GET `/health` — Health check

---

## Flow Summary

```
Trigger (load_out + 6h)
    → Driver Confirmation (Yes/No)
        → No: close
        → Yes: Main Status Menu (shown every 6h for active loads)
            → 1. Enroute
                [Check unresolved S1 issue] → ask resolution
                → Current location (free text)
                → Facing difficulty? (Yes/No)
                    → Yes: select issue type → store + notify team
                    → No: thank you + schedule next 6h
            → 2. Reached unloading point
                [Always ask: unloading report time]
                [Earlier issue?] → ask if still open
                → New issue? → select from list or free text
            → 3. Unloading started
                → Issue while unloading? (Yes/No) → free text if Yes
            → 4. Unloaded, POD not received
                [Always ask: unloading complete time]
                → Charges > INR 100? → amount if Yes
                → POD seal/sign warning
            → 5. Unloaded + POD received
                [Fill any missing S4 fields]
                → Confirm prior charges answer
                    → Yes: POD instruction
                    → No: corrected amount → seal/sign on POD?
                → LOAD CLOSED (is_active = False)
```

### Anti-Redundancy Rule
If driver jumps from Stage 1 to Stage 4:
1. Engine fetches stored S2/S3/S4 critical fields
2. Asks **only missing** critical fields (unloading time, charges)
3. Confirms existing values rather than repeating full questionnaire
4. Continues into selected stage

---

## Database Schema (key columns)

| Column | Purpose |
|--------|---------|
| `current_stage` | Which stage (1-5) the load is currently in |
| `pending_step` | Exact sub-step we're waiting for (e.g. `s4_charges_yn`) |
| `next_followup_due` | UTC datetime for next 6-hour follow-up |
| `is_active` | False = load closed, no more messages |
| `s4_*` | Stage 4 critical fields (reused by Stage 5) |

---

## Production Deployment

```bash
# Using gunicorn + uvicorn workers
pip install gunicorn
gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

For production, replace SQLite with PostgreSQL:
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost/shivani_db
pip install asyncpg
```

### Systemd service (Linux)
```ini
[Unit]
Description=Shivani Driver Tracking
After=network.target

[Service]
WorkingDirectory=/opt/shivani_tracker
ExecStart=/opt/shivani_tracker/venv/bin/gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker
Restart=always
EnvironmentFile=/opt/shivani_tracker/.env

[Install]
WantedBy=multi-user.target
```

---

## WhatsApp Templates

For the **first outbound message** to a driver (opening a new 24-hour session),
you need a pre-approved template in Meta Business Manager.

Suggested template name: `driver_confirmation`
```
Body: Are you the driver for vehicle {{1}} travelling from {{2}} to {{3}}?
Buttons: Yes | No
```

Once approved, update `trigger_load()` in `flow_engine.py` to use `send_template()`.

---

## Notes

- **Date-time picker**: WhatsApp Cloud API has no native date-time widget.
  Drivers type in `DD/MM/YYYY HH:MM AM/PM` format. Add server-side validation
  in `_handle_pending_step` if needed.
- **Support mobile**: Set `SUPPORT_MOBILE` in `.env`. It appears in all
  issue-noted and thank-you messages.
- **POD image receipt**: When a driver WhatsApps the POD image, handle the
  `image` message type in `routes.py` and set `load.s5_pod_copy_received = True`.
