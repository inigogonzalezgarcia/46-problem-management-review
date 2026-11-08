"""Loading: the incidents and problems exported from the ITSM tool (Jira Service Management, HaloITSM, EasyVista or any tool that
exports the same columns), and optionally the changes linked to problems and the CMDB configuration items with their service,
criticality and owner team. Forgiving column names, into plain dataclasses."""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

INCIDENT_ALIASES = {
    "key": ["Issue key", "Key", "Ticket", "Ticket ID", "Incident", "Incident number", "id"],
    "created": ["Created", "Opened", "Date opened", "Reported", "Creation date"],
    "resolved": ["Resolved", "Resolution date", "Date resolved", "resolutiondate", "Closed"],
    "priority": ["Priority", "Impact priority"],
    "service": ["Affected services", "Service", "Business service", "Affected service"],
    "ci": ["Configuration item", "CI", "Asset", "Affected CI", "Affected asset"],
    "category": ["Category", "Components", "Component", "Classification"],
    "group": ["Assignment group", "Team", "Assigned team", "Support group", "Group"],
    "problem": ["Linked problem", "Problem", "Linked problems", "Parent problem"],
    "summary": ["Summary", "Short description", "Subject", "Title"],
    "resolution": ["Resolution code", "Resolution", "Closure code", "Close code"],
    "reopen": ["Reopen count", "Reopened", "Times reopened", "reopen_count"],
    "major": ["Major incident", "Major", "Major incident flag", "is major"],
}
PROBLEM_ALIASES = {
    "key": ["Issue key", "Key", "Problem", "Problem number", "Ticket ID", "id"],
    "summary": ["Summary", "Short description", "Title", "Subject"],
    "opened": ["Created", "Opened", "Date opened", "Creation date"],
    "status": ["Status", "State"],
    "owner": ["Assignee", "Owner", "Problem owner"],
    "team": ["Owner team", "Team", "Assignment group", "Assigned team"],
    "service": ["Affected services", "Service", "Business service"],
    "ci": ["Configuration item", "CI", "Asset", "Affected CI"],
    "rc_category": ["Root cause category", "Root cause type", "Cause category", "Cause code"],
    "root_cause": ["Root cause", "Root cause description", "Cause"],
    "workaround": ["Workaround", "Workaround available", "Has workaround"],
    "workaround_text": ["Workaround text", "Workaround description"],
    "known_error_since": ["Known error since", "Known error date", "Workaround date"],
    "published": ["Published to service desk", "Known error published", "KEDB", "In KEDB", "Published"],
    "change": ["Linked change", "Change", "Linked changes", "Fix change"],
    "target": ["Target date", "Due date", "Due", "Target resolution date"],
    "updated": ["Last update", "Updated", "Last updated", "Last modified"],
    "review": ["Review date", "Next review", "Next review date"],
    "resolved": ["Resolved", "Resolution date", "Date resolved", "Closed"],
}
CHANGE_ALIASES = {
    "key": ["Issue key", "Key", "Change", "Change number", "Ticket ID", "id"],
    "summary": ["Summary", "Short description", "Title"],
    "status": ["Status", "State"],
    "implemented": ["Implemented", "Implemented date", "Actual end", "Completed", "Resolved"],
    "problem": ["Linked problem", "Problem", "Linked problems"],
    "outcome": ["Outcome", "Resolution", "Close code", "Result"],
}
CI_ALIASES = {
    "ci": ["CI", "Name", "Configuration item", "Asset", "Object"],
    "service": ["Service", "Business service", "Affected services"],
    "criticality": ["Criticality", "Business criticality", "Tier", "Impact"],
    "team": ["Owner team", "Support group", "Team", "Owner"],
}
STATUSES = ("new", "under investigation", "root cause known", "known error", "fix in change", "resolved", "closed")
STATUS_LABEL = {"new": "New", "under investigation": "Under investigation", "root cause known": "Root cause known",
                "known error": "Known error", "fix in change": "Fix in change", "resolved": "Resolved", "closed": "Closed"}
STATUS_ALIASES = {"open": "new", "to do": "new", "logged": "new", "investigating": "under investigation", "in progress": "under investigation",
                  "under review": "root cause known", "rca complete": "root cause known", "root cause identified": "root cause known",
                  "known errors": "known error", "kedb": "known error", "awaiting change": "fix in change", "pending change": "fix in change",
                  "completed": "resolved", "done": "resolved", "fixed": "resolved", "canceled": "closed", "cancelled": "closed",
                  "rejected": "closed"}
