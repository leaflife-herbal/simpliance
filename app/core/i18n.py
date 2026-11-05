"""English / Hindi / Punjabi labels for printable notices and pay slips.
Translations should be checked by a native reader before official use."""
LANGS = {"English only": "en", "English + Hindi": "hi", "English + Punjabi": "pa"}
LANG_NAMES = {"en": "English", "hi": "Hindi", "pa": "Punjabi"}

L = {  # key: (English, Hindi, Punjabi)
    "notice_adults": ("NOTICE OF PERIODS OF WORK FOR ADULTS", "वयस्क श्रमिकों के कार्य की अवधि की सूचना",
                      "ਬਾਲਗ ਕਾਮਿਆਂ ਦੇ ਕੰਮ ਦੇ ਸਮੇਂ ਦਾ ਨੋਟਿਸ"),
    "licence_no": ("Factory licence no.", "कारखाना लाइसेंस सं.", "ਫੈਕਟਰੀ ਲਾਇਸੰਸ ਨੰ."),
    "group": ("Group / section", "समूह / विभाग", "ਸਮੂਹ / ਵਿਭਾਗ"),
    "workers": ("No. of workers", "श्रमिकों की संख्या", "ਕਾਮਿਆਂ ਦੀ ਗਿਣਤੀ"),
    "work_from": ("Work starts", "कार्य आरंभ", "ਕੰਮ ਸ਼ੁਰੂ"),
    "work_to": ("Work ends", "कार्य समाप्त", "ਕੰਮ ਖ਼ਤਮ"),
    "rest": ("Interval for rest", "विश्राम का अंतराल", "ਆਰਾਮ ਦਾ ਅੰਤਰਾਲ"),
    "weekly_holiday": ("Weekly holiday", "साप्ताहिक अवकाश", "ਹਫ਼ਤਾਵਾਰੀ ਛੁੱਟੀ"),
    "manager": ("Manager", "प्रबंधक", "ਪ੍ਰਬੰਧਕ"),
    "date": ("Date", "दिनांक", "ਮਿਤੀ"),
    "signature": ("Signature", "हस्ताक्षर", "ਦਸਤਖ਼ਤ"),
    "payslip": ("PAY SLIP", "वेतन पर्ची", "ਤਨਖ਼ਾਹ ਸਲਿੱਪ"),
    "month": ("Month", "माह", "ਮਹੀਨਾ"),
    "emp_code": ("Employee code", "कर्मचारी कोड", "ਕਰਮਚਾਰੀ ਕੋਡ"),
    "name": ("Name", "नाम", "ਨਾਮ"),
    "designation": ("Designation", "पद", "ਅਹੁਦਾ"),
    "department": ("Department", "विभाग", "ਵਿਭਾਗ"),
    "days_month": ("Days in month", "माह के दिन", "ਮਹੀਨੇ ਦੇ ਦਿਨ"),
    "days_paid": ("Days paid", "भुगतान के दिन", "ਭੁਗਤਾਨ ਵਾਲੇ ਦਿਨ"),
    "present": ("Days present", "उपस्थित दिन", "ਹਾਜ਼ਰ ਦਿਨ"),
    "absent": ("Absent days", "अनुपस्थित दिन", "ਗ਼ੈਰਹਾਜ਼ਰ ਦਿਨ"),
    "offs": ("Weekly offs / holidays", "साप्ताहिक अवकाश / छुट्टियाँ", "ਹਫ਼ਤਾਵਾਰੀ ਛੁੱਟੀਆਂ / ਛੁੱਟੀਆਂ"),
    "ot_hours": ("Overtime hours", "ओवरटाइम घंटे", "ਓਵਰਟਾਈਮ ਘੰਟੇ"),
    "earnings": ("Earnings", "आय", "ਕਮਾਈ"),
    "deductions": ("Deductions", "कटौतियाँ", "ਕਟੌਤੀਆਂ"),
    "basic": ("Basic", "मूल वेतन", "ਮੁੱਢਲੀ ਤਨਖ਼ਾਹ"),
    "da": ("Dearness allowance", "महंगाई भत्ता", "ਮਹਿੰਗਾਈ ਭੱਤਾ"),
    "hra": ("House rent allowance", "मकान किराया भत्ता", "ਮਕਾਨ ਕਿਰਾਇਆ ਭੱਤਾ"),
    "other_allow": ("Other allowance", "अन्य भत्ता", "ਹੋਰ ਭੱਤਾ"),
    "overtime": ("Overtime", "ओवरटाइम", "ਓਵਰਟਾਈਮ"),
    "pf": ("Provident Fund", "भविष्य निधि", "ਪ੍ਰੋਵੀਡੈਂਟ ਫੰਡ"),
    "esi": ("ESI", "कर्मचारी राज्य बीमा", "ਕਰਮਚਾਰੀ ਰਾਜ ਬੀਮਾ"),
    "pt": ("Professional Tax", "व्यवसाय कर", "ਪੇਸ਼ਾ ਟੈਕਸ"),
    "advance": ("Advance", "अग्रिम", "ਪੇਸ਼ਗੀ"),
    "other_ded": ("Other deduction", "अन्य कटौती", "ਹੋਰ ਕਟੌਤੀ"),
    "gross": ("Gross earnings", "कुल आय", "ਕੁੱਲ ਕਮਾਈ"),
    "total_ded": ("Total deductions", "कुल कटौती", "ਕੁੱਲ ਕਟੌਤੀ"),
    "net": ("NET PAY", "शुद्ध वेतन", "ਸ਼ੁੱਧ ਤਨਖ਼ਾਹ"),
    "in_words": ("Net pay in words", "शब्दों में शुद्ध वेतन", "ਸ਼ਬਦਾਂ ਵਿੱਚ ਸ਼ੁੱਧ ਤਨਖ਼ਾਹ"),
    "emp_sign": ("Employee signature", "कर्मचारी के हस्ताक्षर", "ਕਰਮਚਾਰੀ ਦੇ ਦਸਤਖ਼ਤ"),
    "auth_sign": ("Authorised signatory", "अधिकृत हस्ताक्षरकर्ता", "ਅਧਿਕਾਰਤ ਦਸਤਖ਼ਤਕਰਤਾ"),
}
DAYS = {  # English weekday: (Hindi, Punjabi)
    "Monday": ("सोमवार", "ਸੋਮਵਾਰ"), "Tuesday": ("मंगलवार", "ਮੰਗਲਵਾਰ"), "Wednesday": ("बुधवार", "ਬੁੱਧਵਾਰ"),
    "Thursday": ("गुरुवार", "ਵੀਰਵਾਰ"), "Friday": ("शुक्रवार", "ਸ਼ੁੱਕਰਵਾਰ"), "Saturday": ("शनिवार", "ਸ਼ਨੀਵਾਰ"),
    "Sunday": ("रविवार", "ਐਤਵਾਰ")}


def lang_code(setting, override=None):
    """override ('en'/'hi'/'pa') wins; company setting text maps to a code; unset defaults to Hindi."""
    if override in LANG_NAMES:
        return override
    return LANGS.get(setting or "", "hi")


def bi(key, lang):
    en, hi, pa = L[key]
    return en if lang == "en" else f"{en} / {hi if lang == 'hi' else pa}"


def bi_day(name, lang):
    if lang == "en" or name not in DAYS:
        return name
    return f"{name} / {DAYS[name][0] if lang == 'hi' else DAYS[name][1]}"
