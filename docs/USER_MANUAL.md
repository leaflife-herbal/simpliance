# User Manual - Factory Compliance Manager (cloud edition)

## 1. Roles
* **Super Admin** (one per installation): creates organisations (with licence limits), companies and users, resets
  passwords, downloads company backups, sees the audit log and renewal reminders. Cannot enter compliance data.
* **Operator**: enters data in the companies assigned to them. Needs the **salary access** tick to see or process pay.
* **Viewer**: read-only.
Passwords: at least 6 characters with a letter and a digit. 5 wrong attempts lock the account for 15 minutes.

## 2. First set-up (Super Admin)
1. Organisations: create the customer, set max companies/users and subscription date.
2. Companies: fill licence, registrations, address, occupier, manager. Check **Payroll settings** (salary divisor, PF
   ceiling, ESI threshold, Professional Tax slabs, attendance time variation) and **Documents** (language for notices
   and pay slips: English only / English + Hindi / English + Punjabi).
3. Users: create an Operator, tick the companies and (if needed) salary access. They change the password at first login.

## 3. Daily and monthly work (Operator)
* **Home** shows licence expiry, active employees, accidents still needing notice, open dangerous occurrences and last
  month's salary status. Pick the working company at the top of Home.
* **Employees**: add one by one, or **Import from Excel** (download the template, fill, upload; all-or-nothing).
  The optional "Name in Hindi / Punjabi" is printed on local-language pay slips.
* **Holidays**: enter the company's paid holidays for the year.
* **Leave**: earned-leave register for the year. Enter each employee's opening balance; accrual (1 day per N days
  worked, N set in the company payroll settings) and leave taken (PL days in attendance) are calculated. PDF/Excel.
* **Monthly processing**: 1 Save days worked (and OT hours, advance, deductions). 2 Generate attendance register
  (natural in/out times, weekly offs and holidays marked). 3 Calculate salary.
* **Attendance**: review and correct any day; download PDF/Excel and the muster roll.
* **Salary**: check, finalise (locks the month) or unlock; pay slips, salary register, PF and ESI statements
  (PDF/Excel). **Print** links open bilingual pay slips: use the browser's Print or Save as PDF.
* **Registers**: child & adolescent workers, accidents, loss & damage, dangerous occurrences, other occurrences.
  Red messages must be fixed; yellow warnings can be saved after confirming.
* **Notice of work periods**: bilingual notice built from your employees' shifts; type the rest interval and print.

## 4. Backups (Super Admin)
Companies > **Backup (CSV zip)** downloads all of that company's data as CSV files (opens in Excel). Do this weekly while
on the free database plan, and keep the zip safe. It is a safety copy, not a one-click restore.

## 5. Legal note
The Factories Act, 1948 has been replaced by the OSH Code, 2020 (in force from 21 Nov 2025). Forms, time limits and
registers under the State rules are still being finalised: confirm them with your State labour department. Hindi and
Punjabi labels should be reviewed by a native reader before official use.

## 6. Using it on a phone
Open the site address in Chrome (Android) or Safari (iPhone). To install it like an app: Chrome menu > **Add to Home screen**
(or **Install app**); Safari Share button > **Add to Home Screen**. Pages adapt to the phone screen and wide tables scroll
sideways. PDFs open in the phone's viewer; for pay slips and notices use the **Print** links, then the browser's Share/Print
menu > **Save as PDF**. On the free hosting plan the first open after a quiet spell can take about a minute.
