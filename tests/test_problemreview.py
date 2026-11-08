import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from problemreview import cli
from problemreview.checks import (CRITICAL, INFO, WARNING, area_status, cab_items, cluster, overall, review, run_all, similar, summary,
                                  tokens, working_days)
from problemreview.model import CI, Change, Data, Incident, Problem, load, load_incidents, load_problems, settings_from_dict

AS_OF = datetime(2026, 11, 8, 9, 0)
TODAY = AS_OF.date()


def write(path: Path, header: list[str], rows: list[list]) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def inc(n, summary, days_ago=10, ci="VPN-01", category="Network / VPN", prio=3, problems=(), major=False, reopen=0, service="Remote access",
        resolved_after=4) -> Incident:
    created = AS_OF - timedelta(days=days_ago)
    return Incident(f"INC-{n}", created, created + timedelta(hours=resolved_after), prio, "", service, ci, category, "Service Desk",
                    list(problems), summary, "", reopen, major)


def prob(key, summary="A problem", status="under investigation", owner="Ana Gil", ci="VPN-01", opened=TODAY - timedelta(days=20), **kw) -> Problem:
    kw.setdefault("updated", TODAY - timedelta(days=2))
    return Problem(key, summary, opened, status, "", owner, kw.pop("team", ""), kw.pop("service", ""), ci, **kw)


def data(incidents=(), problems=(), changes=(), cmdb=(), **raw) -> Data:
    d = Data(settings_from_dict(raw), AS_OF, sorted(incidents, key=lambda i: (i.created, i.key)), list(problems), list(changes),
             {c.ci.lower(): c for c in cmdb})
    d.sources = {"incidents.csv": len(d.incidents)}
    return d


def rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def issues(rv, code):
    return [i for i in rv["issues"] if i.code == code]


VPN = ["VPN certificate error when connecting from home", "VPN says the server certificate is not trusted", "Certificate validation failure on VPN login",
       "VPN certificate expired message on laptop", "VPN client rejects gateway certificate", "VPN certificate prompt every morning"]


class TestLoading(unittest.TestCase):
    def test_jira_service_management_columns(self):
        with tempfile.TemporaryDirectory() as t:
            i = write(Path(t) / "incidents.csv", ["Issue key", "Created", "Resolved", "Priority", "Affected services", "Configuration item", "Components",
                                                  "Team", "Linked problem", "Summary", "Resolution", "Reopen count", "Major incident"],
                      [["inc-1", "2026-11-02T08:15:00.000+0100", "", "Highest", "WMS", "WMS-APP-01", "Application", "Apps", "PRB-9; PRB-10",
                        "WMS down", "", "", "Yes"],
                       ["INC-2", "02/Nov/26 9:05 AM", "03/Nov/26 10:00 AM", "Low", "Email", "", "Email", "", "", "Mailbox full", "Done", "2", "No"]])
            p = write(Path(t) / "problems.csv", ["Key", "Summary", "Created", "Status", "Assignee", "Root cause category", "Workaround", "KEDB",
                                                 "Due date", "Updated"],
                      [["PRB-9", "WMS crash", "2026-10-01", "Open", "", "", "Restart the service", "No", "2026-11-01", "2026-10-02"],
                       ["PRB-10", "Old", "2026-06-01", "Completed", "Ana", "Configuration", "No", "", "", ""]])
            incs, probs = load_incidents(i), load_problems(p)
        self.assertEqual([x.key for x in incs], ["INC-1", "INC-2"])
        self.assertEqual((incs[0].priority, incs[0].major, incs[0].problems, incs[0].category), (1, True, ["PRB-9", "PRB-10"], "Application"))
        self.assertEqual((incs[1].priority, incs[1].reopen, incs[1].resolved), (4, 2, datetime(2026, 11, 3, 10, 0)))
        self.assertEqual((probs[0].status, probs[0].workaround, probs[0].workaround_text, probs[0].published), ("new", True, "Restart the service", False))
        self.assertEqual((probs[1].status, probs[1].workaround, probs[1].open), ("resolved", False, False))


