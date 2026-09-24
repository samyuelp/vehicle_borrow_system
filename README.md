# Vehicle Borrow System

A kiosk-style Django app for managing vehicle borrowing and reservations.

---

## Overview

- **Borrow** — walk-up borrow. Take a car, return it whenever.
- **Reserve** — advance booking for a specific date range. Generates a 4-char pickup code.
- **Return** — bring a car back, log fuel/mileage/notes.
- **Pickup** — enter reservation code to claim a reserved car.

The admin panel is used for managing cars and reviewing activity.

---

## Tech Stack

- Django 6.1 on Python 3.14
- SQLite database
- Gunicorn as the WSGI server
- WhiteNoise for static file serving (admin CSS/JS)
- Docker for packaging
- Hosted on a Proxmox LXC container (LXC ID 100)

---

## Project Layout

```
vehicle_borrow_system/
├── manage.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
├── VBS/                          # project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── vehicles/                     # the app
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── admin.py
│   └── migrations/
└── templates/
    ├── base.html
    ├── home.html
    ├── borrow_list.html
    ├── borrow_form.html
    ├── borrow_unavailable.html
    ├── return_list.html
    ├── return_confirm.html
    ├── return_form.html
    ├── return_reservation_choice.html
    ├── reserve_list.html
    ├── reserve_form.html
    ├── reserve_success.html
    └── pickup.html
```

---

## Local Development

```bash
# activate venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate

# install deps
pip install -r requirements.txt

# apply migrations
python manage.py migrate

# run
python manage.py runserver
```

- App: http://127.0.0.1:8000
- Admin: http://127.0.0.1:8000/admin/

---

## Deployment (Proxmox LXC + Docker)

### Environment

| Item | Value |
|---|---|
| App directory on LXC | `/opt/kiosk` |
| Data directory (SQLite) | `/opt/kiosk-data` |
| Container name | `kiosk` |
| Exposed port | `8000` |

### Deploy Workflow

**1. On your local machine — push changes:**

```bash
cd ~/Projects/vehicle_borrow_system
git add .
git commit -m "description of change"
git push
```

**2. On the LXC — pull, rebuild, restart:**

Enter the LXC from the Proxmox host:

```bash
pct enter 100
```

Then:

```bash
cd /opt/kiosk
git pull
docker build -t kiosk .
docker stop kiosk && docker rm kiosk
docker run -d \
  -p 8000:8000 \
  -v /opt/kiosk-data:/app/data \
  --name kiosk \
  --restart unless-stopped \
  kiosk
```

**3. Verify:**

```bash
docker ps
docker logs kiosk
```

Look for Gunicorn startup lines. Then visit:

```
http://<ip_address>:8000
```

---

## When You Need What

| Change type | Rebuild? | Migrate? |
|---|---|---|
| `models.py` (add/change fields) | Yes | Yes |
| `admin.py` | Yes | No |
| `views.py` | Yes | No |
| `forms.py` | Yes | No |
| Templates | Yes | No |
| `settings.py` | Yes | No |
| `urls.py` | Yes | No |

**Rebuild = any code change.**
**Migrate = only when models change.**

### Migrating (after a model change)

**On your local machine:**

```bash
python manage.py makemigrations
python manage.py migrate
```

Push to git.

**On the LXC (after rebuild):**

```bash
docker exec -it kiosk python manage.py migrate
```

---

## Data & Persistence

- The SQLite database lives at `/opt/kiosk-data/db.sqlite3` on the LXC.
- It's mounted into the container at `/app/data/db.sqlite3`.
- **Rebuilding or recreating the container does NOT affect the database.**
- Only `rm -rf /opt/kiosk-data/` would destroy it.

**Backup:**

```bash
cp /opt/kiosk-data/db.sqlite3 ~/kiosk-backup-$(date +%Y%m%d).sqlite3
```

---

## Common Commands

### Docker

