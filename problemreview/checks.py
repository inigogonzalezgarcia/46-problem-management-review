"""The checks of the monthly problem management review. Six areas: trends (clusters of similar incidents with no problem record,
ranked by count, priority and service criticality), major incidents (no problem record, or no root cause, after a number of working
days), stuck problems (no update, past the target date, under investigation too long, no owner, owner team different from the CI
owner), known errors (a workaround and no permanent fix after a number of days, not published to the service desk, known error
without a workaround), fix verification (problems fixed by a change while matching incidents keep arriving, failed changes, reopened
incidents) and quality (root cause unknown or other, problems closed without a root cause or a change, duplicate problems)."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from .model import CLOSED, STATUS_LABEL, Data, Problem, _norm

CRITICAL, WARNING, INFO = "critical", "warning", "info"
ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}
AREAS = ("Trends", "Major incidents", "Stuck problems", "Known errors", "Fix verification", "Quality")
PREFIX = {"TRD": "Trends", "MAJ": "Major incidents", "STK": "Stuck problems", "KER": "Known errors", "FIX": "Fix verification",
          "QLT": "Quality"}
VERDICT = {CRITICAL: "at risk", WARNING: "attention", None: "healthy"}
RCA_DONE = {"root cause known", "known error", "fix in change", "resolved", "closed"}
STOP = set("""a an the and or of to in on at for from with without by is are was were be been being it its this that these those as
into after before when while during not no cannot can't cant unable please help user users issue issues problem problems error errors
fail fails failed failing failure getting get gets got still again some all any any every new old since via per our your my their his
her we they you he she them me has have had does doesn't dont do did will would should could may might also just very more less much
than then there here out off over under up down about only same other another each both few working work works way ticket""".split())


@dataclass
class Finding:
    severity: str
    area: str
    code: str
    subject: str
    detail: str
    fix: str
    owner: str = ""
    items: list[str] = field(default_factory=list)


@dataclass
class Issue:
    severity: str
    code: str
    text: str
    item: str = ""

    @property
    def area(self) -> str:
        return PREFIX[self.code.split("-")[0]]


def _n(k: int, word: str, plural: str | None = None) -> str:
    return f"{k} {word if k == 1 else (plural or word + 's')}"


def _top(items: list[str], k: int = 6, sep: str = ", ") -> str:
    return sep.join(items[:k]) + (f" and {len(items) - k} more" if len(items) > k else "")


def pct(x: float | None, k: int = 0) -> str:
    return "–" if x is None else f"{x:.{k}%}"


def _ratio(a: int, b: int) -> float | None:
    return a / b if b else None


# ---------------------------------------------------------------- text similarity (standard library only)

def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def tokens(text: str, extra_stop: set | None = None) -> frozenset:
    """Normalised words of a summary: lower case, no accents, digits or punctuation, no stop words, a crude stem."""
    stop = STOP | (extra_stop or set())
    words = re.findall(r"[a-z][a-z0-9]+", _norm(text))
    out = set()
    for w in words:
        if len(w) < 3 or w in stop or re.search(r"\d", w):
            continue
        st = _stem(w)
        if st not in stop:
            out.add(st)
    return frozenset(out)


def similar(a: frozenset, b: frozenset, threshold: float, min_shared: int) -> bool:
    """Overlap coefficient: the shared words over the words of the shorter text, with at least `min_shared` words in common."""
    if not a or not b:
        return False
    shared = len(a & b)
    return shared >= min(min_shared, len(a), len(b)) and shared / min(len(a), len(b)) >= threshold


def core(token_sets: list[frozenset], share: float = 0.5) -> frozenset:
    """The words present in at least `share` of the texts (all the words of a single text)."""
    if not token_sets:
        return frozenset()
    c = Counter(t for ts in token_sets for t in ts)
    n = len(token_sets)
    need = n if n <= 2 else share * n
    return frozenset(t for t, k in c.items() if k >= need)


def words_for(stems: frozenset, texts: list[str]) -> list[str]:
    """The original word most used for each stem, for display."""
    seen = Counter()
    for t in texts:
        for w in re.findall(r"[a-z][a-z0-9]+", _norm(t)):
            if _stem(w) in stems:
                seen[w] += 1
    best = {}
    for w, k in sorted(seen.items(), key=lambda x: (-x[1], x[0])):
        best.setdefault(_stem(w), w)
    return sorted(best.values())


def working_days(start: date, end: date, holidays: set) -> int:
    """Working days after `start` up to and including `end` (Monday to Friday, without the holidays)."""
    if end <= start:
        return 0
    n, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            n += 1
    return n


def add_working_days(start: date, k: int, holidays: set) -> date:
    d = start
    while k > 0:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            k -= 1
    return d


@dataclass
class Cluster:
    id: str
    ci: str
    service: str
    category: str
    members: list = field(default_factory=list)
    sets: list = field(default_factory=list)

    @property
    def core(self) -> frozenset:
        return core(self.sets)


def _group_key(i) -> tuple:
    return ((i.ci or "").lower() or "service:" + _norm(i.service), _norm(i.category))


def cluster(incidents: list, threshold: float, min_shared: int, extra_stop: set | None = None) -> list[Cluster]:
    """Group by CI (or service when there is no CI) and category, then join each incident, in order of creation, to the cluster whose
    core words it shares most, or start a new cluster. Deterministic: the input order is by creation time and key."""
    groups = defaultdict(list)
    for i in incidents:
        groups[_group_key(i)].append(i)
    out: list[Cluster] = []
    for gk in sorted(groups):
        cs: list[Cluster] = []
        for i in groups[gk]:
            ts = tokens(i.summary, extra_stop)
            best, score = None, 0.0
            for c in cs:
                cc = c.core
                if similar(ts, cc, threshold, min_shared):
                    sc = len(ts & cc) / min(len(ts), len(cc))
                    if sc > score:
                        best, score = c, sc
            if best is None:
                best = Cluster("", i.ci, i.service, i.category)
                cs.append(best)
            best.members.append(i)
            best.sets.append(ts)
        merged = True
        while merged:                      # clusters that started apart but share their core words
            merged = False
            for a in range(len(cs)):
                for b in range(a + 1, len(cs)):
                    if similar(cs[a].core, cs[b].core, threshold, min_shared):
                        pairs = sorted(zip(cs[a].members + cs[b].members, cs[a].sets + cs[b].sets), key=lambda x: (x[0].created, x[0].key))
                        cs[a].members, cs[a].sets = [x[0] for x in pairs], [x[1] for x in pairs]
                        del cs[b]
                        merged = True
                        break
                if merged:
                    break
        out += cs
    out.sort(key=lambda c: (-len(c.members), c.ci.lower(), _norm(c.category), c.members[0].key))
    for k, c in enumerate(out, 1):
        c.id = f"C{k:03d}"
    return out


# ---------------------------------------------------------------- review

def _same_place(p: Problem, i) -> bool:
    if p.ci and i.ci:
        return p.ci.lower() == i.ci.lower()
    return bool(p.service) and _norm(p.service) == _norm(i.service)


def review(d: Data) -> dict:
    s, today = d.settings, d.today
    hol = s.holiday_set()
    extra = set(s.stopwords)
    issues: list[Issue] = []
    probs = {p.key: p for p in d.problems}
    changes = {c.key: c for c in d.changes}
    linked = defaultdict(list)                       # problem -> incidents
    for i in d.incidents:
        for k in i.problems:
            linked[k].append(i)
    start = today - timedelta(days=s.window_days)
    window = [i for i in d.incidents if start < i.day <= today]

    def crit(ci: str, service: str = "") -> str:
        x = d.ci(ci)
        if x and x.criticality:
            return _norm(x.criticality)
        svc = [c for c in d.cmdb.values() if service and _norm(c.service) == _norm(service) and c.criticality]
        if svc:
            return max((_norm(c.criticality) for c in svc), key=lambda c: (s.cweight(c), c))
        return _norm(s.default_criticality)

    def signature(p: Problem, before: date | None = None) -> frozenset:
        """The words most of its linked incidents share (before a date), or the words of the problem summary."""
        xs = [i for i in linked.get(p.key, []) if before is None or i.day < before]
        sig = core([tokens(i.summary, extra) for i in xs], 0.4) if len(xs) >= 3 else frozenset()
        return sig if len(sig) >= s.min_shared_tokens else tokens(p.summary, extra)

    sigs = {p.key: signature(p) for p in d.problems}

    def matches(i, p: Problem, sig: frozenset) -> bool:
        return p.key in i.problems or (_same_place(p, i) and similar(tokens(i.summary, extra), sig, s.similarity, s.min_shared_tokens))

    # ------------------------------------------------ trends: candidate problems
    clusters = cluster(window, s.similarity, s.min_shared_tokens, extra)
    cand_rows, link_rows = [], []
    for c in clusters:
        if len(c.members) < s.cluster_min:
            continue
        unl = [i for i in c.members if not i.problems]
        lk = Counter(k for i in c.members for k in i.problems)
        cc = c.core
        match = None
        if lk and len(unl) < len(c.members) / 2:
            match = lk.most_common(1)[0][0]
        else:
            ms = sorted((p for p in d.problems if _same_place(p, c.members[0]) and similar(cc, sigs[p.key], s.similarity, s.min_shared_tokens)),
                        key=lambda p: (not p.open, p.key))
            match = ms[0].key if ms else None
        cr = crit(c.ci, c.service)
        score = sum(s.pweight(i.priority) for i in c.members) * s.cweight(cr)
        ci_ = d.ci(c.ci)
        team = ci_.team if ci_ and ci_.team else ""
        if not team:
            groups = Counter(i.group for i in c.members if i.group)
            team = sorted(groups.items(), key=lambda x: (-x[1], x[0]))[0][0] if groups else ""
        row = {"cluster": c, "unlinked": unl, "problem": match, "criticality": cr, "score": score, "team": team,
               "keywords": words_for(cc, [i.summary for i in c.members]), "priorities": Counter(i.priority for i in c.members),
               "majors": [i for i in c.members if i.major]}
        where = f"{c.ci or c.service or 'no CI'} · {c.category or 'no category'}"
        if match is None:
            sev = CRITICAL if score >= s.cluster_critical_score or row["majors"] else WARNING
            row["severity"] = sev
            cand_rows.append(row)
            issues.append(Issue(sev, "TRD-01", f"{where}: {_n(len(c.members), 'similar incident')} in {s.window_days} days "
                                f"({c.members[0].day:%d %b}–{c.members[-1].day:%d %b}), none linked to a problem; "
                                f"“{c.members[-1].summary}”; score {score:g}", c.id))
        elif unl:
            p = probs.get(match)
            row["severity"] = INFO
            link_rows.append(row)
            st = STATUS_LABEL.get(p.status, p.status) if p else "not in problems.csv"
            issues.append(Issue(INFO, "TRD-02", f"{where}: {_n(len(unl), 'incident')} {'looks' if len(unl) == 1 else 'look'} like {match} ({st}) "
                                "and not linked to it",
                                "; ".join(i.key for i in unl)))
    cand_rows.sort(key=lambda r: (-r["score"], r["cluster"].id))
    for k, r in enumerate(cand_rows, 1):
        r["rank"] = k
    # ------------------------------------------------ major incidents
    major_rows = []
    for i in [x for x in d.incidents if x.major]:
        end = (i.resolved or i.created).date()
        wd = working_days(end, today, hol)
        due = add_working_days(end, s.rca_working_days, hol)
        ps = [probs[k] for k in i.problems if k in probs]
        rca = [p for p in ps if p.status in RCA_DONE or p.root_cause.strip()]
        state = "RCA done" if rca else ("problem, no root cause" if ps else ("problem not in export" if i.problems else "no problem"))
        sev = ""
        if not i.problems:
            sev = CRITICAL if wd > s.rca_working_days else WARNING
            issues.append(Issue(sev, "MAJ-01", f"{i.key} {i.summary} ({end:%d %b}): no problem record, "
                                + (f"{wd} working days after the incident (RCA due {due:%d %b})" if wd > s.rca_working_days
                                   else f"RCA due {due:%d %b}"), i.key))
        elif ps and not rca and wd > s.rca_working_days:
            sev = CRITICAL
            issues.append(Issue(sev, "MAJ-02", f"{i.key} {i.summary} ({end:%d %b}): {', '.join(p.key for p in ps)} "
                                f"{STATUS_LABEL.get(ps[0].status, ps[0].status).lower()} with no root cause, {wd} working days after the incident "
                                f"(due {due:%d %b})", i.key))
        major_rows.append({"incident": i, "end": end, "working_days": wd, "due": due, "problems": i.problems, "state": state, "severity": sev})
    # ------------------------------------------------ open problems
    major_by_problem = defaultdict(list)
    for r in major_rows:
        for k in r["problems"]:
            major_by_problem[k].append(r["incident"].key)
    prob_rows = []
    for p in d.problems:
        pi = []
        recent = sum(1 for i in linked.get(p.key, []) if start < i.day <= today)
        ci_ = d.ci(p.ci)
        row = {"problem": p, "issues": pi, "incidents": len(linked.get(p.key, [])), "recent": recent, "majors": major_by_problem.get(p.key, []),
               "ci_team": ci_.team if ci_ else "", "age": (today - p.opened).days if p.opened else None,
               "since_update": (today - p.updated).days if p.updated else None,
               "past_target": (today - p.target).days if p.target and p.target < today else 0}
        prob_rows.append(row)
        if not p.open:
            continue
        what = f"{p.key} {p.summary}"
        if p.updated is None or row["since_update"] > s.stale_days:
            pi.append(Issue(WARNING, "STK-01", f"{what}: " + ("no update recorded" if p.updated is None else
                                                              f"no update for {row['since_update']} days (since {p.updated:%d %b})"), p.key))
        if row["past_target"]:
            pi.append(Issue(WARNING, "STK-02", f"{what}: {row['past_target']} days past the target date ({p.target:%d %b %Y})", p.key))
        if p.status in ("new", "under investigation") and row["age"] is not None and row["age"] > s.investigation_max_days:
            pi.append(Issue(WARNING, "STK-03", f"{what}: {STATUS_LABEL[p.status].lower()} for {row['age']} days", p.key))
        if not p.owner.strip():
            sev = CRITICAL if row["majors"] else WARNING
            pi.append(Issue(sev, "STK-04", f"{what}: no owner" + (f" (major incident {', '.join(row['majors'])})" if row["majors"] else "")
                            + f", {recent} linked incidents in {s.window_days} days", p.key))
        if p.team and row["ci_team"] and _norm(p.team) != _norm(row["ci_team"]):
            pi.append(Issue(WARNING, "STK-05", f"{what}: owned by {p.team}, {p.ci} is owned by {row['ci_team']} in the CMDB", p.key))
        if p.review and p.review < today:
            pi.append(Issue(INFO, "STK-06", f"{what}: review date {p.review:%d %b} passed", p.key))
        issues += pi
    # ------------------------------------------------ known errors
    ke_rows = []
    for row in prob_rows:
        p = row["problem"]
        if not p.open or not (p.workaround or p.status == "known error"):
            continue
        ki = []
        since = p.known_error_since or p.opened
        days = (today - since).days if since else None
        chs = [changes[k] for k in p.changes if k in changes]
        done = [c for c in chs if c.done and not c.failed]
        what = f"{p.key} {p.summary}"
        if p.workaround and not done and days is not None and days >= s.known_error_fix_days:
            if chs or p.changes:
                planned = ", ".join(f"{c.key} {c.status.lower()}" for c in chs) or ", ".join(p.changes)
                ki.append(Issue(INFO, "KER-01", f"{what}: workaround for {days} days, permanent fix planned ({planned})", p.key))
            else:
                sev = CRITICAL if days >= s.known_error_critical_days else WARNING
                ki.append(Issue(sev, "KER-01", f"{what}: workaround for {days} days (since {since:%d %b %Y}) and no change for a permanent "
                                f"fix; {row['recent']} incidents in {s.window_days} days", p.key))
        if p.workaround and p.published is False:
            ki.append(Issue(WARNING, "KER-02", f"{what}: workaround not published to the service desk", p.key))
        if p.status == "known error" and not p.workaround:
            ki.append(Issue(WARNING, "KER-03", f"{what}: known error with no workaround documented", p.key))
        ke_rows.append({"problem": p, "since": since, "days": days, "changes": chs, "done": done, "recent": row["recent"], "issues": ki})
        issues += ki
    # ------------------------------------------------ fix verification
    fix_rows = []
    for p in d.problems:
        chs = [changes[k] for k in p.changes if k in changes] + [c for c in d.changes if p.key in c.problems and c.key not in p.changes]
        chs = [c for c in chs if c.implemented]
        if not chs or p.status not in ("fix in change", "resolved", "closed"):
            continue
        c = max(chs, key=lambda x: (x.implemented, x.key))
        when = c.implemented
        sig = signature(p, when)
        before = [i for i in d.incidents if when - timedelta(days=90) <= i.day < when and matches(i, p, sig)]
        after = [i for i in d.incidents if i.day > when + timedelta(days=s.fix_grace_days) and i.day <= today and matches(i, p, sig)]
        days_after = (today - when).days
        if c.failed:
            verdict = "change failed"
        elif len(after) >= s.fix_recurrence_min:
            verdict = "not effective"
        elif days_after < 30:
            verdict = "too early"
        else:
            verdict = "effective"
        span = max(1, min(90, (when - min(i.day for i in before)).days + 1)) if before else 90
        r = {"problem": p, "change": c, "implemented": when, "before": before, "after": after, "days_after": days_after, "verdict": verdict,
             "rate_before": len(before) * 30 / span if before else 0.0, "rate_after": len(after) * 30 / max(1, days_after - s.fix_grace_days)}
        fix_rows.append(r)
        if verdict == "not effective":
            nl = sum(1 for i in after if p.key not in i.problems)
            issues.append(Issue(CRITICAL if p.status in CLOSED else WARNING, "FIX-01",
                                f"{p.key} {p.summary}: {STATUS_LABEL.get(p.status, p.status).lower()} by {c.key} on {when:%d %b}, "
                                f"{_n(len(after), 'matching incident')} since ({nl} not linked), {r['rate_after']:.1f} a month against "
                                f"{r['rate_before']:.1f} before", p.key))
        elif verdict == "change failed" and p.status in CLOSED:
            issues.append(Issue(WARNING, "FIX-02", f"{p.key} {p.summary}: {STATUS_LABEL[p.status].lower()}, but {c.key} ended "
                                f"“{c.outcome}”", p.key))
    reopened = [i for i in window if i.reopen >= s.reopen_min]
    if reopened:
        by = Counter(i.service or "(no service)" for i in reopened)
        issues.append(Issue(WARNING, "FIX-03", f"{_n(len(reopened), 'incident')} reopened {s.reopen_min} or more times in {s.window_days} days: "
                            + ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda x: (-x[1], x[0]))),
                            "; ".join(i.key for i in reopened)))
    # ------------------------------------------------ quality
    unknown_set = {_norm(x) for x in s.unknown_categories}
    done = [p for p in d.problems if p.status in RCA_DONE]
    unknown = [p for p in done if not _norm(p.rc_category) or _norm(p.rc_category) in unknown_set]
    share = _ratio(len(unknown), len(done))
    if share is not None and share > s.unknown_rc_max:
        sev = CRITICAL if share > 2 * s.unknown_rc_max else WARNING
        cats = Counter(p.rc_category or "(empty)" for p in unknown)
        issues.append(Issue(sev, "QLT-01", f"Root cause category {', '.join(f'{k} {v}' for k, v in sorted(cats.items()))} on "
                            f"{len(unknown)} of {len(done)} problems past investigation ({pct(share)}, maximum {pct(s.unknown_rc_max)})",
                            "; ".join(p.key for p in unknown)))
    for p in d.problems:
        if p.status not in CLOSED:
            continue
        no_rc = (not _norm(p.rc_category) or _norm(p.rc_category) in unknown_set) and not p.root_cause.strip()
        if no_rc:
            issues.append(Issue(WARNING, "QLT-02", f"{p.key} {p.summary}: {STATUS_LABEL[p.status].lower()} with no root cause", p.key))
        elif not p.changes and not any(p.key in c.problems for c in d.changes):
            issues.append(Issue(INFO, "QLT-04", f"{p.key} {p.summary}: {STATUS_LABEL[p.status].lower()} with no linked change", p.key))
    open_ps = [p for p in d.problems if p.open and p.ci]
    seen = set()
    for a in open_ps:
        for b in open_ps:
            if a.key < b.key and a.ci.lower() == b.ci.lower() and (a.key, b.key) not in seen and \
                    similar(tokens(a.summary, extra), tokens(b.summary, extra), s.similarity, s.min_shared_tokens):
                seen.add((a.key, b.key))
                issues.append(Issue(WARNING, "QLT-03", f"{a.key} “{a.summary}” and {b.key} “{b.summary}” on {a.ci}: likely duplicates",
                                    f"{a.key}; {b.key}"))
    quality = {"done": len(done), "unknown": len(unknown), "share": share}
    linked_window = sum(1 for i in window if i.problems)
    return {"issues": issues, "clusters": clusters, "candidates": cand_rows, "to_link": link_rows, "majors": major_rows, "problems": prob_rows,
            "known": ke_rows, "fixes": fix_rows, "reopened": reopened, "quality": quality, "window": window,
            "linked_share": _ratio(linked_window, len(window)), "start": start}


# ---------------------------------------------------------------- findings

CODES = {
    "TRD-01": ("trends", "recurring incidents with no problem record: candidate problems",
               "Open a problem for each cluster, link its incidents and name the owner team of the CI.", "group"),
    "TRD-02": ("trends", "incidents that match an existing problem and are not linked",
               "Link them so the problem shows its real impact; brief the service desk on the matching rule.", "group"),
    "MAJ-01": ("major", "major incidents with no problem record", "Open the problem today and book the RCA session (timeline, 5 whys).",
               "group"),
    "MAJ-02": ("major", "major incidents whose problem has no root cause after the RCA deadline",
               "Hold the RCA session this week; escalate to the service owner if the evidence is missing.", "group"),
    "STK-01": ("stuck", "open problems with no recent update", "Ask the owner for an update before the review, or bring it to the review.",
               "problem"),
    "STK-02": ("stuck", "open problems past their target date", "Agree a new target date with a reason, or escalate.", "problem"),
    "STK-03": ("stuck", "problems under investigation for too long", "Decide at the review: more resources, a vendor case, or accept and "
               "close with a known error.", "problem"),
    "STK-04": ("stuck", "open problems with no owner", "Name an owner from the team that owns the CI.", "problem"),
    "STK-05": ("stuck", "problems owned by a team different from the CI owner", "Move the problem to the CI owner team or record why not.",
               "problem"),
    "STK-06": ("stuck", "problems with the review date passed", "Set the next review date.", "problem"),
    "KER-01": ("known", "known errors with a workaround and no permanent fix", "Raise the change for the permanent fix and take it to the "
               "next CAB, or accept the workaround with a reason and a review date.", "problem"),
    "KER-02": ("known", "workarounds not published to the service desk", "Publish the known error article for the service desk.", "problem"),
    "KER-03": ("known", "known errors with no workaround documented", "Document the workaround, or move the problem back to investigation.",
               "problem"),
    "FIX-01": ("fix", "fixes that did not stop the incidents", "Reopen the problem, link the new incidents and review the change "
               "with its implementer before the next CAB.", "problem"),
    "FIX-02": ("fix", "problems closed by a change that failed or was backed out", "Reopen the problem and plan the change again.",
               "problem"),
    "FIX-03": ("fix", "reopened incidents", "Check whether the resolutions were workarounds; link the incidents to a problem.", "group"),
    "QLT-01": ("quality", "root cause recorded as unknown or other", "Review each one: a root cause category, or the problem goes back "
               "to investigation.", "group"),
    "QLT-02": ("quality", "problems closed without a root cause", "Reopen or record the root cause before the problem counts as resolved.",
               "problem"),
    "QLT-04": ("quality", "problems closed without a linked change", "Fine when the fix was outside IT change (a vendor fix, a "
               "replacement); record it in the root cause.", "problem"),
    "QLT-03": ("quality", "likely duplicate problems on the same CI", "Merge them: keep one record, link all the incidents to it.", "pair"),
}


def run_all(d: Data, rv: dict | None = None) -> list[Finding]:
    rv = rv if rv is not None else review(d)
    s = d.settings
    hits = defaultdict(list)
    for i in rv["issues"]:
        hits[i.code].append(i)
    out: list[Finding] = []
    for code, (owner, subject, fix, word) in CODES.items():
        for sev in (CRITICAL, WARNING, INFO):
            xs = [i for i in hits.get(code, []) if i.severity == sev]
            if not xs:
                continue
            head = subject if word == "group" else f"{_n(len(xs), word)}: {subject}"
            head = head[0].upper() + head[1:]
            if sev == INFO:
                head = f"For information ({code}): {head}"
            items = list(dict.fromkeys(x for i in xs for x in i.item.split("; ") if x))
            out.append(Finding(sev, PREFIX[code.split("-")[0]], code, head, _top([i.text for i in xs], 8, "; "),
                               fix if sev != INFO else "No action needed before the review; check it at the review.", s.owner(owner), items))
    out.sort(key=lambda f: (ORDER[f.severity], AREAS.index(f.area), f.code))
    return out


def summary(d: Data, rv: dict) -> dict:
    open_ps = [r for r in rv["problems"] if r["problem"].open]
    stuck = [r for r in open_ps if any(i.code in ("STK-01", "STK-02", "STK-03", "STK-04") for i in r["issues"])]
    ke_nofix = [r for r in rv["known"] if any(i.code == "KER-01" and i.severity != INFO for i in r["issues"])]
    return dict(
        incidents=len(d.incidents), window=len(rv["window"]), linked_share=rv["linked_share"],
        first=d.incidents[0].day if d.incidents else None, last=d.incidents[-1].day if d.incidents else None,
        clusters=sum(1 for c in rv["clusters"] if len(c.members) >= d.settings.cluster_min), candidates=len(rv["candidates"]),
        candidates_critical=sum(1 for r in rv["candidates"] if r["severity"] == CRITICAL),
        top=rv["candidates"][0] if rv["candidates"] else None,
        problems=len(d.problems), open=len(open_ps), stuck=len(stuck), no_owner=sum(1 for r in open_ps if not r["problem"].owner.strip()),
        majors=len(rv["majors"]), majors_no_rca=sum(1 for r in rv["majors"] if r["severity"] == CRITICAL),
        known=len(rv["known"]), known_nofix=len(ke_nofix), fixes=len(rv["fixes"]),
        not_effective=sum(1 for r in rv["fixes"] if r["verdict"] == "not effective"), reopened=len(rv["reopened"]),
        unknown_share=rv["quality"]["share"], unknown=rv["quality"]["unknown"], done=rv["quality"]["done"],
        changes=len(d.changes),
    )


def area_status(findings: list[Finding]) -> dict[str, str]:
    st = {}
    for a in AREAS:
        sev = [f.severity for f in findings if f.area == a and f.severity != INFO]
        st[a] = CRITICAL if CRITICAL in sev else WARNING if sev else "ok"
    return st


def overall(findings: list[Finding]) -> str:
    st = set(area_status(findings).values())
    return VERDICT[CRITICAL] if CRITICAL in st else VERDICT[WARNING] if WARNING in st else VERDICT[None]


def cab_items(d: Data, rv: dict) -> list[dict]:
    """What goes to the next CAB: permanent fixes waiting for a change, known errors without one, and fixes that did not work."""
    out = []
    for r in rv["problems"]:
        p = r["problem"]
        if p.status == "fix in change":
            chs = [c for c in d.changes if c.key in p.changes or p.key in c.problems]
            pending = [c for c in chs if not c.done]
            if pending or not chs:
                out.append({"problem": p, "change": ", ".join(c.key for c in pending) or "(none linked)",
                            "ask": "approve and schedule the permanent fix" if pending else "raise the change for the fix", "code": ""})
    for r in rv["known"]:
        for i in r["issues"]:
            if i.code == "KER-01" and i.severity != INFO:
                out.append({"problem": r["problem"], "change": "(to raise)", "ask": "raise a change for the permanent fix", "code": i.code})
    for r in rv["fixes"]:
        if r["verdict"] == "not effective":
            out.append({"problem": r["problem"], "change": r["change"].key, "ask": "post-implementation review: the incidents continue",
                        "code": "FIX-01"})
    return out


__all__ = ["AREAS", "CRITICAL", "WARNING", "INFO", "Finding", "Issue", "review", "run_all", "summary", "area_status", "overall",
           "tokens", "similar", "cluster", "working_days", "cab_items"]
