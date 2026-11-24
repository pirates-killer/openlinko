# Car location (Find my car)

> **Opt-in, off by default.** With `"location": false` (or unset) nothing here runs: no thread, no
> `positions` table, no extra requests to CarLinko.

OpenLinko can keep track of where the car is: a **Find my car** map, a **Navigate** button that hands
the spot to your phone's maps app, and the **route of each trip**. The position comes from CarLinko's
own cloud (`/maps/deviceLocate`), the same cached fix the official app shows. Reading it doesn't wake
the car.

Not every car has one. A Tiggo 7 CSH in Malaysia reports a position. A Jaecoo J5 in Indonesia
doesn't: the cloud answers `50052`, and after three tries the feature pauses itself, asking again once
a day. If you
try it on another model, a note in [#23](https://github.com/GodrezJr2/openlinko/issues/23) helps.

## Before you start
- **It stores where your car has been.** Keep the dashboard on your LAN or Tailscale, or set a
  `dashboard_password`. The logger prints a warning at start-up if location is on without one.
  See [Privacy & security](../README.md#privacy--security).
- The logger must be running (`carlinko-logger`). The server only reads what the logger stored.

## Turn it on
Add to `tools/creds.json` and restart the logger:

```json
{
  "location": true,
  "location_interval": 40,
  "location_parked_interval": 0,
  "location_keep_days": 90
}
```

The log should then say:

```
location: on (every 40s while moving, only on stop while parked, keep 90 days)
```

| Setting | Default | Meaning |
|---|---|---|
| `location` | `false` | `true` turns the feature on. |
| `location_interval` | `40` | Seconds between fixes while driving. **Minimum `30`**: a lower value is raised to 30 (see [How often](#how-often)). The default gets a fresh fix almost every time. |
| `location_parked_interval` | `0` | Seconds between fixes while parked. `0` = none: one fix is still read when the car stops and at start-up. Minimum `300` when set. |
| `location_keep_days` | `90` | Days of positions to keep. `0` = forever. |

Settings are read when the logger starts. Restart it after a change.

## What you get
- **Classic** (`/index.html`): a *Find my car* card on the **Trips** tab, with the last fix, its
  age, Navigate and Share. Tap a trip to draw its route. A fix read while moving that is more than
  5 minutes old shows only *last seen …*, not *moving*, in case the stop fix never landed.
- **v2** (`/`): a *Location* row on Home and a **Location** page with the map, Navigate, Share,
  the *Last trip* (tap for its route), *Back to the car*, and *Trips by day*, which opens the
  calendar on Distance. `/#loc` opens the page directly. The row reads *Moving · 1 min ago* or
  *Parked · 3 d ago*; an old moving fix reads *Last seen 3 d ago*.
- **Any day's routes, from the calendar.** Pick a day on the Distance calendar (v2), or on the
  classic page's calendar view: every drive of that day with a recorded route gets its own colour.
  In v2 the day card shows them on a map, and tapping a drive focuses it (tap again for the whole
  day). In classic the day sheet lists the drives; tap one for its route, or *Show this day's
  routes* for all of them, on the *Find my car* map. Days from before the first stored position
  have no map.
- Routes longer than 2,000 points (multi-day outings only) are thinned evenly.
- **Navigate** opens the device's own chooser: `geo:` on Android (any installed maps app), Apple
  Maps on iPhone and iPad, Google Maps directions on a desktop.
- **Share location** uses the system share sheet where there is one (coordinates plus a Google Maps
  link). Otherwise the button reads **Copy location** and copies the coordinates.

**Map tiles** come from OpenStreetMap's tile server, loaded by your browser, under the
[OSMF Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/). The map always shows
the credit "© OpenStreetMap contributors" (linked to the
[copyright page](https://www.openstreetmap.org/copyright); the data is under the ODbL) and a
*Report a map issue* link. The policy requires a Referer on tile requests from web pages, so the
tiles set `referrerPolicy="strict-origin-when-cross-origin"`: only the dashboard's origin is sent,
even behind a reverse proxy that sets a stricter page-wide `Referrer-Policy`. If you run OpenLinko
behind a proxy, don't put a tile cache in front of `tile.openstreetmap.org` (the policy doesn't
recommend one), and never strip the Referer.

## How it works
The logger is the **only** thing that calls CarLinko for the position. It runs as a thread in the
logger process, reuses the logger's `token.txt`, never logs in by itself, and stays silent while
the login guard holds. The server just reads the `positions` table (`/api/location`, `/api/route`).
Every open tab reads that table, never the cloud.

**When a fix is read:**
- every `location_interval` seconds **while the car is moving** (speed > 0, or the odometer went up
  in the last 3 minutes)
- once **when the car stops**, so *Find my car* shows where it was left
- once **at start-up**
- every `location_parked_interval` seconds while parked, if you set it

A start-up or stop fix that fails is retried after 1, 1, 2, 4 and 8 minutes. If none of those six
reads lands, the thread waits until the car moves again, so a parked car that only gets `50052` or
errors costs six requests, not one a minute.

### How often
The car uploads its position to the cloud about **every 30 seconds**. On a Tiggo 7, reads 25–30 s
apart got the same cached fix back 12–15% of the time while driving. Reading faster than the car
uploads only repeats the last fix and adds load on CarLinko's API, so `location_interval` can't go
below 30. A value a little above the upload rate gets a new fix on almost every read, so the default
is 40 s: on a Tiggo 7 drive at 40 s, none of 29 reads while moving repeated the previous fix.

### `50052` — no position
`50052 查询定位失败` ("location query failed") has two meanings:
- **The car has no position in the cloud at all** (J5, Indonesia). If the car has **never** produced
  a fix (the `positions` table is empty) and three reads in a row say `50052`, the thread pauses.
  It then asks once a day for two more days. Only a `50052` answer counts as one of those checks: a
  timeout, a network error, a stale token or the login guard is no answer, and that check is tried
  again an hour later. If the car gains a position in that time, location
  comes back by itself, without a restart. If all of those say `50052` too, the thread **closes for
  good**: about five requests in total, then none, and the decision is saved in the database
  (`loc_state` table), so a restart doesn't start the asking over. A different car or account
  (`device_sn`) gets its own three tries, and the old car's stored positions don't count for it
  (`loc_state` remembers which car they came from). To ask again on the same car, run
  `python3 -c "import sqlite3; c=sqlite3.connect('carlinko.db'); c.execute('DELETE FROM loc_state'); c.commit()"`
  next to `carlinko.db` and restart the logger.
- **A one-off gap.** A car that normally reports a position also answers `50052` now and then,
  mid-drive, between good fixes. It isn't a rate limit: the next read is fine. Once the car has any
  fix stored, `50052` is logged and the normal schedule carries on.

## How a position is checked
CarLinko's cached position is usually right, but not always: now and then it is far off, or one
coordinate arrives with its **decimal point shifted** left, every digit still there. A car at
E 101.77 came back as `10.177`, and the cloud's own geocoder put it in Cameroon (reported by
[@anderscheow](https://github.com/anderscheow) in [#23](https://github.com/GodrezJr2/openlinko/issues/23)).
A Tiggo 7 in Malaysia showed all three kinds in one night: a longitude ÷ 10, a longitude ÷ 100
(like E 100.36 as `1.0036`) and a latitude ÷ 10 (like N 6.12 as `0.612`). So every position goes
through these steps before it is stored. Nothing is smoothed or snapped to roads: a position is kept
as read, unshifted, or not stored at all, so the map never draws a spike to another continent.

```
new position from CarLinko
  │
  ├─ nothing stored yet? ──► 1. first-position check (lng ±18, lat ±9)
  │
  └─ compare with the last good position ──► 2. jump check (haversine + allowance)
        ├─ fits ............................... keep it
        ├─ unshifted (× 10 / × 100) it fits ... 3. repair it, keep it
        ├─ the stored one unshifted fits ...... 3. correct the stored one, keep this one
        └─ none of these ...................... drop it ── 4. three drops that agree: keep
```

### 1. The first position: the band check
The very first position has nothing to be compared with. The check uses one fact: a shifted
coordinate is the real one divided by 10 or 100, the largest longitude is 180 and the largest
latitude 90, so **a shifted longitude is always between −18 and +18, and a shifted latitude between
−9 and +9**.

- **Outside both bands** (Thailand and north of it, most of Asia, Australia, the Americas): it can't
  be a shifted reading. It is stored straight away, with no extra request.
- **Inside a band** it is ambiguous: a real place (Europe, Africa, or anywhere near the equator such
  as Malaysia, Singapore and Indonesia) or a shifted reading from elsewhere. The logger holds it and
  reads again **45 s later**, once the cloud has refreshed (about every 30 s):
  - if one reading is the other with a coordinate × 10 or × 100, the **larger one is kept**. The
    cloud only ever shifts the point left.
  - if they agree, the first is stored and the second goes through the jump check as usual.
  - if the second read gets no position (three tries), the first is stored as read; step 3 corrects
    it later if it was shifted.

At most one extra request per install, and only when the first position is inside a band. The
quirk comes and goes (a Tiggo 7 in Malaysia showed none in its first 681 positions, then three in
one night, hours apart; another car showed it twice in a day), so two shifted readings in a row are
unlikely.

### 2. Every position after that: the jump check
Every new position is compared with the last good one using the great-circle (haversine) distance.
It is kept if it is no farther than the car could have driven:

```
allowed km = min(200 km/h × time since the last good position,  km on the odometer since then + 1)  + 2
```

- The time runs from the last **good** position, so `50052` gaps only widen the allowance and
  never cause a good position to be dropped.
- The odometer keeps a parked car tight: parked for a week, a position may be about 3 km off, not
  33,000. The `+ 1` covers the odometer's whole-km steps. The `+ 2` covers GPS jitter and the age
  of the cloud's cached position.
- With no telemetry for the period (the logger was down), only the 200 km/h limit applies.

Checked against 681 real positions from a Tiggo 7: none dropped, with at least 1.8 km to spare.
The check costs about 11 µs per position on a Raspberry Pi 5.

### 3. A shifted coordinate: the two repairs
- **The new position is shifted.** When it jumps more than **500 km** and the position with its
  longitude or latitude × 10 or × 100 fits the jump check (and lands 10 times closer than the raw
  reading), that unshifted position is stored instead.
- **The stored position was shifted** (both reads in step 1 were shifted, which is rare). When a new
  position fails the jump check but lands exactly where the stored one would be unshifted, the
  stored one and the positions just before it that were shifted the same way are corrected, and the
  new one is kept at once.

Both use the same guards: only for jumps over 500 km, and the unshifted reading must fit the
allowance and be 10 times closer. A real drive near longitude 0 (London: −0.12 → −0.012 is 7.5 km)
is therefore never "repaired", and history that was right is never rewritten. A shifted latitude
close to the equator (Singapore: 1.35 → 0.135 is 135 km) is under 500 km, so it is simply dropped by
the jump check. This works in any region; there is no region table.

### 4. When the car really moved: three that agree
A dropped position is remembered. The next one is compared with **that dropped one**: if they agree
(within the allowance), the count goes up, otherwise it starts over. When **three dropped positions
in a row agree** on a new place, the car really moved while nothing was read (a ferry, a tow truck,
the logger was down), and the new place is kept. That takes about 2 minutes while driving, or three
parked reads.

### Examples

| Situation | What happens |
|---|---|
| Normal driving, 40 s at 60 km/h (0.7 km) | allowed ≈ 3–4 km: kept |
| GPS glitch while parked, pin 15 km away | odometer flat, allowed 3 km: dropped |
| First position 13.75, 100.50 (Bangkok) | outside both bands: kept at once |
| First position 6.12, 100.36 (Malaysia) | latitude inside ±9: second read agrees, kept (one extra request) |
| First position 6.12, 10.036 (the quirk) | inside ±18: second read 100.36 is × 10, so 100.36 is kept |
| First position 6.12, 1.0036 | inside ±18: second read 100.36 is × 100, so 100.36 is kept |
| First position 0.612, 100.36 | inside ±9: second read 6.12 is × 10, so 6.12 is kept |
| First position 13.40 (Berlin), second 13.40 | they agree: kept |
| Mid-drive 100.48 → 10.048 | 9,900 km jump, × 10 fits: repaired to 100.48 |
| Parked 100.36 → 1.0036 or 6.12 → 0.612 | jump over 500 km, × 100 / × 10 fits: repaired |
| Both first reads 10.048, then 100.48 | the stored ones are corrected, 100.48 kept |
| Car on a ferry (moved, odometer flat) | dropped, dropped, then kept on the third agreeing read |
| `50052` mid-drive | no position this time; the next read carries on |

## Log lines

| Line | Meaning |
|---|---|
| `location: on (every 40s while moving, …)` | Started with these settings. |
| `location: WARNING no dashboard_password is set …` | Location is on and the dashboard is open to anyone who can reach it. |
| `location: location_interval=5 is below the minimum, using 30` | Your setting was raised to the floor. |
| `location: no fix this time (50052): call 57 since start, 100 km/h, last fix 31s ago; still trying` | A one-off gap. Nothing to do. |
| `location: CarLinko has no position for this car (50052); location capture is paused, checking again once a day for 2 more days` | This car may have no cloud position. Three asks said so. |
| `location: still no position for this car; checking again in 24 h` | A daily check, still `50052`. |
| `location: CarLinko still has no position for this car after 3 days of asking; location capture is closed and will not ask again, even after a restart` | Given up. No more requests until the `loc_state` row is deleted (see `50052` above). |
| `location: closed earlier -- CarLinko has no position for this car; not asking again` | The logger restarted and kept the saved decision. |
| `location: CarLinko has a position for this car now; location capture is back on` | The daily check found a position. |
| `location: dropped a fix 44 km from the last one (allowed 3.7 km; 61s after it, 2600 km/h implied)` | An impossible jump was ignored. The line gives distance, time and implied speed, never coordinates, so it is safe to paste in a bug report. |
| `location: 3 fixes in a row agree on a new place; taking it …` | The car moved while no fix was read. |
| `location: checking the first position with a second read in 45s` | Step 1: the first position is inside a band. |
| `location: the first position had its decimal point shifted; kept the second read` | Step 1 caught the quirk. |
| `location: no second read to check the first position against; keeping it …` | Step 1 got no second position; step 3 covers it. |
| `location: CarLinko sent a position with its decimal point shifted; using it unshifted …` | Step 3: the new position was shifted, repaired. |
| `location: the stored position had its decimal point shifted; corrected 2 rows and kept the new read` | Step 3: the stored one was shifted, corrected. |
| `location: request failed: ReadTimeout(…)` | CarLinko didn't answer in time. Retried on the normal schedule. |
| `location: no parked position after 6 reads; waiting until the car moves again` | The stop or start-up fix kept failing; no more reads until the next drive. |
| `location: the daily check got no answer; trying again in 1 h` | While paused for `50052`: a timeout or error, which doesn't count as a check. |
| `location: a different car than the stored positions; its own position is read from scratch` | `device_sn` changed. The old car's rows stay in the history but aren't used for this car. |

None of them print coordinates.

## Turning it off and erasing it
Set `"location": false` and restart the logger. New fixes stop and the card is hidden. Stored
fixes still age out after `location_keep_days`. To erase them now, stop the logger and, next to
`carlinko.db`, run:

```
python -c "import sqlite3; c=sqlite3.connect('carlinko.db'); c.execute('DROP TABLE IF EXISTS positions'); c.commit()"
```

## For developers
The cloud call and its quirks are in [api-map.md → Car position](api-map.md#car-position--mapsdevicelocate),
and the two read-only endpoints in [api-map.md → `/api/location`, `/api/route`](api-map.md#car-position--apilocation-apiroute-opt-in).
The code is the `location` section of `tools/logger.py` and `location_latest` / `location_route` in
`tools/server.py`. In the logger, `_loc_step()` is one tick of the thread (so it can be tested with a
fake clock), `_loc_confirm()` is step 1, `_loc_gate()` steps 2 and 3 for the new position,
`_loc_repair_stored()` step 3 for the stored one, and `location_loop()` just calls `_loc_step()` every 5 s.

Tests: `python3 tools/location_selftest.py` (44 checks, no network, no real data; based on
anderscheow's self-test). It covers the reader, the motion check, retention, both endpoints, every
step above, `50052`, and that no log line carries a coordinate.
