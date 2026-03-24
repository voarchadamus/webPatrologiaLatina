#!/usr/bin/env python3
"""
Decode PLD Greek runs to Unicode Greek.

The PLD / DynaText Greek text is not stored as Unicode. It uses a compact
token stream whose mapping is described by local conversion tables:
- `PLDGCONV.TXT`
- `ACCGRK.TXT`

This module reads those tables and performs a longest-match tokenization.
"""
from __future__ import annotations
import unicodedata
from dataclasses import dataclass
from pathlib import Path


BASE_GREEK_MAP = {
  "a": "α",
  "b": "β",
  "c": "χ",
  "d": "δ",
  "e": "ε",
  "f": "φ",
  "g": "γ",
  "h": "η",
  "i": "ι",
  "k": "κ",
  "l": "λ",
  "m": "μ",
  "n": "ν",
  "o": "ο",
  "p": "π",
  "q": "θ",
  "r": "ρ",
  "s": "σ",
  "t": "τ",
  "u": "υ",
  "w": "ω",
  "x": "ξ",
  "y": "ψ",
  "z": "ζ",
}

ACCENT_MARKS = {
  "acute": ["\u0301"],
  "grave": ["\u0300"],
  "tilde": ["\u0342"],
  "diaresis": ["\u0308"],
  "macron": ["\u0304"],
  "smooth": ["\u0313"],
  "rough": ["\u0314"],
  "smooth_acute": ["\u0313", "\u0301"],
  "smooth_grave": ["\u0313", "\u0300"],
  "smooth_tilde": ["\u0313", "\u0342"],
  "rough_acute": ["\u0314", "\u0301"],
  "rough_grave": ["\u0314", "\u0300"],
  "rough_tilde": ["\u0314", "\u0342"],
  "diaresis_acute": ["\u0308", "\u0301"],
  "diaresis_grave": ["\u0308", "\u0300"],
  "diaresis_tilde": ["\u0308", "\u0342"],
  "up_smooth": ["\u0313"],
  "up_rough": ["\u0314"],
  "up_acute": ["\u0301"],
  "up_grave": ["\u0300"],
  "up_tilde": ["\u0342"],
  "up_smooth_acute": ["\u0313", "\u0301"],
  "up_smooth_grave": ["\u0313", "\u0300"],
  "up_smooth_tilde": ["\u0313", "\u0342"],
  "up_rough_acute": ["\u0314", "\u0301"],
  "up_rough_grave": ["\u0314", "\u0300"],
  "up_rough_tilde": ["\u0314", "\u0342"],
  "up_smooth_diaresis": ["\u0313", "\u0308"],
}

MARKER_CHARS = set("12345678jJv")
MARKER_CHARS.update(chr(code) for code in [130, 141, 217, 221, 222, 223, 228, 229, 230, 231, 232, 233, 240, 248, 250, 251])


@dataclass(frozen=True)
class GreekToken:
  """One entry from `PLDGCONV.TXT`."""
  entity: str
  source: str
  base_hint: str
  accent: str
  unicode_text: str


@dataclass(frozen=True)
class GreekDecodeResult:
  """Decoded Greek output plus a small amount of diagnostics."""
  text: str
  unknown_count: int


def _decode_source_token(
    source: str
  ) -> str:
  out: list[str] = []
  idx = 0
  while idx < len(source):
    if source[idx] == "&":
      end = idx + 1
      while end < len(source) and source[end].isdigit():
        end += 1
      if end > idx + 1:
        out.append(chr(int(source[idx + 1 : end])))
        idx = end
        continue
    out.append(source[idx])
    idx += 1
  return "".join(out)


def _base_from_source(
    source: str
  ) -> str:
  letters = [char for char in source if char.isalpha() and char not in {"j", "J", "v"}]
  if not letters:
    return ""
  return letters[0]


def _unicode_for_token(
    entity: str,
    source: str,
    accent: str
  ) -> str:
  if entity == "&isubgr;":
    return "\u0345"
  if accent == "sigma_final":
    return "ς"
  if accent == "sigma_lunar":
    return "ϲ"
  if accent == "up_sigma_lunar":
    return "Ϲ"
  base_letter = _base_from_source(source)
  if not base_letter:
    return source
  greek = BASE_GREEK_MAP.get(base_letter.lower())
  if greek is None:
    return source
  if base_letter.isupper():
    greek = greek.upper()
  marks = ACCENT_MARKS.get(accent, [])
  return unicodedata.normalize("NFC", greek + "".join(marks))


class GreekDecoder:
  def __init__(self, root: Path):
    self.root = root
    self.tokens = self._load_tokens(root / "PLDGCONV.TXT")
    self.by_source = {token.source: token for token in self.tokens if token.source}
    self.max_token_length = max(len(token.source) for token in self.tokens if token.source)

  def _load_tokens(self, path: Path) -> list[GreekToken]:
    tokens: list[GreekToken] = []
    for line in path.read_text("latin-1").splitlines():
      if not line.strip():
        continue
      entity, raw_source, base_hint, accent = line.split("|")
      source = _decode_source_token(raw_source)
      unicode_text = _unicode_for_token(entity, source, accent)
      tokens.append(
        GreekToken(
          entity=entity,
          source=source,
          base_hint=base_hint,
          accent=accent,
          unicode_text=unicode_text,
        )
      )
    return tokens

  def decode(self, text: str) -> GreekDecodeResult:
    out: list[str] = []
    idx = 0
    unknown_count = 0

    while idx < len(text):
      token = self._match(text, idx)
      if token is None:
        if text[idx] == "1":
          # In the PLD source stream, a standalone `1` can act like the same
          # breathing/elision glyph that appears attached to capital vowels in
          # tokens such as `1A`. The legacy HTML viewer renders it as U+1FEF.
          out.append("\u1fef")
          idx += 1
          continue
        if text[idx] == "×":
          out.append("·")
          idx += 1
          continue
        out.append(text[idx])
        idx += 1
        unknown_count += 1 if text[idx - 1].isalpha() else 0
        continue
      if token.entity == "&isubgr;" and out:
        out[-1] = unicodedata.normalize("NFC", out[-1] + token.unicode_text)
      else:
        out.append(token.unicode_text)
      idx += len(token.source)
    return GreekDecodeResult(
      text="".join(out),
      unknown_count=unknown_count,
    )

  def _match(self, text: str, idx: int) -> GreekToken | None:
    max_len = min(self.max_token_length, len(text) - idx)
    for length in range(max_len, 0, -1):
      token = self.by_source.get(text[idx : idx + length])
      if token is not None:
        return token
    return None
#$ Greek Decoder

def default_greek_decoder() -> GreekDecoder:
  root = Path(__file__).resolve().parent
  return GreekDecoder(root)