```bash
docker ps                                                 # running containers
docker logs kiosk --tail 50                               # recent logs
docker exec -it kiosk bash                                # shell inside container
docker exec -it kiosk python manage.py migrate            # run migrations
docker exec -it kiosk python manage.py createsuperuser    # new admin user
```

### Proxmox

```bash
pct list                           # list all containers
pct enter 100                      # enter the kiosk LXC
pct exec 100 -- ip a               # get the LXC's IP
```

### Django

```bash
python manage.py showmigrations vehicles   # check migration state
python manage.py check                     # validate config
python manage.py shell                     # interactive shell
```

---

## Troubleshooting

### Admin panel looks unstyled (plain HTML)

Static files aren't being served. Check:

```bash
docker exec kiosk ls /app/staticfiles/admin/css/
```

Should list `base.css`, `login.css`, etc. If empty/missing, `collectstatic` failed during the build. Confirm the Dockerfile has:

```dockerfile
RUN python manage.py collectstatic --noinput
```

And `settings.py` has:

- `whitenoise.middleware.WhiteNoiseMiddleware` right after `SecurityMiddleware`
- `STATIC_ROOT = BASE_DIR / 'staticfiles'`
- `whitenoise` in `requirements.txt`

### "no such table: ..." errors

Migrations haven't run against the database. Fix:

```bash
docker exec -it kiosk python manage.py migrate
```

### 500 error, no traceback in logs

`DEBUG = False` hides the traceback. Temporarily flip it:

```bash
docker exec -it kiosk python -c "
import pathlib
p = pathlib.Path('/app/VBS/settings.py')
s = p.read_text().replace('DEBUG = False', 'DEBUG = True')
p.write_text(s)
"
docker restart kiosk
```

Reload the page — the traceback appears in the browser. Then flip it back:

```bash
docker exec -it kiosk python -c "
import pathlib
p = pathlib.Path('/app/VBS/settings.py')
s = p.read_text().replace('DEBUG = True', 'DEBUG = False')
p.write_text(s)
"
docker restart kiosk
```

### Timezone is off by a day

`settings.py` should have:

```python
TIME_ZONE = 'America/Anchorage'
```

If it says `UTC`, change it and rebuild.

### Container won't start

```bash
docker logs kiosk
```

Almost always a Python import error or syntax error. Fix locally, push, rebuild.

### Changes don't appear after rebuild

Browser cache. Hard-refresh:

- Windows/Linux: `Ctrl + Shift + R`
- Mac: `Cmd + Shift + R`

---

## Models Reference

### `Vehicle`

- `car_name` — the display name

### `BorrowDetail` — walk-up borrow record

- `vehicle` — FK to Vehicle
- `borrowers_name`, `destination`
- `borrow_time` — auto-set on creation
- `actual_return_time` — set when returned
- `expected_return_date` — set only when borrow came from a reservation
- `reservation` — FK to Reservation (nullable, set only for pickup borrows)
- `fuel_percent`, `current_mileage`, `notes`
- `is_overdue` — property: expected_return_date passed and not returned

### `Reservation` — advance booking

- `vehicle`, `borrowers_name`, `destination`
- `start_date`, `end_date` — inclusive both ends
- `code` — 4-char pickup code (auto-generated, unique)
- `fulfilled` — True once closed out after the window ended
- `cancelled` — True if reserver released it early
- `notes`
- `is_active` — property: within window, not cancelled/fulfilled
- `is_overdue` — property: window ended, linked borrow still out

---

## Key Behaviors

**Borrow list status:**

- Overdue — blocked, contact admin
- Currently out — blocked
- Reserved today — tappable, goes to pickup flow
- Available — tappable, normal borrow

**Returning a car early (with active reservation):**

- System asks "Cancel reservation or keep it?"
- Cancel → reservation cancelled, car free
- Keep → reservation stays active through its window

**Reservation without pickup:**

- Ages out naturally after `end_date`. No cleanup needed.

---

## Repository

Local path: `~/Projects/vehicle_borrow_system`

Git remote: [*(repo url)*](https://github.com/samyuelp/vehicle_borrow_system.git)
