# OpenLinko — a self-hosted dashboard for CarLinko cars

*Jaecoo · Omoda · Chery · Exeed — BEV and PHEV. Formerly **J5 EV Dashboard**: it started on a Jaecoo J5 EV, and owners have since confirmed it on the Omoda E5, Tiggo 7 PHEV and Tiggo 8 PHEV.*

**English** · [Bahasa Indonesia](README.id.md) · [Website](https://jaylabb.my.id/openlinko/)

A clean, mobile-first PWA for any car on the CarLinko app: live battery, range and state,
remote lock / A/C / windows / tailgate, energy use net of regen, charge sessions and cost, tyres,
12 V health, and a head-unit add-on.

It exists because the stock CarLinko app shows the current state and little else: no trip totals,
no charge-cost history, no efficiency over time. Everything here is derived from data the car
**already** sends to its own cloud. This project just reads your own account and keeps the history.
Per-wheel tyre pressures appear when your car has direct TPMS; cars with indirect TPMS
(like the J5 EV) only ever report a status, and the dashboard says so instead of inventing numbers.

> Built against real cars, not a spec sheet. Charge-cost output matches the owner's PLN Mobile
> receipts to **99.6–99.9 %** (see [Accuracy](#accuracy)) — that figure is from one car, since it
> needs real receipts to check against. The telemetry decode itself is confirmed on two.

> **Other CarLinko cars?** Confirmed on **four cars, three brands, two powertrains, four countries** —
> a Jaecoo J5 EV (BEV, Indonesia), a Chery Tiggo 8 PHEV (South Africa), a Chery Tiggo 7 PHEV
> (Malaysia) and an Omoda E5 (BEV, Uruguay). Every telemetry byte
> offset held identical across all of them, which suggests the blob layout comes from the CarLinko
> platform itself rather than the model. The per-model constants that *do* differ (tyre scale,
> powertrain, the car's own photo) are read from the API at setup, so a new car largely configures
> itself.
>
> Caveat worth stating plainly: Jaecoo, Omoda, Exeed and Chery are all **Chery Group** brands, and
> CarLinko is Chery Group's app — so "works on CarLinko" realistically means "works across Chery
> Group", not literally any car. Four cars is a strong signal, not proof: bytes we haven't mapped
> may well differ, and no pure-ICE car has been tried. If you have a different car, please try it
> and file a [car report](https://github.com/GodrezJr2/openlinko/issues/new?template=add-car.yml) — a second car
> was worth more to this project than any amount of staring at the first. 🙏

## Demo

<p align="center"><img src="docs/media/walkthrough.gif" width="800" alt="Walkthrough of the v2 interface: home, energy, distance calendar, 3D doors view, charging and the charge calculator"></p>

*One continuous take of the v2 interface on a phone-sized screen, running the built-in demo mode
(`python server.py --demo`, sample data, no account needed). Cut in [Motion Studio](https://github.com/GodrezJr2/motion-studio).*

Recorded on a real car instead: [1½ minutes on a phone against a real Jaecoo J5 EV](https://github.com/user-attachments/assets/f17d167d-cbf9-4eb0-92b4-44361f6da6a5)
(Classic interface, plate and VIN masked, also [downloadable](https://github.com/GodrezJr2/openlinko/releases/download/assets/j5-dashboard-demo.mp4)).

## Screenshots

The **v2 interface** (the default at `/`, also at `/v2.html`). The pictures follow your GitHub theme;
both a light and a dark theme are built in.

<table>
<tr><th>Home</th><th>Energy</th><th>Distance</th></tr>
<tr><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-home-dark.jpg"><img src="docs/screenshots/v2-home-light.jpg" width="260" alt="Home: range, battery, climate, doors and tyres"></picture></td><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-energy-dark.jpg"><img src="docs/screenshots/v2-energy-light.jpg" width="260" alt="Energy: kWh/100 km per day, net of regen, beside the head-unit figure"></picture></td><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-dist-dark.jpg"><img src="docs/screenshots/v2-dist-light.jpg" width="260" alt="Distance: a calendar of km, energy and charging cost per day"></picture></td></tr>
<tr><th>Doors &amp; windows</th><th>Charging</th><th>Charge calculator</th></tr>
<tr><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-doors-dark.jpg"><img src="docs/screenshots/v2-doors-light.jpg" width="260" alt="Doors and windows on a 3D car you can turn, with remote controls"></picture></td><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-chg-dark.jpg"><img src="docs/screenshots/v2-chg-light.jpg" width="260" alt="Charging: last session curve, kWh in and cost"></picture></td><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-plan-dark.jpg"><img src="docs/screenshots/v2-plan-light.jpg" width="260" alt="Charge calculator: time, kWh and cost to a target %"></picture></td></tr>
</table>

*Shown with demo data. Plate and VIN are masked by default (privacy eye-toggle).*

The **Classic interface** (`/index.html`, or pick it as the default under Settings) adds the long-trip planner and the SPKLU map:

<table>
<tr><th>Trip planner</th><th>SPKLU map</th></tr>
<tr><td align="center" valign="top"><img src="docs/screenshots/trip-planner.png" width="300" alt="Long-trip planner — route, on-route charge stops with connectors and arrival %"></td><td align="center" valign="top"><img src="docs/screenshots/spklu-map.png" width="300" alt="Interactive SPKLU map — pins, live availability, directions"></td></tr>
</table>

---

## ⚠️ Legal & ethics — read this first

This is a **personal interoperability / reverse-engineering** project for accessing **your
own vehicle and your own account**. It is provided for educational and personal use.

- **Use it only with an account and a car you own.** Do not access anyone else's data.
- This talks to a **private, undocumented vendor API**. There is **no warranty** and it can
  break at any time if the vendor changes their backend. It is **not affiliated with,
  endorsed by, or supported by** Jaecoo, Chery, or CarLinko.
- **No personal data is shipped.** Your account, token, VIN, plate, vehicle id and device
  serial live only in a gitignored `creds.json` (see [Setup](#setup)). The request-signing key
  is an **app-global constant** (the same string baked into every CarLinko install, trivially
  readable from the APK) — it's bundled so setup is just email + password; it is not a secret
  tied to you.
- **Do not run this as a public/hosted multi-user service.** Doing so means storing other
  people's credentials (which can unlock/control their car) and almost certainly violates the
  vendor's terms. The intended deployment is **one instance per owner**, self-hosted, private
  (e.g. behind Tailscale). See [Going multi-user](#going-multi-user).
- Mostly read-only. There **is** a Control tab (lock, A/C, windows, sunroof, tailgate, find-car,
  stop-charge), but it is **beta**: only *Stop charging* is a confirmed opcode, the rest are
  best-effort decodes from the APK, and every tap is a **real actuation on a real car** — watch
  the car when you use it. It is also **cloud-only: no Bluetooth.** The CarLinko app's
  Bluetooth-proximity control is **not** implemented, so the car must be awake and have cellular
  signal or the command just fails (`50043`).

If you don't accept the above, don't use this.

---

## Features

The default interface is **v2** (`/`), a car-first app: a 3D model of your car with live state,
and one screen per part of it. The classic interface is still at `/index.html` (or switch in Settings).

- **Live vehicle** — battery %, range, odometer, 12 V, parked / charging / driving, doors,
  windows, sunroof, tailgate and lock state, pushed over CarLinko's realtime WebSocket and kept in SQLite.
- **Remote control** — lock / unlock, A/C on / off with target temperature, windows, tailgate,
  find car, stop charging. Commands are AES-encrypted the way the official app sends them, and the
  UI only shows a change once the car itself reports it. Lock, trunk, windows and A/C are
  runtime-confirmed on the J5 EV; see [docs/control-opcodes.md](docs/control-opcodes.md).
  **Cloud only — no Bluetooth.**
- **Climate** — A/C and target temperature, plus a head-unit style seat panel; seat heat / ventilation and defog controls are beta.
- **Energy** — per-trip and rolling kWh/100 km **net of regen** (the head-unit figure is kept as
  "before regen"), lifetime kWh, cost and km, savings vs petrol.
- **Battery & charging** — auto-detected charge sessions (kWh into the pack, kWh billed, cost),
  charge curves, battery-care hints, 12 V health, and a rough battery-health trend learned from
  long charges (home AC or fast DC, no OBD dongle needed).
- **Tyres** — per-wheel pressure where the car reports direct TPMS; a single status on indirect-TPMS cars.
- **Share card** — a clean image of your car's stats to post, with plate and VIN masked.
- **Head unit add-on** — Climate Gesture: two-finger fan and temperature control on the J5 head
  unit, installed from the dashboard over the local network. See [Head unit add-on](#head-unit-add-on-climate-gesture).
- **BEV and PHEV** — fuel level, fuel range and fuel consumption on PHEVs.
- **Find my car (opt-in)** — where the car is parked, a Navigate button for your phone's maps app,
  and the route of each trip, for any day on the calendar, from CarLinko's cached position. Off by
  default; works where the cloud has a position (Tiggo 7 CSH, Malaysia; not the J5 in Indonesia). See [docs/LOCATION.md](docs/LOCATION.md).
- **Home Assistant** — read it over REST sensors with battery-low / charge-done notifications
  ([docs/HOMEASSISTANT.md](docs/HOMEASSISTANT.md)). For a native integration see [Related projects](#related-projects).
- **Extras (optional, need a Google Maps key)** — long-trip charge planner and SPKLU charger map.
- Privacy toggles, dark mode, English / Bahasa Indonesia.

See [PRODUCT.md](PRODUCT.md) for the product rationale and [DESIGN.md](DESIGN.md) for the
visual system.

## Architecture

```
  Car TCU ──(cellular)──> CarLinko cloud  ──┐
                                            │  WebSocket (token auth, no signing) — telemetry blob
   tools/logger.py  ◀───────────────────────┘  decodes + stores every frame to carlinko.db
        │                                       (auth.py auto-refreshes the token on expiry)
        ▼
   carlinko.db (SQLite)
        │
        ▼
   tools/server.py  ── /api/summary, /api/trip, /api/spklu ──▶  web/ PWA (vanilla JS, Leaflet)
   (stdlib http.server)        + Google Places (optional)        served over Tailscale
```

- **No framework, no build step.** Backend is Python standard library; frontend is hand-written
  HTML/CSS/JS with two vendored libs (Leaflet, slot-text). Self-hosted and offline-friendly.
- **The telemetry is a 73-byte blob.** Field offsets were recovered by driving the car and
  watching which bytes moved (battery = byte 28, range = 29–30 BE, odometer = 18–20 BE, …).
  See [docs/api-map.md](docs/api-map.md).

## Accuracy

The charge analytics are calibrated against the owner's real PLN Mobile receipts:

| Session            | Dashboard            | Receipt              | Match   |
| ------------------ | -------------------- | -------------------- | ------- |
| 58 → 100 %         | 28.9 kWh / Rp 73,491 | 28.94 kWh / Rp 73,521 | 99.9 % |
| 35 → 80 %          | 29.1 kWh / Rp 73,981 | 29.23 kWh / Rp 74,273 | 99.6 % |

DC charge efficiency is modelled as SoC-dependent (charging to 100 % loses more than to 80 %),
calibrated to two receipts. Usable pack ≈ 58.9 kWh.

The charge planner predicts what you'll actually pay at the meter, checked against a real
PLN Mobile SPKLU receipt:

| The app's charge planner | The real PLN Mobile receipt |
| :---: | :---: |
| ![Charge planner estimate](docs/screenshots/accuracy-app.png) | ![PLN Mobile SPKLU receipt](docs/screenshots/accuracy-receipt.png) |

The app estimates **58.2 kWh** to buy at the meter at **Rp 2,540/kWh**; the receipt shows
**57.34 kWh** actually delivered at the same **Rp 2,540/kWh** all-in tariff — the per-kWh
price is exact and the volume lands within ~1.5 % (the receipt session stopped a little short
of a full charge). The refund maths line up too: bought Rp 152,448, used Rp 145,694.

## Try it first (demo, no account)
Want to see the UI before setting anything up? Run it in **demo mode** — fake but realistic data,
no CarLinko account, no car, no database:
```bash
cd tools && python server.py --demo      # then open http://localhost:8088
# or with Docker:  docker compose run --rm -p 8088:8088 web python server.py --demo 8088
```
A 🧪 *Demo mode* banner makes clear nothing is real. Nice for a quick look or a screenshot.

## Privacy & security
This runs **entirely on your machine** — there is no backend operated by me, and your data is
never sent to any server I control. See **[SECURITY.md](SECURITY.md)** for the full picture; in short:
- Your CarLinko **email/password** are stored locally in `tools/creds.json` (gitignored) and used
  only to log in to **CarLinko's own** cloud (`*.hzhjcl.com`) over TLS — same place the app talks to.
- The only other outbound calls are to **Google Maps** (if you add a key) and free map/route
  services (OpenStreetMap / OSRM) for the trip planner. Nothing else leaves your device.
- Keep the dashboard private (LAN / Tailscale). If it must face the internet, set a
  `dashboard_password` so `/api/summary` isn't open to the world.
- **Car location is opt-in** (`"location": true`). When on, `carlinko.db` holds a history of where the
  car has been, and `/api/location` + `/api/route` serve it. Don't enable it on a dashboard reachable
  from the internet without a `dashboard_password`. Positions never go into `car_report` or the logs.
  Turning it off stops new fixes and hides the card; stored fixes still age out after
  `location_keep_days`. To erase them now, stop the logger and, next to `carlinko.db`, run
  `python -c "import sqlite3; c=sqlite3.connect('carlinko.db'); c.execute('DROP TABLE IF EXISTS positions'); c.commit()"`.
- Found a security issue? See [SECURITY.md](SECURITY.md) — please report privately, don't open a public issue.

## Setup

### Prerequisites
- Python 3.10+, `pip install requests websocket-client`
- A CarLinko account with your car on it
- (optional) a Google Maps API key for the trip planner / SPKLU map

No app capture, no MITM, no decompiling needed — you just log in with your account. (The
signing key is bundled, and the `v-data` blob the app sends turned out to be ignored by the
server, so it's dropped entirely.)

### Account risk — read this first
This dashboard is **unofficial**: it talks to CarLinko's cloud the way the app does, but CarLinko
did not approve it. In November 2026 a user reported that the CarLinko account they ran the
dashboard on was **disabled** ("Your account has been disabled"). We don't know what triggered it.
Any account you log the dashboard into could be disabled the same way, so use it at your own risk.

What the dashboard does to keep its footprint small: one persistent socket instead of polling,
and a **login guard**: automatic re-logins are capped at 6 per hour, back off from 1 minute up to
30 minutes after a failure, and stop completely when CarLinko rejects the account (the dashboard
then shows a banner until you log in again by hand). Keep your install up to date. Older versions
could retry a failing login every few seconds.

### Second account (optional)
CarLinko keeps **one active session per account**, so logging the dashboard in can sign you out
of the official app. You can avoid the clash by giving the dashboard its **own** CarLinko account
(this keeps your main account out of it, but see the risk note above: the reported disabled
account was a second account):

1. Make a second CarLinko account (different email).
2. From your main account, **Me → Authorisation → +** and authorise the second account's email
   to your car.
3. Log the dashboard into the second account; keep the app on your main account.

> Heads-up: the in-app *Authorisation* screen describes Bluetooth control sharing — confirm the
> authorised account can also pull the car over the **cloud** (run `python setup.py` on it; if
> auto-detect finds the vehicle, you're good). If it can't, the alternative is to just use one
> account and accept the occasional re-login.

### Quick start — Windows, no Docker (easiest)
1. On this page click **Code → Download ZIP**, then extract it.
2. Double-click **`start.bat`**. First run installs Python if you lack it (then double-click again)
   and two small libraries.
3. Your browser opens the login page. Enter your CarLinko email + password; it finds your car.

Leave the window open — it runs the dashboard *and* the logger. Same limits as everywhere:
the PC has to stay on to build history. Not on Windows? `python tools/run.py` does the same.

### Quick start — Docker
```bash
docker compose up -d        # then open http://localhost:8088
```
On first open the dashboard shows a **login page** — enter your CarLinko **email + password** and
it logs in and **auto-detects your car** (vehicle id, device SN, VIN, plate, model). That's it.
Prefer the terminal? `docker compose run --rm web python setup.py` does the same interactively.
Everything that persists (creds, token, database) lives in `./data`.

### Quick start — one command (Linux, always-on)

If you have a machine that stays on — a home server, a mini PC, a Raspberry Pi — this does the
whole thing: virtualenv, dependencies, login, and both systemd services so it survives reboots.

```bash
git clone https://github.com/GodrezJr2/openlinko.git
cd openlinko
./tools/install.sh                 # add --tailscale to reach it from your phone anywhere
```

It only asks what it can't work out: your CarLinko login, and your country/currency. Everything
scoped to the current user and this folder — no paths assumed, nothing installed globally except
Tailscale if you ask for it.

```
./tools/install.sh --tailscale     # + private access from anywhere, nothing exposed publicly
./tools/install.sh --port 9000     # different port
./tools/install.sh --no-service    # just set it up; don't install systemd units
```

**Why `--tailscale`?** The logger needs to run 24/7 to build trends, charge history and cost. You'll
want the dashboard on your phone — but this reads your car's data, so you should *not* port-forward
it to the open internet. Tailscale puts the machine and your phone on a private network, so the
dashboard is reachable from anywhere while staying invisible to everyone else. It's free for
personal use.

### Quick start — Python (manual)
```bash
pip install requests websocket-client
cd tools
python setup.py                # interactive config + login + auto-detect car
python logger.py --adaptive    # record telemetry (fast when awake, slow when parked)
python server.py 8088          # dashboard at http://<host>:8088
```
Prefer not to use the helper? `cp creds.example.json tools/creds.json && chmod 600 tools/creds.json`
and fill it in by hand. `creds.json` and `token.txt` are gitignored — never commit them.

Reference systemd units are in [`tools/`](tools/) if you'd rather write them yourself
([logger](tools/carlinko-logger.service), [web](tools/carlinko-web.service)) — but `install.sh`
generates correct ones for your user and paths, so you shouldn't need to.

### `creds.json` reference
| key | required | what |
| --- | --- | --- |
| `email`, `password` | ✅ | your CarLinko login (plaintext over TLS; stored locally only) |
| `region` | | API region, default `sea` (Southeast Asia). **Login fails with the wrong one** — an account made in Europe/Middle East/Africa needs `emea` (reported on a J5 Noble in Israel, [#6](https://github.com/GodrezJr2/openlinko/issues/6)). If a correct password is refused, try another region before anything else |
| `vehicle_id`, `device_sn` | auto | your vehicle id + device serial — **`setup.py` fills these for you** |
| `vehicle` | auto | `{plate, model, vin}` — auto-detected; UI hides plate+VIN by default |
| `battery_kwh`, `wltp_kwh_100` | | usable pack size + WLTP reference. **The car never reports pack size**, so it comes from you or from the [known-cars table](#known-cars); an unrecognised model is asked at setup and labelled *assumed* in the UI until you set it. It scales every kWh, cost and efficiency figure |
| `currency` | | `{symbol, locale, code}` for non-IDR countries, e.g. `{"symbol":"R","locale":"en-ZA","code":"ZAR"}`. Default `Rp` / `id-ID` |
| `tariff`, `petrol_price`, `petrol_kml` | | your local charging tariff/kWh + petrol price/L + economy, in your currency |
| `tyre_unit` | | `psi` (default), `bar`, or `kpa` for the tyre display |
| `tpms_scale` | | raw tyre-byte → kPa scale. J5 is indirect (no real PSI); cars that send real pressure need this recalibrated (see below) |
| `car_image` | auto | override for the dashboard hero picture. Normally unnecessary — `setup.py` saves the render CarLinko hosts of *your* car (right model, right colour) and the server caches it at `/car-photo`. Set this to a filename in `web/` or a full URL only if you'd rather use your own photo |
| `specs` | | brochure figures for the **Specifications** card — `{label, source, performance:[[name,value,unit]], dimensions:[…]}`. Only the J5's are bundled; any other model hides the card rather than showing another car's numbers, so fill this in if you want it |
| `powertrain` | | `auto` (default), `bev` or `phev`. On `auto` the car is treated as a PHEV once it reports a fuel tank — a BEV never does, so this stays off unless it should be on |
| `chemistry` | | `lfp` (default) or `nmc` — picks the battery-care advice |
| `full_charge_days` | | how often to recommend a 100% charge. Default `7` for LFP, `90` for NMC |
| `gmaps_key` | | Google Maps key — enables trip planner + SPKLU map (else OSM fallback) |
| `location` | | `true` turns on **Find my car** and per-trip routes (default `false`). The logger reads the car's position from CarLinko (`/maps/deviceLocate`, a cached fix that doesn't wake the car) and stores it in `carlinko.db`. Not every car has one: if CarLinko answers `50052` three times in a row and has never given this car a fix, the feature pauses itself and asks once a day for two more days, so it comes back on its own if the car gains a position in that time; if every check says `50052` it closes for good (saved in the database, so a restart does not ask again; see docs/LOCATION.md to re-enable) (a car that has had a fix just gets the odd `50052` gap and carries on). Each fix is checked against the last one: a jump farther than the car could have driven (200 km/h, and no more than the odometer moved) is dropped, and a coordinate the cloud sends with its decimal point shifted (101.7 as 10.17 or 1.017, 6.12 as 0.612) is put right, including on the very first position (a shifted longitude is always within ±18 and a shifted latitude within ±9, so only a first position inside one of those bands is read again before it is kept). **Stores where your car has been** — see Privacy below. Restart the logger after changing it. Full guide: [docs/LOCATION.md](docs/LOCATION.md) |
| `location_interval` | | seconds between fixes while driving, default `40` (a fresh fix almost every time). Min `30`: the car only uploads a new position about every 30 s, so a lower value is raised to `30` (reading faster just repeats the same fix and loads CarLinko's API) |
| `location_parked_interval` | | seconds between fixes while parked, default `0` = none (one fix is still read when the car stops and at start-up). Min `300` when set (a lower value is raised to `300`) |
| `location_keep_days` | | days of positions to keep, default `90`; `0` = forever |
| `dashboard_password` | | set it (login page → Advanced) to lock the dashboard behind a password — **do this if the URL is reachable from the internet** |

> **Not in Indonesia? `setup.py` now asks.** It offers presets for Indonesia, South Africa, the UK
> and the Eurozone (and lets you type any other currency), then asks for your charging tariff,
> petrol price and tyre unit — so every cost on the dashboard is in your money without hand-editing
> `creds.json`. Re-run `python setup.py` any time to change them; it keeps your existing values.
> The trip planner + charge map remain Indonesia-only (they use SPKLU/PLN data).
>
> Bundled prices are a *starting point* and go stale — Indonesian defaults are Pertamax at
> Rp16,250/L and PLN SPKLU at Rp2,540/kWh (Jul 2026). Set `petrol_price` / `tariff` to yours.

> **`tariff_idr` is the old name for `tariff`** — still read, so existing configs keep working, but
> prefer `tariff` now that costs aren't Indonesia-only.
>
> **Tyre pressure is now calibrated for you.** CarLinko publishes the per-model tyre formula
> (`appKpaFormula`, e.g. `data * 1.373`), so `setup.py` reads your car's own scale straight off the
> API — no hand-calibration. If you've already set `tpms_scale` yourself, setup keeps your value and
> just mentions what CarLinko says; delete the key to adopt theirs. Pick the display unit with
> `tyre_unit` (`psi`/`bar`/`kpa`).
>
> If the numbers still look wrong, the tyre card shows the **raw bytes** — read one wheel off your
> car's own screen and `tpms_scale = your_kPa / raw_byte`. Note that some cars (the J5 included)
> have *indirect* TPMS and report tyre **status only**, never a real pressure.

### Known cars

Settings other owners have confirmed. Please add yours via a
[car report](https://github.com/GodrezJr2/openlinko/issues/new?template=add-car.yml).

These are **applied automatically** from your detected model — the table lives in
[`tools/known_cars.py`](tools/known_cars.py), and anything you set in `creds.json` still wins.

| Car | `battery_kwh` | `tpms_scale` | `tyre_unit` | Notes |
| --- | --- | --- | --- | --- |
| Jaecoo J5 EV (ID) | `58.9` | n/a | `psi` | Reference car. *Indirect* TPMS — reports tyre **status only**, never a pressure |
| Chery Tiggo 8 PHEV 2025 (ZA) | `18.3` | `1.779` | `bar` | Direct TPMS (raw `136` = 2.42 bar). PHEV — fuel level, fuel consumption and fuel range all decoded ([#2](https://github.com/GodrezJr2/openlinko/issues/2)) |
| Chery Tiggo 7 PHEV (MY) | `18.3` | `1.779` | `psi` | Same pack and tyre scale as the Tiggo 8 PHEV, independently confirmed ([#3](https://github.com/GodrezJr2/openlinko/issues/3)). Malaysia badges it **`TIGGO 7 CSH`** — matched automatically |
| Omoda E5 2025 (UY) | `61` | — | — | LFP, WLTP 15.5 kWh/100 km — owner-confirmed ([#5](https://github.com/GodrezJr2/openlinko/issues/5)). Everything works incl. login, auto-detect and charging |

**If your car isn't listed**, nothing is invented on your behalf: `setup.py` asks for the pack size,
the battery card labels it *assumed* until you set it, and the spec card stays hidden rather than
showing another car's brochure figures.

**PHEVs.** Fuel tank % (byte 21), fuel consumption L/100 km (byte 53) and **fuel range**
(bytes 70–71) are decoded and shown next to the battery. Those bytes read `0` on every BEV frame, so
BEV owners see no fuel UI. `range_km` stays strictly **EV-only** and is labelled *EV range* on a
PHEV; the combined figure the car's own dash shows is **not transmitted** — it is exactly EV + fuel
(verified on three captures), so the app computes it and says so rather than passing it off as the
car's number. Because a PHEV also covers distance on petrol, kWh/100 km and savings-vs-petrol are
approximate on one.

## Where to run it

It needs a host that's on **24/7** (the logger polls continuously to build trends and charge
history). Your daily phone can't be that host: iOS can't run a background server at all, and
Android kills background apps on a phone you carry around. A **spare Android phone left on the
charger** can, though (see [Old Android phone (Termux)](#old-android-phone-termux) below). Your own
phone is then just the browser (add it to your home screen as a PWA).

| Host | Cost | Notes |
| --- | --- | --- |
| A spare PC / old laptop / **Raspberry Pi** at home | free | best privacy; reach it over [Tailscale](https://tailscale.com) |
| A spare **Android phone** on the charger (Termux) | free | no PC needed; see [below](#old-android-phone-termux). Tested on an Android 14 emulator; real-phone reports welcome |
| A small **VPS** (Hetzner, Contabo, DigitalOcean…) | ~$4/mo | easiest always-on; keep it private with Tailscale, or set a `dashboard_password` |
| **Fly.io / Railway / Render** free tier | free | deploy the Docker image; set a `dashboard_password`. A host that gives you one service and one volume can run the logger alongside the dashboard with the start command `bash railway_start.sh` (see below) |
| **Oracle Cloud Free / Google e2-micro** | free | always-on free VM |

> **Public hosting = set a dashboard password.** On a private/home/Tailscale host you can leave it
> open. The moment the URL is reachable from the internet, set a `dashboard_password` (login page →
> Advanced) so only you can open the dashboard.

> **One service, both processes.** `docker compose` runs the dashboard and the logger as two
> services sharing `./data`. A host that attaches a volume to a *single* service (Railway) can't
> do that, so `tools/railway_start.sh` starts the logger in the background and the dashboard in
> the foreground from one container. Set it as the service's start command —
> `bash railway_start.sh` — and put the contents of `creds.json` in a `CREDS_JSON` service
> variable; the script writes it into the volume on every boot. It is deliberately **not** the
> image's default: CarLinko allows one live session per account, so a `docker run` that quietly
> started a logger would knock your own CarLinko app offline.

### Old Android phone (Termux)

Any Android 7+ phone you no longer use can be the always-on box: on the charger, on Wi-Fi, in a drawer.

1. Install **Termux** and **Termux:Boot** from [F-Droid](https://f-droid.org/packages/com.termux/)
   (the Play Store build of Termux is outdated). Open Termux:Boot once.
2. In Termux:
   ```bash
   pkg install -y git && git clone https://github.com/GodrezJr2/openlinko ~/openlinko
   bash ~/openlinko/tools/termux-setup.sh
   ```
3. Open the address it prints and sign in.

It installs Python and two libraries, holds a wake-lock, restarts the dashboard if it ever
exits, and starts it again after a reboot. Control it with `openlinko start | stop | restart |
status | log | update`.

To keep Android from killing it:
- **Settings → Apps → Termux → Battery → Unrestricted.** On Xiaomi / OPPO / vivo / realme also allow
  **Autostart** and lock Termux in the recent-apps screen.
- Android 12+ may kill Termux's child processes ("phantom process killer"). On Android 14+ turn on
  **Developer options → Disable child process restrictions**; on 12–13 run once from a PC:
  `adb shell settings put global settings_enable_monitor_phantom_procs false`.
- To reach it away from home, install the Tailscale app on this phone and on yours.

### Per-OS setup
The Docker path is identical on every OS — install Docker, then `docker compose up -d` and open
`http://localhost:8088`:
- **macOS / Windows**: install [Docker Desktop](https://www.docker.com/products/docker-desktop/), open it, then run the two commands in Terminal / PowerShell from the cloned repo folder.
- **Linux**: `sudo apt install docker.io docker-compose-plugin` (or your distro's equivalent), then the same two commands.

No Docker? Install **Python 3.10+** ([python.org](https://www.python.org/downloads/) on macOS/Windows, `sudo apt install python3 python3-pip` on Linux) and use the *Quick start — Python* steps above.

### Updating a self-hosted box

**Docker:** `git pull && docker compose up -d --build`.

**systemd** (the layout `tools/install.sh` sets up: the units run out of a git checkout). Push your
commits, then from your own machine:

```bash
./tools/deploy.sh user@host          # or set CARLINKO_HOST; an ssh alias works too
```

It refuses if you have unpushed commits or dirty tracked files, fast-forwards the checkout on the
box, then runs `tools/apply.sh` there: restarts only the units whose code changed (web-only edits
need none), checks `/api/status`, then fetches the changed pages back from the running server and
compares them with the repo. So "deployed" means "being served", not just "a file landed". Set
`CARLINKO_DIR` (default `~/j5-ev-dashboard`), `CARLINKO_PORT`, `CARLINKO_BRANCH` or
`CARLINKO_SERVICES` if your layout differs. Or run `tools/apply.sh` on the box itself. The
maintainer's push-to-deploy pipeline is described in [docs/ci-cd.md](docs/ci-cd.md).

### Set it up with an AI coding agent
If the terminal isn't your thing, paste this into an AI coding agent (Claude Code, Cursor, etc.)
running on the machine that will host it:

```text
Set up the open-source project https://github.com/GodrezJr2/openlinko on this machine.
Clone it, then bring it up with Docker (docker compose up -d). It serves a login page on
http://localhost:8088 — tell me the URL when it's running. I'll enter my CarLinko email and
password there myself; do not ask me for them. If Docker isn't available, fall back to the
Python quick-start in the README (pip install requests websocket-client, then run
tools/server.py and tools/logger.py). If the host is reachable from the internet, remind me to
set a dashboard password on the login page's Advanced section.
```

## Head unit add-on: Climate Gesture
Set the fan and temperature from **anywhere on the head unit screen** with two fingers, without
opening the climate screen. Rest two fingers for about a third of a second, then slide:
sideways = fan (1 to 10), up/down = temperature (15.5 to 30.5 °C). A small card shows the value.
It starts by itself after every restart. Tested on a real Jaecoo J5 EV (head unit T13J-INTL
00.04.15, Android 12).

**Step-by-step guide with drawings is built into the dashboard:** run it on a laptop (Windows:
the `start` file, or `python tools/server.py`), log in, then **Account → Head unit add-ons**.
Only want the add-on? No CarLinko login needed: tap **Only want the head unit add-on?** on the
sign-in page, or open `/addons`.
About 10 minutes, parked, no cable. Short version:

1. **Engineering menu** — head unit *Settings → System → Version information*, tap *APP Version*
   10 times, type the **last 6 digits of the SOC Version** as the password.
2. **Enable ADB** — switch it on in Engineering mode. Touch nothing else there.
3. **Same hotspot** — phone hotspot on; head unit (*Connection → WiFi*) and laptop both join it.
4. **Find and install** — tap *Find head unit*, pick it, *Install*.
5. **Try it** — two fingers, hold, slide. Turn the head unit WiFi off again afterwards
   (wireless CarPlay / Android Auto don't work while it's on); the add-on keeps working.

No backup needed: it's an ordinary app install, no system files or car settings change. To undo,
open the Climate Gesture app and tap **Remove Climate Gesture**. Once installed, it closes ADB
over WiFi so nothing else on the network can reach the head unit. **Unofficial** — not from
Jaecoo or Chery; a head unit update may stop it. The installer checks the A/C first and refuses
a head unit it doesn't recognise. Source: [headunit/climate-gesture](headunit/climate-gesture),
APK: [headunit/dist](headunit/dist) (manual `adb` commands are on the add-ons page).

## Going multi-user

This is intentionally **single-tenant per instance**. The clean way to let other owners use
it is to have **each of them run their own instance** with their own `creds.json` — not to
host one service holding everyone's credentials. Different models can override
`battery_kwh` / `wltp_kwh_100` / `tariff_idr`, and the vehicle name/VIN/plate come from
`creds.json`, so the app already adapts per car.

## Project layout
- `tools/` — everything the dashboard runs: `server.py`, `logger.py`, `auth.py`, `run.py`, the
  installers (`install.sh`, `termux-setup.sh`, `start.bat` at the root) and deploy scripts
- `web/` — the PWA (`v2.html` default, `index.html` classic, vendored `leaflet.*` / `three.module.min.js`)
- `headunit/` — the Climate Gesture head-unit add-on (Java source + built APK)
- `docs/` — API map, control opcodes, CI/CD, Home Assistant notes, car location
- `research/` — the reverse-engineering scripts behind those docs; not needed to run anything ([README](research/README.md))
- `PRODUCT.md`, `DESIGN.md` — product + visual design notes

## Related projects

OpenLinko was the first open-source CarLinko client (June 2026). Open-source projects built
alongside it, on the same cloud:

- [elad-bar/ha-carlinko](https://github.com/elad-bar/ha-carlinko) + [carlinko-card](https://github.com/elad-bar/carlinko-card) — native Home Assistant integration with remote controls and a Lovelace card. elad-bar extracted the control opcode table this repo now uses ([#11](https://github.com/GodrezJr2/openlinko/issues/11)).
- [jebentancour/ha-carlinko](https://github.com/jebentancour/ha-carlinko) — Home Assistant integration, read-only (Omoda E5, Uruguay). jebentancour also found the REST telemetry endpoint and decoded more of the blob ([#5](https://github.com/GodrezJr2/openlinko/issues/5), [#15](https://github.com/GodrezJr2/openlinko/issues/15)).
- [thititongumpun/ha-carlinko](https://github.com/thititongumpun/ha-carlinko) — Home Assistant integration (Omoda C5 EV, Thailand).

The protocol notes in [docs/api-map.md](docs/api-map.md) and [docs/control-opcodes.md](docs/control-opcodes.md)
are a shared reference; corrections from any of these projects are welcome.

## Third-party clients

Clients other people have built against this server's `/api/*` contract. Listed so you can
find them, not as a recommendation: this project has not audited them, and each is the
responsibility of whoever publishes it.

- **[Voltmoss](https://voltmoss.web.app)** — a native iOS and Android app (home-screen widgets,
  charge and trip planning, remote commands) that points at an instance you host; it does nothing
  without one. **Closed source**, and it **contains ads and analytics** — Google AdMob, Firebase
  Analytics and Crashlytics (analytics opt-out in its Settings) — and sells **optional in-app
  purchases** (ad removal, a Voltmoss Plus subscription). By
  [@anderscheow](https://github.com/anderscheow); support and bug reports go to
  <ll123mg@gmail.com>, not to this tracker. Parts of it are derived from this project under MIT
  and credited on its open-source licences screen.

## Contributing
Other Jaecoo / CarLinko owners welcome — an [Add my car](https://github.com/GodrezJr2/openlinko/issues/new?template=add-car.yml) report
is the most useful thing right now: in the dashboard, **Account → Report my car** copies a redacted
report (no plate, VIN or location) to paste into it. See
[CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md) for privacy/security.
Questions → [Discussions](https://github.com/GodrezJr2/openlinko/discussions).

## License
[MIT](LICENSE). Not affiliated with Jaecoo, Chery, or CarLinko. Trademarks belong to their owners.
