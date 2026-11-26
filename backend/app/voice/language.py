"""Conservative supported-script checks. Never guess a transcription's intended words."""

import re
import unicodedata


def script_counts(text: str) -> dict[str, int]:
    counts = {"latin": 0, "devanagari": 0, "unsupported": 0}
    for char in text:
        if not unicodedata.category(char).startswith("L"):
            continue
        name = unicodedata.name(char, "")
        key = "devanagari" if "DEVANAGARI" in name else "latin" if "LATIN" in name else "unsupported"
        counts[key] += 1
    return counts


def resolve_language(text: str, preference: str = "auto") -> str:
    if preference in {"en", "hi", "hinglish"}:
        return preference
    # Explicit language requests in this turn take priority over old conversation history.
    if re.search(r"\b(?:in|speak|answer|respond in)\s+english\b", text, re.I):
        return "en"
    if re.search(r"\bhinglish\b", text, re.I):
        return "hinglish"
    if re.search(r"\b(?:in|speak|answer|respond in)\s+hindi\b", text, re.I):
        return "hi"
    counts = script_counts(text)
    if counts["devanagari"]:
        return "hinglish" if counts["latin"] else "hi"
    markers = re.findall(r"\b(?:hai|hain|aap|kya|mujhe|mein|nahi|samjhao|batao)\b", text.lower())
    return "hinglish" if len(markers) >= 2 else "en"


def language_issue(text: str, language: str, detected: str | None = None) -> str | None:
    counts = script_counts(text)
    if counts["unsupported"]:
        return "unsupported_script"
    if detected and detected not in {"en", "hi"}:
        return "language_mismatch"
    if language in {"en","hi"} and detected in {"en","hi"} and detected != language:
        return "language_mismatch"
    if language == "en" and counts["devanagari"]:
        return "language_mismatch"
    if language in {"hi", "hinglish"} and counts["latin"] and not counts["devanagari"]:
        return "script_mismatch"
    return None


def voice_instruction(language: str) -> str:
    target = {
        "en": "natural English using Latin script",
        "hi": "natural Hindi using Devanagari script, with English technical terms only where necessary",
        "hinglish": "natural conversational Hindi using Devanagari mixed with English technical terms; do not write Roman Hindi",
    }[language]
    return (f"For this voice turn respond in {target}. This current language setting overrides older "
            "conversation language preferences. Do not use Urdu/Arabic or other unsupported scripts. "
            "Start with one short complete sentence, then explain as needed. Be concise by default, "
            "but provide longer teaching explanations when requested. Preserve facts and tool safety.")


def language_notice(language: str) -> str:
    return ("The response could not be spoken in the selected language. Please check the text response."
            if language == "en" else "उत्तर चुनी हुई भाषा में नहीं बोला जा सका। कृपया लिखित उत्तर देखें।")
