"""Fictional demo: Fabrikam Logistics, a made-up logistics company with about 1,800 people at Madrid HQ, the Zaragoza hub and the
Valencia port warehouse. Six months of incidents (May to November 2026), the problem records, the changes linked to them and the CIs
of the CMDB, as Jira Service Management would export them. Reviewed on Sunday 8 November 2026 for the monthly problem review of
Thursday 12 November. Every person, ticket and CI is made up. The problems are placed on purpose among the everyday ones."""
from __future__ import annotations

import csv
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ORG = "Fabrikam Logistics"
SEED = 46
TODAY = date(2026, 11, 8)
START = date(2026, 5, 11)
END = date(2026, 11, 7)

SETTINGS = {
    "organisation": ORG,
    "as_of": "2026-11-08 09:00",
    "window_days": 90,
    "cluster_min": 5,
    "cluster_critical_score": 100,
    "similarity": 0.5,
    "min_shared_tokens": 2,
    "priority_weights": {"Highest": 8, "High": 4, "Medium": 2, "Low": 1, "Lowest": 1},
    "criticality_weights": {"Critical": 3, "High": 2, "Medium": 1.5, "Low": 1},
    "default_criticality": "Medium",
    "stopwords": ["madrid", "zaragoza", "valencia", "hub", "office", "warehouse"],
    "rca_working_days": 5,
    "holidays": ["2026-05-15", "2026-10-12", "2026-12-08", "2026-12-25"],
    "stale_days": 30,
    "investigation_max_days": 60,
    "known_error_fix_days": 90,
    "known_error_critical_days": 180,
    "fix_grace_days": 3,
    "fix_recurrence_min": 3,
    "reopen_min": 2,
    "unknown_rc_max": 0.2,
    "unknown_categories": ["Unknown", "Other"],
    "next_review": "2026-11-12",
    "next_cab": "2026-11-17",
    "owners": {"trends": "Problem manager (Elena Vidal)", "major": "Major incident manager (Jorge Prieto)",
               "stuck": "Problem manager (Elena Vidal)", "known": "Service desk lead (Sara Ibáñez)", "fix": "Change manager (Pablo Ruiz)",
               "quality": "Problem manager (Elena Vidal)"},
}

