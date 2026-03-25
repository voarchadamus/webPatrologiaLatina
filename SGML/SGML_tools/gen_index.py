"""
Generate SGML/index.html from DocumentaCatholicaOmniaTOC{1,2,3}.txt.

Parses the TOC HTML files, extracts per-volume chapter entries
(Volumen, Ab Ad Columnas, Auctor Floruit, Auctor, Operis Nomen), produces SGML/index.html

  python3 SGML/SGML_tools/gen_index.py --out SGML/index.html
"""

from __future__ import annotations
NOTE_SYMBOL = "⁜" # Dotted Cross
FIGURE_SYMBOL = "▩"
TOC_SYMBOL = "🜍"
FONT_SYMBOL = "🜞" # Crocus Of Iron
SIZE_SYMBOL = "∑"
WIDTH_SYMBOL = "∮"
import argparse
import html
import re
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote as _url_quote

_HERE      = Path(__file__).resolve().parent   # SGML/SGML_tools/
_SGML_DIR  = _HERE.parent                      # SGML/
_REPO_ROOT = _SGML_DIR.parent                  # webPatrologiaLatina/
_IGNOREUS  = _REPO_ROOT / 'ignoreus'

_TOC_FILES = [
  _IGNOREUS / 'DocumentaCatholicaOmniaTOC1.txt',
  _IGNOREUS / 'DocumentaCatholicaOmniaTOC2.txt',
  _IGNOREUS / 'DocumentaCatholicaOmniaTOC3.txt',
]

_PAGES_DIR   = _SGML_DIR / 'Pages'
_DEFAULT_OUT = _SGML_DIR / 'index.html'

e = html.escape


# ── data types ────────────────────────────────────────────────────────────────

class Entry(NamedTuple):
  volumen: str   # e.g. "MPL001"
  ab_ad:   str   # column range, e.g. "0009 - 0072C"
  floruit: str   # date, e.g. "0160-0220"
  auctor:  str   # author name (plain text)
  operis:  str   # work name (plain text)


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _strip_html(s: str) -> str:
  """Remove all HTML tags and decode basic entities."""
  s = re.sub(r'<[^>]+>', '', s)
  s = (s
    .replace('&nbsp;', ' ')
    .replace('&amp;',  '&')
    .replace('&lt;',   '<')
    .replace('&gt;',   '>')
    .replace('&quot;', '"'))
  return s.strip()


def _clean(s: str) -> str:
  """Strip HTML tags and collapse whitespace."""
  return re.sub(r'\s+', ' ', _strip_html(s)).strip()


# ── TOC parsing ───────────────────────────────────────────────────────────────

def parse_toc(path: Path) -> dict[str, list[Entry]]:
  """Parse one TOC HTML file -> {vol_num: [Entry, ...]}  e.g. {'001': [...]}."""
  text = path.read_text(encoding='iso-8859-1', errors='replace')

  # Split into volume sections at each volume anchor.
  # The anchors look like:
  #   <A Name="Migne Patrologia Latina - Volumen 001"></a>
  parts = re.split(
    r'<A\s+Name="Migne Patrologia Latina - Volumen (\d+)"[^>]*>',
    text, flags=re.IGNORECASE,
  )
  # parts = [preamble, vol_num, section_text, vol_num, section_text, ...]

  volumes: dict[str, list[Entry]] = {}

  i = 1
  while i < len(parts) - 1:
    vol_num = parts[i].zfill(3)   # '1' -> '001'
    section = parts[i + 1]
    i += 2

    # The data table has border=1 and contains the column headers
    # "Volumen", "Ab Ad Columnas", etc.
    table_m = re.search(
      r'<Table[^>]*border=1[^>]*>(.*?)</Table>',
      section, re.IGNORECASE | re.DOTALL,
    )
    if not table_m:
      volumes.setdefault(vol_num, [])
      continue

    table_body = table_m.group(1)

    # Split on <TR> to get individual rows.
    # tr_parts[0] = junk before first TR
    # tr_parts[1] = header row (Volumen | Ab Ad Columnas | ...)
    # tr_parts[2+] = data rows
    tr_parts = re.split(r'<TR\b[^>]*>', table_body, flags=re.IGNORECASE)

    entries: list[Entry] = []
    for tr in tr_parts[2:]:
      # Split on <TD> to get cell contents.
      # tds[0] = junk before first TD in this row
      # tds[1] = Volumen, tds[2] = Ab Ad Columnas, tds[3] = Floruit,
      # tds[4] = Auctor, tds[5] = Operis Nomen
      tds = re.split(r'<TD\b[^>]*>', tr, flags=re.IGNORECASE)
      if len(tds) < 6:
        continue

      vol_cell  = _clean(tds[1])
      ab_cell   = _clean(tds[2])
      flor_cell = _clean(tds[3])
      auct_cell = _clean(tds[4])
      oper_cell = _clean(tds[5])

      if not vol_cell or not vol_cell.upper().startswith('MPL'):
        continue

      entries.append(Entry(
        volumen=vol_cell,
        ab_ad=ab_cell,
        floruit=flor_cell,
        auctor=auct_cell,
        operis=oper_cell,
      ))

    volumes[vol_num] = entries

  return volumes


