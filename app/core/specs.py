"""Declarative field specifications. These drive the database DDL, the data-entry
forms, validation and the printed registers, so the three can never drift apart."""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Field:
    key: str
    label: str
    type: str = "text"   # text multiline date time int number choice bool employee
    required: bool = False
    choices: Optional[list] = None
    default: object = None
    list_col: bool = False     # shown in grid / printed register
    group: str = ""
    readonly: bool = False     # computed by validator, not editable
    unique_per_company: bool = False


@dataclass
class RegisterSpec:
    key: str
    title: str
    table: str
    fields: List[Field]
    sort: str
    help: str = ""


def F(*a, **k):
    return Field(*a, **k)


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
STATES = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
          "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
          "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
          "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
          "Uttarakhand", "West Bengal", "Andaman & Nicobar", "Chandigarh",
          "Dadra & Nagar Haveli and Daman & Diu", "Delhi", "Jammu & Kashmir", "Ladakh",
          "Lakshadweep", "Puducherry"]

COMPANY_FIELDS = [
    F("name", "Company / Factory name", required=True, list_col=True, group="Identification"),
    F("short_code", "Short code", required=True, list_col=True, unique_per_company=False, group="Identification"),
    F("nature_of_industry", "Manufacturing process / nature of industry", group="Identification"),
    F("factory_licence_no", "Factory licence no.", required=True, list_col=True, group="Factory licence"),
    F("licence_valid_from", "Licence valid from", "date", group="Factory licence"),
    F("licence_valid_to", "Licence valid up to", "date", group="Factory licence"),
    F("factory_registration_no", "Factory registration no.", group="Factory licence"),
    F("plan_approval_no", "Plan approval no.", group="Factory licence"),
    F("max_workers", "Max. workers on any day (licensed)", "int", group="Factory licence"),
    F("installed_power", "Installed power (HP / kW)", "number", group="Factory licence"),
    F("cin", "CIN", group="Registrations"),
    F("pan", "PAN", group="Registrations"),
    F("gstin", "GSTIN", group="Registrations"),
    F("pf_code", "EPF establishment code", group="Registrations"),
    F("esic_code", "ESIC employer code", group="Registrations"),
    F("udyam_no", "Udyam registration no.", group="Registrations"),
    F("pt_reg_no", "Professional Tax reg. no.", group="Registrations"),
    F("address1", "Address line 1", required=True, group="Factory address"),
    F("address2", "Address line 2", group="Factory address"),
    F("city", "City / Town", required=True, list_col=True, group="Factory address"),
    F("district", "District", group="Factory address"),
    F("state", "State", "choice", True, STATES, "Punjab", group="Factory address"),
    F("pincode", "PIN code", group="Factory address"),
    F("occupier_name", "Occupier name", required=True, group="Occupier"),
    F("occupier_father", "Occupier's father's name", group="Occupier"),
    F("occupier_designation", "Occupier designation", group="Occupier"),
    F("occupier_address", "Occupier residential address", "multiline", group="Occupier"),
    F("occupier_phone", "Occupier phone", group="Occupier"),
    F("manager_name", "Factory manager name", required=True, group="Factory manager"),
    F("manager_father", "Manager's father's name", group="Factory manager"),
    F("manager_phone", "Manager phone", group="Factory manager"),
    F("manager_email", "Manager email", group="Factory manager"),
    F("phone", "Factory phone", list_col=True, group="Contact"),
    F("email", "Factory email", group="Contact"),
    F("website", "Website", group="Contact"),
    F("wage_divisor", "Monthly salary divisor", "choice", True, ["Calendar days", "30 days", "26 days"],
      "Calendar days", group="Payroll settings"),
    F("hours_per_day", "Normal working hours per day", "number", True, default=8, group="Payroll settings"),
    F("attendance_variation", "Attendance time variation in minutes (in-time up to X min early, out-time up to X min late; 0 = exact shift times)",
      "int", default=10, group="Payroll settings"),
    F("pf_wage_ceiling", "PF wage ceiling (Rs.)", "number", True, default=15000, group="Payroll settings"),
    F("pf_on_actual", "PF on actual wages (ignore ceiling)", "bool", default=False, group="Payroll settings"),
    F("esi_threshold", "ESI wage threshold (Rs./month)", "number", True, default=21000, group="Payroll settings"),
    F("pt_slabs", "Professional Tax slabs (one per line: from-to:amount, e.g. 20834-*:200)", "multiline",
      group="Payroll settings"),
]