N = 7
# ci, service, criticality, owner team, category, times each everyday summary is reported in six months, the summaries
CIS = [
    ("LAPTOP-FLEET", "Laptops", "Medium", "End user services", "Hardware / Laptop", N, [
        "Laptop battery swollen", "Keyboard keys not responding", "Screen flickers on battery", "Laptop overheating and fan loud",
        "Touchpad stopped responding", "Webcam not detected in Teams", "Headset microphone muted by default", "USB-C charger not charging",
        "Laptop will not wake from sleep", "Blue screen when undocking", "Disk almost full on laptop", "Microsoft Office activation prompt",
        "OneDrive sync paused on laptop", "Bluetooth mouse keeps disconnecting", "Laptop stolen from car", "Cracked laptop screen",
        "Windows update stuck at 30 percent", "Fingerprint reader not recognised", "Laptop very slow opening Excel", "Wrong keyboard layout",
        "Adobe Reader crashes opening invoices", "Laptop clock shows wrong time zone", "Speakers crackle during calls", "Hinge broken on laptop",
        "Software Center shows no applications", "Printer list empty in Word", "Laptop asks for BitLocker PIN twice", "Edge opens blank pages",
        "Docking station power light off", "Spilled coffee on keyboard", "Teams desktop app will not start", "Zoom plugin request for client call",
        "Grinding noise from cooling fan", "Projector not detected over HDMI"]),
    ("EXO-TENANT", "Email", "High", "Workplace", "Email / Exchange Online", N, [
        "Mailbox full warning", "Calendar invites arrive late", "Out of office not sending replies", "Shared mailbox missing in Outlook",
        "Email stuck in outbox", "Distribution list rejects external senders", "Signature disappeared", "Phishing email reported by user",
        "Attachment blocked as unsafe", "Meeting room booking declined", "Delegate cannot open manager calendar", "Search finds no older messages",
        "Mobile mail app asks password repeatedly", "Quarantine release request", "Rule moves every message to junk",
        "Read receipts requested on all mail", "Contact group lost after reinstall", "Room mailbox shows double bookings"]),
    ("ENTRA-ID", "Identity", "Critical", "Workplace", "Identity / Access", N, [
        "Account locked after holiday", "MFA prompt on new phone", "Authenticator app lost with phone", "Password expired while travelling",
        "Guest user cannot accept invitation", "Conditional access blocks home PC", "Group membership missing for new starter",
        "SSO fails for carrier portal", "Self-service password reset not offered", "Sign-in risk flagged for traveller", "Leaver account still active",
        "Temporary access pass expired before use", "Name change not reflected in directory", "Contractor needs extension of expiry date"]),
    ("TEAMS-PHONE", "Telephony", "High", "Workplace", "Telephony / Teams Phone", N, [
        "Desk phone shows sign-in error", "Voicemail greeting cannot be changed", "Call forwarding to mobile ignored", "Caller ID shows wrong number",
        "Headset buttons do nothing in Teams", "Cannot transfer external call", "Emergency number location missing", "Hunt group member not ringing",
        "Reception console shows offline", "No alert for missed calls"]),
    ("WMS-APP-01", "Warehouse management", "Critical", "Business applications", "Application / WMS", N, [
        "Pick list shows wrong bin location", "Stock adjustment not saved", "Goods receipt screen frozen", "Replenishment task not created",
        "Pallet label reprint missing", "User cannot see new warehouse zone", "Cycle count variance report empty", "Despatch confirmation duplicated",
        "Returns order cannot be closed", "Supervisor dashboard shows yesterday", "Lot number field rejects letters", "Putaway suggests full location",
        "Expiry date blank on inbound goods", "Picker assigned to closed aisle", "Cross dock order not visible", "Inventory transfer report blank"]),
    ("TMS-APP-01", "Transport management", "Critical", "Business applications", "Application / TMS", N, [
        "Carrier booking rejected", "Freight cost missing on shipment", "Tracking link shows no events", "Delivery slot calendar empty",
        "Proof of delivery photo not attached", "Customs document template outdated", "Driver app cannot download manifest", "Load plan exceeds weight",
        "Subcontractor portal login refused", "Fuel surcharge table not applied", "Return trip not offered to planners"]),
    ("ERP-D365", "ERP", "High", "Business applications", "Application / ERP", N, [
        "Purchase order approval stuck", "Vendor invoice matching mismatch", "Cost centre missing for new team", "Expense report rejected by workflow",
        "Fixed asset depreciation wrong", "Customer credit limit not updated", "Budget report totals differ", "Sales order tax code wrong",
        "Bank statement import duplicates lines", "Intercompany journal unbalanced", "Payment proposal excludes approved vendor",
        "Currency revaluation used old rate"]),
    ("SCN-FLEET-ZAZ", "Handheld scanners", "High", "End user services", "Hardware / Scanner", N, [
        "Scanner trigger broken", "Scanner screen cracked", "Charging cradle not charging", "Scanner stuck on boot logo", "Scanner keypad worn"]),
    ("SCN-FLEET-VLC", "Handheld scanners", "High", "End user services", "Hardware / Scanner", N, [
        "Handheld battery will not hold charge", "Barcode reader misreads labels", "Handheld lost on quay", "Handheld app crashes at login",
        "Handheld strap broken"]),
    ("WIFI-ZAZ", "Warehouse Wi-Fi", "High", "Network", "Network / Wi-Fi", N, [
        "No coverage in mezzanine", "Access point offline in aisle", "Guest network password not working", "Visitor portal page not loading"]),
    ("WIFI-VLC", "Warehouse Wi-Fi", "High", "Network", "Network / Wi-Fi", N, [
        "Weak signal at loading bay", "Access point blinking orange", "Forklift terminal shows no network", "Wi-Fi slow near cold store"]),
    ("WIFI-MAD", "Office Wi-Fi", "Medium", "Network", "Network / Wi-Fi", N, [
        "Meeting room Wi-Fi drops", "New phone cannot join corporate network", "Wi-Fi asks for certificate trust on Mac", "Fourth floor slow internet"]),
    ("PRT-MAD-01", "Printing", "Low", "End user services", "Printing", N, [
        "Paper jam on second floor printer", "Toner empty in finance", "Scan to email not sending", "Badge release fails at copier",
        "Colour prints come out pale"]),
    ("PRT-VLC-01", "Printing", "Low", "End user services", "Printing", N, [
        "Label printer prints blank labels", "Quay printer out of paper", "Print job held in secure queue", "Copier asks for service code"]),
    ("PRT-ZAZ-01", "Printing", "Low", "End user services", "Printing", N, [
        "Paper jam on dock printer", "Toner low on multifunction", "Scanned documents sent to wrong folder", "Badge reader on copier broken"]),
    ("FS-MAD-02", "File services", "High", "Infrastructure", "Storage / File share", N, [
        "Restore deleted folder from yesterday", "Access request to finance share", "Quota exceeded on team folder", "Shortcut to archive broken"]),
    ("VPN-ASA-01", "Remote access", "High", "Network", "Network / VPN", N, [
        "VPN disconnects every few minutes on hotel Wi-Fi", "VPN slow when copying large files", "Remote desktop drops over VPN",
        "VPN profile missing after laptop rebuild", "VPN access needed for new contractor"]),
    ("EDI-GW-01", "EDI with customers", "Critical", "Integration", "Integration / EDI", N, [
        "Customer reports missing invoice message", "Order acknowledgement late", "New trading partner setup request", "EDI mapping error for unit codes"]),
    ("LABEL-SRV-01", "Label printing", "High", "Business applications", "Application / Labels", N, [
        "Carrier label layout changed", "Label printer not listed in app", "Barcode too small on pallet label", "Label shows old company address"]),
    ("INTRANET", "Intranet", "Low", "Workplace", "Application / Intranet", N, [
        "Intranet news page not updating", "Canteen menu link broken"]),
    ("BACKUP-01", "Backup", "High", "Infrastructure", "Infrastructure / Backup", N, [
        "Restore test request", "Backup report email missing"]),
    ("SW-ZAZ-CORE", "LAN", "High", "Network", "Network / LAN", N, [
        "Network port dead at desk", "Patch request for new printer"]),
    ("WMS-DB-01", "Warehouse management", "Critical", "Database", "Database", N, [
        "Database maintenance window request"]),
]
SITES = {"ZAZ": "Zaragoza hub", "VLC": "Valencia port warehouse", "MAD": "Madrid HQ"}
FIRST = ["Ana", "Luis", "Marta", "Javier", "Lucía", "Pablo", "Elena", "Sergio", "Carmen", "David", "Laura", "Jorge", "Sara", "Álvaro",
         "Paula", "Diego", "Irene", "Rubén", "Nerea", "Hugo", "Inés", "Óscar", "Alba", "Adrián"]