def load_all_tocs() -> dict[str, list[Entry]]:
  """Load all available TOC files, merged into a single dict."""
  result: dict[str, list[Entry]] = {}
  for toc in _TOC_FILES:
    if toc.exists():
      print(f'  Parsing {toc.name}…')
      result.update(parse_toc(toc))
    else:
      print(f'  [skip] {toc.name} not found')
  return result


# ── HTML generation ───────────────────────────────────────────────────────────

def _col_start(ab_ad: str) -> str:
  """Extract the start column from an 'Ab Ad Columnas' value like '0009 - 0072C'."""
  parts = re.split(r'\s*-\s*', ab_ad, maxsplit=1)
  return parts[0].strip() if parts else ''


def _ab_ad_cell(ab_ad: str, page_href: str | None) -> str:
  """Render the Ab Ad Columnas cell, optionally linking to the column in the page.

  Uses a text-fragment URL (#:~:text=…) so no modification to the target
  pages is required.  Supported by Chromium-based browsers and Safari 16.1+.
  """
  if not page_href:
    return e(ab_ad)
  col = _col_start(ab_ad)
  if not col:
    return e(ab_ad)
  fragment = '#:~:text=' + _url_quote(f'[Col. {col}]', safe='')
  return f'<a href="{e(page_href)}{e(fragment)}">{e(ab_ad)}</a>'


_PAGE_TOOLS = (
  '<div class="page-tools">\n'
  '  <label class="tool-toggle" data-tool-group="toc" title="Show or hide the volume index.">'
  '<input type="checkbox" data-toc-toggle checked> 🜍</label>\n'
  '  <div class="tool-cluster tool-cluster-font">\n'
  '    <label class="tool-select-wrap" title="Switch the main reading font.">\n'
  f'      <span class="tool-select-text">{FONT_SYMBOL}</span>\n'
  '      <select class="tool-select" data-font-select aria-label="Select reading font">\n'
  '        <option value="garamontio" selected>Garamontio</option>\n'
  '        <option value="centaur">Centaur</option>\n'
  '      </select>\n'
  '    </label>\n'
  '  </div>\n'
  '  <label class="tool-select-wrap" title="Set page font size in percent.">\n'
  f'    <span class="tool-select-text">{SIZE_SYMBOL}</span>\n'
  '    <input type="number" class="tool-size-input" data-size-input '
  'min="50" max="250" step="5" value="150" aria-label="Font size percent">\n'
  '  </label>\n'
  '  <label class="tool-select-wrap" title="Set text column width in rem.">\n'
  f'    <span class="tool-select-text">{WIDTH_SYMBOL}</span>\n'
  '    <input type="number" class="tool-size-input" data-width-input '
  'min="20" max="120" step="2" value="72" aria-label="Text width in rem">\n'
  '  </label>\n'
  '  <button type="button" class="tool-theme-btn" data-theme-toggle '
  'title="Switch between light and dark theme" aria-label="Toggle dark theme">\u2600 Light</button>\n'
  '</div>\n'
)


