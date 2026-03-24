#!/usr/bin/env python3
"""Batch-generate HTML for all PL volumes from a directory of SGML source files.

Pipeline
--------
  Convert each Volumes/NNN.sgml to Pages/NNN.html.

Usage
-----
  python3 SGML/SGML_tools/batch_gen.py

  # Custom directories:
  python3 SGML/SGML_tools/batch_gen.py \
    --volumes-dir Volumes \
    --pages-dir Pages
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_HERE      = Path(__file__).resolve().parent   # SGML/SGML_tools/
_SGML_DIR  = _HERE.parent                      # SGML/

sys.path.insert(0, str(_HERE))


def gen_html(sgml_paths: list[Path], pages_dir: Path) -> tuple[int, list[Path]]:
  from sgml_tools import sanitize_sgml
  from gen_sgml_page import Renderer, wrap_html
  from greek_parser import default_greek_decoder

  pages_dir.mkdir(parents=True, exist_ok=True)
  decoder = default_greek_decoder()
  ok, failed = 0, []

  for src in sorted(sgml_paths):
    out = pages_dir / src.with_suffix('.html').name
    try:
      text     = src.read_text(encoding='cp1252')
      root     = ET.fromstring(sanitize_sgml(text))
      renderer = Renderer(decoder=decoder, output_path=out.resolve())
      body     = renderer.render(root)
      title    = src.stem
      result   = wrap_html(body, title, output_path=out.resolve())
      out.write_text(result, encoding='utf-8')
      print(f'    {src.name} → {out.name}  ({out.stat().st_size // 1024} KB)', flush=True)
      ok += 1
    except Exception as exc:
      print(f'    FAIL {src.name}: {exc}', flush=True)
      failed.append(src)

  return ok, failed


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  parser.add_argument(
    '--volumes-dir', type=Path, default=_SGML_DIR / 'Volumes',
    help='Directory containing split volume .sgml files (default: SGML/Volumes/).',
  )
  parser.add_argument(
    '--pages-dir', type=Path, default=_SGML_DIR / 'Pages',
    help='Directory for generated HTML pages (default: SGML/Pages/).',
  )
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  volumes_dir = args.volumes_dir
  sgml_paths = sorted(volumes_dir.glob('*.sgml')) if volumes_dir.exists() else []
  if not sgml_paths:
    print(f'[skip] no .sgml files in {volumes_dir}')
    return 0
  ok, failed = gen_html(sgml_paths, args.pages_dir)
  print(f'\nTotal: {ok} OK, {len(failed)} failed')
  for p in failed:
    print(f'  FAILED: {p}')
  return 1 if failed else 0


if __name__ == '__main__':
  sys.exit(main())
