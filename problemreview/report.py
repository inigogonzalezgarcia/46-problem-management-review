"""Outputs: report.html (verdict, tiles, candidate problems, major incidents, open problems, known errors, fix effectiveness, quality and
all findings), problem-review-pack.md (the agenda and pack for the monthly problem review, with a decision column, and what goes to the
next CAB), and the CSVs: candidate-problems, problem-status, known-errors, fix-effectiveness, actions and findings."""
from __future__ import annotations

import csv
import html
from pathlib import Path

from .checks import AREAS, CRITICAL, INFO, VERDICT, WARNING, Finding, _n, area_status, cab_items, overall, pct, summary
from .model import FILES, STATUS_LABEL, Data

e = html.escape
TODO = "**[TO COMPLETE]**"


# ---------------------------------------------------------------- csv

def _w(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _d(x) -> str:
    return x.isoformat() if x else ""


def _worst(issues) -> str:
    sev = {i.severity for i in issues}
    return CRITICAL if CRITICAL in sev else WARNING if WARNING in sev else INFO if sev else ""


def _codes(issues) -> str:
    return "; ".join(dict.fromkeys(i.code for i in issues))


def _prios(counter) -> str:
    return " ".join(f"P{k}:{counter[k]}" for k in sorted(counter))


def write_findings(findings: list[Finding], path: Path) -> None:
    _w(path, ["severity", "area", "code", "subject", "detail", "next_step", "owner", "items"],
       [[f.severity, f.area, f.code, f.subject, f.detail, f.fix, f.owner, "; ".join(f.items)] for f in findings])


def write_actions(d: Data, findings: list[Finding], path: Path) -> None:
    due = _d(d.settings.next_review)
    _w(path, ["ref", "action", "next_step", "owner", "severity", "items", "due", "decision", "done"],
       [[f.code, f.subject, f.fix, f.owner, f.severity, "; ".join(f.items), due if f.severity == CRITICAL else "", "", ""]
        for f in findings if f.severity != INFO])


def write_candidates(d: Data, rv: dict, path: Path) -> None:
    _w(path, ["rank", "cluster", "configuration_item", "service", "category", "criticality", "incidents", "first_seen", "last_seen", "priorities",
              "major_incidents", "score", "severity", "keywords", "latest_summary", "proposed_owner", "incident_keys", "decision", "problem_opened"],
       [[r["rank"], r["cluster"].id, r["cluster"].ci, r["cluster"].service, r["cluster"].category, r["criticality"], len(r["cluster"].members),
         _d(r["cluster"].members[0].day), _d(r["cluster"].members[-1].day), _prios(r["priorities"]), len(r["majors"]), f"{r['score']:g}",
         r["severity"], " ".join(r["keywords"]), r["cluster"].members[-1].summary, r["team"], "; ".join(i.key for i in r["cluster"].members), "", ""]
        for r in rv["candidates"]])


def problem_step(r: dict) -> str:
    codes = {i.code for i in r["issues"] if i.severity != INFO}
    acts = []
    if "STK-04" in codes:
        acts.append("name an owner")
    if "STK-05" in codes:
        acts.append("move to the CI owner team")
    if "STK-03" in codes:
        acts.append("decide: resources, vendor case or known error")
    if "STK-02" in codes:
        acts.append("new target date or escalate")
    if "STK-01" in codes:
        acts.append("update from the owner")
    return "; ".join(acts)


def write_problems(d: Data, rv: dict, path: Path, known: dict, fixes: dict) -> None:
    rows = []
    for r in rv["problems"]:
        p = r["problem"]
        iss = r["issues"] + known.get(p.key, []) + fixes.get(p.key, [])
        rows.append([p.key, p.summary, STATUS_LABEL.get(p.status, p.status_label), "yes" if p.open else "no", p.owner, p.team, r["ci_team"], p.service,
                     p.ci, _d(p.opened), "" if r["age"] is None else r["age"], _d(p.updated), "" if r["since_update"] is None else r["since_update"],
                     _d(p.target), r["past_target"] or "", _d(p.review), p.rc_category, "yes" if p.workaround else "no",
                     "" if p.published is None else ("yes" if p.published else "no"), "; ".join(p.changes), r["incidents"], r["recent"],
                     "; ".join(r["majors"]), _worst(iss), _codes(iss), problem_step(r)])
    _w(path, ["key", "summary", "status", "open", "owner", "owner_team", "ci_owner_team", "service", "configuration_item", "opened", "age_days",
              "last_update", "days_since_update", "target_date", "days_past_target", "review_date", "root_cause_category", "workaround",
              "published", "linked_changes", "linked_incidents", f"incidents_last_{d.settings.window_days}_days", "major_incidents", "severity",
              "codes", "next_step"], rows)


def write_known(d: Data, rv: dict, path: Path) -> None:
    _w(path, ["key", "summary", "service", "configuration_item", "status", "known_error_since", "days_with_workaround", "workaround",
              "published", "linked_changes", "change_status", f"incidents_last_{d.settings.window_days}_days", "severity", "codes", "decision"],
       [[r["problem"].key, r["problem"].summary, r["problem"].service, r["problem"].ci, STATUS_LABEL.get(r["problem"].status, r["problem"].status),
         _d(r["since"]), "" if r["days"] is None else r["days"], r["problem"].workaround_text,
         "" if r["problem"].published is None else ("yes" if r["problem"].published else "no"), "; ".join(r["problem"].changes),
         "; ".join(f"{c.key} {c.status}" for c in r["changes"]), r["recent"], _worst(r["issues"]), _codes(r["issues"]), ""] for r in rv["known"]])


def write_fixes(d: Data, rv: dict, path: Path) -> None:
    _w(path, ["problem", "summary", "status", "change", "change_status", "implemented", "outcome", "incidents_90_days_before",
              "incidents_after", "days_since_change", "rate_before_per_30_days", "rate_after_per_30_days", "verdict", "incident_keys_after"],
       [[r["problem"].key, r["problem"].summary, STATUS_LABEL.get(r["problem"].status, r["problem"].status), r["change"].key, r["change"].status,
         _d(r["implemented"]), r["change"].outcome, len(r["before"]), len(r["after"]), r["days_after"], f"{r['rate_before']:.1f}",
         f"{r['rate_after']:.1f}", r["verdict"], "; ".join(i.key for i in r["after"])] for r in rv["fixes"]])


def by_problem(rv: dict) -> tuple[dict, dict]:
    known, fixes = {}, {}
    for r in rv["known"]:
        known[r["problem"].key] = r["issues"]
    for i in rv["issues"]:
        if i.code in ("FIX-01", "FIX-02"):
            fixes.setdefault(i.item, []).append(i)
    return known, fixes


# ---------------------------------------------------------------- the pack

def _md(x) -> str:
    return str(x).replace("|", "/")


def _status_word(st: str) -> str:
    return "HEALTHY" if st == "ok" else VERDICT[st].upper()


def decisions(d: Data, rv: dict) -> list[tuple]:
    """(ref, item, proposal) for the decisions table of the pack."""
    out = []
    for r in rv["candidates"]:
        c = r["cluster"]
        out.append((c.id, f"{len(c.members)} incidents on {c.ci or c.service} ({c.category}): “{c.members[-1].summary}”",
                    f"open a problem, owner {r['team'] or 'to name'}" + (" (critical)" if r["severity"] == CRITICAL else "")))
    for r in rv["majors"]:
        if r["severity"] == CRITICAL:
            i = r["incident"]
            out.append((i.key, f"Major incident {i.summary} ({r['end']:%d %b})",
                        "open the problem and hold the RCA" if r["state"] == "no problem" else f"hold the RCA for {', '.join(r['problems'])} this week"))
    for r in rv["fixes"]:
        if r["verdict"] == "not effective":
            out.append((r["problem"].key, f"{r['problem'].summary}: {len(r['after'])} incidents after {r['change'].key}",
                        "reopen the problem; post-implementation review at the CAB"))
    for r in rv["known"]:
        if any(i.code == "KER-01" and i.severity != INFO for i in r["issues"]):
            out.append((r["problem"].key, f"{r['problem'].summary}: workaround for {r['days']} days",
                        "raise the change for the permanent fix, or accept with a review date"))
    for r in rv["problems"]:
        if any(i.code in ("STK-03", "STK-04") for i in r["issues"]):
            out.append((r["problem"].key, f"{r['problem'].summary} ({STATUS_LABEL[r['problem'].status].lower()}, {r['age']} days)",
                        problem_step(r)))
    return out


def pack_md(d: Data, rv: dict, findings: list[Finding], title: str) -> str:
    s, sm, st = d.settings, summary(d, rv), area_status(findings)
    out = [f"# {title}", "",
           f"> Generated by problemreview on {d.as_of:%a %d %b %Y} from the exports listed under *Scope and evidence*. Read-only: nothing was "
           f"changed in the ITSM tool. Incidents are counted over the last {s.window_days} days unless said otherwise; sections marked {TODO} "
           "are for the meeting.", "",
           f"**Overall: {overall(findings).upper()}**"
           + (f" · Problem review: {s.next_review:%a %d %b %Y}" if s.next_review else "") + (f" · Next CAB: {s.next_cab:%a %d %b %Y}" if s.next_cab else ""),
           "", "## Decisions for this review", "", "| Ref | Item | Proposal | Decision |", "|---|---|---|---|"]
    dec = decisions(d, rv)
    out += [f"| {_md(a)} | {_md(b)} | {_md(c)} | {TODO} |" for a, b, c in dec] or ["| – | Nothing to decide | | |"]
    out += ["", "| Area | Status | To act on |", "|---|---|---|"]
    for a in AREAS:
        n = sum(f.area == a and f.severity != INFO for f in findings)
        out.append(f"| {a} | {_status_word(st[a])} | {n} |")
    top = sm["top"]
    out += ["", "## Headlines", "",
            f"- {sm['incidents']:,} incidents from {sm['first']:%d %b} to {sm['last']:%d %b %Y}; {sm['window']:,} in the last {s.window_days} days, "
            f"{pct(sm['linked_share'])} of them linked to a problem.",
            f"- **{sm['candidates']} candidate problems** (recurring incidents with no problem record)"
            + (f"; the largest: {len(top['cluster'].members)} incidents on {top['cluster'].ci} with “{' '.join(top['keywords'])}” in common, "
               f"score {top['score']:g}." if top else "."),
            f"- {sm['majors']} major incidents in the period; **{sm['majors_no_rca']} without a problem or a root cause** after "
            f"{s.rca_working_days} working days.",
            f"- {sm['open']} open problems of {sm['problems']}; {sm['stuck']} stuck (no update, past target, too long in investigation or no "
            f"owner), {sm['no_owner']} with no owner.",
            f"- {sm['known']} open known errors or problems with a workaround; {sm['known_nofix']} with a workaround older than "
            f"{s.known_error_fix_days} days and no change for the fix.",
            f"- {sm['fixes']} fixes checked against the incidents that followed; **{sm['not_effective']} not effective**.",
            f"- Root cause recorded as unknown or other on {sm['unknown']} of {sm['done']} problems past investigation ({pct(sm['unknown_share'])}).",
            "", "## Agenda (60 minutes)", "", "| Minutes | Topic | Section | Who |", "|---|---|---|---|",
            "| 5 | Actions from the last review; status by area | Decisions, Actions | Problem manager |",
            "| 15 | Candidate problems: open, link or reject | 1 | Problem manager, service desk lead, CI owner teams |",
            "| 10 | Major incidents and their RCA | 2 | Major incident manager |",
            "| 10 | Open problems stuck or without an owner | 3 | Problem owners |",
            "| 10 | Known errors and fixes that did not work | 4, 5 | Service desk lead, change manager |",
            "| 5 | Quality of the records | 6 | Problem manager |",
            "| 5 | What goes to the next CAB; decisions and owners | 7, Decisions | Change manager |",
            "", "## Scope and evidence", "", f"- Organisation: {s.organisation}", f"- Reference date: {d.as_of:%a %d %b %Y %H:%M}",
            f"- Similar incidents: same CI (or service) and category, sharing at least {s.min_shared_tokens} words and {pct(s.similarity)} of the "
            f"words of the shorter text; a candidate needs {s.cluster_min} or more in {s.window_days} days",
            "", "| Source | File | Records |", "|---|---|---|"]
    out += [f"| {FILES.get(k, k)} | `{k}` | {v:,} |" for k, v in d.sources.items()]
    # 1 candidates
    out += ["", "## 1. Candidate problems", "",
            "| Rank | Cluster | CI · category | Incidents | First – last | Priorities | Score | Common words | Proposed owner | Decision |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rv["candidates"]:
        c = r["cluster"]
        out.append(f"| {r['rank']} | {c.id}{' **(critical)**' if r['severity'] == CRITICAL else ''} | {_md(c.ci or c.service)} · {_md(c.category)} | "
                   f"{len(c.members)} | {c.members[0].day:%d %b} – {c.members[-1].day:%d %b} | {_prios(r['priorities'])} | {r['score']:g} | "
                   f"{_md(' '.join(r['keywords']))} | {_md(r['team'] or '–')} | |")
    if not rv["candidates"]:
        out.append("| – | None | | | | | | | | |")
    if rv["to_link"]:
        out += ["", "Incidents to link to an existing problem (not candidates):", ""]
        grp = {}
        for r in rv["to_link"]:
            g = grp.setdefault(r["problem"], {"ci": r["cluster"].ci or r["cluster"].service, "keys": []})
            g["keys"] += [i.key for i in r["unlinked"]]
        for k in sorted(grp):
            keys = sorted(grp[k]["keys"])
            out.append(f"- {k}: {_n(len(keys), 'incident')} on {grp[k]['ci']} ({', '.join(keys[:8])}{' …' if len(keys) > 8 else ''})")
    out += ["", "Every incident of each cluster is in `candidate-problems.csv`."]
    # 2 majors
    out += ["", "## 2. Major incidents and RCA", "", "| Incident | Date | Summary | Problem | RCA status | Working days | RCA due | Decision |",
            "|---|---|---|---|---|---|---|---|"]
    for r in rv["majors"]:
        i = r["incident"]
        out.append(f"| {i.key} | {r['end']:%d %b} | {_md(i.summary)} | {', '.join(r['problems']) or '–'} | "
                   f"{r['state']}{' **(overdue)**' if r['severity'] == CRITICAL else ''} | {r['working_days']} | {r['due']:%d %b} | |")
    if not rv["majors"]:
        out.append("| – | | No major incidents | | | | | |")
    # 3 problems
    out += ["", "## 3. Open problems: stuck, overdue, no owner", "",
            "| Problem | Status | Owner | Age (days) | Last update | Target | Linked incidents (90 d) | Findings | Next step | Decision |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    flagged = [r for r in rv["problems"] if r["problem"].open and any(i.severity != INFO for i in r["issues"])]
    for r in flagged:
        p = r["problem"]
        out.append(f"| {p.key} {_md(p.summary)} | {STATUS_LABEL[p.status]} | {_md(p.owner or '**(none)**')} | {r['age'] if r['age'] is not None else '–'} | "
                   f"{_d(p.updated) or '–'} | {_d(p.target) or '–'} | {r['recent']} | {_codes(r['issues'])} | {_md(problem_step(r))} | |")
    if not flagged:
        out.append("| None | | | | | | | | | |")
    by = {}
    for r in rv["problems"]:
        if r["problem"].open:
            by[r["problem"].status] = by.get(r["problem"].status, 0) + 1
    out += ["", "Open problems by status: " + ", ".join(f"{STATUS_LABEL[k]} {v}" for k, v in sorted(by.items(), key=lambda x: _status_order(x[0]))) + "."]
    # 4 known errors
    out += ["", "## 4. Known errors", "", "| Problem | Since | Days | Workaround | Published | Change | Incidents (90 d) | Findings | Decision |",
            "|---|---|---|---|---|---|---|---|---|"]
    for r in rv["known"]:
        p = r["problem"]
        out.append(f"| {p.key} {_md(p.summary)} | {_d(r['since']) or '–'} | {r['days'] if r['days'] is not None else '–'} | {_md(p.workaround_text or '**(none)**')} | "
                   f"{'–' if p.published is None else ('yes' if p.published else '**no**')} | "
                   f"{_md(', '.join(f'{c.key} {c.status.lower()}' for c in r['changes']) or '–')} | {r['recent']} | {_codes(r['issues']) or '–'} | |")
    if not rv["known"]:
        out.append("| None | | | | | | | | |")
    # 5 fixes
    out += ["", "## 5. Fix effectiveness", "", "| Problem | Change | Implemented | Before (90 d) | After | Per 30 days before → after | Verdict |",
            "|---|---|---|---|---|---|---|"]
    for r in rv["fixes"]:
        out.append(f"| {r['problem'].key} {_md(r['problem'].summary)} | {r['change'].key} | {r['implemented']:%d %b} | {len(r['before'])} | "
                   f"{len(r['after'])} | {r['rate_before']:.1f} → {r['rate_after']:.1f} | "
                   f"{'**' + r['verdict'] + '**' if r['verdict'] in ('not effective', 'change failed') else r['verdict']} |")
    if not rv["fixes"]:
        out.append("| None | | | | | | |")
    out += ["", f"Matching incidents: linked to the problem, or on the same CI with the words its incidents had in common before the change. "
            f"Not effective with {s.fix_recurrence_min} or more after the change plus {s.fix_grace_days} days; too early under 30 days."]
    if rv["reopened"]:
        out += ["", f"Reopened {s.reopen_min} or more times in {s.window_days} days: " + ", ".join(i.key for i in rv["reopened"]) + "."]
    # 6 quality
    q = rv["quality"]
    out += ["", "## 6. Quality of the problem records", "",
            f"- Root cause category unknown or other: {q['unknown']} of {q['done']} problems past investigation ({pct(q['share'])}; maximum "
            f"{pct(s.unknown_rc_max)})."]
    out += [f"- {i.text}" + (" (for information)" if i.severity == INFO else "") for i in rv["issues"] if i.code in ("QLT-02", "QLT-03", "QLT-04")]
    # 7 cab
    out += ["", "## 7. For the next CAB" + (f" ({s.next_cab:%a %d %b})" if s.next_cab else ""), "",
            "| Problem | Change | Ask | Decision |", "|---|---|---|---|"]
    cab = cab_items(d, rv)
    out += [f"| {r['problem'].key} {_md(r['problem'].summary)} | {_md(r['change'])} | {_md(r['ask'])} | |" for r in cab] or ["| None | | | |"]
    out += ["", "## Findings", ""]
    for f in findings:
        if f.severity == INFO:
            continue
        out += [f"### {f.code} · {f.subject} ({f.severity})", "", _md(f.detail), "", f"Next step: {f.fix} Owner: {f.owner}.", ""]
    out += ["## Actions", "", "| Ref | Action | Owner | Due | Decision |", "|---|---|---|---|---|"]
    out += [f"| {f.code} | {_md(f.subject)} | {f.owner} | {TODO if f.severity == CRITICAL else ''} | |" for f in findings if f.severity != INFO]
    out += ["", "## Notes", "",
            "- The status of an area is AT RISK with a critical finding, ATTENTION with warnings only, HEALTHY otherwise; the overall status is "
            "the worst area.",
            f"- A candidate problem is critical with a score of {s.cluster_critical_score:g} or more (the priority weights of its incidents "
            "times the criticality of the CI) or with a major incident in it.",
            "- Similarity is a word comparison of the summaries, not a judgement: reject a cluster that is not one problem and record why.",
            f"- Working days exclude weekends and the holidays in settings.json; the RCA is due {s.rca_working_days} working days after the "
            "major incident is resolved.",
            f"- Decisions of the review: {TODO}", "",
            "## Sign-off", "", f"- Prepared by (problem manager): {TODO}",
            f"- Reviewed with (service desk, major incident, change, CI owner teams): {TODO}", f"- Date: {TODO}", ""]
    return "\n".join(out)


def _status_order(st: str) -> int:
    order = list(STATUS_LABEL)
    return order.index(st) if st in order else len(order)


# ---------------------------------------------------------------- html

CSS = """
:root{--bg:#f6f7f8;--card:#fff;--ink:#1b2128;--muted:#66717c;--line:#e2e5e9;--ok:#1e7a4c;--warn:#a46200;--bad:#b42318;--info:#0b6bcb;--bar:#3d6fb6;--bar2:#c9d6ea}
@media (prefers-color-scheme:dark){:root{--bg:#13171b;--card:#1b2127;--ink:#e7eaee;--muted:#9aa5b0;--line:#2b333b;--ok:#4cc38a;--warn:#f0a83a;--bad:#f2685c;--info:#5aa9f0;--bar:#6f9be0;--bar2:#2e3d55}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:28px 18px 60px}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:34px 0 12px}h3{font-size:15px;margin:18px 0 8px}
.muted{color:var(--muted)}.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-top:20px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}.tile b{display:block;font-size:24px}
.overall{display:inline-block;margin-top:14px;padding:6px 14px;border-radius:99px;font-weight:700;border:2px solid currentColor}
.areas{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.area{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--ok);border-radius:10px;padding:10px 14px}
.area.critical{border-left-color:var(--bad)}.area.warning{border-left-color:var(--warn)}
.area .lbl{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin-bottom:4px}.area .cnt{display:block;font-size:13px;color:var(--muted);margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
tr:last-child td{border-bottom:0}.wrap{overflow-x:auto}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pill{display:inline-block;white-space:nowrap;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:600;border:1px solid currentColor}
.critical{color:var(--bad)}.warning{color:var(--warn)}.info{color:var(--info)}.ok{color:var(--ok)}
.area.critical,.area.warning,.area.ok{color:inherit}
.pill.healthy{color:var(--ok)}.pill.attention{color:var(--warn)}.pill.at-risk{color:var(--bad)}
td.subj{min-width:190px}td.nw{white-space:nowrap}td.fix{font-size:13px;color:var(--muted);min-width:200px;max-width:380px}td.sm{font-size:13px}
.brk{overflow-wrap:anywhere;word-break:break-word}
.bar{position:relative;height:14px;min-width:120px;background:var(--bar2);border-radius:3px}.bar i{position:absolute;left:0;top:0;bottom:0;background:var(--bar);border-radius:3px}
.bar i.hot{background:var(--bad)}
footer{margin-top:40px;font-size:13px}
"""


def _pill(cls: str, text: str) -> str:
    return f"<span class='pill {cls}'>{e(text)}</span>"


def _vpill(v: str) -> str:
    return _pill(v.replace(" ", "-"), v.upper())


def _table(head: list[str], rows: list[str]) -> str:
    return "<div class='wrap'><table><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr>" + "".join(rows) + "</table></div>"


def _sect(h: list, n: int, title: str, area: str, st: dict, note: str) -> None:
    pill = _vpill("healthy" if st[area] == "ok" else VERDICT[st[area]])
    h.append(f"<h2>{n}. {e(title)} {pill}</h2><p class='muted'>{e(note)}</p>")


def _area_table(findings: list[Finding], prefix: str) -> str:
    xs = [f for f in findings if f.code.startswith(prefix)]
    if not xs:
        return "<p class='muted'>Nothing to report.</p>"
    return _table(["Severity", "Finding", "Detail", "Next step"],
                  [f"<tr><td>{_pill(f.severity, f.severity.upper())}</td><td class='subj'><b>{e(f.code)}</b> {e(f.subject)}</td>"
                   f"<td class='sm brk'>{e(f.detail)}</td><td class='fix'>{e(f.fix)}</td></tr>" for f in xs])


def _bar(value: float, top: float, hot: bool = False) -> str:
    w = 0 if not top else max(2.0, min(100.0, value * 100 / top))
    return f"<div class='bar'><i class='{'hot' if hot else ''}' style='width:{w:.1f}%'></i></div>"


def render_html(d: Data, rv: dict, findings: list[Finding], title: str) -> str:
    s, sm, st = d.settings, summary(d, rv), area_status(findings)
    ov = overall(findings)
    h = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>{e(title)}</title><style>{CSS}</style></head><body><main>",
         f"<h1>{e(title)}</h1><p class='muted'>{e(s.organisation)} · as of {d.as_of:%a %d %b %Y} · incidents from {sm['first']:%d %b} to "
         f"{sm['last']:%d %b %Y}, trends over the last {s.window_days} days</p>",
         f"<span class='overall {'critical' if ov == 'at risk' else 'warning' if ov == 'attention' else 'ok'}'>Overall: {e(ov.upper())}</span>"
         "<div class='tiles'>"]
    tiles = [("Incidents", f"{sm['incidents']:,}", f"{sm['window']:,} in {s.window_days} days, {pct(sm['linked_share'])} linked"),
             ("Candidate problems", str(sm["candidates"]), f"{sm['candidates_critical']} critical"),
             ("Major incidents", str(sm["majors"]), f"{sm['majors_no_rca']} without RCA in time"),
             ("Open problems", str(sm["open"]), f"of {sm['problems']} · {sm['no_owner']} with no owner"),
             ("Stuck problems", str(sm["stuck"]), f"no update, overdue or {s.investigation_max_days}+ days in investigation"),
             ("Known errors", str(sm["known"]), f"{sm['known_nofix']} with no fix after {s.known_error_fix_days} days"),
             ("Fixes checked", str(sm["fixes"]), f"{sm['not_effective']} not effective"),
             ("Root cause unknown", pct(sm["unknown_share"]), f"{sm['unknown']} of {sm['done']} · maximum {pct(s.unknown_rc_max)}")]
    h += [f"<div class='tile'><span class='muted'>{e(x)}</span><b>{e(y)}</b><span class='muted'>{e(z)}</span></div>" for x, y, z in tiles]
    h.append("</div><h2>Status by area</h2><div class='areas'>")
    for ar in AREAS:
        n = sum(f.area == ar and f.severity != INFO for f in findings)
        h.append(f"<div class='area {st[ar]}'><span class='lbl'>{e(ar)}</span>"
                 f"{_pill(st[ar].replace('ok', 'healthy').replace('critical', 'at-risk').replace('warning', 'attention'), _status_word(st[ar]))}"
                 f"<span class='cnt'>{n} to act on</span></div>")
    h.append("</div>")
    crit = [f for f in findings if f.severity == CRITICAL]
    if crit:
        h.append("<h2>Fix first</h2>")
        h.append(_table(["Subject", "What", "Next step", "Owner"],
                        [f"<tr><td class='subj'><b>{e(f.subject)}</b><br><span class='muted'>{e(f.area)} · {e(f.code)}</span></td>"
                         f"<td class='sm brk'>{e(f.detail)}</td><td class='fix'>{e(f.fix)}</td><td class='nw'>{e(f.owner)}</td></tr>" for f in crit]))
    # 1 candidates
    _sect(h, 1, "Candidate problems", "Trends", st, f"Similar incidents in the last {s.window_days} days on the same CI and category with no "
          f"problem record, {s.cluster_min} or more, ranked by the priority weights of the incidents times the criticality of the CI. "
          "candidate-problems.csv has every incident.")
    top = max([r["score"] for r in rv["candidates"]] or [0])
    h.append(_table(["#", "CI · category", "Incidents", "First – last", "Common words", "Score", "", "Owner"],
                    [f"<tr><td class='num'>{r['rank']}</td><td class='sm'><b>{e(r['cluster'].ci or r['cluster'].service)}</b><br>"
                     f"<span class='muted'>{e(r['cluster'].category)} · {e(r['criticality'])}</span></td><td class='num'>{len(r['cluster'].members)}</td>"
                     f"<td class='nw sm'>{r['cluster'].members[0].day:%d %b} – {r['cluster'].members[-1].day:%d %b}</td>"
                     f"<td class='sm'>{e(' '.join(r['keywords']))}<br><span class='muted'>“{e(r['cluster'].members[-1].summary)}”</span></td>"
                     f"<td class='num {r['severity']}'>{r['score']:g}</td><td>{_bar(r['score'], top, r['severity'] == CRITICAL)}</td>"
                     f"<td class='sm'>{e(r['team'] or '–')}</td></tr>" for r in rv["candidates"]]) if rv["candidates"] else
             "<p class='muted'>No candidate problems.</p>")
    h.append("<p></p>" + _area_table(findings, "TRD"))
    # 2 majors
    _sect(h, 2, "Major incidents and RCA", "Major incidents", st, f"Every major incident needs a problem record and a root cause within "
          f"{s.rca_working_days} working days of its resolution.")
    h.append(_table(["Incident", "Date", "Problem", "RCA", "Working days", "Due"],
                    [f"<tr><td class='sm'><b>{e(r['incident'].key)}</b> {e(r['incident'].summary)}</td><td class='nw'>{r['end']:%d %b}</td>"
                     f"<td class='sm'>{e(', '.join(r['problems']) or '–')}</td><td class='sm {r['severity']}'>{e(r['state'])}</td>"
                     f"<td class='num'>{r['working_days']}</td><td class='nw'>{r['due']:%d %b}</td></tr>" for r in rv["majors"]])
             if rv["majors"] else "<p class='muted'>No major incidents.</p>")
    h.append("<p></p>" + _area_table(findings, "MAJ"))
    # 3 problems
    _sect(h, 3, "Open problems", "Stuck problems", st, f"No update for {s.stale_days} days, past the target date, new or under investigation "
          f"for more than {s.investigation_max_days} days, no owner, or an owner team different from the CI owner. problem-status.csv has every "
          "problem.")
    flagged = [r for r in rv["problems"] if r["problem"].open and any(i.severity != INFO for i in r["issues"])]
    h.append(_table(["Problem", "Status", "Owner", "Age", "Last update", "Target", "Next step"],
                    [f"<tr><td class='sm'><b>{e(r['problem'].key)}</b> {e(r['problem'].summary)}</td><td class='sm'>{e(STATUS_LABEL[r['problem'].status])}"
                     f"</td><td class='sm {'warning' if not r['problem'].owner else ''}'>{e(r['problem'].owner or '(none)')}</td>"
                     f"<td class='num'>{r['age'] if r['age'] is not None else '–'}</td><td class='nw sm'>{_d(r['problem'].updated) or '–'}</td>"
                     f"<td class='nw sm {'warning' if r['past_target'] else ''}'>{_d(r['problem'].target) or '–'}</td><td class='fix'>{e(problem_step(r))}"
                     f"</td></tr>" for r in flagged]) if flagged else "<p class='muted'>None.</p>")
    h.append("<p></p>" + _area_table(findings, "STK"))
    # 4 known errors
    _sect(h, 4, "Known errors", "Known errors", st, f"Open problems with a workaround: how long the workaround has been the answer, "
          f"whether the service desk has it, and whether a change for the permanent fix exists (after {s.known_error_fix_days} days).")
    h.append(_table(["Problem", "Days", "Workaround", "Published", "Change", "Incidents"],
                    [f"<tr><td class='sm'><b>{e(r['problem'].key)}</b> {e(r['problem'].summary)}</td><td class='num {_worst(r['issues'])}'>"
                     f"{r['days'] if r['days'] is not None else '–'}</td><td class='sm'>{e(r['problem'].workaround_text or '(none)')}</td>"
                     f"<td class='sm'>{'–' if r['problem'].published is None else ('yes' if r['problem'].published else 'no')}</td>"
                     f"<td class='sm'>{e(', '.join(c.key + ' ' + c.status.lower() for c in r['changes']) or '–')}</td><td class='num'>{r['recent']}</td></tr>"
                     for r in rv["known"]]) if rv["known"] else "<p class='muted'>None.</p>")
    h.append("<p></p>" + _area_table(findings, "KER"))
    # 5 fixes
    _sect(h, 5, "Fix effectiveness", "Fix verification", st, f"For each problem fixed by a change: the matching incidents in the 90 days "
          f"before and since the change (after {s.fix_grace_days} days of grace). fix-effectiveness.csv has the incidents.")
    h.append(_table(["Problem", "Change", "Implemented", "Before", "After", "Per 30 days", "Verdict"],
                    [f"<tr><td class='sm'><b>{e(r['problem'].key)}</b> {e(r['problem'].summary)}</td><td class='nw'>{e(r['change'].key)}</td>"
                     f"<td class='nw'>{r['implemented']:%d %b}</td><td class='num'>{len(r['before'])}</td><td class='num'>{len(r['after'])}</td>"
                     f"<td class='num'>{r['rate_before']:.1f} → {r['rate_after']:.1f}</td><td class='sm "
                     f"{'critical' if r['verdict'] == 'not effective' else 'warning' if r['verdict'] == 'change failed' else ''}'>{e(r['verdict'])}</td></tr>"
                     for r in rv["fixes"]]) if rv["fixes"] else "<p class='muted'>No fixes to verify.</p>")
    h.append("<p></p>" + _area_table(findings, "FIX"))
    # 6 quality
    q = rv["quality"]
    _sect(h, 6, "Quality of the records", "Quality", st, f"Root cause category unknown or other on {q['unknown']} of {q['done']} problems "
          f"past investigation ({pct(q['share'])}, maximum {pct(s.unknown_rc_max)}); problems closed without a root cause or a change; "
          "likely duplicates.")
    h.append(_area_table(findings, "QLT"))
    # cab
    cab = cab_items(d, rv)
    h.append("<h2>For the next CAB" + (f" ({s.next_cab:%d %b})" if s.next_cab else "") + "</h2>")
    h.append(_table(["Problem", "Change", "Ask"], [f"<tr><td class='sm'><b>{e(r['problem'].key)}</b> {e(r['problem'].summary)}</td>"
                                                    f"<td class='nw'>{e(r['change'])}</td><td class='sm'>{e(r['ask'])}</td></tr>" for r in cab])
             if cab else "<p class='muted'>Nothing for the CAB.</p>")
    h.append("<h2>All findings</h2>")
    h.append(_table(["Severity", "Area", "Subject", "Detail", "Owner"],
                    [f"<tr><td>{_pill(f.severity, f.severity.upper())}</td><td class='nw'>{e(f.area)}</td><td>{e(f.subject)}</td>"
                     f"<td class='sm brk'>{e(f.detail)}</td><td class='nw'>{e(f.owner)}</td></tr>" for f in findings]))
    h.append("<footer class='muted'>Generated by problemreview. Fictional demo data unless you ran it on your own exports. The pack for the "
             "problem review is problem-review-pack.md.</footer></main></body></html>")
    return "".join(h)


__all__ = ["render_html", "pack_md", "write_candidates", "write_problems", "write_known", "write_fixes", "write_actions", "write_findings"]
