# CCSE_FFA - Starfleet Academy Operations Inventory Management System

Flask REST API + browser GUI for tracking Starfleet Academy inventory, with role-based
access control, modification history, and audit logging.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running it

```bash
python3 app.py
```

Opens on `http://127.0.0.1:5000`. First run creates `instance/inventory.db` automatically.

Open `http://127.0.0.1:5000` in a browser for the GUI, or use the curl examples below to hit
the API directly.

## Running tests

```bash
pytest test_app.py -v
```

Tests run against an in-memory database (see `DATABASE_URL` handling in `app.py`) - they
never touch `instance/inventory.db`.

## Roles

- **cadet**: can view inventory, single items, and item history. Cannot add/edit/remove
  items, add users, or view the audit log.
- **command_officer**: everything a cadet can do, plus add/edit/remove inventory items,
  add users, and view the audit log.

There's no signup route - accounts are created via `/user/add` (officer only) or the
`/user/temp_add` bootstrap route below.

## Auth

Login is session-cookie based, not token based - once you log in with curl, pass the
same cookie jar on every request after that:

```bash
curl -c cookies.txt -X POST http://127.0.0.1:5000/login \
  -d "username=testofficer&password=testpassword"

curl -b cookies.txt http://127.0.0.1:5000/inventory
```

`-c cookies.txt` saves the session cookie, `-b cookies.txt` sends it back. Use both
(`-b cookies.txt -c cookies.txt`) if a request might change the session (e.g. logging in
as a different user).

## Endpoints

### Bootstrap test accounts (no auth required, for local testing only)

```bash
# creates testcadet / testpassword
curl http://127.0.0.1:5000/user/temp_add

# creates testofficer / testpassword
curl http://127.0.0.1:5000/user/temp_add?role=command_officer

# creates a test inventory item, no login needed
curl http://127.0.0.1:5000/item/temp_add
```

### Login / logout

```bash
curl -c cookies.txt -X POST http://127.0.0.1:5000/login \
  -d "username=testofficer&password=testpassword"

curl -b cookies.txt -X POST http://127.0.0.1:5000/logout
```

### Inventory - read (any logged in role)

```bash
# list all items
curl -b cookies.txt http://127.0.0.1:5000/inventory

# single item
curl -b cookies.txt http://127.0.0.1:5000/inventory/1

# modification history for one item
curl -b cookies.txt http://127.0.0.1:5000/inventory/1/history
```

### Inventory - write (command_officer only)

```bash
# add
curl -b cookies.txt -X POST http://127.0.0.1:5000/inventory/add \
  -d "name=tricorder&quantity=5"

# update - real PUT verb works
curl -b cookies.txt -X PUT http://127.0.0.1:5000/inventory/1 \
  -d "name=tricorder mk2&quantity=9"

# remove - real DELETE verb works, this is a soft delete (is_removed flag, row stays in the db)
curl -b cookies.txt -X DELETE http://127.0.0.1:5000/inventory/1
```

The browser's edit/remove forms POST to the same `/inventory/<id>` URL instead of using
PUT/DELETE directly, since plain HTML forms can't send those verbs - a hidden
`_action=delete` field tells the route which one it is. Both paths run the same code.

### Users (command_officer only to create)

```bash
curl -b cookies.txt -X POST http://127.0.0.1:5000/user/add \
  -d "username=newcadet&password=somepassword&role=cadet"
```

### Audit log (command_officer only)

```bash
curl -b cookies.txt http://127.0.0.1:5000/audit-log
```

Returns an HTML page (table), not JSON - open it in a browser while logged in as an
officer, or `curl` it and read the raw HTML.

## Notes for reviewers

- Auth is session-cookie based (Flask's built-in signed session), not JWT. See
  `app.py` comments and prior report sections for why - short version: no fetch/JS
  needed anywhere in the GUI, plain HTML forms handle everything.
- `SECRET_KEY` in `app.py` is a hardcoded dev value, would be an environment variable
  in a real deployment.
- Soft delete (`is_removed` flag) is what makes modification history possible - a
  removed item's row still exists, so its history rows still resolve.