def generate_index(
    volumes:  dict[str, list[Entry]],
    pages:    set[str],
    out_path: Path,
  ) -> None:
  all_vols = sorted(set(volumes) | pages)

  parts: list[str] = []
  parts.append('<!DOCTYPE html>\n')
  parts.append('<html lang="la">\n')
  parts.append('<head>\n')
  parts.append('  <meta charset="utf-8">\n')
  parts.append('  <title>Patrologia Latina \u2014 Index Voluminum</title>\n')
  parts.append('  <link rel="stylesheet" href="assets/tree_style.css">\n')
  parts.append('  <link rel="stylesheet" href="assets/index_style.css">\n')
  parts.append('</head>\n')
  parts.append('<body>\n')
  parts.append(
    '<script>!function(){try{var b=document.body,ls=localStorage,'
    "t=ls.getItem('pl-tree-theme'),f=ls.getItem('pl-tree-text-font'),"
    "s=parseInt(ls.getItem('pl-tree-font-size'),10),"
    "w=parseInt(ls.getItem('pl-tree-width'),10);"
    "if(t==='dark')b.setAttribute('data-theme','dark');"
    "if(f==='centaur')b.setAttribute('data-text-font','centaur');"
    "document.documentElement.style.fontSize=(isNaN(s)?150:s)+'%';"
    "if(!isNaN(w)&&w!==72)b.style.setProperty('--content-width',w*16 + 'px');"
    "}catch(e){}}();</script>\n"
  )
  # #ebt-toc must be a direct child of <body> so the CSS grid rule
  # body:has(#ebt-toc:not([hidden])) creates the two-column layout.
  parts.append('<nav id="ebt-toc" class="toc-nav" aria-label="Volume index" hidden></nav>\n')
  parts.append('<article class="pl-page">\n')
  parts.append('<header><h1 class="tree-title">Patrologia Latina \u2014 Index Voluminum</h1></header>\n')
  parts.append(_PAGE_TOOLS)
  parts.append('<main class="pl-tree">\n\n')

  # ── per-volume sections ───────────────────────────────────────────────────
  # h2.doc-title is picked up by tree_scripts.js buildToc(), which
  # auto-populates #ebt-toc with volume links as the sidebar.
  for vol in all_vols:
    has_page  = vol in pages
    entries   = volumes.get(vol, [])
    page_href = f'Pages/{vol}.html' if has_page else ''

    parts.append(f'<section id="{e(vol)}" class="vol-section">\n')

    heading = f'Volumen {int(vol)}'
    if has_page:
      parts.append(
        f'  <h2 class="vol-heading doc-title">'
        f'<a href="{e(page_href)}">{e(heading)}</a></h2>\n'
      )
    else:
      parts.append(f'  <h2 class="vol-heading doc-title">{e(heading)}</h2>\n')
      parts.append('  <p class="vol-note">Page not yet generated.</p>\n')

    if entries:
      parts.append('  <table class="idx-table">\n')
      parts.append('    <thead><tr>\n')
      parts.append('      <th class="idx-col-volumen">Volumen</th>\n')
      parts.append('      <th class="idx-col-abad">Ab Ad Columnas</th>\n')
      parts.append('      <th class="idx-col-floruit">Auctor Floruit</th>\n')
      parts.append('      <th class="idx-col-auctor">Auctor</th>\n')
      parts.append('      <th class="idx-col-operis">Operis Nomen</th>\n')
      parts.append('    </tr></thead>\n')
      parts.append('    <tbody>\n')
      for ent in entries:
        ab_ad_html = _ab_ad_cell(ent.ab_ad, page_href)
        parts.append('      <tr>\n')
        parts.append(f'        <td>{e(ent.volumen)}</td>\n')
        parts.append(f'        <td>{ab_ad_html}</td>\n')
        parts.append(f'        <td>{e(ent.floruit)}</td>\n')
        parts.append(f'        <td>{e(ent.auctor)}</td>\n')
        parts.append(f'        <td>{e(ent.operis)}</td>\n')
        parts.append('      </tr>\n')
      parts.append('    </tbody>\n')
      parts.append('  </table>\n')
    else:
      parts.append('  <p class="vol-note">No TOC entries found for this volume.</p>\n')

    parts.append('</section>\n\n')

  parts.append('</main>\n')
  parts.append('</article>\n')
  parts.append('<script src="assets/tree_scripts.js"></script>\n')
  parts.append('</body>\n')
  parts.append('</html>\n')

  out_path.write_text(''.join(parts), encoding='utf-8')
  print(f'Written: {out_path}')


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  parser.add_argument(
    '--out', type=Path, default=_DEFAULT_OUT,
    help='Output HTML path (default: SGML/index.html)',
  )
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)

  print('Loading TOC files…')
  volumes = load_all_tocs()
  print(f'  Total volumes in TOC: {len(volumes)}')

  pages = {p.stem for p in sorted(_PAGES_DIR.glob('*.html'))}
  print(f'  Pages found in {_PAGES_DIR.name}/: {len(pages)}')

  generate_index(volumes, pages, args.out)
  return 0


if __name__ == '__main__':
  sys.exit(main())
