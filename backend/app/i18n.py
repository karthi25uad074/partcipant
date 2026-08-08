"""Multi-language advisory localisation (English, Tamil, Malayalam, Hindi).

Two-stage, fully offline (no network, no LLM) so it runs on an edge node:
  1. Pattern layer  — regex templates for the advisory sentences the engine emits,
     with numbers/dates/names carried through as capture groups.
  2. Glossary layer — term-by-term substitution for anything the patterns miss,
     so output degrades gracefully instead of failing.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

SUPPORTED = ("en", "ta", "ml", "hi")

# ---------------------------------------------------------------- patterns ---
# (regex, {lang: template}) — \1, \2 ... refer to capture groups.
PATTERNS: List[Tuple[str, Dict[str, str]]] = [
    (r"^Irrigate on (\S+) — ([\d.]+) mm \(([\d,]+) L\)$", {
        "ta": r"\1 அன்று நீர்ப்பாசனம் செய்யுங்கள் — \2 மி.மீ (\3 லிட்டர்)",
        "ml": r"\1-ന് നനയ്ക്കുക — \2 മി.മീ (\3 ലിറ്റർ)",
        "hi": r"\1 को सिंचाई करें — \2 मिमी (\3 लीटर)",
    }),
    (r"^Run (.+?) irrigation for about (\d+) minutes on (\S+), applying ([\d.]+) mm gross\. Skip if more than ([\d.]+) mm of rain falls first\.$", {
        "ta": r"\3 அன்று \1 முறையில் சுமார் \2 நிமிடம் நீர் பாய்ச்சுங்கள் (\4 மி.மீ). அதற்கு முன் \5 மி.மீ மேல் மழை பெய்தால் தவிர்க்கவும்.",
        "ml": r"\3-ന് \1 രീതിയിൽ ഏകദേശം \2 മിനിറ്റ് നനയ്ക്കുക (\4 മി.മീ). അതിനുമുൻപ് \5 മി.മീ-ൽ കൂടുതൽ മഴ ലഭിച്ചാൽ ഒഴിവാക്കുക.",
        "hi": r"\3 को \1 सिंचाई लगभग \2 मिनट चलाएँ (\4 मिमी)। उससे पहले \5 मिमी से अधिक वर्षा हो तो न करें।",
    }),
    (r"^No irrigation needed this week$", {
        "ta": "இந்த வாரம் நீர்ப்பாசனம் தேவையில்லை",
        "ml": "ഈ ആഴ്ച നനയ്ക്കേണ്ട ആവശ്യമില്ല",
        "hi": "इस सप्ताह सिंचाई की आवश्यकता नहीं है",
    }),
    (r"^Forecast rainfall of ([\d.]+) mm covers crop water demand\. Keep drains clear instead\.$", {
        "ta": r"முன்னறிவிப்பு மழை \1 மி.மீ பயிரின் நீர்த் தேவையை பூர்த்தி செய்யும். வடிகால்களை சுத்தமாக வைக்கவும்.",
        "ml": r"പ്രവചിച്ച \1 മി.മീ മഴ വിളയുടെ ജലാവശ്യം നിറവേറ്റും. ചാലുകൾ വൃത്തിയായി സൂക്ഷിക്കുക.",
        "hi": r"अनुमानित \1 मिमी वर्षा फसल की जल आवश्यकता पूरी करेगी। नालियों को साफ रखें।",
    }),
    (r"^Apply ([\d.]+) kg N/ha \(([\d.]+) kg urea for this plot\)$", {
        "ta": r"ஹெக்டேருக்கு \1 கிலோ நைட்ரஜன் இடவும் (இந்த நிலத்திற்கு \2 கிலோ யூரியா)",
        "ml": r"ഹെക്ടറിന് \1 കിലോ നൈട്രജൻ നൽകുക (ഈ പ്ലോട്ടിന് \2 കിലോ യൂറിയ)",
        "hi": r"प्रति हेक्टेयर \1 किग्रा नाइट्रोजन दें (इस खेत के लिए \2 किग्रा यूरिया)",
    }),
    (r"^Top-dress ([\d.]+) kg urea across ([\d.]+) ha between (.+?)\. Band it 5 cm beside the plant row and irrigate lightly within 24 hours\.$", {
        "ta": r"\3 இடையே \2 ஹெக்டேருக்கு \1 கிலோ யூரியா மேல் உரமாக இடவும். வரிசைக்கு 5 செ.மீ பக்கவாட்டில் இட்டு 24 மணி நேரத்தில் இலகுவாக நீர் பாய்ச்சவும்.",
        "ml": r"\3 ഇടയിൽ \2 ഹെക്ടറിൽ \1 കിലോ യൂറിയ മേൽവളമായി നൽകുക. നിരയിൽ നിന്ന് 5 സെ.മീ അകലെ ഇട്ട് 24 മണിക്കൂറിനുള്ളിൽ ചെറുതായി നനയ്ക്കുക.",
        "hi": r"\3 के बीच \2 हेक्टेयर में \1 किग्रा यूरिया टॉप-ड्रेस करें। पंक्ति से 5 सेमी दूर डालें और 24 घंटे में हल्की सिंचाई करें।",
    }),
    (r"^(.+?) risk is (High|Medium|Low) \((\d+)%\)$", {
        "ta": r"\1 அபாயம் \2 (\3%)",
        "ml": r"\1 അപകടസാധ്യത \2 (\3%)",
        "hi": r"\1 का जोखिम \2 (\3%)",
    }),
    (r"^(.+?) risk is (High|Medium|Low)$", {
        "ta": r"\1 அபாயம் \2",
        "ml": r"\1 അപകടസാധ്യത \2",
        "hi": r"\1 का जोखिम \2",
    }),
    (r"^Scout 10 random plants per acre within 48 hours\. If the threshold is crossed: (.+)$", {
        "ta": r"48 மணி நேரத்தில் ஏக்கருக்கு 10 செடிகளை சோதிக்கவும். வரம்பு தாண்டினால்: \1",
        "ml": r"48 മണിക്കൂറിനുള്ളിൽ ഏക്കറിന് 10 ചെടികൾ പരിശോധിക്കുക. പരിധി കടന്നാൽ: \1",
        "hi": r"48 घंटे में प्रति एकड़ 10 पौधों की जाँच करें। सीमा पार हो तो: \1",
    }),
    (r"^(.+?) is the dominant risk \((\d+)%\)$", {
        "ta": r"முதன்மை அபாயம் \1 (\2%)",
        "ml": r"പ്രധാന അപകടസാധ്യത \1 (\2%)",
        "hi": r"मुख्य जोखिम \1 (\2%)",
    }),
    (r"^Target harvest around (\S+)$", {
        "ta": r"\1 வாக்கில் அறுவடை திட்டமிடுங்கள்",
        "ml": r"\1-ന് അടുത്ത് വിളവെടുപ്പ് ആസൂത്രണം ചെയ്യുക",
        "hi": r"\1 के आसपास कटाई की योजना बनाएँ",
    }),
    (r"^Plan (\d+) labour-days or one combine slot for (\S+)\. Expected output ([\d.]+) tonnes\.$", {
        "ta": r"\2 அன்று \1 ஆள்-நாள் அல்லது ஒரு அறுவடை இயந்திரம் ஒதுக்குங்கள். எதிர்பார்க்கும் விளைச்சல் \3 டன்.",
        "ml": r"\2-ന് \1 തൊഴിലാളി-ദിവസം അല്ലെങ്കിൽ ഒരു കൊയ്ത്തുയന്ത്രം ക്രമീകരിക്കുക. പ്രതീക്ഷിക്കുന്ന വിളവ് \3 ടൺ.",
        "hi": r"\2 के लिए \1 श्रम-दिवस या एक कंबाइन स्लॉट रखें। अपेक्षित उपज \3 टन।",
    }),
    (r"^Follow (.+?) with (.+)$", {
        "ta": r"\1 க்குப் பிறகு \2 பயிரிடுங்கள்",
        "ml": r"\1 കഴിഞ്ഞ് \2 കൃഷി ചെയ്യുക",
        "hi": r"\1 के बाद \2 बोएँ",
    }),
    (r"^AgriSense (.+?) \((.+?)\)$", {
        "ta": r"அக்ரிசென்ஸ் \1 (\2)",
        "ml": r"അഗ്രിസെൻസ് \1 (\2)",
        "hi": r"अग्रिसेंस \1 (\2)",
    }),
    (r"^Health ([\d.]+)/100 (\w+)$", {
        "ta": r"பயிர் ஆரோக்கியம் \1/100 \2",
        "ml": r"വിള ആരോഗ്യം \1/100 \2",
        "hi": r"फसल स्वास्थ्य \1/100 \2",
    }),
    (r"^Yield ([\d.]+) t/ha \(conf (\d+)%\)$", {
        "ta": r"விளைச்சல் \1 டன்/ஹெ (நம்பகம் \2%)",
        "ml": r"വിളവ് \1 ടൺ/ഹെ (വിശ്വാസ്യത \2%)",
        "hi": r"उपज \1 टन/हे (विश्वास \2%)",
    }),
    (r"^Irrigate (\S+) ([\d.]+)mm$", {
        "ta": r"நீர்ப்பாசனம் \1 \2மிமீ",
        "ml": r"നന \1 \2മിമീ",
        "hi": r"सिंचाई \1 \2मिमी",
    }),
    (r"^No irrigation needed 7d$", {
        "ta": "7 நாள் நீர்ப்பாசனம் தேவையில்லை", "ml": "7 ദിവസം നന വേണ്ട", "hi": "7 दिन सिंचाई नहीं",
    }),
    (r"^No pest alert$", {
        "ta": "பூச்சி எச்சரிக்கை இல்லை", "ml": "കീട മുന്നറിയിപ്പ് ഇല്ല", "hi": "कीट चेतावनी नहीं",
    }),
    (r"^Do: (.+)$", {"ta": r"செய்யவும்: \1", "ml": r"ചെയ്യുക: \1", "hi": r"करें: \1"}),
]

# ---------------------------------------------------------------- glossary ---
GLOSSARY: Dict[str, Dict[str, str]] = {
    "High": {"ta": "அதிகம்", "ml": "ഉയർന്നത്", "hi": "अधिक"},
    "Medium": {"ta": "மத்திமம்", "ml": "മധ്യമം", "hi": "मध्यम"},
    "Low": {"ta": "குறைவு", "ml": "കുറവ്", "hi": "कम"},
    "Excellent": {"ta": "மிகச் சிறந்தது", "ml": "മികച്ചത്", "hi": "उत्तम"},
    "Good": {"ta": "நல்லது", "ml": "നല്ലത്", "hi": "अच्छा"},
    "Moderate": {"ta": "சராசரி", "ml": "സാധാരണ", "hi": "ठीक"},
    "Poor": {"ta": "மோசம்", "ml": "മോശം", "hi": "खराब"},
    "Critical": {"ta": "மிக மோசம்", "ml": "അതീവ ഗുരുതരം", "hi": "गंभीर"},
    "Drought stress": {"ta": "வறட்சி அழுத்தம்", "ml": "വരൾച്ചാ സമ്മർദ്ദം", "hi": "सूखा तनाव"},
    "Flood / waterlogging": {"ta": "வெள்ளம் / நீர் தேங்குதல்", "ml": "വെള്ളപ്പൊക്കം / നീർക്കെട്ട്", "hi": "बाढ़ / जलभराव"},
    "Pest outbreak": {"ta": "பூச்சித் தாக்குதல்", "ml": "കീടബാധ", "hi": "कीट प्रकोप"},
    "Fungal disease": {"ta": "பூஞ்சை நோய்", "ml": "കുമിൾ രോഗം", "hi": "फंगल रोग"},
    "Climate anomaly": {"ta": "காலநிலை மாறுபாடு", "ml": "കാലാവസ്ഥാ വ്യതിയാനം", "hi": "जलवायु विसंगति"},
    "Rice": {"ta": "நெல்", "ml": "നെല്ല്", "hi": "धान"},
    "Banana": {"ta": "வாழை", "ml": "വാഴ", "hi": "केला"},
    "Coconut": {"ta": "தென்னை", "ml": "തെങ്ങ്", "hi": "नारियल"},
    "Maize": {"ta": "மக்காச்சோளம்", "ml": "ചോളം", "hi": "मक्का"},
    "Groundnut": {"ta": "நிலக்கடலை", "ml": "നിലക്കടല", "hi": "मूंगफली"},
    "Black Pepper": {"ta": "மிளகு", "ml": "കുരുമുളക്", "hi": "काली मिर्च"},
    "Tapioca": {"ta": "மரவள்ளி", "ml": "മരച്ചീനി", "hi": "टैपिओका"},
    "Blackgram": {"ta": "உளுந்து", "ml": "ഉഴുന്ന്", "hi": "उड़द"},
    "Cowpea": {"ta": "தட்டைப்பயறு", "ml": "പയർ", "hi": "लोबिया"},
    "Sesame": {"ta": "எள்", "ml": "എള്ള്", "hi": "तिल"},
    "Brown Plant Hopper": {"ta": "பச்சைத் தத்துப்பூச்சி", "ml": "തവിട്ട് ചാഴി", "hi": "भूरा फुदका"},
    "Leaf Folder": {"ta": "இலைச்சுருட்டுப் புழு", "ml": "ഓലചുരുട്ടിപ്പുഴു", "hi": "पत्ती लपेटक"},
    "Fall Armyworm": {"ta": "படைப்புழு", "ml": "പട്ടാളപ്പുഴു", "hi": "फॉल आर्मीवर्म"},
    "Pseudostem Weevil": {"ta": "தண்டு வண்டு", "ml": "മാണവണ്ട്", "hi": "स्यूडोस्टेम घुन"},
    "Sigatoka Leaf Spot": {"ta": "சிகடோகா இலைப்புள்ளி", "ml": "സിഗട്ടോക്ക പുള്ളിരോഗം", "hi": "सिगाटोका पत्ती धब्बा"},
    "Rhinoceros Beetle": {"ta": "காண்டாமிருக வண்டு", "ml": "കൊമ്പൻചെല്ലി", "hi": "गैंडा भृंग"},
    "Root Wilt": {"ta": "வேர் வாடல்", "ml": "കടലിനാശം (വേരുചീയൽ)", "hi": "जड़ म्लानि"},
    "Leaf Miner": {"ta": "இலைச்சுரங்கப் புழு", "ml": "ഇലതുരപ്പൻ", "hi": "पत्ती सुरंगक"},
    "Tikka Leaf Spot": {"ta": "திக்கா இலைப்புள்ளி", "ml": "ടിക്ക പുള്ളിരോഗം", "hi": "टिक्का पत्ती धब्बा"},
    "Quick Wilt (Phytophthora)": {"ta": "துரித வாடல் நோய்", "ml": "ദ്രുതവാട്ടം", "hi": "शीघ्र म्लानि"},
    "Cassava Mosaic Vector (Whitefly)": {"ta": "வெள்ளை ஈ (மொசைக் நோய்க்காரணி)", "ml": "വെള്ളീച്ച (മൊസൈക് വാഹകൻ)", "hi": "सफेद मक्खी (मोज़ेक वाहक)"},
}

STAGE = {
    "initial": {"ta": "ஆரம்ப நிலை", "ml": "ആരംഭ ഘട്ടം", "hi": "प्रारंभिक अवस्था"},
    "development": {"ta": "வளர்ச்சி நிலை", "ml": "വളർച്ചാ ഘട്ടം", "hi": "विकास अवस्था"},
    "mid": {"ta": "நடு நிலை", "ml": "മധ്യ ഘട്ടം", "hi": "मध्य अवस्था"},
    "late": {"ta": "முதிர் நிலை", "ml": "പാകമാകുന്ന ഘട്ടം", "hi": "पकने की अवस्था"},
}

UI_STRINGS = {
    "en": {"dashboard": "Dashboard", "advisory": "Advisory", "risk": "Risk", "yield": "Yield",
           "irrigation": "Irrigation", "confidence": "Confidence", "health": "Crop health", "action": "Do"},
    "ta": {"dashboard": "முகப்பு", "advisory": "ஆலோசனை", "risk": "அபாயம்", "yield": "விளைச்சல்",
           "irrigation": "நீர்ப்பாசனம்", "confidence": "நம்பகத்தன்மை", "health": "பயிர் ஆரோக்கியம்", "action": "செய்யவும்"},
    "ml": {"dashboard": "ഡാഷ്ബോർഡ്", "advisory": "ഉപദേശം", "risk": "അപകടസാധ്യത", "yield": "വിളവ്",
           "irrigation": "നനയ്ക്കൽ", "confidence": "വിശ്വാസ്യത", "health": "വിള ആരോഗ്യം", "action": "ചെയ്യുക"},
    "hi": {"dashboard": "डैशबोर्ड", "advisory": "सलाह", "risk": "जोखिम", "yield": "उपज",
           "irrigation": "सिंचाई", "confidence": "विश्वास", "health": "फसल स्वास्थ्य", "action": "करें"},
}

_COMPILED = [(re.compile(p), m) for p, m in PATTERNS]


def translate(text: str, lang: str = "en") -> str:
    """Localise one advisory sentence. Returns the input unchanged for English."""
    if lang == "en" or lang not in SUPPORTED or not text:
        return text
    stripped = text.strip()
    for rx, mapping in _COMPILED:
        m = rx.match(stripped)
        if m and lang in mapping:
            out = rx.sub(mapping[lang], stripped)
            return _glossary_pass(out, lang)
    return _glossary_pass(stripped, lang)


def _glossary_pass(text: str, lang: str) -> str:
    for term, mapping in sorted(GLOSSARY.items(), key=lambda kv: -len(kv[0])):
        if lang not in mapping:
            continue
        lead = r"\b" if term[:1].isalnum() else ""
        trail = r"\b" if term[-1:].isalnum() else ""
        text = re.sub(rf"{lead}{re.escape(term)}{trail}", mapping[lang], text)
    for stage, mapping in STAGE.items():
        if lang in mapping:
            text = re.sub(rf"\b{stage}\b", mapping[lang], text)
    return text


def ui_strings(lang: str = "en") -> Dict[str, str]:
    return UI_STRINGS.get(lang, UI_STRINGS["en"])


def ui(key: str, lang: str = "en") -> str:
    """Look up a short interface label, falling back to English then the key."""
    table = UI_STRINGS.get(lang if lang in SUPPORTED else "en", UI_STRINGS["en"])
    return table.get(key) or UI_STRINGS["en"].get(key, key)
