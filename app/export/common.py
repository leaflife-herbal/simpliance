from dataclasses import dataclass, field
from typing import List


@dataclass
class Report:
    title: str
    headers: List[str]
    rows: List[list]
    subtitle: str = ""
    widths: List[float] = field(default_factory=list)   # relative column widths
    landscape: bool = True
    font_size: float = 8
    footer_rows: List[list] = field(default_factory=list)   # e.g. totals


def company_lines(c):
    """Header lines printed on every document. c: company row/dict."""
    addr = ", ".join(x for x in [c["address1"], c["address2"], c["city"], c["district"], c["state"], c["pincode"]] if x)
    lic = " | ".join(x for x in [
        f"Factory Licence No.: {c['factory_licence_no']}" if c["factory_licence_no"] else "",
        f"Reg. No.: {c['factory_registration_no']}" if c["factory_registration_no"] else ""] if x)
    people = " | ".join(x for x in [
        f"Occupier: {c['occupier_name']}" if c["occupier_name"] else "",
        f"Manager: {c['manager_name']}" if c["manager_name"] else ""] if x)
    return [c["name"], addr, lic, people]
