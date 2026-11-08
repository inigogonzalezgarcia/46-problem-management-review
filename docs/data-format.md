# Data format

Put the files in one folder and run `python -m problemreview review <folder>`. `incidents.csv` is required; `problems.csv` adds the checks on problems, known errors, fixes and quality, `changes.csv` the fix verification, and `cmdb.csv` the criticality and owner teams. Comma, semicolon or tab separated, UTF-8. Column names are matched loosely (case, accents and punctuation are ignored), and the alternatives below are accepted, so exports from Jira Service Management, HaloITSM or EasyVista work with little or no renaming. Dates as ISO 8601 (`2026-11-08`, `2026-11-08 09:00` or `2026-11-08T09:00:00.000+0100`), the Jira list format `08/Nov/26 9:05 AM`, `dd/mm/yyyy` or `MM/dd/yyyy`; the time zone suffix is ignored. Yes/no columns accept `Yes`, `True`, `1` and `Y`. Ticket keys are free text (`INC-10001`, `ITSM-482`, `12345`) and compared in upper case.

`scripts/Export-ProblemReviewData.ps1` writes `incidents.csv`, `problems.csv` and `changes.csv` from Jira Service Management Cloud. `cmdb.csv` comes from Assets or your CMDB.

## How the review works

| Step | Rule |
|---|---|
| Window | Trends, linked share and reopened incidents look at incidents created in the last `window_days` (default 90) before the reference date. Major incidents and fix verification use every incident in the file |
| Words | Each summary becomes a set of words: lower case, no accents, digits or punctuation, words of three letters or more, no stop words (a built-in English list plus `stopwords` in settings.json, for site names and the like), a crude stem (`printing` → `print`, `certificates` → `certificate`) |
| Similar | Two sets are similar when they share at least `min_shared_tokens` words (default 2) and the shared words are at least `similarity` (default 50%) of the words of the shorter set (the overlap coefficient) |
| Clusters | Incidents are grouped by CI (or service when there is no CI) and category. In order of creation, each incident joins the cluster whose core words (the words in at least half of its incidents; both incidents' common words for a cluster of two) it is most similar to, or starts a new one; clusters whose cores are similar are merged. Deterministic, standard library only |
| Candidate problem | A cluster of `cluster_min` or more (default 5) where most incidents have no linked problem and no existing problem on the same CI is similar to it. Score: the sum of `priority_weights` of its incidents times the `criticality_weights` of the CI (from cmdb.csv; `default_criticality` otherwise). Critical with a score of `cluster_critical_score` or more, or with a major incident in it |
| Problem signature | The words that at least 40% of a problem's linked incidents share (with three or more linked incidents), or the words of its summary |
| Working days | Monday to Friday, without `holidays`. The RCA of a major incident is due `rca_working_days` after the incident was resolved (or created, if still open) |
| RCA done | The linked problem is in *Root cause known* or later, or has a root cause written |
| Fix verification | For problems in *Fix in change*, *Resolved* or *Closed* with an implemented change: matching incidents are linked to the problem, or on the same CI (or service) and similar to its signature from before the change. *Not effective* with `fix_recurrence_min` or more after the implementation date plus `fix_grace_days`; *too early* under 30 days; *change failed* when the outcome says failed, backed out or rolled back |
| Status | An area is AT RISK with a critical finding, ATTENTION with warnings only, HEALTHY otherwise; the overall status is the worst area. Findings *for information* do not count |

## incidents.csv

One row per incident.

| Column | Alternatives | Notes |
|---|---|---|
| Issue key | Key, Ticket, Ticket ID, Incident number | Required |
| Created | Opened, Date opened, Reported | Required |
| Resolved | Resolution date, resolutiondate, Closed | Empty while open; the RCA deadline of a major incident counts from here |
| Priority | Impact priority | `Highest`, `High`, `Medium`, `Low`, `Lowest` (Jira), `P1`–`P5`, `1`–`5`, `Critical`, `Moderate` or `1 - Critical`; unknown values count as P3 |
| Affected services | Service, Business service | Used when there is no CI, and for the reopened incidents by service |
| Configuration item | CI, Asset, Affected CI | Clusters, fix verification and duplicates compare CIs; joins cmdb.csv |
| Category | Components, Classification | Part of the cluster key |
| Assignment group | Team, Support group | Proposed owner of a candidate when the CI has no owner team |
| Linked problem | Problem, Linked problems | Problem keys separated by `;` |
| Summary | Short description, Subject, Title | The text compared |
| Resolution | Resolution code, Closure code | Read, not used in the rules |
| Reopen count | Reopened, Times reopened | FIX-03 at `reopen_min` or more |
| Major incident | Major, Major incident flag | `Yes` marks a major incident |

## problems.csv

One row per problem record.

| Column | Alternatives | Notes |
|---|---|---|
| Issue key | Key, Problem number | Required |
| Summary | Short description, Title | Duplicates (QLT-03) and the signature when few incidents are linked |
| Created | Opened, Date opened | Age; STK-03 |
| Status | State | `New`, `Under investigation`, `Root cause known`, `Known error`, `Fix in change`, `Resolved`, `Closed`. Also accepted: `Open` (new), `In progress` (under investigation), `Under review` (root cause known), `Completed`/`Done` (resolved), `Canceled` (closed) |
| Assignee | Owner, Problem owner | Empty: STK-04 |
| Owner team | Team, Assignment group | Compared with the owner team of the CI in cmdb.csv (STK-05) |
| Affected services | Service | |
| Configuration item | CI, Asset | |
| Root cause category | Root cause type, Cause code | Empty or one of `unknown_categories` counts as unknown (QLT-01) |
| Root cause | Root cause description | Text; a closed problem with neither category nor text is QLT-02 |
| Workaround | Workaround available | `Yes`/`No`, or the text of the workaround itself |
| Workaround text | Workaround description | |
| Known error since | Known error date, Workaround date | Start of the KER-01 count; empty uses Created |
| Published to service desk | KEDB, Known error published | `No` with a workaround is KER-02; empty is unknown and not checked |
| Linked change | Change, Linked changes | Change keys separated by `;` |
| Target date | Due date, Due | STK-02 |
| Updated | Last update, Last updated | STK-01 |
| Review date | Next review | STK-06 (information) |
| Resolved | Resolution date | |

## changes.csv (optional)

| Column | Alternatives | Notes |
|---|---|---|
| Issue key | Key, Change number | Required |
| Summary | Short description | |
| Status | State | Implemented when the status is `Implemented`, `Closed`, `Completed`, `Done`, `Resolved` or `Review` and there is a date |
| Implemented | Actual end, Completed, Resolved | Start of the fix verification |
| Linked problem | Problem | Also read from the problem side (`Linked change`) |
| Outcome | Resolution, Close code, Result | `Failed`, `Backed out`, `Rolled back`, `Unsuccessful` make it a failed change |

## cmdb.csv (optional)

| Column | Alternatives | Notes |
|---|---|---|
| CI | Name, Configuration item, Asset | Matched to the CI of incidents and problems, ignoring case |
| Service | Business service | When an incident has a service but no CI, the most critical CI of the service gives the criticality |
| Criticality | Business criticality, Tier | A key of `criticality_weights` (`Critical`, `High`, `Medium`, `Low`) |
| Owner team | Support group, Team | Proposed owner of candidate problems; STK-05 |

## settings.json

| Key | Default | Meaning |
|---|---|---|
| `organisation` | | Name in the report |
| `as_of` | now | Reference date (`2026-11-08 09:00`); `--as-of` overrides it |
| `window_days` | 90 | Days of incidents for trends and reopened incidents |
| `cluster_min` | 5 | Incidents for a candidate problem |
| `cluster_critical_score` | 100 | Score that makes a candidate critical |
| `similarity` | 0.5 | Overlap coefficient for two summaries to be similar (`50` is read as 50%) |
| `min_shared_tokens` | 2 | Words two summaries must share |
| `priority_weights` | P1 8, P2 4, P3 2, P4 1, P5 1 | Keys as in your export (`Highest`, `P1`, `1`) |
| `criticality_weights` | Critical 3, High 2, Medium 1.5, Low 1 | |
| `default_criticality` | Medium | For CIs not in cmdb.csv |
| `stopwords` | | Extra words to ignore (site names, the company name) |
| `rca_working_days` | 5 | Working days for the problem record and the root cause of a major incident |
| `holidays` | | Dates excluded from working days |
| `stale_days` | 30 | STK-01 |
| `investigation_max_days` | 60 | STK-03, for problems new or under investigation |
| `known_error_fix_days` | 90 | KER-01 warning |
| `known_error_critical_days` | 180 | KER-01 critical |
| `fix_grace_days` | 3 | Days after the change before incidents count against it |
| `fix_recurrence_min` | 3 | Matching incidents after the change for FIX-01 |
| `reopen_min` | 2 | FIX-03 |
| `unknown_rc_max` | 0.2 | QLT-01 warning above it, critical above twice it |
| `unknown_categories` | Unknown, Other, Not determined, Undetermined | |
| `next_review`, `next_cab` | | Dates printed in the pack; due date of critical actions |
| `owners` | | Owner per area: `trends`, `major`, `stuck`, `known`, `fix`, `quality` |

## Findings

| Code | Severity | Rule |
|---|---|---|
| TRD-01 | critical / warning | Candidate problem (see *How the review works*) |
| TRD-02 | info | Incidents in a cluster that match an existing problem and are not linked to it |
| MAJ-01 | critical / warning | Major incident with no linked problem: critical after `rca_working_days`, a warning before |
| MAJ-02 | critical | Major incident whose problems have no root cause after `rca_working_days` |
| STK-01 | warning | Open problem with no update for `stale_days`, or no update date |
| STK-02 | warning | Open problem past its target date |
| STK-03 | warning | New or under investigation for more than `investigation_max_days` |
| STK-04 | critical / warning | Open problem with no owner; critical when linked to a major incident |
| STK-05 | warning | Owner team different from the CI owner team |
| STK-06 | info | Review date passed |
| KER-01 | critical / warning / info | Open problem with a workaround for `known_error_fix_days` (critical after `known_error_critical_days`) and no implemented change; information when a change is linked but not implemented yet |
| KER-02 | warning | Workaround not published to the service desk |
| KER-03 | warning | Known error with no workaround |
| FIX-01 | critical / warning | Fix not effective: critical when the problem is resolved or closed, a warning while in *Fix in change* |
| FIX-02 | warning | Problem resolved or closed while its change failed or was backed out |
| FIX-03 | warning | Incidents reopened `reopen_min` or more times in the window |
| QLT-01 | critical / warning | Share of problems past investigation with an unknown root cause category |
| QLT-02 | warning | Problem resolved or closed with no root cause (category and text) |
| QLT-03 | warning | Two open problems on the same CI with similar summaries |
| QLT-04 | info | Problem resolved or closed with no linked change |