CLOSED = {"resolved", "closed"}
PRIORITY_ALIASES = {"highest": 1, "critical": 1, "p1": 1, "1": 1, "high": 2, "p2": 2, "2": 2, "medium": 3, "moderate": 3, "p3": 3, "3": 3,
                    "low": 4, "p4": 4, "4": 4, "lowest": 5, "planning": 5, "p5": 5, "5": 5}
YES = {"yes", "y", "true", "1", "on", "si", "x", "published", "major"}
NO = {"no", "n", "false", "0", "off", "none"}
DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M", "%d/%m/%Y", "%d/%b/%y %I:%M %p", "%d/%b/%y", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M", "%m/%d/%Y")
DEFAULT_OWNERS = {"trends": "Problem manager", "major": "Major incident manager", "stuck": "Problem manager",
                  "known": "Service desk lead", "fix": "Change manager", "quality": "Problem manager"}
DEFAULT_PRIORITY_WEIGHTS = {"1": 8, "2": 4, "3": 2, "4": 1, "5": 1}
DEFAULT_CRITICALITY_WEIGHTS = {"critical": 3, "high": 2, "medium": 1.5, "low": 1}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(ch for ch in s if not unicodedata.combining(ch))).strip()


def parse_dt(v) -> datetime | None:
    s = str(v or "").strip()
    if not s or _norm(s) in {"n a", "na", "none", "null", "never"}:
        return None
    s = re.sub(r"(\.\d+)?(Z|[+-]\d{2}:?\d{2})$", "", s)
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def parse_d(v) -> date | None:
    x = parse_dt(v)
    return x.date() if x else None


def yes(v) -> bool:
    return _norm(v) in YES


def tri(v) -> bool | None:
    """yes / no / unknown (empty)."""
    n = _norm(v)
    if not n:
        return None
    return n in YES


def num(v) -> float | None:
    s = str(v or "").strip().replace("%", "").replace(" ", "")
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    s = s.replace(",", "")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def split_list(v) -> list[str]:
    return [x.strip() for x in re.split(r"[;|,]", str(v or "")) if x.strip()]


def priority(v) -> int:
    n = _norm(v)
    if n in PRIORITY_ALIASES:
        return PRIORITY_ALIASES[n]
    m = re.match(r"(p\s?)?([1-5])\b", n)
    if m:
        return int(m.group(2))
    for word, p in PRIORITY_ALIASES.items():
        if not word[0].isdigit() and re.search(rf"\b{word}\b", n):
            return p
    return 3


def status(v) -> str:
    n = _norm(v)
    if n in STATUSES:
        return n
    return STATUS_ALIASES.get(n, "new" if not n else n)


def _key(v) -> str:
    return str(v or "").strip().upper()


def natural(key: str) -> tuple:
    """PRB-9 before PRB-10."""
    return tuple(int(x) if x.isdigit() else x for x in re.split(r"(\d+)", key))


def _ci(v) -> str:
    return str(v or "").strip()