class TestTrends(unittest.TestCase):
    def test_similarity_and_clusters(self):
        a, b = tokens("VPN certificate error when connecting"), tokens("Certificate validation failure on VPN login")
        self.assertTrue(similar(a, b, 0.5, 2))
        self.assertFalse(similar(tokens("VPN slow when copying files"), a, 0.5, 2))
        xs = [inc(k, VPN[k % 6], 40 - k) for k in range(12)] + [inc(100 + k, f"Paper jam tray {k}", 30 - k, "PRT-01", "Printing") for k in range(3)]
        cs = cluster(xs, 0.5, 2)
        self.assertEqual(len(cs[0].members), 12)
        self.assertEqual(sorted(cs[0].core), ["certificate", "vpn"])

    def test_candidate_problems_ranked_with_criticality(self):
        vpn = [inc(k, VPN[k % 6], 5 + k, prio=2 if k < 3 else 3) for k in range(20)]
        prt = [inc(100 + k, "Printer driver error after update", 5 + k, "PRT-01", "Printing", 4) for k in range(6)]
        old = [inc(200 + k, "Printer driver error after update", 120 + k, "PRT-01", "Printing", 4) for k in range(6)]   # outside the window
        cmdb = [CI("VPN-01", "Remote access", "High", "Network"), CI("PRT-01", "Printing", "Low", "End user services")]
        rv = review(data(vpn + prt + old, cmdb=cmdb, cluster_critical_score=90))
        self.assertEqual([(r["cluster"].ci, len(r["cluster"].members), r["score"], r["severity"]) for r in rv["candidates"]],
                         [("VPN-01", 20, (3 * 4 + 17 * 2) * 2, CRITICAL), ("PRT-01", 6, 6.0, WARNING)])
        self.assertEqual(rv["candidates"][0]["team"], "Network")

    def test_clusters_that_match_a_problem_are_not_candidates(self):
        p = prob("PRB-1", "VPN certificate not trusted")
        xs = [inc(k, VPN[k % 6], 5 + k, problems=["PRB-1"] if k % 3 else []) for k in range(9)]
        rv = review(data(xs, [p]))
        self.assertEqual(rv["candidates"], [])
        self.assertEqual(issues(rv, "TRD-02")[0].item, "INC-6; INC-3; INC-0")
        rv = review(data([inc(k, VPN[k % 6], 5 + k) for k in range(9)], [p]))     # unlinked, but the problem exists
        self.assertEqual((rv["candidates"], rv["to_link"][0]["problem"]), ([], "PRB-1"))


class TestMajorIncidents(unittest.TestCase):
    def test_no_problem_and_no_root_cause_after_working_days(self):
        late = inc(1, "WMS down", 19, "WMS", "App", 1, major=True)                      # Tue 20 Oct
        fresh = inc(2, "Phones down", 3, "TEL", "Tel", 1, major=True)                   # Thu 5 Nov
        rca = inc(3, "TMS down", 25, "TMS", "App", 1, ["PRB-1"], major=True)
        done = inc(4, "Mail delayed", 25, "EXO", "Mail", 1, ["PRB-2"], major=True)
        ps = [prob("PRB-1", status="under investigation"), prob("PRB-2", status="root cause known", rc_category="Configuration")]
        rv = review(data([late, fresh, rca, done], ps, holidays=["2026-10-26"]))
        self.assertEqual([(i.item, i.severity) for i in issues(rv, "MAJ-01")], [("INC-1", CRITICAL), ("INC-2", WARNING)])
        self.assertEqual([i.item for i in issues(rv, "MAJ-02")], ["INC-3"])
        self.assertEqual(working_days(date(2026, 10, 20), TODAY, {date(2026, 10, 26)}), 12)
        self.assertEqual({r["incident"].key: r["state"] for r in rv["majors"]}["INC-4"], "RCA done")


