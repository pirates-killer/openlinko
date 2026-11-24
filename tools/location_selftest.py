#!/usr/bin/env python3
"""Checks for the opt-in car location feature (#23): reading CarLinko's cached position, the checks
every position goes through (first-position check, jump check, shifted-coordinate repairs, 50052), and the
server's two read-only views. Nothing here touches the network or real data.

    python3 tools/location_selftest.py

Based on anderscheow's tools/location_selftest.py (https://github.com/anderscheow/openlinko, commit
926e795, MIT), adapted to this branch: there is no region box or dashboard switch here, the location
thread is driven through _loc_step() with a fake clock, and the first-position (lng +-18, lat +-9) and
stored-fix repair cases are added. anderscheow's case (E 101.77414 sent as 10.177414) is used as is, plus
the three shifts a Tiggo 7 showed in one night (lng / 10, lng / 100, lat / 10).
"""
import atexit
import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import math
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock, patch

_TMP = tempfile.TemporaryDirectory()
atexit.register(_TMP.cleanup)
os.environ["CARLINKO_DATA"] = _TMP.name        # both modules read it at import: never the real creds.json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auth     # noqa: E402
import logger   # noqa: E402
import server   # noqa: E402

KL = (3.139, 101.6869)                        # a plausible fix in Kuala Lumpur
BKK = (13.7563, 100.5018)                     # Bangkok: outside both first-fix bands, so kept at once
SHORT_CASE = (3.048407, 10.177414)            # anderscheow's live case: E 101.77414 lost a digit
SHORT_REAL = (3.048407, 101.77414)
# The three shifts a Tiggo 7 in Malaysia showed in one night, every digit kept (the last two one second
# after a parked read of the same spot). Made-up places with the same shape, not the car's real ones.
T7_SPOT = (6.121347, 100.367198)
T7_LNG10 = (6.118263, 10.036142)       # real (6.118265, 100.361417): / 10, mid-drive
T7_LNG100 = (6.121313, 1.003672)       # real (6.121314, 100.367198): / 100, parked
T7_LAT10 = (0.612133, 100.367191)      # real (6.121319, 100.367208): latitude / 10, parked