def _read(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        header = fh.readline()
        fh.seek(0)
        delim = max(",;\t", key=header.count)
        reader = csv.DictReader(fh, delimiter=delim)
        return list(reader.fieldnames or []), list(reader)


def _map(fields: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    heads = {_norm(h): h for h in fields}
    cols = {}
    for k, names in aliases.items():
        for n in names + [k.replace("_", " ")]:
            if _norm(n) in heads and heads[_norm(n)] not in cols.values():
                cols[k] = heads[_norm(n)]
                break
    return cols


def _rows(path: Path, aliases: dict[str, list[str]]) -> list[dict]:
    fields, raw = _read(path)
    cols = _map(fields, aliases)
    return [{k: (r.get(c) or "").strip() for k, c in cols.items()} for r in raw]


@dataclass
class Incident:
    key: str
    created: datetime
    resolved: datetime | None = None
    priority: int = 3
    priority_label: str = ""
    service: str = ""
    ci: str = ""
    category: str = ""
    group: str = ""
    problems: list = field(default_factory=list)
    summary: str = ""
    resolution: str = ""
    reopen: int = 0
    major: bool = False

    @property
    def day(self) -> date:
        return self.created.date()


@dataclass
class Problem:
    key: str
    summary: str = ""
    opened: date | None = None
    status: str = "new"
    status_label: str = ""
    owner: str = ""
    team: str = ""
    service: str = ""
    ci: str = ""
    rc_category: str = ""
    root_cause: str = ""
    workaround: bool = False
    workaround_text: str = ""
    known_error_since: date | None = None
    published: bool | None = None
    changes: list = field(default_factory=list)
    target: date | None = None
    updated: date | None = None
    review: date | None = None
    resolved: date | None = None

    @property
    def open(self) -> bool:
        return self.status not in CLOSED


@dataclass
class Change:
    key: str
    summary: str = ""
    status: str = ""
    implemented: date | None = None
    problems: list = field(default_factory=list)
    outcome: str = ""

    @property
    def done(self) -> bool:
        return self.implemented is not None and _norm(self.status) in {"implemented", "closed", "completed", "done", "resolved", "review"}

    @property
    def failed(self) -> bool:
        return any(w in _norm(self.outcome) for w in ("fail", "backed out", "back out", "rolled back", "rollback", "unsuccessful"))


@dataclass
class CI:
    ci: str
    service: str = ""
    criticality: str = ""
    team: str = ""


@dataclass
class Settings:
    organisation: str = "Problem management review"
    as_of: datetime | None = None
    window_days: int = 90
    history_days: int = 180
    cluster_min: int = 5
    cluster_critical_score: float = 100
    similarity: float = 0.5
    min_shared_tokens: int = 2
    priority_weights: dict = field(default_factory=lambda: dict(DEFAULT_PRIORITY_WEIGHTS))
    criticality_weights: dict = field(default_factory=lambda: dict(DEFAULT_CRITICALITY_WEIGHTS))
    default_criticality: str = "medium"
    stopwords: list = field(default_factory=list)
    rca_working_days: int = 5
    holidays: list = field(default_factory=list)
    stale_days: int = 30
    investigation_max_days: int = 60
    known_error_fix_days: int = 90
    known_error_critical_days: int = 180
    fix_grace_days: int = 3
    fix_recurrence_min: int = 3
    reopen_min: int = 2
    unknown_rc_max: float = 0.2
    unknown_categories: list = field(default_factory=lambda: ["unknown", "other", "not determined", "undetermined"])
    next_review: date | None = None
    next_cab: date | None = None
    owners: dict = field(default_factory=lambda: dict(DEFAULT_OWNERS))

    def owner(self, area: str) -> str:
        return self.owners.get(area) or DEFAULT_OWNERS.get(area, "Problem manager")

    def pweight(self, p: int) -> float:
        return float(num(self.priority_weights.get(str(p))) or 1)

    def cweight(self, crit: str) -> float:
        c = _norm(crit) or _norm(self.default_criticality)
        return float(num(self.criticality_weights.get(c)) or 1)

    def holiday_set(self) -> set:
        return {x for x in (parse_d(h) for h in self.holidays) if x}


def settings_from_dict(raw: dict) -> Settings:
    s = Settings()
    for k, v in raw.items():
        if not hasattr(s, k) or v is None:
            continue
        cur = getattr(s, k)
        if k == "as_of":
            s.as_of = parse_dt(v)
        elif k in ("next_review", "next_cab"):
            setattr(s, k, parse_d(v))
        elif k == "holidays":
            s.holidays = [str(x) for x in v]
        elif k == "criticality_weights":
            s.criticality_weights.update({_norm(a): b for a, b in v.items()})
        elif k == "priority_weights":
            s.priority_weights.update({str(priority(a)): b for a, b in v.items()})
        elif isinstance(cur, dict):
            cur.update({str(a): b for a, b in v.items()})
        elif isinstance(cur, list):
            setattr(s, k, [str(x).lower() for x in v])
        elif isinstance(cur, bool):
            setattr(s, k, bool(v))
        elif isinstance(cur, int) and not isinstance(cur, bool):
            setattr(s, k, int(num(v) or 0))
        elif isinstance(cur, float):
            x = float(num(v) or 0)
            setattr(s, k, x / 100 if k in ("similarity", "unknown_rc_max") and x > 1 else x)
        else:
            setattr(s, k, v)
    return s


@dataclass
class Data:
    settings: Settings
    as_of: datetime
    incidents: list[Incident] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    cmdb: dict = field(default_factory=dict)        # ci (lower) -> CI
    sources: dict = field(default_factory=dict)

    @property
    def today(self) -> date:
        return self.as_of.date()

    def ci(self, name: str) -> CI | None:
        return self.cmdb.get(str(name or "").strip().lower())


# ---------------------------------------------------------------- loaders

def load_incidents(path: Path) -> list[Incident]:
    out = []
    for r in _rows(path, INCIDENT_ALIASES):
        created = parse_dt(r.get("created"))
        if not r.get("key") or not created:
            continue
        out.append(Incident(_key(r["key"]), created, parse_dt(r.get("resolved")), priority(r.get("priority")), r.get("priority", ""),
                            r.get("service", ""), _ci(r.get("ci")), r.get("category", ""), r.get("group", ""),
                            [_key(x) for x in split_list(r.get("problem"))], r.get("summary", ""), r.get("resolution", ""),
                            int(num(r.get("reopen")) or 0), yes(r.get("major"))))
    return sorted(out, key=lambda i: (i.created, natural(i.key)))


def load_problems(path: Path) -> list[Problem]:
    out = []
    for r in _rows(path, PROBLEM_ALIASES):
        if not r.get("key"):
            continue
        wt, wa = r.get("workaround_text", ""), r.get("workaround", "")
        nw = _norm(wa)
        if nw and nw not in YES and nw not in NO and not wt:
            wt = wa                      # the workaround column holds the text itself
        has = nw in YES or (nw not in NO and bool(wt))
        out.append(Problem(_key(r["key"]), r.get("summary", ""), parse_d(r.get("opened")), status(r.get("status")), r.get("status", ""),
                           r.get("owner", ""), r.get("team", ""), r.get("service", ""), _ci(r.get("ci")), r.get("rc_category", ""),
                           r.get("root_cause", ""), has, wt, parse_d(r.get("known_error_since")), tri(r.get("published")),
                           [_key(x) for x in split_list(r.get("change"))], parse_d(r.get("target")), parse_d(r.get("updated")),
                           parse_d(r.get("review")), parse_d(r.get("resolved"))))
    return sorted(out, key=lambda p: natural(p.key))


def load_changes(path: Path) -> list[Change]:
    return sorted([Change(_key(r["key"]), r.get("summary", ""), r.get("status", ""), parse_d(r.get("implemented")),
                          [_key(x) for x in split_list(r.get("problem"))], r.get("outcome", ""))
                   for r in _rows(path, CHANGE_ALIASES) if r.get("key")], key=lambda c: natural(c.key))


def load_cmdb(path: Path) -> dict:
    return {r["ci"].strip().lower(): CI(r["ci"].strip(), r.get("service", ""), r.get("criticality", ""), r.get("team", ""))
            for r in _rows(path, CI_ALIASES) if r.get("ci")}


FILES = {
    "incidents.csv": "Incidents exported from the ITSM tool (Jira Service Management, HaloITSM, EasyVista)",
    "problems.csv": "Problem records with status, owner, root cause category, workaround, linked change and dates",
    "changes.csv": "Changes linked to problems, with status, implementation date and outcome (optional)",
    "cmdb.csv": "Configuration items with service, criticality and owner team (optional)",
}


def _find(folder: Path, name: str) -> Path | None:
    p = folder / name
    if p.exists():
        return p
    stem = name.rsplit(".", 1)[0]
    alts = sorted(folder.glob(f"{stem}*.csv"))
    return alts[0] if alts else None


def load(folder: Path, as_of: datetime | None = None) -> Data:
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"no folder {folder}")
    sp = folder / "settings.json"
    s = settings_from_dict(json.loads(sp.read_text(encoding="utf-8"))) if sp.exists() else Settings()
    when = as_of or s.as_of or datetime.now().replace(second=0, microsecond=0)
    paths = {n: _find(folder, n) for n in FILES}
    if not paths["incidents.csv"]:
        raise FileNotFoundError(f"{folder}: need incidents.csv ({FILES['incidents.csv']})")
    d = Data(s, when)
    d.incidents = load_incidents(paths["incidents.csv"])
    if not d.incidents:
        raise ValueError(f"{paths['incidents.csv']}: no incidents (check the key and created columns)")
    loaders = {"problems.csv": ("problems", load_problems), "changes.csv": ("changes", load_changes), "cmdb.csv": ("cmdb", load_cmdb)}
    for n, (attr, fn) in loaders.items():
        if paths[n]:
            setattr(d, attr, fn(paths[n]))
    d.sources = {"incidents.csv": len(d.incidents)} | {n: len(getattr(d, attr)) for n, (attr, _) in loaders.items() if paths[n]}
    return d


__all__ = ["Data", "Settings", "Incident", "Problem", "Change", "CI", "load", "STATUSES", "STATUS_LABEL", "CLOSED", "FILES"]