LAST = ["García", "López", "Martín", "Sánchez", "Pérez", "Gómez", "Ruiz", "Díaz", "Moreno", "Muñoz", "Álvarez", "Romero", "Navarro",
        "Torres", "Domínguez", "Vázquez", "Ramos", "Gil", "Serrano", "Blanco"]
PRIO = ["Highest", "High", "Medium", "Low"]

# key, summary, opened, status, owner, team, ci, root cause category, root cause, workaround, known error since, published,
# changes, target, updated, review, resolved; then the incidents linked to it: (phrases, count, first, last, share linked, priorities)
P = [
    ("PRB-1001", "Mail flow to customers delayed by connector TLS error", "2026-05-27", "Closed", "Marta Gil", "Workplace", "EXO-TENANT",
     "Configuration", "Outbound connector required TLS 1.2 with a certificate name the partner relay did not present", "", "", "",
     "CHG-2001", "2026-06-15", "2026-06-12", "", "2026-06-10",
     (["Outbound mail to customers delayed", "Customer did not receive our email for hours", "Mail delayed by connector TLS error"], 9,
      "2026-05-25", "2026-06-02", 0.9, "HM")),
    ("PRB-1002", "WMS handheld sessions dropped after access point firmware", "2026-05-20", "Closed", "Iván Sanz", "Network", "WIFI-ZAZ",
     "Software defect (vendor)", "Access point firmware bug in fast roaming; fixed in the next vendor release", "", "", "",
     "CHG-2002", "2026-06-30", "2026-06-26", "", "2026-06-24",
     (["Handheld WMS session dropped in aisle", "WMS session drops when walking between racks", "Handheld lost WMS session again"], 14,
      "2026-05-14", "2026-06-19", 0.85, "HMM")),
    ("PRB-1003", "BitLocker recovery prompt after BIOS update", "2026-06-15", "Resolved", "Raquel Ortiz", "End user services", "LAPTOP-FLEET",
     "Change (failed or untested)", "BIOS update deployed without suspending BitLocker", "Give the recovery key from Entra ID", "", "Yes",
     "CHG-2003", "2026-07-15", "2026-07-10", "", "2026-07-10",
     (["BitLocker recovery key requested after BIOS update", "Laptop asks for BitLocker recovery key at boot", "BitLocker recovery screen after BIOS"], 12,
      "2026-06-11", "2026-07-06", 0.9, "MMH")),
    ("PRB-1004", "Mapped drive disconnects and files locked on FS-MAD-02", "2026-07-20", "Resolved", "Tomás Herrera", "Infrastructure",
     "FS-MAD-02", "Configuration", "SMB opportunistic locking with the antivirus real-time scan of Office temporary files", "Reconnect the drive",
     "", "Yes", "CHG-2004", "2026-09-30", "2026-09-18", "", "2026-09-18",
     (["Mapped drive S disconnects", "Excel file on shared drive locked by another user", "Shared drive S disconnected and file locked",
       "Cannot save file on shared drive, file locked"], 16, "2026-07-14", "2026-09-14", 0.85, "MMH")),
    ("PRB-1005", "TMS label print timeout to carrier API", "2026-06-03", "Closed", "Nerea Blanco", "Business applications", "TMS-APP-01",
     "Unknown", "", "", "", "", "", "2026-07-03", "2026-07-20", "", "2026-07-20",
     (["Carrier label print times out in TMS", "TMS label request timeout to carrier"], 7, "2026-05-28", "2026-07-02", 0.8, "MH")),
    ("PRB-1006", "Teams Phone calls drop on office Wi-Fi", "2026-06-08", "Closed", "Marta Gil", "Workplace", "TEAMS-PHONE", "Other",
     "Could not be reproduced after the Teams client update", "", "", "", "", "2026-07-08", "2026-07-30", "", "2026-07-30",
     (["Teams call drops on Wi-Fi", "Calls cut after a minute on office Wi-Fi"], 6, "2026-06-01", "2026-07-10", 0.8, "M")),
    ("PRB-1007", "EDI orders rejected after gateway certificate renewal", "2026-07-14", "Closed", "Alba Castro", "Integration", "EDI-GW-01",
     "Change (failed or untested)", "Renewed certificate deployed without the intermediate chain", "", "", "", "CHG-2005", "2026-07-31",
     "2026-07-24", "", "2026-07-24",
     (["EDI orders rejected by customer gateway", "Customer gateway rejects our EDI messages"], 6, "2026-07-14", "2026-07-21", 1.0, "HH")),
    ("PRB-1008", "ERP batch posting job fails at month end", "2026-06-02", "Resolved", "Ángel Rubio", "Business applications", "ERP-D365",
     "Capacity", "Batch server memory exhausted when month-end jobs run in parallel", "Rerun the batch at night", "", "Yes", "CHG-2006",
     "2026-08-15", "2026-08-07", "", "2026-08-07",
     (["Month end batch posting job failed", "ERP posting batch stopped at month end"], 5, "2026-05-30", "2026-07-31", 1.0, "H")),
    ("PRB-1009", "Snapshot backup jobs fail for FS-MAD-02", "2026-06-22", "Closed", "Tomás Herrera", "Infrastructure", "BACKUP-01",
     "Unknown", "", "", "", "", "", "2026-07-22", "2026-08-12", "", "2026-08-12",
     (["Snapshot backup job failed for file server", "File server snapshot backup failed overnight"], 5, "2026-06-18", "2026-08-05", 1.0, "M")),
    ("PRB-1010", "Label server spooler hangs during peak", "2026-09-07", "Resolved", "Nerea Blanco", "Business applications", "LABEL-SRV-01",
     "Software defect (vendor)", "Spooler memory leak in the label software; fixed in version 11.4", "Restart the spooler", "", "Yes",
     "CHG-2007", "2026-10-31", "2026-10-22", "", "2026-10-22",
     (["Label spooler hangs, no pallet labels", "Pallet labels stuck in spooler during peak", "Label spooler frozen again"], 9,
      "2026-09-01", "2026-10-16", 0.9, "HH")),
    ("PRB-1011", "Sign-in loops on shared warehouse PCs", "2026-06-15", "Closed", "Marta Gil", "Workplace", "ENTRA-ID", "Configuration",
     "Conditional Access session policy on shared devices", "", "", "", "CHG-2008", "2026-07-15", "2026-07-02", "", "2026-07-02",
     (["Sign-in loop on shared warehouse PC", "Shared PC keeps asking to sign in"], 6, "2026-06-10", "2026-06-29", 1.0, "M")),
    ("PRB-1012", "Intranet search returns no results", "2026-07-06", "Closed", "Marta Gil", "Workplace", "INTRANET", "Other",
     "Search indexing service issue at the provider, fixed by the provider", "", "", "", "", "2026-08-06", "2026-07-21", "", "2026-07-21",
     (["Intranet search returns nothing", "No results in intranet search"], 5, "2026-07-02", "2026-07-17", 1.0, "L")),
    ("PRB-1013", "Scanner batteries drain in the cold store", "2026-07-27", "Closed", "Raquel Ortiz", "End user services", "SCN-FLEET-VLC",
     "Hardware", "Standard batteries below their rated temperature; cold-rated batteries ordered", "", "", "", "", "2026-08-27",
     "2026-08-25", "", "2026-08-25",
     (["Scanner battery dead after an hour in cold store", "Cold store scanner battery drains fast"], 6, "2026-07-20", "2026-08-21", 1.0, "M")),
    ("PRB-1014", "WMS database deadlocks during wave release", "2026-08-26", "Fix in change", "Ángel Rubio", "Database", "WMS-DB-01",
     "Software defect (in-house)", "Wave release procedure locks the stock table in the wrong order", "Release waves in smaller batches", "",
     "Yes", "CHG-2009", "2026-11-30", "2026-11-03", "2026-11-26", "",
     (["Wave release fails with database deadlock", "Deadlock when releasing picking wave"], 9, "2026-08-20", "2026-11-04", 0.9, "HH")),
    ("PRB-1015", "Core switch CPU spikes drop handheld sessions", "2026-09-14", "Fix in change", "Iván Sanz", "Network", "SW-ZAZ-CORE",
     "Capacity", "Multicast flooding from the label printers saturates the core switch CPU", "Move the handhelds to the backup SSID", "", "Yes",
     "CHG-2010", "2026-11-20", "2026-10-30", "2026-11-19", "",
     (["Core switch CPU high, handhelds disconnected", "Handhelds disconnected when core switch CPU spikes"], 7, "2026-09-10", "2026-11-02", 0.9, "H")),
    ("PRB-1016", "Outlook freezes with large shared mailboxes", "2026-09-21", "Fix in change", "Marta Gil", "Workplace", "EXO-TENANT",
     "Configuration", "Shared mailboxes auto-mapped and cached in full on every laptop", "Remove the auto-mapping", "", "Yes", "CHG-2011",
     "2026-11-15", "2026-10-29", "2026-11-26", "",
     (["Outlook freezes with shared mailbox open", "Outlook not responding with big shared mailbox"], 8, "2026-09-15", "2026-10-26", 0.9, "M")),
    ("PRB-1017", "Zebra scanners lose Wi-Fi when roaming between aisles", "2026-06-29", "Known error", "Raquel Ortiz", "End user services",
     "SCN-FLEET-ZAZ", "Software defect (vendor)", "Roaming threshold of the scanner Wi-Fi profile too low for the aisle layout",
     "Toggle Wi-Fi on the scanner or put it back in the cradle for ten seconds", "2026-07-11", "Yes", "", "2026-09-30", "2026-10-27",
     "2026-12-10", "",
     (["Scanner loses Wi-Fi between aisles", "Zebra scanner drops Wi-Fi when roaming", "Scanner Wi-Fi lost moving between aisles"], 38,
      "2026-06-25", "2026-11-06", 0.85, "MMH")),
    ("PRB-1018", "Boardroom audio echo in Teams meetings", "2026-09-17", "Known error", "Marta Gil", "Workplace", "TEAMS-PHONE", "Other",
     "", "Use the ceiling microphone preset on the room console", "2026-09-20", "No", "", "2026-11-30", "2026-10-21", "2026-11-19", "",
     (["Echo in boardroom Teams meeting", "Remote attendees hear echo from boardroom"], 6, "2026-09-14", "2026-10-30", 1.0, "M")),
    ("PRB-1019", "ERP export to Excel truncates rows", "2026-05-25", "Known error", "Ángel Rubio", "Business applications", "ERP-D365",
     "Software defect (vendor)", "Export limit of the vendor's Excel add-in", "Export as CSV", "2026-06-01", "Yes", "CHG-2012", "2026-12-15",
     "2026-10-20", "2026-12-01", "",
     (["ERP export to Excel cuts rows", "Excel export from ERP missing rows"], 8, "2026-05-20", "2026-10-28", 0.9, "L")),
    ("PRB-1020", "TMS route planner slow on Monday mornings", "2026-09-28", "Known error", "Nerea Blanco", "Business applications",
     "TMS-APP-01", "Unknown", "", "", "2026-10-01", "", "", "2026-12-01", "2026-10-26", "2026-11-23", "",
     (["Route planner very slow Monday morning", "TMS route planning slow at start of week"], 8, "2026-09-21", "2026-11-02", 0.9, "M")),
    ("PRB-1021", "Docking stations lose external monitors after sleep", "2026-08-28", "Known error", "Raquel Ortiz", "End user services",
     "LAPTOP-FLEET", "Software defect (vendor)", "Dock firmware 1.0.22 with the current display driver", "Unplug and plug the dock cable",
     "2026-09-01", "Yes", "", "2026-12-15", "2026-10-30", "2026-11-26", "",
     (["External monitors black after sleep on dock", "Dock loses external monitor after sleep"], 10, "2026-08-24", "2026-11-05", 0.85, "L")),
    ("PRB-1022", "Printer queues pause after print server reboot", "2026-09-30", "Root cause known", "Raquel Ortiz", "End user services",
     "PRT-VLC-01", "Configuration", "Print queues set to start paused after a spooler restart", "", "", "", "", "2026-11-20", "2026-11-02",
     "2026-11-19", "",
     (["Printer queue paused after server reboot", "All quay printer queues paused after reboot"], 6, "2026-09-28", "2026-10-30", 1.0, "M")),
    ("PRB-1023", "Forklift terminals roam slowly in Valencia", "2026-08-11", "Root cause known", "Iván Sanz", "Network", "WIFI-VLC", "Other",
     "", "", "", "", "", "2026-11-30", "2026-10-28", "2026-11-26", "",
     (["Forklift terminal slow to roam between access points", "Forklift terminal roaming delay at quay"], 7, "2026-08-05", "2026-10-29", 1.0, "M")),
    ("PRB-1024", "Duplicate ASN messages sent to customers", "2026-10-06", "Root cause known", "Alba Castro", "Integration", "EDI-GW-01",
     "Software defect (in-house)", "Retry logic resends the ASN when the acknowledgement arrives late", "", "", "", "", "2026-11-30",
     "2026-11-04", "2026-11-26", "",
     (["Customer received duplicate ASN", "Duplicate advance shipping notice sent"], 5, "2026-10-01", "2026-11-03", 1.0, "H")),
    ("PRB-1025", "TMS unavailable for three hours", "2026-10-15", "Under investigation", "Nerea Blanco", "Business applications",
     "TMS-APP-01", "", "", "", "", "", "", "2026-11-13", "2026-10-19", "2026-11-12", "", None),
    ("PRB-1026", "WMS scanning slow at the Zaragoza dock", "2026-08-20", "Under investigation", "", "Business applications", "WMS-APP-01",
     "", "", "", "", "", "", "2026-10-15", "2026-10-29", "2026-11-12", "",
     (["WMS scanning slow at dock", "Slow scanning response on WMS dock screens"], 9, "2026-08-18", "2026-11-04", 0.9, "M")),
    ("PRB-1027", "Slow scan response in WMS during peak hours", "2026-10-05", "Under investigation", "Diego Navarro", "Business applications",
     "WMS-APP-01", "", "", "", "", "", "", "2026-11-30", "2026-11-02", "2026-11-26", "",
     (["WMS scan response slow at peak", "Peak hours WMS scanning slow"], 6, "2026-10-01", "2026-11-05", 1.0, "M")),
    ("PRB-1028", "Email to some external domains bounced intermittently", "2026-07-01", "Under investigation", "Marta Gil", "Workplace",
     "EXO-TENANT", "", "", "", "", "", "", "2026-09-30", "2026-09-10", "2026-10-15", "",
     (["Email bounced by external domain", "Intermittent bounce to customer domain"], 7, "2026-06-28", "2026-09-30", 1.0, "M")),
    ("PRB-1029", "Slow logon on laptops after the new Intune policy", "2026-10-12", "Under investigation", "Sara Ibáñez", "Service Desk",
     "LAPTOP-FLEET", "", "", "", "", "", "", "2026-11-27", "2026-11-05", "2026-11-26", "",
     (["Logon takes ten minutes after Intune policy", "Very slow logon since Intune policy change"], 7, "2026-10-08", "2026-11-05", 1.0, "M")),
    ("PRB-1030", "Backup window overruns into the morning", "2026-10-20", "Under investigation", "", "Infrastructure", "BACKUP-01", "", "",
     "", "", "", "", "2026-11-30", "2026-10-21", "2026-11-26", "",
     (["Backup still running in the morning", "Backup window overrun slows servers"], 4, "2026-10-14", "2026-11-03", 1.0, "M")),
    ("PRB-1031", "Shared mailbox permissions lost after migration", "2026-09-28", "Under investigation", "Marta Gil", "Workplace",
     "EXO-TENANT", "", "", "", "", "", "", "2026-11-30", "2026-10-30", "2026-11-26", "",
     (["Lost access to shared mailbox after migration", "Shared mailbox permission missing since migration"], 6, "2026-09-24", "2026-10-29", 1.0, "M")),
    ("PRB-1032", "Handheld clock drift in Valencia", "2026-11-02", "New", "", "End user services", "SCN-FLEET-VLC", "", "", "", "", "", "",
     "2026-12-15", "2026-11-02", "2026-11-26", "",
     (["Handheld clock wrong, scans timestamped late", "Handheld time drift on scan records"], 5, "2026-10-26", "2026-11-05", 0.8, "M")),
    ("PRB-1033", "Intermittent DNS resolution failures on VPN", "2026-10-28", "New", "Iván Sanz", "Network", "VPN-ASA-01", "", "", "", "", "",
     "", "2026-12-15", "2026-11-04", "2026-11-26", "",
     (["Intranet names do not resolve on VPN", "DNS lookups time out over VPN"], 4, "2026-10-22", "2026-11-04", 1.0, "M")),
    ("PRB-1034", "Call queue not ringing agents", "2026-10-30", "New", "Marta Gil", "Workplace", "TEAMS-PHONE", "", "", "", "", "", "",
     "2026-12-15", "2026-11-03", "2026-11-26", "",
     (["Customer service call queue does not ring", "Agents not receiving queue calls"], 4, "2026-10-27", "2026-11-04", 1.0, "H")),
    ("PRB-1035", "ERP invoice PDF missing the logo", "2026-09-01", "New", "Ángel Rubio", "Business applications", "ERP-D365", "", "", "",
     "", "", "", "2026-10-01", "2026-09-02", "2026-10-01", "",
     (["Invoice PDF printed without logo", "Customer invoice missing company logo"], 4, "2026-08-28", "2026-10-20", 1.0, "L")),
]