class FixTest(unittest.TestCase):
    def test_only_plausible_fixes_pass(self):
        self.assertEqual(logger._loc_fix({"lat": 3.139, "lng": 101.6869}), KL)
        self.assertEqual(logger._loc_fix({"lat": "3.139", "lng": "101.6869"}), KL)
        for bad in (None, [], "x", {}, {"lat": None, "lng": 1}, {"lat": "abc", "lng": 1},
                    {"lat": 0, "lng": 0},                       # the "no fix" placeholder
                    {"lat": 91, "lng": 0}, {"lat": 0, "lng": 181},
                    {"lat": math.nan, "lng": 1}, {"lat": math.inf, "lng": 1}):
            self.assertIsNone(logger._loc_fix(bad), bad)

    def test_config_typos_fall_back_instead_of_raising(self):
        with patch.dict(logger._C, {"location_interval": "soon", "location_keep_days": ""}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(logger._loc_int("location_interval", 40, 30, 86400), 40)
            self.assertEqual(logger._loc_int("location_keep_days", 90, -1, 36500), 90)
        with patch.dict(logger._C, {"location_interval": 1}):
            self.assertEqual(logger._loc_int("location_interval", 40, 30, 86400), 30)   # clamped, not obeyed
        self.assertFalse(logger._loc_flag("false"))
        self.assertTrue(logger._loc_flag("true"))
        self.assertFalse(logger._loc_flag(None))


class LocateTest(unittest.TestCase):
    """locate() is the only code in this feature that talks to CarLinko."""

    def setUp(self):
        for name, fn in (("login_status", lambda: None), ("api_base", lambda: "https://api.invalid"),
                         ("headers_for", lambda body, token=None: {"t": token})):
            p = patch.object(auth, name, fn)
            p.start()
            self.addCleanup(p.stop)
        for name, value in (("_cfg", lambda: {"device_sn": "SN1"}), ("_loc_token", lambda: "tok")):
            p = patch.object(logger, name, value)
            p.start()
            self.addCleanup(p.stop)

    def post(self, reply):
        resp = MagicMock()
        resp.json.return_value = reply
        return patch("requests.post", return_value=resp)

    def test_reads_the_cached_position_with_the_exact_request_the_cloud_accepts(self):
        with self.post({"code": "0000", "data": {"lat": 3.139, "lng": 101.6869, "address": None}}) as post:
            self.assertEqual(logger.locate(), KL)
        (url,), kw = post.call_args
        self.assertEqual(url, "https://api.invalid/maps/deviceLocate")
        self.assertEqual(kw["json"], {"sn": "SN1", "showAddress": 1})
        self.assertIs(type(kw["json"]["showAddress"]), int)       # JSON true is answered 1000 "unknown error"
        self.assertEqual(kw["headers"], {"t": "tok"})

    def test_the_reader_passes_a_short_longitude_through_untouched(self):
        # Repairs happen where there is something to compare with (the loop), never on the raw read.
        with self.post({"code": "0000", "data": {"lat": SHORT_CASE[0], "lng": SHORT_CASE[1]}}):
            self.assertEqual(logger.locate(), SHORT_CASE)

    def test_50052_means_no_position_this_time(self):
        with self.post({"code": "50052", "msg": "查询定位失败"}):
            self.assertEqual(logger.locate(), "unsupported")

    def test_everything_else_is_a_quiet_retry_later(self):
        for reply in ({"code": "9997"}, {"code": "0000", "data": {"lat": 0, "lng": 0}},
                      {"code": "1000", "msg": "x"}, ["not", "a", "dict"], {"code": "0000", "data": None}):
            with self.post(reply), contextlib.redirect_stdout(io.StringIO()):
                self.assertIsNone(logger.locate(), reply)
        with patch("requests.post", side_effect=OSError("down")), contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(logger.locate())

    def test_no_request_while_the_login_guard_holds_or_before_setup(self):
        with self.post({"code": "0000", "data": {"lat": 1, "lng": 1}}) as post:
            with patch.object(auth, "login_status", lambda: {"blocked": True, "wait": None, "reason": "x"}):
                self.assertIsNone(logger.locate())
            with patch.object(logger, "_loc_token", lambda: ""):
                self.assertIsNone(logger.locate())
            with patch.object(logger, "_cfg", lambda: {}), patch.object(logger, "SN", ""):
                self.assertIsNone(logger.locate())
        post.assert_not_called()


class MotionAndRetentionTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(logger.SCHEMA)
        self.addCleanup(self.conn.close)
        self.now = int(time.time())

    def frame(self, age, odo, raw=None):
        self.conn.execute("INSERT INTO telemetry(ts, odo_guess, raw) VALUES (?,?,?)", (self.now - age, odo, raw))

    def test_moving_means_speed_or_an_advancing_odometer_in_a_fresh_frame(self):
        self.assertFalse(logger._loc_moving(self.conn))                   # no frames at all
        self.frame(200, 1000); self.frame(5, 1000)
        self.assertFalse(logger._loc_moving(self.conn))                   # parked: odometer flat
        self.frame(2, 1003)
        self.assertTrue(logger._loc_moving(self.conn))                    # odometer advanced
        self.conn.execute("DELETE FROM telemetry"); self.frame(5, 1000, "ab")
        with patch.object(logger, "decode", return_value={"speed": 12}):
            self.assertTrue(logger._loc_moving(self.conn))                # speed reading wins
        with patch.object(logger, "decode", side_effect=ValueError("bad blob")):
            self.assertFalse(logger._loc_moving(self.conn))               # malformed blob = no reading

    def test_a_stale_frame_is_never_motion(self):
        self.frame(600, 1000); self.frame(400, 1050)
        self.assertFalse(logger._loc_moving(self.conn))

    def test_purge_drops_only_what_is_older_than_the_keep_window(self):
        self.conn.executescript(logger.LOC_SCHEMA)
        day = 86400
        for age_days in (200, 91, 89, 1):
            self.conn.execute("INSERT INTO positions(ts, lat, lng, moving) VALUES (?,?,?,0)",
                              (self.now - age_days * day, 1.0, 2.0))
        with patch.object(logger, "LOC_KEEP", 90):
            logger._loc_purge(self.conn)
        left = [r[0] for r in self.conn.execute("SELECT ts FROM positions ORDER BY ts")]
        self.assertEqual(left, [self.now - 89 * day, self.now - 1 * day])
        with patch.object(logger, "LOC_KEEP", 0):                         # 0 = keep forever
            self.conn.execute("INSERT INTO positions(ts, lat, lng, moving) VALUES (1, 1.0, 2.0, 0)")
            logger._loc_purge(self.conn)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM positions WHERE ts = 1").fetchone()[0], 1)

    def test_purge_without_a_positions_table_is_a_no_op(self):
        with patch.object(logger, "LOC_KEEP", 90):
            logger._loc_purge(self.conn)                                  # location was never on


class ServerHarness(unittest.TestCase):
    """A dashboard on a throwaway data dir; no tests of its own."""
    def setUp(self):
        self.data = tempfile.TemporaryDirectory()
        self.addCleanup(self.data.cleanup)
        for name, value in (("_DATA", self.data.name), ("DEMO", False),
                            ("DB", os.path.join(self.data.name, "carlinko.db"))):
            p = patch.object(server, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_port
        server._ensure_db()
        self.now = int(time.time())

    def creds(self, **kw):
        with open(os.path.join(self.data.name, "creds.json"), "w") as f:
            json.dump(kw, f)

    def seed(self, rows):
        conn = sqlite3.connect(server.DB)
        conn.executescript(logger.LOC_SCHEMA)
        conn.executemany("INSERT INTO positions(ts, lat, lng, moving) VALUES (?,?,?,?)", rows)
        conn.commit()
        conn.close()

    def get(self, path, cookie=None):
        req = urllib.request.Request(self.base + path, headers={"Cookie": cookie} if cookie else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            self.addCleanup(e.close)
            return e.code, None


class ServerTest(ServerHarness):
    def test_off_by_default_even_when_positions_exist(self):
        self.seed([(self.now - 10, 3.139, 101.6869, 1)])
        for creds in ({}, {"location": False}, {"location": "false"}, {"location": 0}):
            self.creds(**creds)
            _, loc = self.get("/api/location")
            self.assertFalse(loc["enabled"], creds)
            self.assertIsNone(loc["lat"], creds)
            _, route = self.get("/api/route?from=0&to=%d" % self.now)
            self.assertEqual(route.get("points"), [], creds)

    def test_demo_never_serves_a_position(self):
        self.creds(location=True)
        self.seed([(self.now - 10, 3.139, 101.6869, 1)])
        with patch.object(server, "DEMO", True):
            _, loc = self.get("/api/location")
        self.assertFalse(loc["enabled"])
        self.assertIsNone(loc["lat"])

    def test_latest_fix_and_age_and_since(self):
        self.creds(location=True)
        _, none_yet = self.get("/api/location")                           # logger not restarted yet: no table
        self.assertEqual((none_yet["enabled"], none_yet["lat"]), (True, None))
        self.seed([(self.now - 7200, 1.0, 2.0, 1), (self.now - 60, 3.139, 101.6869, 0)])
        _, loc = self.get("/api/location")
        self.assertEqual((loc["lat"], loc["lng"], loc["moving"]), (3.139, 101.6869, False))
        self.assertIn(loc["age_s"], range(60, 70))
        self.assertEqual(loc["since"], self.now - 7200)

    def test_route_is_one_outing_padded_ordered_and_bounded(self):
        self.creds(location=True)
        t = self.now - 10 * 86400
        self.seed([(t - 1000, 9.0, 9.0, 0), (t - 200, 1.0, 1.0, 1), (t, 2.0, 2.0, 1),
                   (t + 600, 3.0, 3.0, 1), (t + 900, 4.0, 4.0, 0), (t + 5000, 9.0, 9.0, 0)])
        _, route = self.get("/api/route?from=%d&to=%d" % (t, t + 600))
        self.assertEqual([p[0] for p in route["points"]], [1.0, 2.0, 3.0, 4.0])   # +-300 s pad
        self.assertEqual(route["points"][0], [1.0, 1.0, t - 200])
        _, wide = self.get("/api/route?from=%d&to=%d" % (t, t + 4 * 86400))       # beyond the 3-day cap
        self.assertEqual(wide.get("points"), [])
        _, backwards = self.get("/api/route?from=%d&to=%d" % (t + 5, t))
        self.assertEqual(backwards.get("points"), [])
        _, huge = self.get("/api/route?from=0&to=%d" % (2 ** 62))             # must not overflow SQLite
        self.assertEqual(huge.get("points"), [])
        status, _ = self.get("/api/route?from=abc&to=1")
        self.assertEqual(status, 400)

    def test_after_a_car_swap_find_my_car_does_not_show_the_old_car(self):
        self.creds(location=True)
        self.seed([(self.now - 7200, 3.139, 101.6869, 0)])                       # the old car's last fix
        conn = sqlite3.connect(server.DB)
        logger._loc_kv_set(conn, sn="NEW", sn_since=self.now - 7200)             # as the logger records a swap
        conn.close()
        _, loc = self.get("/api/location")
        self.assertIsNone(loc["lat"])                                            # nothing for the new car yet
        self.assertEqual(loc["since"], self.now - 7200)                          # old trips keep their routes
        self.seed([(self.now - 30, 52.52, 13.405, 1)])                           # the new car's first fix
        _, loc = self.get("/api/location")
        self.assertEqual((loc["lat"], loc["ts"]), (52.52, self.now - 30))

    def test_latest_still_works_without_loc_state(self):
        # A positions table from before loc_state existed (logger not restarted yet).
        self.creds(location=True)
        conn = sqlite3.connect(server.DB)
        conn.execute("CREATE TABLE positions (ts INTEGER PRIMARY KEY, lat REAL, lng REAL, moving INTEGER)")
        conn.execute("INSERT INTO positions VALUES (?, 3.139, 101.6869, 0)", (self.now - 60,))
        conn.commit(); conn.close()
        _, loc = self.get("/api/location")
        self.assertEqual(loc["lat"], 3.139)

    def test_calendar_drives_carry_the_times_a_route_needs(self):
        # /api/history's per-day drives get start_ts/end_ts, so a calendar day can open each drive's route.
        t0 = int(time.mktime((2026, 3, 10, 8, 0, 0, 0, 0, -1)))
        legs = [{"start_ts": t0, "end_ts": t0 + 900, "km": 12},
                {"start_ts": t0 + 1000, "end_ts": t0 + 1800, "km": 9},           # parked < 20 min: same outing
                {"start_ts": t0 + 9000, "end_ts": t0 + 9600, "km": 7}]           # a second outing
        conn = sqlite3.connect(server.DB)
        conn.execute("INSERT INTO telemetry(ts, dt, online, raw) VALUES (?, ?, 1, 'x')",
                     (t0, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0))))
        conn.commit(); conn.close()
        with patch.object(server, "decode_cached", return_value={}), \
                patch.object(server, "build_trips", return_value=legs), \
                patch.object(server, "day_energy", return_value={}), \
                patch.object(server, "day_regen", return_value={}), \
                patch.object(server, "day_regen_kw", return_value={}), \
                patch.object(server, "build_sessions", return_value=[]):
            h = server.month_history("2026-03")
        drives = h["days"][9]["trips"]
        self.assertEqual([(d["start_ts"], d["end_ts"], d["km"]) for d in drives],
                         [(t0, t0 + 1800, 21), (t0 + 9000, t0 + 9600, 7)])
        self.assertEqual(set(drives[0]), {"from", "to", "km", "min", "start_ts", "end_ts"})

    def test_a_long_route_is_thinned_evenly_keeping_both_ends(self):
        self.creds(location=True)
        t = self.now - 5 * 86400
        self.seed([(t + 30 * i, 3.0 + i * 1e-5, 101.0, 1) for i in range(8600)])   # 3 days at 30 s, worst case
        _, route = self.get("/api/route?from=%d&to=%d" % (t, t + 30 * 8599))
        pts = route["points"]
        self.assertEqual(len(pts), server.ROUTE_SEND_POINTS)
        self.assertEqual((pts[0][2], pts[-1][2]), (t, t + 30 * 8599))
        self.assertEqual([p[2] for p in pts], sorted(p[2] for p in pts))

    def test_both_endpoints_need_a_session_when_the_dashboard_is_gated(self):
        self.creds(location=True)
        self.seed([(self.now - 10, 3.139, 101.6869, 1)])
        server.set_dashboard_password("test-password")
        for path in ("/api/location", "/api/route?from=0&to=%d" % self.now):
            self.assertEqual(self.get(path)[0], 401, path)
            self.assertEqual(self.get(path, "sid=" + server.make_session())[0], 200, path)


class LoopHarness(unittest.TestCase):
    """The location thread, one _loc_step() at a time, on a fake clock and an in-memory database."""

    def setUp(self):
        for name, value in (("LOC_PARKED", 0), ("LOC_EVERY", 40)):
            p = patch.object(logger, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.locate = MagicMock(return_value=BKK)
        p = patch.object(logger, "locate", self.locate)
        p.start()
        self.addCleanup(p.stop)
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(logger.SCHEMA)
        self.conn.executescript(logger.LOC_SCHEMA)
        self.addCleanup(self.conn.close)
        self.t = 1_800_000_000.0
        self.out = io.StringIO()
        self.st = logger._LocState(self.conn)

    def tick(self, dt=5):
        self.t += dt
        with contextlib.redirect_stdout(self.out):
            return logger._loc_step(self.conn, self.st, self.t)

    def drive(self, dt=60, km=1):
        """A tick while driving: fresh frames with an advancing odometer, so a fix is due."""
        odo = self.conn.execute("select coalesce(max(odo_guess), 1000) from telemetry").fetchone()[0]
        self.conn.execute("insert or replace into telemetry(ts, odo_guess) values (?, ?)",
                          (int(self.t + dt) - 200, odo))
        self.conn.execute("insert or replace into telemetry(ts, odo_guess) values (?, ?)",
                          (int(self.t + dt) - 5, odo + km))
        return self.tick(dt)

    def stop(self):
        """Tick until the drive's frames age out; returns the call count just before the stop read."""
        while logger._loc_moving(self.conn, self.t + 5):
            self.tick()
        return self.locate.call_count

    def stored(self):
        return self.conn.execute("select count(*) from positions").fetchone()[0]

    def lngs(self):
        return [round(r[0], 5) for r in self.conn.execute("select lng from positions order by ts")]


class LoopTest(LoopHarness):
    def test_a_car_that_never_had_a_fix_pauses_after_three_50052s_then_checks_once_a_day(self):
        self.locate.return_value = "unsupported"
        for _ in range(3):                                                       # the J5: asked three times...
            self.assertTrue(self.tick(61))
        self.assertEqual(self.locate.call_count, 3)
        self.assertIn("paused, checking again once a day", self.out.getvalue())
        for _ in range(23):                                                      # ...then quiet for a day
            self.tick(3600)
        self.assertEqual(self.locate.call_count, 3)
        self.tick(3600)
        self.assertEqual(self.locate.call_count, 4)                              # one check a day
        self.assertIn("checking again in 24 h", self.out.getvalue())
        self.assertEqual(self.stored(), 0)
        self.locate.return_value = BKK                                            # the car gains a position
        self.tick(86400)
        self.assertEqual(self.locate.call_count, 5)
        self.assertEqual(self.stored(), 1)                                       # back on, without a restart
        self.assertIn("back on", self.out.getvalue())
        self.locate.return_value = "unsupported"
        for _ in range(5):
            self.drive()                                                         # now a 50052 is only a gap
        self.assertIsNone(self.st.dormant_until)

    def test_after_the_daily_checks_all_say_50052_location_closes_for_good(self):
        self.locate.return_value = "unsupported"
        for _ in range(3):
            self.tick(61)                                                        # day 0: three asks, paused
        self.assertTrue(self.tick(86400))                                        # day 1: still 50052, keep waiting
        self.assertFalse(self.tick(86400))                                       # day 2: closed
        self.assertEqual(self.locate.call_count, 5)
        self.assertIn("will not ask again", self.out.getvalue())
        for _ in range(10):
            self.assertFalse(self.tick(86400))                                   # and never asks again
        self.assertEqual(self.locate.call_count, 5)

    def test_closed_stays_closed_after_a_restart_but_not_for_another_car(self):
        self.locate.return_value = "unsupported"
        for _ in range(3):
            self.tick(61)
        self.tick(86400); self.tick(86400)
        calls = self.locate.call_count
        with patch.object(logger, "_loc_sn", return_value="SN1"):
            self.conn.execute("DELETE FROM loc_state WHERE k='closed'")
            logger._loc_kv_set(self.conn, closed="SN1")
            self.assertTrue(logger._LocState(self.conn).closed)                  # logger restarted: still closed
        with patch.object(logger, "_loc_sn", return_value="SN2"):
            self.assertFalse(logger._LocState(self.conn).closed)                 # a different car: tries again
        self.assertEqual(self.locate.call_count, calls)

    def test_a_daily_check_without_an_answer_is_not_a_probe(self):
        # Timeouts, network errors, a stale token and the login guard all make locate() return None.
        self.locate.return_value = "unsupported"
        for _ in range(3):
            self.tick(61)                                                        # paused
        self.locate.return_value = None
        for _ in range(10):                                                      # day 1: no answer, 10 hours running
            self.assertTrue(self.tick(86400 if _ == 0 else 3600))
        self.assertEqual(self.st.probes, 0)
        self.assertFalse(logger._LocState(self.conn).closed)                     # and a restart doesn't close it
        self.assertIn("trying again in 1 h", self.out.getvalue())
        self.locate.return_value = BKK                                            # the network comes back
        self.tick(3600)
        self.assertEqual(self.stored(), 1)
        self.assertIsNone(self.st.dormant_until)

    def test_only_50052s_count_towards_closing(self):
        self.locate.return_value = "unsupported"
        for _ in range(3):
            self.tick(61)
        self.locate.return_value = None
        self.assertTrue(self.tick(86400)); self.assertTrue(self.tick(86400))    # two empty checks (the review case)
        self.assertEqual(self.locate.call_count, 5)
        self.locate.return_value = "unsupported"
        self.assertTrue(self.tick(3600))                                         # first real probe (1 h retry)
        self.assertTrue(self.tick(3600))                                         # not due yet: a day later
        self.assertFalse(self.tick(86400))                                       # second probe: now closed
        self.assertEqual(self.st.probes, 2)

    def test_a_parked_car_that_gets_no_fix_stops_asking_after_six_reads(self):
        self.tick()                                                              # stored fix, parked
        self.drive(); self.drive()                                               # a drive...
        self.locate.return_value = "unsupported"                                 # ...whose stop fix keeps failing
        calls = self.stop()
        for _ in range(24 * 720):                                                # 24 h of 5 s ticks, parked
            self.tick()
        self.assertEqual(self.locate.call_count - calls, logger.LOC_PARKED_TRIES)
        self.assertIn("waiting until the car moves again", self.out.getvalue())
        self.locate.return_value = None                                          # errors instead: same cap
        self.drive(); self.drive()
        calls = self.stop()
        for _ in range(24 * 720):
            self.tick()
        self.assertEqual(self.locate.call_count - calls, logger.LOC_PARKED_TRIES)
        self.locate.return_value = BKK
        self.drive()                                                             # moving again: reads resume
        self.assertGreater(self.locate.call_count, calls + logger.LOC_PARKED_TRIES)

    def test_a_parked_retry_backs_off(self):
        self.tick()
        self.drive()
        self.locate.return_value = None
        self.stop()
        times = []
        for _ in range(4000):
            n = self.locate.call_count
            self.tick()
            if self.locate.call_count > n:
                times.append(self.t)
        gaps = [round(b - a) for a, b in zip(times, times[1:])]
        self.assertEqual(len(times), logger.LOC_PARKED_TRIES)
        self.assertEqual([g // 60 for g in gaps], [1, 1, 2, 4, 8])

    def test_another_cars_positions_do_not_count_for_this_car(self):
        # positions has no device column; loc_state 'sn' says which car the rows belong to.
        with patch.object(logger, "_loc_sn", return_value="OLD"):
            self.conn.execute("insert into positions(ts, lat, lng, moving) values (1, 3.1, 101.7, 0)")
            st = logger._LocState(self.conn)
            self.assertTrue(st.has_fix)                                          # history from before: adopted
        with patch.object(logger, "_loc_sn", return_value="NEW"):
            self.st = logger._LocState(self.conn)
            self.assertFalse(self.st.has_fix)
            self.assertIsNone(self.st.ref)                                       # not judged against the old car
            self.locate.return_value = "unsupported"
            for _ in range(3):
                self.tick(61)
            self.assertIsNotNone(self.st.dormant_until)                          # the new car's 50052s count
        with patch.object(logger, "_loc_sn", return_value="NEW"):
            self.assertFalse(logger._LocState(self.conn).has_fix)                # also after a restart

    def test_the_digit_short_repair_never_touches_the_old_cars_rows(self):
        # The old car's rows look shifted (lng 10.17); the new car's first fix (kept as read
        # after empty check reads) is too, and its next read is x 10. Only the new car's row is corrected.
        self.conn.execute("insert into positions(ts, lat, lng, moving) values (?, 13.7563, 10.05018, 0)",
                          (int(self.t) - 600,))
        with patch.object(logger, "_loc_sn", return_value="OLD"):
            logger._LocState(self.conn)
        with patch.object(logger, "_loc_sn", return_value="NEW"):
            self.st = logger._LocState(self.conn)
            self.locate.return_value = (13.7563, 10.05018)
            self.tick()                                                          # first fix inside +-18: held
            self.locate.return_value = None
            for _ in range(logger.LOC_CONFIRM_TRIES):
                self.tick(46)                                                    # no check read: kept as read
            self.locate.return_value = BKK
            self.drive(61)                                                       # x 10 of it: repair
        self.assertIn("corrected 1 row", self.out.getvalue())
        self.assertEqual(self.lngs(), [10.05018, 100.5018, 100.5018])

    def test_a_restart_while_paused_does_not_start_the_asking_over(self):
        self.locate.return_value = "unsupported"
        for _ in range(3):
            self.tick(61)
        self.tick(86400)                                                         # day 1 probe
        st = logger._LocState(self.conn)                                         # restart
        self.assertEqual(st.probes, 1)
        self.assertIsNotNone(st.dormant_until)
        self.assertFalse(st.closed)

    def test_a_stored_fix_clears_the_give_up_state(self):
        logger._loc_kv_set(self.conn, probes=1, paused_until=5, closed="x")
        self.conn.execute("insert into positions(ts, lat, lng, moving) values (1, 3.1, 101.7, 0)")
        st = logger._LocState(self.conn)
        self.assertFalse(st.closed)
        self.assertEqual(self.conn.execute("select count(*) from loc_state").fetchone()[0], 0)

    def test_a_good_read_before_the_third_50052_means_the_car_has_a_position(self):
        self.locate.return_value = "unsupported"
        self.tick(61); self.tick(61)                                             # two misses...
        self.locate.return_value = BKK
        self.assertTrue(self.tick(61))                                           # ...then a fix
        self.assertEqual(self.stored(), 1)
        self.locate.return_value = "unsupported"
        for _ in range(8):
            self.assertTrue(self.drive())                                        # never stops again

    def test_a_50052_mid_drive_is_a_gap_not_the_end_of_location(self):
        # Seen on a Tiggo 7 in Malaysia: now and then, between good fixes; the next read worked.
        self.tick()
        self.assertEqual(self.stored(), 1)
        self.locate.return_value = "unsupported"
        for _ in range(5):                                                       # more than LOC_GIVE_UP in a row
            self.assertTrue(self.drive())
        self.assertEqual(self.stored(), 1)                                       # nothing invented for the gap
        self.locate.return_value = (13.76, 100.51)
        self.drive()
        self.assertEqual(self.stored(), 2)                                       # and the drive carries on
        self.assertIn("no fix this time (50052)", self.out.getvalue())

    def test_a_fix_the_car_could_not_have_driven_to_is_dropped(self):
        self.tick()
        self.locate.return_value = (48.1, 11.5)                                  # Europe, a minute later
        self.drive()
        self.assertEqual(self.stored(), 1)
        self.assertIn("dropped a fix", self.out.getvalue())

    def test_three_rejected_fixes_that_agree_win_because_the_car_did_move(self):
        self.tick()
        self.locate.return_value = (5.9, 116.1)                                  # Kota Kinabalu, 1,600 km away
        self.drive(); self.drive()
        self.assertEqual(self.stored(), 1)                                       # two agreeing rejects: not yet
        self.drive()
        self.assertEqual(self.stored(), 2)                                       # the third wins
        self.assertIn("agree on a new place", self.out.getvalue())

    def test_rejects_that_disagree_with_each_other_start_over(self):
        self.tick()
        for fix in ((48.1, 11.5), (35.7, 139.7), (48.1, 11.5), (35.7, 139.7), (48.1, 11.5)):
            self.locate.return_value = fix
            self.drive()
        self.assertEqual(self.stored(), 1)                                       # never three alike in a row

    def test_a_longitude_shifted_by_10_is_repaired_when_it_fits_the_last_fix(self):
        self.tick()
        self.locate.return_value = (13.7563, 10.05018)                             # 100.5018 with its point shifted (/10)
        self.drive()
        self.assertEqual(self.lngs(), [100.5018, 100.5018])
        self.assertIn("decimal point shifted", self.out.getvalue())


class FirstPositionTest(LoopHarness):
    """The very first fix has nothing to be judged against. A shifted longitude is the real one / 10 or
    / 100, so it is always within +-18, and a shifted latitude within +-9: only a first fix inside one of
    those bands gets a second read."""

    def test_a_first_fix_outside_both_bands_is_kept_at_once_with_no_extra_call(self):
        self.tick()
        self.assertEqual(self.lngs(), [100.5018])
        self.assertEqual(self.locate.call_count, 1)
        self.assertNotIn("checking the first position", self.out.getvalue())

    def test_a_short_first_fix_is_checked_and_the_larger_reading_kept(self):
        self.locate.return_value = SHORT_CASE                                   # would be a pin in Cameroon
        self.tick()
        self.assertEqual(self.stored(), 0)                                       # held, not stored
        self.locate.return_value = SHORT_REAL
        self.tick(40)
        self.assertEqual(self.locate.call_count, 1)                              # the check waits 45 s
        self.tick(5)
        self.assertEqual(self.locate.call_count, 2)
        self.assertEqual(self.lngs(), [101.77414])                               # only the real one is kept
        self.assertIn("shifted; kept the second read", self.out.getvalue())

    def test_a_real_first_fix_inside_18_is_kept(self):
        self.locate.return_value = (52.52, 13.405)                               # Berlin: genuinely inside +-18
        self.tick(); self.tick(45)
        self.assertEqual(set(self.lngs()), {13.405})
        self.assertGreaterEqual(self.stored(), 1)

    def test_when_the_check_read_is_the_short_one_the_first_is_kept(self):
        self.locate.return_value = (52.52, 13.405)
        self.tick()
        self.locate.return_value = (52.52, 1.3405)                               # the check read lost a digit
        self.tick(45)
        self.assertEqual(set(self.lngs()), {13.405})                             # repaired by the jump check

    def test_with_no_check_read_the_first_fix_is_kept_after_three_tries(self):
        self.locate.return_value = SHORT_CASE
        self.tick()
        self.locate.return_value = None
        self.tick(45); self.tick(45)
        self.assertEqual(self.stored(), 0)
        self.tick(45)
        self.assertEqual(self.lngs(), [10.17741])                                # kept as read; see the safety net
        self.assertIn("no second read", self.out.getvalue())

    def test_50052_during_the_check_does_not_switch_location_off(self):
        self.locate.return_value = SHORT_CASE
        self.tick()
        self.locate.return_value = "unsupported"
        for _ in range(3):
            self.assertTrue(self.tick(45))                                       # the car did give a fix
        self.assertEqual(self.stored(), 1)

    def test_if_both_reads_were_short_the_next_good_read_corrects_them(self):
        self.locate.return_value = SHORT_CASE
        self.tick(); self.tick(45)                                               # short twice (rare)
        self.assertEqual(self.lngs(), [10.17741, 10.17741])
        self.locate.return_value = SHORT_REAL
        self.drive()                                                             # the next read is right
        self.assertEqual(self.lngs(), [101.77414, 101.77414, 101.77414])          # corrected, kept at once
        self.assertIn("corrected 2 rows", self.out.getvalue())

    def test_a_first_fix_with_its_longitude_shifted_by_100_is_checked(self):
        self.locate.return_value = T7_LNG100                                    # would be a pin off Gabon
        self.tick()
        self.assertEqual(self.stored(), 0)
        self.locate.return_value = T7_SPOT
        self.tick(45)
        self.assertEqual(self.lngs(), [100.3672])
        self.assertIn("shifted; kept the second read", self.out.getvalue())

    def test_a_first_fix_with_its_latitude_shifted_is_checked(self):
        self.locate.return_value = T7_LAT10                                     # 0.61 N: inside the +-9 band
        self.tick()
        self.assertEqual(self.stored(), 0)
        self.locate.return_value = T7_SPOT
        self.tick(45)
        self.assertEqual([round(r[0], 5) for r in self.conn.execute("select lat from positions")], [6.12135])

    def test_a_real_first_fix_near_the_equator_costs_one_check_read(self):
        self.locate.return_value = KL                                           # 3.1 N: inside the band
        self.tick(); self.tick(45)
        self.assertEqual(self.locate.call_count, 2)
        self.assertEqual(set(self.lngs()), {101.6869})

    def test_if_both_reads_had_the_latitude_shifted_the_next_good_read_corrects_them(self):
        self.locate.return_value = T7_LAT10
        self.tick(); self.tick(45)
        self.locate.return_value = T7_SPOT
        self.drive()
        lats = [round(r[0], 4) for r in self.conn.execute("select lat from positions order by ts")]
        self.assertEqual(lats, [6.1213, 6.1213, 6.1213])
        self.assertIn("corrected 2 rows", self.out.getvalue())

    def test_the_safety_net_never_rewrites_real_history(self):
        self.locate.return_value = (51.5, -0.12)                                 # London, near longitude 0
        self.tick(); self.tick(45)
        before = self.lngs()
        self.locate.return_value = (51.5, -1.2)                                  # 75 km away: just a dropped jump
        self.drive()
        self.assertEqual(self.lngs(), before)
        self.assertIn("dropped a fix", self.out.getvalue())

    def test_the_log_never_carries_a_coordinate(self):
        self.locate.return_value = SHORT_CASE
        self.tick(); self.tick(45)
        self.locate.return_value = SHORT_REAL
        self.drive()
        self.locate.return_value = "unsupported"
        self.drive()
        self.locate.return_value = (48.1, 11.5)
        self.drive()
        out = self.out.getvalue()
        for needle in ("3.048", "10.177", "101.77", "48.1", "11.5"):
            self.assertNotIn(needle, out)
        for said in ("checking the first position", "corrected", "50052", "dropped a fix"):
            self.assertIn(said, out)


class GateTest(unittest.TestCase):
    """The jump check on its own: the last good fix against a new one."""
    REF = (1_800_000_000, 3.139, 101.6869, 1000)         # ts, lat, lng, odometer

    def gate(self, p, dt=60, odo=1000, ref=None):
        ref = ref or self.REF
        return logger._loc_gate(ref, p, ref[0] + dt, odo)

    def test_the_first_fix_has_nothing_to_be_judged_against(self):
        self.assertEqual(logger._loc_gate(None, (48.1, 11.5), 1_800_000_000, None), ("ok", (48.1, 11.5)))

    def test_a_short_drive_passes(self):
        self.assertEqual(self.gate((3.15, 101.70), odo=1001), ("ok", (3.15, 101.70)))

    def test_a_jump_no_car_could_make_is_dropped(self):
        self.assertEqual(self.gate((48.1, 11.5)), ("drop", None))

    def test_the_odometer_caps_what_a_long_parked_gap_allows(self):
        # A week parked at 200 km/h allows 33,000 km; the odometer says it did not move, so 3 km at most.
        week = 7 * 86400
        self.assertEqual(self.gate((3.20, 101.69), dt=week, odo=1000)[0], "drop")        # ~6 km away
        self.assertEqual(self.gate((3.145, 101.69), dt=week, odo=1000)[0], "ok")         # ~1 km: GPS jitter

    def test_a_digit_short_longitude_is_repaired_even_after_a_long_gap(self):
        self.assertEqual(self.gate((3.139, 10.16869), dt=7 * 86400, odo=1000), ("repaired", KL))
        ref = (self.REF[0], self.REF[1], self.REF[2], None)                 # no odometer: a huge allowance
        verdict, fix = self.gate((3.139, 10.16869), dt=7 * 86400, odo=None, ref=ref)
        self.assertEqual((verdict, round(fix[1], 4)), ("repaired", 101.6869))

    def test_a_real_drive_near_longitude_zero_is_never_repaired(self):
        london = (1_800_000_000, 51.5, -0.12, 500)
        self.assertEqual(logger._loc_gate(london, (51.5, -0.012), london[0] + 1800, 520)[0], "ok")

    def test_the_allowance_is_speed_for_the_time_but_never_more_than_the_odometer(self):
        ref = self.REF
        self.assertAlmostEqual(logger._loc_allow_km(ref, ref[0] + 3600, None), 200 + logger.LOC_SLACK_KM)
        self.assertAlmostEqual(logger._loc_allow_km(ref, ref[0] + 3600, 1010), 11 + logger.LOC_SLACK_KM)
        self.assertAlmostEqual(logger._loc_allow_km(ref, ref[0] - 100, None), logger.LOC_SLACK_KM)   # a clock step

    def test_distance_is_great_circle(self):
        self.assertAlmostEqual(logger._loc_km((0, 0), (0, 1)), 111.2, delta=0.3)
        self.assertAlmostEqual(logger._loc_km(KL, KL), 0.0)

    def test_shifted_needs_the_larger_reading_to_be_where_the_small_one_unshifted_lands(self):
        self.assertTrue(logger._loc_shifted(SHORT_CASE, SHORT_REAL, 3))
        self.assertFalse(logger._loc_shifted(SHORT_REAL, SHORT_CASE, 3))           # never the other way round
        self.assertFalse(logger._loc_shifted((52.52, 13.405), (52.52, 13.405), 3))  # equal readings
        self.assertFalse(logger._loc_shifted((3.0, 20.0), (3.0, 200.0), 3))        # x 10 off the globe

    def test_the_three_shifts_seen_on_a_tiggo_7_are_repaired(self):
        moving = (1_800_000_000, 6.114042, 100.360019, None)
        verdict, fix = logger._loc_gate(moving, T7_LNG10, moving[0] + 42, None)
        self.assertEqual((verdict, round(fix[1], 5)), ("repaired", 100.36142))
        parked = (1_800_000_000, T7_SPOT[0], T7_SPOT[1], 1000)
        verdict, fix = logger._loc_gate(parked, T7_LNG100, parked[0] + 1, 1000)
        self.assertEqual((verdict, round(fix[1], 4)), ("repaired", 100.3672))
        verdict, fix = logger._loc_gate(parked, T7_LAT10, parked[0] + 1, 1000)
        self.assertEqual((verdict, round(fix[0], 5)), ("repaired", 6.12133))

    def test_a_shifted_latitude_near_the_equator_is_dropped_not_repaired(self):
        # Singapore 1.35 -> 0.135 is a 135 km jump: under LOC_REPAIR_KM, so only the jump check applies
        sg = (1_800_000_000, 1.35, 103.82, 1000)
        self.assertEqual(logger._loc_gate(sg, (0.135, 103.82), sg[0] + 40, 1000), ("drop", None))

    def test_shifted_knows_lat_and_lng_by_10_and_100(self):
        real = (6.121314, 100.367198)
        self.assertTrue(logger._loc_shifted(T7_LNG100, real, 3))
        self.assertTrue(logger._loc_shifted(T7_LAT10, real, 3))
        self.assertTrue(logger._loc_shifted(T7_LNG10, (6.118265, 100.361417), 3))
        self.assertFalse(logger._loc_shifted(real, T7_LAT10, 3))                 # never the other way round


class IntervalFloorTest(unittest.TestCase):
    """The car uploads about every 30 s, so reading faster only repeats a fix and loads CarLinko."""
    def test_the_floors_and_the_default(self):
        self.assertEqual((logger.LOC_MIN_EVERY, logger.LOC_MIN_PARKED), (30, 300))
        self.assertEqual(logger.LOC_EVERY, 40)                                   # nothing set in creds here
        self.assertTrue(logger.LOC_PARKED == 0 or logger.LOC_PARKED >= 300)

    def test_a_lower_interval_is_raised_and_says_so(self):
        out = io.StringIO()
        with patch.dict(logger._C, {"location_interval": 10}), patch.object(logger, "LOC_ON", True), \
                contextlib.redirect_stdout(out):
            self.assertEqual(logger._loc_int("location_interval", 40, logger.LOC_MIN_EVERY, 86400), 30)
        self.assertIn("location_interval=10 is below the minimum, using 30", out.getvalue())

    def test_a_value_in_range_is_left_alone_and_silent(self):
        out = io.StringIO()
        with patch.dict(logger._C, {"location_interval": 45}), contextlib.redirect_stdout(out):
            self.assertEqual(logger._loc_int("location_interval", 40, logger.LOC_MIN_EVERY, 86400), 45)
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
