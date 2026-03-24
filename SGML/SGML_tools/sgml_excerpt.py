#!/usr/bin/env python3
"""Extract a slice of a PL SGML volume by page-column range.

Scans the raw SGML for <COL N="…"> markers and extracts the text between
--start-col and --end-col (inclusive), wrapped in the ancestor elements
that were open at the extraction point, so the output is a parseable
stand-alone SGML file.

COL N values use the Migne column notation: a 4-digit number optionally
followed by a letter suffix indicating the sub-column (e.g. "0523A",
"0523B", "0533").  Comparison is numeric-first then alphabetic so that
"0523A" < "0523B" < "0524A" < "0533".

Usage
-----
  python3 SGML/SGML_tools/sgml_excerpt.py \\
    SGML/Volumes/CD1_SGML_VOLUME_002.sgml \\
    --start-col 0523A \\
    --end-col   0533  \\
    --out       SGML/Volumes/excerpts/vol002_0523A-0533.sgml

  python3 SGML/SGML_tools/sgml_excerpt.py \\
    SGML/Volumes/CD1_SGML_VOLUME_002.sgml \\
    --start-col 0019B \\
    --end-col   0020D \\
    --out       SGML/Volumes/excerpts/vol002_0019B-0020D.sgml
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Structural (block-level) tags that define nesting ancestors.
# Inline tags (HI, FOREIGN, SUP, …) are intentionally excluded: they open and
# close within a single line and tracking them would only add noise.
_STRUCTURAL = {
  "VOLUME", "VOLFRONT", "VOLBODY", "FRONT", "BACK",
  "GROUP", "BODY", "DOC", "DIV1", "DIV2", "DIV3",
  "P", "HEAD", "NOTE", "POEM", "TBL", "LIST", "ITEM",
  "CONTENTS", "SOURCE", "CAPTION",
}

_TAG_OPEN  = re.compile(r"<([A-Z][A-Z0-9._]*)\b[^>]*/?>")
_TAG_CLOSE = re.compile(r"</([A-Z][A-Z0-9._]*)>")
_COL_PAT   = re.compile(r'<COL\s+N="([^"]+)"')


def col_key(n: str) -> tuple[int, str]:
  """Parse a COL N= value into (numeric, letter) for proper ordering."""
  m = re.match(r"^(\d+)([A-Z]*)$", n.strip())
  if m:
    return (int(m.group(1)), m.group(2))
  return (0, n)


def in_col_range(n: str, start: str, end: str) -> bool:
  return col_key(start) <= col_key(n) <= col_key(end)


def _evolve_stack(stack: list[str], text: str) -> list[str]:
  """Return updated tag stack after processing structural open/close tags in *text*."""
  result = list(stack)
  for m in re.finditer(r"<(/?)([A-Z][A-Z0-9._]*)\b[^>]*(?<!/)>", text):
    closing, tag = m.group(1), m.group(2)
    if tag not in _STRUCTURAL:
      continue
    if closing:
      if result and result[-1] == tag:
        result.pop()
    else:
      result.append(tag)
  return result


def _open_ancestors(text: str) -> list[str]:
  """Return the structural tag stack that is open at the end of *text*."""
  return _evolve_stack([], text)


def extract_col_range(
  source: Path,
  start_col: str,
  end_col:   str,
  encoding:  str = "cp1252",
) -> str:
  """Return a stand-alone SGML string for the given column range."""
  text = source.read_text(encoding=encoding)

  # ── locate start ──────────────────────────────────────────────────────────
  start_pos: int | None = None
  for m in _COL_PAT.finditer(text):
    if col_key(m.group(1)) >= col_key(start_col):
      start_pos = m.start()
      break

  if start_pos is None:
    raise ValueError(f"Column {start_col!r} not found in {source.name}")

  # ── locate end ────────────────────────────────────────────────────────────
  # Keep the last COL marker that still falls within the range, then advance
  # to the *next* COL after it so we include its trailing text.
  end_pos: int = len(text)
  last_end_col_end: int | None = None

  for m in _COL_PAT.finditer(text, start_pos):
    n = m.group(1)
    if col_key(n) <= col_key(end_col):
      last_end_col_end = m.start()
    else:
      # First COL that is past end_col: slice just before it
      end_pos = m.start()
      break

  if last_end_col_end is None:
    raise ValueError(f"Column {end_col!r} not found after {start_col!r} in {source.name}")

  # ── compute open ancestor stack at start_pos ──────────────────────────────
  ancestors = _open_ancestors(text[:start_pos])

  # ── build the excerpt ─────────────────────────────────────────────────────
  body = text[start_pos:end_pos]

  # Open with the ancestor stack at the start point, but close with whatever
  # is *actually* open at the end of the slice (the body may open or close
  # some structural elements relative to the starting state).
  open_wrap    = "".join(f"<{t}>" for t in ancestors)
  final_stack  = _evolve_stack(ancestors, body)
  close_wrap   = "".join(f"</{t}>" for t in reversed(final_stack))

  return open_wrap + body + close_wrap


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  parser.add_argument("source", help="Path to the .sgml volume file.")
  parser.add_argument(
    "--start-col", required=True,
    help='First column to include, e.g. "0523A".',
  )
  parser.add_argument(
    "--end-col", required=True,
    help='Last column to include, e.g. "0533".',
  )
  parser.add_argument(
    "--out",
    help="Output path (default: excerpts/<stem>_<start>-<end>.sgml next to source).",
  )
  parser.add_argument(
    "--encoding", default="cp1252",
    help="Source file encoding (default: cp1252).",
  )
  return parser


def main(argv: list[str] | None = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)

  source = Path(args.source)
  out = Path(args.out) if args.out else (
    source.parent / "excerpts" / f"{source.stem}_{args.start_col}-{args.end_col}.sgml"
  )
  out.parent.mkdir(parents=True, exist_ok=True)

  try:
    excerpt = extract_col_range(
      source    = source,
      start_col = args.start_col,
      end_col   = args.end_col,
      encoding  = args.encoding,
    )
  except ValueError as e:
    print(f"Error: {e}", file=sys.stderr)
    return 1

  out.write_text(excerpt, encoding=args.encoding)
  print(out)
  return 0


if __name__ == "__main__":
  sys.exit(main())