EMPLOYEE_FIELDS = [
    F("emp_code", "Employee code", required=True, list_col=True, unique_per_company=True, group="Personal"),
    F("name", "Full name", required=True, list_col=True, group="Personal"),
    F("father_name", "Father's / husband's name", group="Personal"),
    F("gender", "Gender", "choice", True, ["Male", "Female", "Other"], group="Personal"),
    F("date_of_birth", "Date of birth", "date", True, group="Personal"),
    F("address", "Address", "multiline", group="Personal"),
    F("mobile", "Mobile", group="Personal"),
    F("designation", "Designation", list_col=True, group="Employment"),
    F("department", "Department / section", list_col=True, group="Employment"),
    F("skill_category", "Skill category", "choice", False,
      ["Unskilled", "Semi-skilled", "Skilled", "Highly skilled", "Clerical", "Supervisory"], group="Employment"),
    F("date_of_joining", "Date of joining", "date", True, group="Employment"),
    F("date_of_leaving", "Date of leaving", "date", group="Employment"),
    F("is_active", "Currently employed", "bool", default=True, group="Employment"),
    F("shift_in", "Shift in-time (HH:MM)", "time", True, default="09:00", list_col=True, group="Shift"),
    F("shift_out", "Shift out-time (HH:MM)", "time", True, default="18:00", list_col=True, group="Shift"),
    F("weekly_off", "Weekly off day", "choice", True, WEEKDAYS, "Sunday", group="Shift"),
    F("uan", "UAN (PF)", group="Statutory / bank"),
    F("esic_no", "ESIC IP number", group="Statutory / bank"),
    F("bank_name", "Bank name", group="Statutory / bank"),
    F("bank_account", "Bank account no.", group="Statutory / bank"),
    F("ifsc", "IFSC", group="Statutory / bank"),
    F("salary_type", "Salary type", "choice", True, ["MONTHLY", "DAILY"], "MONTHLY", group="Salary structure"),
    F("basic", "Basic (per month, or per day if DAILY)", "number", True, default=0, group="Salary structure"),
    F("da", "Dearness allowance", "number", default=0, group="Salary structure"),
    F("hra", "HRA", "number", default=0, group="Salary structure"),
    F("other_allowance", "Other allowance", "number", default=0, group="Salary structure"),
    F("pf_applicable", "PF applicable", "bool", default=True, group="Salary structure"),
    F("esi_applicable", "ESI applicable (if within threshold)", "bool", default=True, group="Salary structure"),
    F("pt_applicable", "Professional Tax applicable", "bool", default=True, group="Salary structure"),
]

ACCIDENT_SEVERITY = ["Minor (no notice)", "Serious (disabled 48+ hrs)", "Fatal"]