# key, summary, status, implemented, problem, outcome
CHANGES = [
    ("CHG-2001", "Update outbound connector certificate name for partner relay", "Closed", "2026-06-03", "PRB-1001", "Successful"),
    ("CHG-2002", "Upgrade Zaragoza access point firmware", "Closed", "2026-06-20", "PRB-1002", "Successful"),
    ("CHG-2003", "Suspend BitLocker in the BIOS update task sequence", "Closed", "2026-07-08", "PRB-1003", "Successful"),
    ("CHG-2004", "Disable SMB oplocks on FS-MAD-02 and exclude Office temporary files from the scan", "Closed", "2026-09-15", "PRB-1004",
     "Successful"),
    ("CHG-2005", "Redeploy EDI gateway certificate with the full chain", "Closed", "2026-07-22", "PRB-1007", "Successful"),
    ("CHG-2006", "Add memory to the ERP batch server and split month-end jobs", "Closed", "2026-08-05", "PRB-1008", "Successful"),
    ("CHG-2007", "Upgrade label software to 11.4", "Closed", "2026-10-20", "PRB-1010", "Successful"),
    ("CHG-2008", "Exclude shared warehouse PCs from the sign-in frequency policy", "Closed", "2026-06-25", "PRB-1011", "Backed out"),
    ("CHG-2009", "Fix lock order in the wave release procedure", "Scheduled", "", "PRB-1014", ""),
    ("CHG-2010", "Multicast filtering on the Zaragoza core switch", "Awaiting approval", "", "PRB-1015", ""),
    ("CHG-2011", "Remove auto-mapping of large shared mailboxes", "Implemented", "2026-10-28", "PRB-1016", "Successful"),
    ("CHG-2012", "Replace the ERP Excel add-in with the native export", "Draft", "", "PRB-1019", ""),
    ("CHG-2013", "Renew the wildcard certificate of the intranet", "Closed", "2026-06-17", "", "Successful"),
    ("CHG-2014", "Monthly Windows patching, pilot ring", "Closed", "2026-10-14", "", "Successful"),
    ("CHG-2015", "Monthly Windows patching, broad ring", "Closed", "2026-10-21", "", "Successful"),
    ("CHG-2016", "Add access points to the Valencia quay", "Closed", "2026-09-09", "", "Successful"),
    ("CHG-2017", "WMS minor release 8.2.3", "Closed", "2026-08-12", "", "Successful"),
    ("CHG-2018", "TMS carrier connector update", "Closed", "2026-10-13", "", "Successful"),
    ("CHG-2019", "Move file server backups to the new repository", "Closed", "2026-07-29", "", "Successful"),
    ("CHG-2020", "Intune logon script optimisation", "Scheduled", "", "", ""),
]

