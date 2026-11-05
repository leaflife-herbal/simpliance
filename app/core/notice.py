"""Groups workers by identical working periods for the Notice of Periods of Work."""


def group_shifts(emps):
    """emps: dicts with department, shift_in, shift_out, weekly_off. Returns rows sorted by start time."""
    groups = {}
    for e in emps:
        key = (e.get("department") or "All workers", e["shift_in"], e["shift_out"], e["weekly_off"])
        groups[key] = groups.get(key, 0) + 1
    rows = [{"group": k[0], "start": k[1], "end": k[2], "weekly_off": k[3], "count": n} for k, n in groups.items()]
    return sorted(rows, key=lambda r: (r["start"], r["end"], r["group"]))