class TestProblems(unittest.TestCase):
    def test_stuck_overdue_no_owner_and_team_mismatch(self):
        ps = [prob("PRB-1", updated=TODAY - timedelta(days=45)),
              prob("PRB-2", target=TODAY - timedelta(days=10)),
              prob("PRB-3", opened=TODAY - timedelta(days=90)),
              prob("PRB-4", owner="", ci="WMS"),
              prob("PRB-5", team="Service Desk", ci="LAPTOPS"),
              prob("PRB-6", status="closed", owner="", updated=TODAY - timedelta(days=200))]
        major = inc(9, "WMS down", 3, "WMS", "App", 1, ["PRB-4"], major=True)
        rv = review(data([major], ps, cmdb=[CI("LAPTOPS", "Laptops", "Medium", "End user services")]))
        got = {(i.code, i.item): i.severity for i in rv["issues"] if i.code.startswith("STK")}
        self.assertEqual(got, {("STK-01", "PRB-1"): WARNING, ("STK-02", "PRB-2"): WARNING, ("STK-03", "PRB-3"): WARNING,
                               ("STK-04", "PRB-4"): CRITICAL, ("STK-05", "PRB-5"): WARNING})


class TestKnownErrors(unittest.TestCase):
    def test_workaround_without_fix_unpublished_and_no_workaround(self):
        ps = [prob("PRB-1", status="known error", workaround=True, workaround_text="Toggle Wi-Fi", known_error_since=TODAY - timedelta(days=120),
                   published=True),
              prob("PRB-2", status="known error", workaround=True, known_error_since=TODAY - timedelta(days=200)),
              prob("PRB-3", status="known error", workaround=True, known_error_since=TODAY - timedelta(days=150), changes=["CHG-1"]),
              prob("PRB-4", status="known error", workaround=True, known_error_since=TODAY - timedelta(days=10), published=False),
              prob("PRB-5", status="known error")]
        rv = review(data([], ps, [Change("CHG-1", "Fix", "Scheduled")]))
        got = {(i.code, i.item): i.severity for i in rv["issues"] if i.code.startswith("KER")}
        self.assertEqual(got, {("KER-01", "PRB-1"): WARNING, ("KER-01", "PRB-2"): CRITICAL, ("KER-01", "PRB-3"): INFO,
                               ("KER-02", "PRB-4"): WARNING, ("KER-03", "PRB-5"): WARNING})


class TestFixes(unittest.TestCase):
    def test_fix_not_effective_failed_change_and_reopened(self):
        ph = ["Mapped drive S disconnects", "Shared drive S disconnected and file locked", "Excel file on shared drive locked"]
        before = [inc(k, ph[k % 3], 80 - k * 3, "FS-02", "Storage", problems=["PRB-1"]) for k in range(9)]
        after = [inc(50 + k, ph[k % 3], 40 - k * 5, "FS-02", "Storage", problems=["PRB-1"] if k == 0 else []) for k in range(5)]
        noise = [inc(90 + k, "Restore deleted folder", 30 - k, "FS-02", "Storage") for k in range(3)]
        fixed = [inc(200 + k, "Sign-in loop on shared PC", 150 - k, "ENTRA", "Identity", problems=["PRB-2"]) for k in range(4)]
        ps = [prob("PRB-1", "Mapped drive disconnects", "resolved", ci="FS-02", changes=["CHG-1"]),
              prob("PRB-2", "Sign-in loops", "closed", ci="ENTRA", changes=["CHG-2"], rc_category="Configuration")]
        chs = [Change("CHG-1", "SMB", "Closed", TODAY - timedelta(days=54), ["PRB-1"], "Successful"),
               Change("CHG-2", "CA", "Closed", TODAY - timedelta(days=130), ["PRB-2"], "Backed out")]
        reo = inc(300, "Laptop slow", 5, "LAP", "Hardware", reopen=2)
        rv = review(data(before + after + noise + fixed + [reo], ps, chs))
        r = {x["problem"].key: x for x in rv["fixes"]}
        self.assertEqual((r["PRB-1"]["verdict"], len(r["PRB-1"]["after"]), len(r["PRB-1"]["before"])), ("not effective", 5, 9))
        self.assertEqual(issues(rv, "FIX-01")[0].severity, CRITICAL)
        self.assertIn("(4 not linked)", issues(rv, "FIX-01")[0].text)
        self.assertEqual((r["PRB-2"]["verdict"], issues(rv, "FIX-02")[0].item), ("change failed", "PRB-2"))
        self.assertEqual(issues(rv, "FIX-03")[0].item, "INC-300")
        self.assertEqual([c["problem"].key for c in cab_items(data(before + after, ps[:1], chs[:1]), review(data(before + after, ps[:1], chs[:1])))],
                         ["PRB-1"])