# the planted ones
VPN = ["VPN certificate error when connecting from home", "VPN says the server certificate is not trusted", "Certificate validation failure on VPN login",
       "VPN certificate expired message on laptop", "Cannot start VPN, untrusted certificate warning", "VPN client rejects gateway certificate",
       "VPN certificate prompt every morning", "VPN login blocked by certificate error after update"]
PRINTER = ["Printer driver crashes when printing delivery notes", "Printer driver error after Windows update", "Printer driver asks for admin rights",
           "Wrong printer driver, pages print garbage", "Printer driver resets tray settings", "Printer driver missing on shared queue"]
FILESHARE_AFTER = ["Mapped drive S disconnects", "Excel file on shared drive locked by another user", "Shared drive S disconnected and file locked",
                   "Cannot save file on shared drive, file locked"]
MAJORS = [  # created, summary, ci, problem, hours to resolve
    ("2026-10-20 06:40", "Warehouse management unavailable at the Zaragoza hub", "WMS-APP-01", "", 4.5),
    ("2026-10-14 10:05", "Transport management system unavailable", "TMS-APP-01", "PRB-1025", 3.1),
    ("2026-05-26 09:15", "Outbound email to customers delayed for all users", "EXO-TENANT", "PRB-1001", 6.0),
    ("2026-09-02 08:20", "File shares unavailable at Madrid HQ", "FS-MAD-02", "PRB-1004", 2.4),
    ("2026-07-14 07:30", "EDI orders not received from customers", "EDI-GW-01", "PRB-1007", 5.2),
    ("2026-11-05 15:10", "Teams Phone calls failing in Valencia", "TEAMS-PHONE", "", 1.6),
]
RESOLUTION = {"workaround": "Resolved - workaround", "fix": "Resolved - permanent fix", "guidance": "Resolved - user guidance",
              "hardware": "Resolved - hardware replaced", "config": "Resolved - configuration change"}


