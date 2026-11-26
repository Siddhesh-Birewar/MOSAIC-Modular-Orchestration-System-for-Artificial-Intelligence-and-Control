"""Spoken representation, language routing, and incremental sentence boundaries."""

import re
import json
from dataclasses import dataclass
import unicodedata
from typing import Literal

Language = Literal['auto', 'en', 'hi', 'hinglish']
VOICES = {'en': 'af_bella', 'hi': 'hf_alpha', 'hinglish': 'hf_alpha'}
ABBREVIATIONS = {'mr', 'mrs', 'ms', 'dr', 'prof', 'vs', 'etc', 'e.g', 'i.e', 'st', 'jr'}


def language_for(text: str, preference: str = 'auto', detected: str | None = None) -> str:
    # Response script has priority over input detection: the response may change language.
    if re.search('[\u0900-\u097f]', text):
        return 'hinglish' if re.search('[A-Za-z]{2,}', text) else 'hi'
    if preference in {'en', 'hi', 'hinglish'}:
        return preference
    roman_hindi = re.findall(r'\b(?:hai|hain|aap|ka|ki|kya|mein|mujhe|nahi|aur|samjhao)\b', text.lower())
    return 'hinglish' if len(roman_hindi) >= 2 else 'en'


def normalize_speech(text: str) -> str:
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'```[\s\S]*?(?:```|$)', ' Code is available in the text response. ', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'!\[([^]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\[([^]]+)\]\(https?://[^)]+\)', r'\1', text)
    text = re.sub(r'https?://[^\s<>]+', ' link in the text response ', text)
    # JSON/tool-like blobs are not speech. Never read keys/arguments as an action.
    while match := re.search(r'\{\s*"|\[\s*["{]', text):
        try:
            _, length = json.JSONDecoder().raw_decode(text[match.start():])
        except ValueError:
            length = len(text)-match.start()
        text = text[:match.start()] + ' structured data in the text response ' + text[match.start()+length:]
    text = re.sub(r'(?m)^\s*(?:#{1,6}\s+|[-*+•]\s+|\d+[.)]\s+)', '', text)
    text = re.sub(r'\*\*([^*]+)\*\*|__([^_]+)__', lambda m: m[1] or m[2], text)
    text = re.sub(r'(?<!\w)[*_]([^*_\n]+)[*_](?!\w)', r'\1', text)
    text = re.sub(r'(?<=\d)%', ' percent', text)
    text = re.sub(r'(?<=\d)\s*\+\s*(?=\d)', ' plus ', text)
    text = re.sub(r'(?<=\d)\s*[×*]\s*(?=\d)', ' times ', text)
    text = re.sub(r'(?<=\d)\s*/\s*(?=\d)', ' slash ', text)  # preserves dates/fractions without guessing
    text = text.translate(str.maketrans({'=': ' equals ', '≤': ' less than or equal to ', '≥': ' greater than or equal to ', '°': ' degrees ', '₹': ' rupees ', '$': ' dollars ', '€': ' euros ', '£': ' pounds ', '➕': ' plus ', '➖': ' minus ', '✖': ' times ', '➗': ' divided by ', '→': ' to '}))
    text = re.sub(r'\b(API|CPU|GPU|SQL|RAM|HTTP|URL|TTS|STT|LLM)\b', lambda m: ' '.join(m[0]), text)
    # Preserve meaningful math/currency; omit decorative emoji and controls only.
    text = ''.join(c for c in text if not (unicodedata.category(c) in {'Cs', 'Co'} or
                   (0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF) or ord(c) in {0xFE0F, 0x200D}) )
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', text)
    return ' '.join(text.split())


@dataclass(frozen=True)
class SpeechSegment:
    text: str
    language: str


class Segmenter:
    """Incremental sentence parser. Keep fences, URLs, decimals and abbreviations intact."""
    def __init__(self, limit: int = 160, language: str = "auto") -> None:
        self.buffer = ''
        self.limit = limit
        self.language = language

    def feed_segments(self, text: str, final: bool = False) -> list[SpeechSegment]:
        self.buffer += text
        if len(self.buffer) > 20000:
            raise ValueError('Speech segment buffer exceeds limit')
        result = []
        while self.buffer:
            fence = False
            inline = False
            depth = 0
            cut = None
            i = 0
            while i < len(self.buffer):
                if self.buffer.startswith('```', i):
                    fence = not fence
                    i += 3
                    continue
                c = self.buffer[i]
                if c == '`' and not fence:
                    inline = not inline
                if not fence and not inline:
                    if c in '{[':
                        depth += 1
                    elif c in '}]':
                        depth = max(0,depth-1)
                if not fence and not inline and depth == 0 and c in '.!?।\n' and (i + 1 < len(self.buffer) or final):
                    following = self.buffer[i+1:i+2]
                    prefix = self.buffer[:i+1]
                    word = re.search(r'([^\s]+)$', prefix)
                    tail = word[1].lower() if word else ''
                    abbreviation = tail.rstrip('.') in ABBREVIATIONS or bool(re.fullmatch(r'(?:[a-z]\.){1,}', tail))
                    decimal = c == '.' and i > 0 and self.buffer[i-1].isdigit() and following.isdigit()
                    if (c in '\n।' or not following or following.isspace()) and not abbreviation and not decimal:
                        cut = i + 1
                        break
                i += 1
            if cut is None:
                if not final:
                    break
                cut = len(self.buffer)
            sentence, self.buffer = self.buffer[:cut], self.buffer[cut:]
            spoken = normalize_speech(sentence)
            route = language_for(spoken,self.language)
            # Word-bounded small Hindi chunks mitigate upstream phonemizer truncation.
            while len(spoken) > self.limit:
                position = spoken.rfind(' ', 0, self.limit + 1)
                if position < 1:
                    position = self.limit
                result.append(SpeechSegment(spoken[:position].strip(),route))
                spoken = spoken[position:].strip()
            if spoken:
                result.append(SpeechSegment(spoken,route))
        return result

    def feed(self, text: str, final: bool = False) -> list[str]:
        return [segment.text for segment in self.feed_segments(text,final)]
