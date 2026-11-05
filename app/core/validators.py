"""Business-rule validators. Each returns (errors, warnings) and may add computed values.
Rules are indicative summaries of the Factories Act, 1948 and the Child and Adolescent
Labour (Prohibition and Regulation) Act, 1986 - always verify against your State
Factories Rules."""
from datetime import date

from .util import age_on, minutes_between, parse_iso, t2m


def employee(v, cid, row_id):
    e, w = [], []
    dob, doj = parse_iso(v["date_of_birth"]), parse_iso(v["date_of_joining"])
    if doj < dob:
        e.append("Date of joining cannot be before date of birth")
    else:
        age = age_on(dob, doj)
        if age < 14:
            e.append(f"Employee was only {age} years old on joining. Employment of a child below 14 is "
                     "prohibited (Sec. 67). Do not register this person as a worker.")
        elif age < 18:
            w.append(f"Employee was {age} on joining (child/adolescent). Record fitness certificate "
                     "details in the Child & Adolescent Workers Register.")
    if v.get("date_of_leaving") and parse_iso(v["date_of_leaving"]) < doj:
        e.append("Date of leaving cannot be before date of joining")
    if v["shift_in"] == v["shift_out"]:
        e.append("Shift in-time and out-time cannot be the same")
    if v["salary_type"] == "MONTHLY" and (v.get("basic") or 0) <= 0:
        w.append("Basic salary is zero - the salary will be zero")
    if v.get("date_of_leaving") and v.get("is_active"):
        w.append("A date of leaving is set but 'Currently employed' is ticked")
    return e, w


def child_labour(v, cid, row_id):
    e, w = [], []
    dob, doe = parse_iso(v["date_of_birth"]), parse_iso(v["date_of_employment"])
    if doe < dob:
        return ["Date of employment cannot be before date of birth"], []
    age = age_on(dob, doe)
    v["age_years"] = age
    if age < 14:
        e.append(f"Age at employment is {age}. Employment of children below 14 years is prohibited "
                 "(Sec. 67 Factories Act; Child and Adolescent Labour Act).")
        v["category"] = "Not permitted (under 14)"
    elif age < 15:
        v["category"] = "Child (14-15)"
    elif age < 18:
        v["category"] = "Adolescent (15-18)"
    else:
        v["category"] = "Adult"
        w.append("Person is 18 or older - this register is only for children and adolescents")
    mins = minutes_between(v["work_from"], v["work_to"])
    if mins == 0:
        e.append("Work period 'from' and 'to' cannot be the same")
        return e, w
    rest = v.get("rest_minutes") or 0
    hours = round((mins - rest) / 60, 2)
    v["daily_hours"] = hours
    if v["category"].startswith("Child"):
        if hours > 4.5:
            e.append(f"Daily work of {hours} hours exceeds the 4.5-hour limit for children (Sec. 71)")
        # night = 22:00-06:00; check overlap of work window with it
        s, f = t2m(v["work_from"]), t2m(v["work_to"])
        f = f if f > s else f + 1440
        for ns, nf in ((22 * 60, 30 * 60), (-2 * 60, 6 * 60), (22 * 60 + 1440, 30 * 60 + 1440)):
            if s < nf and f > ns:
                e.append("Work period overlaps night hours (10 pm - 6 am), not permitted for children (Sec. 71)")
                break
        if mins > 5 * 60:
            w.append("Children's work period should not spread over more than 5 hours per relay (Sec. 71)")
    if v.get("hazardous") and age < 18:
        e.append("Children and adolescents may not be employed in hazardous processes or occupations "
                 "(Child and Adolescent Labour Act, 1986)")
    if age < 18 and not v.get("certificate_no"):
        w.append("No certificate of fitness number recorded (Sec. 68 requires one)")
    if v.get("certificate_date") and parse_iso(v["certificate_date"]) > doe:
        w.append("Certificate of fitness is dated after the date of employment")
    return e, w


def accident(v, cid, row_id):
    e, w = [], []
    ad = parse_iso(v["accident_date"])
    if ad > date.today():
        e.append("Accident date is in the future")
    nd = parse_iso(v["notice_date"]) if v.get("notice_date") else None
    if nd and nd < ad:
        e.append("Notice date cannot be before the accident date")
    reportable = v["severity"] != "Minor (no notice)"
    if reportable and not nd:
        w.append("Fatal / 48-hour-disabling accidents must be notified to the Inspector (Sec. 88). "
                 "Notice date is blank.")
    if reportable and nd and (nd - ad).days > 1:
        w.append(f"Notice was sent {(nd - ad).days} days after the accident - check the time limit in your State Rules")
    if v["severity"].startswith("Serious") and (v.get("days_lost") or 0) < 2:
        w.append("'Serious' means disablement of 48 hours or more, but days lost is under 2")
    return e, w


def loss_damage(v, cid, row_id):
    e, w = [], []
    if parse_iso(v["incident_date"]) > date.today():
        e.append("Incident date is in the future")
    if v.get("insured") and not v.get("claim_no"):
        w.append("Marked insured but no claim number entered")
    return e, w


def dangerous(v, cid, row_id):
    e, w = [], []
    od = parse_iso(v["occurrence_date"])
    if od > date.today():
        e.append("Occurrence date is in the future")
    nd = parse_iso(v["notice_date"]) if v.get("notice_date") else None
    if nd and nd < od:
        e.append("Notice date cannot be before the occurrence date")
    if not nd:
        w.append("No notice date recorded - dangerous occurrences must be notified (Sec. 88A)")
    if v.get("target_date") and parse_iso(v["target_date"]) < od:
        e.append("Target completion date is before the occurrence date")
    return e, w


def other(v, cid, row_id):
    return [], []


BY_REGISTER = {"child_labour": child_labour, "accidents": accident, "loss_damage": loss_damage,
               "dangerous": dangerous, "other": other}
