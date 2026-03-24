#!/usr/bin/env python3
"""Convert an SGML file into HTML (semantic or structure-view tree).

Usage
-----
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, 'SGML/SGML_tools')
from sgml_tools import convert_sgml_to_html

failed = []
index_range = [1, 2]
for i in range(index_range[0], index_range[1] + 1):
  src = Path(f'SGML/Volumes/{i:03d}.sgml')
  out = Path(f'SGML/VolumesStruct/SGML_VOLUME_{i:03d}.html')
  try:
    convert_sgml_to_html(source=src, output_path=out, structure=True)
    print(f'VOL {i:03d} OK')
  except Exception as e:
    print(f'VOL {i:03d} FAIL: {e}')
    failed.append(i)
print()
print(f'Done: {index_range[1] - len(failed)}/index_range[1] OK, {len(failed)} failed:', failed)
"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sgml_tools import convert_sgml_to_html


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  parser.add_argument("source", help="Path to the SGML file.")
  parser.add_argument("--output-path", help="Path for the generated HTML file.")
  parser.add_argument(
    "--structure",
    action="store_true",
    help="Render a structure-view tree instead of semantic HTML.",
  )
  return parser


def main(argv: list[str] | None = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)

  print(
    convert_sgml_to_html(
      source=args.source,
      output_path=args.output_path,
      structure=args.structure,
    )
  )
  return 0


if __name__ == "__main__":
  sys.exit(main())