def _w(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _day(rnd: random.Random, a: date, b: date, weekdays: bool = True) -> date:
    for _ in range(50):
        d = a + timedelta(days=rnd.randint(0, max(0, (b - a).days)))
        if not weekdays or d.weekday() < 5:
            return d
    return a


def _when(rnd: random.Random, d: date, shifts: bool) -> datetime:
    h = rnd.randint(6, 21) if shifts else rnd.randint(8, 18)
    return datetime(d.year, d.month, d.day, h, rnd.randint(0, 59))


def _resolve(rnd: random.Random, created: datetime, prio: str) -> datetime | None:
    hours = {"Highest": (1, 6), "High": (2, 30), "Medium": (1, 80), "Low": (2, 150)}[prio]
    r = created + timedelta(hours=rnd.uniform(*hours))
    if (TODAY - created.date()).days <= 4 and rnd.random() < 0.35:
        return None
    return r if r < datetime(2026, 11, 8, 9, 0) else None


def _prio(rnd: random.Random, code: str) -> str:
    return {"H": "High", "M": "Medium", "L": "Low", "X": "Highest"}[rnd.choice(code)]


def incidents(rnd: random.Random) -> list[dict]:
    meta = {c[0]: c for c in CIS}
    rows = []

    def add(ci: str, summary: str, created: datetime, prio: str, problem: str = "", major: bool = False, reopen: int = 0,
            resolution: str = "", hours: float | None = None):
        _, service, _, team, category, _, _ = meta[ci]
        group = team if prio in ("Highest", "High") or rnd.random() < 0.6 else "Service Desk"
        res = created + timedelta(hours=hours) if hours else _resolve(rnd, created, prio)
        rows.append({"created": created, "resolved": res, "priority": prio, "service": service, "ci": ci, "category": category, "group": group,
                     "problem": problem, "summary": summary, "resolution": (resolution or rnd.choice(["guidance", "fix", "config", "workaround"]))
                     if res else "", "reopen": reopen, "major": major})

    # everyday incidents: each summary used in turn, so none repeats more than a few times in 90 days
    span = (END - START).days
    for ci, service, crit, team, category, n, phrases in CIS:
        shifts = ci.startswith(("WMS", "SCN", "WIFI-Z", "WIFI-V"))
        items = []
        for ph in phrases:              # spread evenly over the six months
            step = span / n
            for k in range(n):
                d = START + timedelta(days=int((k + rnd.uniform(0.15, 0.85)) * step))
                while not shifts and d.weekday() >= 5:
                    d -= timedelta(days=1)
                items.append((d, ph))
        for d, ph in sorted(items):
            prio = rnd.choices(PRIO, [1, 12, 60, 27])[0] if crit != "Critical" else rnd.choices(PRIO, [2, 25, 55, 18])[0]
            reopen = 1 if rnd.random() < 0.04 else 0
            add(ci, ph, _when(rnd, d, ci.startswith(("WMS", "SCN", "WIFI-Z", "WIFI-V"))), prio, reopen=reopen,
                resolution="hardware" if category.startswith("Hardware") and rnd.random() < 0.4 else "")
    # incidents linked to the problem records
    for p in P:
        spec = p[17]
        if not spec:
            continue
        phrases, n, a, b, share, prios = spec
        a, b = date.fromisoformat(a), date.fromisoformat(b)
        for k in range(n):
            d = _day(rnd, a, b, False) if k else a
            if p[0] == "PRB-1004" and k == 0:
                d = date(2026, 7, 14)
            link = p[0] if (k == 0 or rnd.random() < share) else ""
            add(p[6], phrases[k % len(phrases)], _when(rnd, d, True), _prio(rnd, prios), link,
                resolution="workaround" if p[9] else "")
    # 1. VPN certificate: 46 incidents since late August, no problem record
    for k in range(46):
        d = _day(rnd, date(2026, 10, 5) if k % 2 else date(2026, 8, 24), END) if k > 5 else date(2026, 8, 24) + timedelta(days=k * 3)
        prio = "High" if k % 8 == 3 else "Medium"
        add("VPN-ASA-01", VPN[k % len(VPN)], _when(rnd, d, False), prio, reopen=2 if k in (7, 19, 33) else 0,
            resolution="workaround")
    # 2. printer driver cluster at the Zaragoza hub
    for k in range(17):
        d = _day(rnd, date(2026, 9, 10), END)
        add("PRT-ZAZ-01", PRINTER[k % len(PRINTER)], _when(rnd, d, False), "Medium" if k % 3 == 0 else "Low")
    # 3. FS-MAD-02 incidents after CHG-2004 (15 Sep): the fix did not hold
    for k in range(11):
        d = _day(rnd, date(2026, 9, 22), END)
        add("FS-MAD-02", FILESHARE_AFTER[k % 4], _when(rnd, d, False), "High" if k == 5 else "Medium", "PRB-1004" if k % 3 == 0 else "",
            reopen=2 if k == 4 else 0, resolution="workaround")
    # 4. major incidents
    for created, summary, ci, prob, hours in MAJORS:
        add(ci, summary, datetime.fromisoformat(created), "Highest", prob, True, resolution="fix", hours=hours)
    rows.sort(key=lambda r: (r["created"], r["ci"], r["summary"]))
    for k, r in enumerate(rows):
        r["key"] = f"INC-{10001 + k}"
        if r["resolved"] and r["resolved"] > datetime(2026, 11, 8, 9, 0):
            r["resolved"] = None
    return rows


def write(folder: Path) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(SEED)
    inc = incidents(rnd)
    fmt = lambda x: x.strftime("%Y-%m-%d %H:%M") if x else ""  # noqa: E731
    _w(folder / "incidents.csv", ["Issue key", "Created", "Resolved", "Priority", "Affected services", "Configuration item", "Category",
                                  "Assignment group", "Linked problem", "Summary", "Resolution", "Reopen count", "Major incident"],
       [[r["key"], fmt(r["created"]), fmt(r["resolved"]), r["priority"], r["service"], r["ci"], r["category"], r["group"], r["problem"],
         r["summary"], RESOLUTION.get(r["resolution"], "") if r["resolved"] else "", r["reopen"], "Yes" if r["major"] else "No"] for r in inc])
    meta = {c[0]: c for c in CIS}
    _w(folder / "problems.csv", ["Issue key", "Summary", "Created", "Status", "Assignee", "Owner team", "Affected services",
                                 "Configuration item", "Root cause category", "Root cause", "Workaround", "Workaround text", "Known error since",
                                 "Published to service desk", "Linked change", "Target date", "Updated", "Review date", "Resolved"],
       [[p[0], p[1], p[2], p[3], p[4], p[5], meta[p[6]][1], p[6], p[7], p[8], "Yes" if p[9] else "No", p[9], p[10], p[11], p[12], p[13],
         p[14], p[15], p[16]] for p in P])
    _w(folder / "changes.csv", ["Issue key", "Summary", "Status", "Implemented", "Linked problem", "Outcome"], [list(c) for c in CHANGES])
    _w(folder / "cmdb.csv", ["CI", "Service", "Criticality", "Owner team"], [[c[0], c[1], c[2], c[3]] for c in CIS])
    (folder / "settings.json").write_text(json.dumps(SETTINGS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


__all__ = ["write", "ORG", "SETTINGS"]