class TestQuality(unittest.TestCase):
    def test_unknown_root_cause_closed_without_cause_and_duplicates(self):
        ps = [prob(f"PRB-{k}", status="closed", rc_category=rc, root_cause="", changes=["CHG-1"])
              for k, rc in enumerate(["Unknown", "Other", "Configuration", "Capacity", "Hardware"])]
        ps += [prob("PRB-7", "WMS scanning slow at the dock", ci="WMS"), prob("PRB-8", "Slow scan response in WMS at peak", ci="WMS"),
               prob("PRB-9", "Label printer offline", ci="WMS"), prob("PRB-10", "Vendor fixed it", status="closed", rc_category="Third party")]
        rv = review(data([], ps, unknown_rc_max=0.2))
        self.assertIn("2 of 6", issues(rv, "QLT-01")[0].text)
        self.assertEqual(issues(rv, "QLT-01")[0].severity, WARNING)
        self.assertEqual([i.item for i in issues(rv, "QLT-02")], ["PRB-0", "PRB-1"])
        self.assertEqual([i.item for i in issues(rv, "QLT-03")], ["PRB-7; PRB-8"])
        self.assertEqual([i.item for i in issues(rv, "QLT-04")], ["PRB-10"])


class TestVerdictAndSettings(unittest.TestCase):
    def test_area_status_and_overall(self):
        d = data([inc(1, "Laptop slow", 3, "LAP", "Hardware")], [prob("PRB-1")])
        f = run_all(d)
        self.assertEqual(overall(f), "healthy")
        d = data([inc(k, VPN[k % 6], 5 + k) for k in range(5)] + [inc(9, "WMS down", 20, "WMS", "App", 1, major=True)], [prob("PRB-1", owner="")])
        f = run_all(d)
        st = area_status(f)
        self.assertEqual((st["Trends"], st["Major incidents"], st["Stuck problems"], st["Known errors"]), ("warning", CRITICAL, "warning", "ok"))
        self.assertEqual(overall(f), "at risk")

    def test_settings_overrides(self):
        s = settings_from_dict({"window_days": "60", "similarity": "60", "priority_weights": {"Highest": 10, "P3": 3},
                                "criticality_weights": {"Critical": 5}, "holidays": ["2026-12-08"], "next_cab": "2026-11-17",
                                "owners": {"fix": "CAB chair"}, "stopwords": ["Madrid"]})
        self.assertEqual((s.window_days, s.similarity, s.pweight(1), s.pweight(3), s.cweight("critical"), s.cweight("")), (60, 0.6, 10.0, 3.0, 5.0, 1.5))
        self.assertEqual((s.holiday_set(), s.next_cab, s.owner("fix"), s.owner("known"), s.stopwords),
                         ({date(2026, 12, 8)}, date(2026, 11, 17), "CAB chair", "Service desk lead", ["madrid"]))