REGISTERS = [
    RegisterSpec("child_labour", "Child & Adolescent Workers Register", "reg_child_labour", [
        F("name", "Name of child / adolescent", required=True, list_col=True, group="Identity"),
        F("father_name", "Father's name", group="Identity"),
        F("date_of_birth", "Date of birth", "date", True, list_col=True, group="Identity"),
        F("date_of_employment", "Date of employment", "date", True, list_col=True, group="Identity"),
        F("category", "Category (auto)", readonly=True, list_col=True, group="Identity"),
        F("age_years", "Age at employment (auto)", "int", readonly=True, list_col=True, group="Identity"),
        F("certificate_no", "Certificate of fitness no.", list_col=True, group="Fitness certificate"),
        F("certificate_date", "Certificate date", "date", group="Fitness certificate"),
        F("certifying_surgeon", "Certifying surgeon", group="Fitness certificate"),
        F("nature_of_work", "Nature of work", list_col=True, group="Work"),
        F("hazardous", "Hazardous process / occupation", "bool", default=False, group="Work"),
        F("shift_group", "Group / relay", "choice", False, ["Group I", "Group II", "Group III"], group="Work"),
        F("work_from", "Work period from (HH:MM)", "time", True, list_col=True, group="Work"),
        F("work_to", "Work period to (HH:MM)", "time", True, list_col=True, group="Work"),
        F("daily_hours", "Daily hours (auto)", "number", readonly=True, list_col=True, group="Work"),
        F("rest_minutes", "Rest interval (minutes)", "int", group="Work"),
        F("weekly_holiday", "Weekly holiday", "choice", False, WEEKDAYS, "Sunday", group="Work"),
        F("date_of_leaving", "Date of leaving", "date", group="Work"),
        F("remarks", "Remarks", "multiline", group="Work"),
    ], "date_of_employment DESC",
        "Sec. 67-77 Factories Act 1948 and the Child and Adolescent Labour Act 1986."),
    RegisterSpec("accidents", "Accident Register", "reg_accidents", [
        F("accident_date", "Date of accident", "date", True, list_col=True, group="Accident"),
        F("accident_time", "Time (HH:MM)", "time", group="Accident"),
        F("place", "Department / place", list_col=True, group="Accident"),
        F("employee_id", "Employee (optional)", "employee", group="Injured person"),
        F("injured_name", "Name of injured person", required=True, list_col=True, group="Injured person"),
        F("age", "Age", "int", group="Injured person"),
        F("gender", "Gender", "choice", False, ["Male", "Female", "Other"], group="Injured person"),
        F("designation", "Occupation", group="Injured person"),
        F("nature_of_injury", "Nature of injury", required=True, list_col=True, group="Injury"),
        F("body_part", "Part of body injured", group="Injury"),
        F("cause", "Cause of accident", "multiline", group="Injury"),
        F("severity", "Severity", "choice", True, ACCIDENT_SEVERITY, ACCIDENT_SEVERITY[0], True, group="Injury"),
        F("days_lost", "Days lost", "int", list_col=True, group="Injury"),
        F("medical_treatment", "Medical treatment given", "multiline", group="Injury"),
        F("notified_to", "Notice sent to", "choice", False,
          ["Inspector of Factories", "Dy. Chief Inspector of Factories", "ESIC", "Police", "Other"],
          group="Notification (Sec. 88)"),
        F("notice_date", "Notice date", "date", list_col=True, group="Notification (Sec. 88)"),
        F("notice_ref", "Notice reference no.", group="Notification (Sec. 88)"),
        F("notice_mode", "Mode", "choice", False, ["By hand", "Post / courier", "Email", "Online portal"],
          group="Notification (Sec. 88)"),
        F("compensation", "Compensation paid (Rs.)", "number", group="Follow-up"),
        F("witness", "Witness(es)", group="Follow-up"),
        F("remarks", "Remarks", "multiline", group="Follow-up"),
    ], "accident_date DESC", "Sec. 88 Factories Act 1948: notice of fatal / 48-hour-disabling accidents."),
    RegisterSpec("loss_damage", "Loss & Damage Register", "reg_loss_damage", [
        F("incident_date", "Date of incident", "date", True, list_col=True, group="Incident"),
        F("asset_type", "Category", "choice", True,
          ["Plant & machinery", "Building", "Raw material", "Finished goods", "Tools", "Vehicle", "Other"],
          list_col=True, group="Incident"),
        F("item", "Property / plant / machinery affected", required=True, list_col=True, group="Incident"),
        F("location", "Location", group="Incident"),
        F("nature", "Nature", "choice", True, ["Damage", "Loss", "Theft", "Fire", "Breakdown", "Other"],
          list_col=True, group="Incident"),
        F("description", "Description", "multiline", group="Incident"),
        F("estimated_loss", "Estimated loss (Rs.)", "number", list_col=True, group="Value"),
        F("cause", "Cause", "multiline", group="Value"),
        F("insured", "Insured", "bool", default=False, group="Insurance"),
        F("claim_no", "Claim no.", group="Insurance"),
        F("claim_amount", "Claim amount (Rs.)", "number", group="Insurance"),
        F("action_taken", "Action taken", "multiline", list_col=True, group="Action"),
        F("responsible", "Person responsible / reported by", group="Action"),
        F("remarks", "Remarks", "multiline", group="Action"),
    ], "incident_date DESC", "Record of loss of property and damage to plant and machinery."),
    RegisterSpec("dangerous", "Dangerous Occurrences Register", "reg_dangerous_occurrences", [
        F("occurrence_date", "Date", "date", True, list_col=True, group="Occurrence"),
        F("occurrence_time", "Time (HH:MM)", "time", group="Occurrence"),
        F("location", "Location / department", required=True, list_col=True, group="Occurrence"),
        F("description", "Description of occurrence", "multiline", True, list_col=True, group="Occurrence"),
        F("cause", "Cause", "multiline", True, list_col=True, group="Occurrence"),
        F("persons_affected", "Persons affected", "int", group="Occurrence"),
        F("property_damage", "Property damage (Rs.)", "number", group="Occurrence"),
        F("corrective_action", "Corrective action", "multiline", True, list_col=True, group="Action"),
        F("preventive_action", "Preventive action", "multiline", group="Action"),
        F("action_owner", "Responsible person", group="Action"),
        F("target_date", "Target completion date", "date", group="Action"),
        F("status", "Status", "choice", True, ["Open", "In progress", "Closed"], "Open", list_col=True,
          group="Action"),
        F("notified_to", "Notice sent to", "choice", False,
          ["Inspector of Factories", "Dy. Chief Inspector of Factories", "Other"],
          group="Notification (Sec. 88A)"),
        F("notice_date", "Notice date", "date", group="Notification (Sec. 88A)"),
        F("notice_ref", "Notice reference no.", group="Notification (Sec. 88A)"),
        F("remarks", "Remarks", "multiline", group="Notification (Sec. 88A)"),
    ], "occurrence_date DESC", "Sec. 88A Factories Act 1948: notice of dangerous occurrences."),
    RegisterSpec("other", "Other Occurrences Register", "reg_other_occurrences", [
        F("occurrence_date", "Date", "date", True, list_col=True, group="Occurrence"),
        F("occurrence_type", "Type", "choice", True,
          ["Near miss", "Fire / evacuation drill", "Safety training", "Safety committee meeting",
           "Inspector's visit", "Medical examination", "Notifiable disease (Sec. 89)", "Stoppage of work",
           "Power failure", "Other"], list_col=True, group="Occurrence"),
        F("description", "Description", "multiline", True, list_col=True, group="Occurrence"),
        F("persons", "Persons involved", list_col=True, group="Occurrence"),
        F("action_taken", "Action taken", "multiline", list_col=True, group="Follow-up"),
        F("reported_to", "Reported to", group="Follow-up"),
        F("follow_up_date", "Follow-up date", "date", group="Follow-up"),
        F("status", "Status", "choice", False, ["Open", "Closed"], "Closed", list_col=True, group="Follow-up"),
        F("remarks", "Remarks", "multiline", group="Follow-up"),
    ], "occurrence_date DESC", "Other statutory and operational occurrences."),
]

REGISTER_BY_KEY = {r.key: r for r in REGISTERS}
