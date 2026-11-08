# Problem review

How to run the monthly problem review with the tool. The tool only reads exports; problems are opened, linked, updated and closed in the ITSM tool, by their owners, and permanent fixes go through change management and the CAB.

## Who attends

| Role | Why |
|---|---|
| Problem manager (chair) | Owns the process, the pack and the decisions log |
| Service desk lead | Sees the trends first; publishes known errors and workarounds |
| Major incident manager | Brings the major incidents of the month and their RCA |
| Problem owners | Report on their open problems; owners of stuck problems attend in person |
| CI owner teams (network, infrastructure, applications, workplace) | Take the new problems on their CIs |
| Change manager | Takes the permanent fixes to the CAB and the post-implementation reviews |

## Cadence

| When | What | From the outputs |
|---|---|---|
| Review minus 4 days | Export and run the review; send each owner their lines | `problem-review-pack.md`, `problem-status.csv` |
| Review minus 2 days | Owners update their problems in the ITSM tool; run again | `problem-status.csv` |
| Review day (60 minutes) | Agenda in the pack; record every decision | The pack, *Decisions for this review* |
| Same day | Open the agreed problems, link the incidents, raise the changes | `candidate-problems.csv`, `actions.csv` |
| Next CAB | Section 7 of the pack | *For the next CAB* |
| Weekly, between reviews | Run the review on Monday; the service desk lead looks at the candidates | `candidate-problems.csv` |

```powershell
.\scripts\Export-ProblemReviewData.ps1 -Site https://fabrikam.atlassian.net -Project ITSM -OutputFolder .\data -ServiceField <id> -CIField <id> `
    -TeamField <id> -MajorIncidentField <id> -RootCauseCategoryField <id> -WorkaroundField <id> -PublishedField <id> -ReopenCount
```

```bash
python -m problemreview review data/
```

## How to read the pack

- **Decisions for this review**: one line per item that needs a decision today: candidate problems, major incidents without RCA, fixes that did not work, old known errors, and stuck problems or problems without an owner. Write the decision in the last column, with an owner and a date.
- **Status by area**: AT RISK means something critical is waiting; ATTENTION, warnings only.
- **1. Candidate problems**: the clusters ranked by score. The *common words* say why the incidents were grouped; read three or four summaries in `candidate-problems.csv` before deciding.
- **2. Major incidents**: every major incident of the period with its problem, the RCA status and the working days since it was resolved.
- **3. Open problems**: only those with a finding, with the next step.
- **4 and 5. Known errors and fixes**: how long each workaround has been the answer, and whether the incidents stopped after each fix.
- **6. Quality**: the share of root causes recorded as unknown or other, problems closed without a root cause, duplicates.
- **7. For the next CAB**: what the change manager takes to the CAB.

## When to open a problem

Open a problem when any of these is true, and link the incidents to it the same day:

- a major incident, always, the day it is resolved;
- a candidate problem from the review, unless the group decides it is not one problem (write why in the decision column);
- the same workaround applied three times in a month;
- a service desk analyst or a resolver group asks for one: an incident resolved with a workaround is a reason to ask;
- a vendor confirms a defect.

Reject a candidate when the incidents only share words (for example *VPN slow* and *VPN profile missing*), or when they are requests logged as incidents; then fix the categorisation, not the problem list. Add recurring site or product names that cause false groupings to `stopwords` in settings.json.

## Root cause analysis

| Technique | When | How |
|---|---|---|
| Timeline | Every major incident, first | Minute by minute from the first symptom to recovery: alerts, changes, actions and who did them. Most root causes show up in the gap between the last change and the first alert |
| 5 whys | One clear failure | Ask why from the symptom until the answer is a process, a design or a configuration someone can change. Stop at a cause you can act on, not at a person |
| Ishikawa (fishbone) | Several possible causes, intermittent faults | Branches for people, process, technology, suppliers, environment and data; test each cause against the evidence of the incidents |
| Change correlation | Incidents that started on one date | Compare the first incident with the change calendar of the week before |
| Fault tree or Kepner-Tregoe *is / is not* | Faults that affect some sites, devices or users and not others | List where it happens and where it does not; the difference points at the cause |

Record the root cause category (from a short list agreed with the team: configuration, change, software defect from the vendor or in-house, capacity, hardware, third party) and one or two sentences of root cause. *Unknown* or *Other* is allowed while investigating, never as the way to close a problem; the review flags them above 20%.

## From problem to change

1. Root cause known: the owner documents the workaround and the service desk lead publishes it (known error).
2. The owner writes the permanent fix with the CI owner team and raises the change, linked to the problem; status *Fix in change*.
3. The change goes to the CAB with the problem key, the incidents it should stop and the rollback plan.
4. After implementation, the problem stays open for 30 days. The review checks the matching incidents; with none (or fewer than `fix_recurrence_min`) the problem is resolved.
5. If the incidents continue, the review flags FIX-01: reopen the problem, link the new incidents and hold the post-implementation review at the next CAB.
6. A known error can be accepted without a fix (cost, end of life of the CI). Record the reason and a review date in the decision column; it comes back on that date.

## Recording decisions

- In the pack: the *Decision* columns and *Decisions of the review* under Notes; keep the pack with the exports of that month.
- In `actions.csv`: owner, due date, decision (do, defer with a reason, reject with a reason) and done; import it into the tracker the team uses.
- In `candidate-problems.csv`: the decision and the key of the problem opened for each cluster.
- In the ITSM tool: every agreed problem, link and change, the same day.

Keep each month's folder (exports, pack, CSVs). The next review starts with the actions of this one.