class TestOutputs(unittest.TestCase):
    def test_demo_end_to_end_is_deterministic(self):
        with tempfile.TemporaryDirectory() as t:
            hashes = []
            for k in range(2):
                out = Path(t) / f"out{k}"
                self.assertEqual(cli.main(["demo", "--data", str(Path(t) / f"data{k}"), "--out", str(out)]), 0)
                self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(cli.OUTPUTS))
                hashes.append({n: hashlib.sha1((out / n).read_bytes()).hexdigest() for n in cli.OUTPUTS}
                              | {n.name: hashlib.sha1(n.read_bytes()).hexdigest() for n in (Path(t) / f"data{k}").iterdir()})
            self.assertEqual(hashes[0], hashes[1])
            self.assertEqual(json.loads((Path(t) / "data0" / "settings.json").read_text(encoding="utf-8"))["as_of"], "2026-11-08 09:00")
            self.assertLess(sum(p.stat().st_size for p in (Path(t) / "data0").iterdir()), 1_000_000)
            d = load(Path(t) / "data0")
        rv = review(d)
        f = run_all(d, rv)
        sm = summary(d, rv)
        self.assertEqual(overall(f), "at risk")
        self.assertEqual((sm["problems"], sm["changes"], sm["majors"], sm["majors_no_rca"], sm["no_owner"], sm["not_effective"]), (35, 20, 6, 2, 3, 1))
        top = rv["candidates"]
        self.assertEqual([(r["cluster"].ci, len(r["cluster"].members), r["severity"]) for r in top],
                         [("VPN-ASA-01", 46, CRITICAL), ("PRT-ZAZ-01", 17, WARNING)])
        self.assertEqual({x.code for x in f if x.severity == CRITICAL}, {"TRD-01", "MAJ-01", "MAJ-02", "FIX-01"})
        self.assertIn("PRB-1004", [x for x in f if x.code == "FIX-01"][0].detail)
        self.assertIn("PRB-1017", [x for x in f if x.code == "KER-01" and x.severity == WARNING][0].detail)
        self.assertEqual(round(sm["unknown_share"], 2), 0.29)

    def test_pack_and_csv_outputs(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(cli.main(["demo", "--data", str(Path(t) / "d"), "--out", str(Path(t) / "o")]), 0)
            o = Path(t) / "o"
            pack = (o / "problem-review-pack.md").read_text(encoding="utf-8")
            html = (o / "report.html").read_text(encoding="utf-8")
            cand = rows(o / "candidate-problems.csv")
            ps = rows(o / "problem-status.csv")
            ke = rows(o / "known-errors.csv")
            fx = rows(o / "fix-effectiveness.csv")
            act = rows(o / "actions.csv")
        for h in ("## Decisions for this review", "## Headlines", "## Agenda (60 minutes)", "## 1. Candidate problems", "## 2. Major incidents and RCA",
                  "## 3. Open problems: stuck, overdue, no owner", "## 4. Known errors", "## 5. Fix effectiveness", "## 6. Quality of the problem records",
                  "## 7. For the next CAB", "## Actions", "## Sign-off"):
            self.assertIn(h, pack)
        self.assertEqual((cand[0]["configuration_item"], cand[0]["incidents"], cand[0]["decision"]), ("VPN-ASA-01", "46", ""))
        self.assertEqual(len(ps), 35)
        self.assertEqual({r["key"]: r["codes"] for r in ke}["PRB-1018"], "KER-02")
        self.assertEqual({r["problem"]: r["verdict"] for r in fx}["PRB-1004"], "not effective")
        self.assertTrue(all(a["severity"] in ("critical", "warning") for a in act))
        self.assertIn("Candidate problems", html)
        self.assertNotIn("\r", pack)

    def test_review_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(cli.main(["review", t, "--out", str(Path(t) / "o")]), 2)
            self.assertEqual(cli.main(["review", "--out", str(Path(t) / "o")]), 2)
            write(Path(t) / "incidents.csv", ["Issue key"], [])
            self.assertEqual(cli.main(["review", t, "--out", str(Path(t) / "o")]), 2)
            write(Path(t) / "incidents.csv", ["Key", "Created", "Summary"], [["INC-1", "2026-11-02", "Laptop slow"]])
            self.assertEqual(cli.main(["review", t, "--out", str(Path(t) / "o"), "--as-of", "2026-11-08"]), 0)


if __name__ == "__main__":
    unittest.main()
