#!/usr/bin/env python3
"""Generate a styled HTML page from a PL SGML volume or excerpt file.

Produces the same CSS class names and page structure as gen_tree_page.py so
that assets/tree_style.css and assets/tree_scripts.js work unchanged.

Usage
-----
  python3 SGML/SGML_tools/gen_sgml_page.py \\
    --sgml  SGML/Volumes/excerpts/vol002_0523A-0533_excerpt4.sgml \\
    --title "Tertullianus – excerpt 4" \\
    --out   SGML/Volumes/html/vol002_excerpt4.html

  python3 SGML/SGML_tools/gen_sgml_page.py \\
    --sgml SGML/Volumes/CD1_SGML_VOLUME_002.sgml \\
    --title "Tertullianus Vol. II" \\
    --out  SGML/Volumes/html/vol002.html

  # Standalone file (CSS/JS inlined, no external assets):
  python3 SGML/SGML_tools/gen_sgml_page.py \\
    --sgml  SGML/Volumes/excerpts/vol002_0019B-0020D_ornament_nested.sgml \\
    --title "Vol. II – ornament" \\
    --out   SGML/Volumes/html/ornament_nested.html \\
    --no-external-assets
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
import os
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
_HERE           = Path(__file__).resolve().parent      # SGML/SGML_tools/
_SGML_DIR       = _HERE.parent                        # SGML/
_REPO_ROOT      = _SGML_DIR.parent                   # webPatrologiaLatina/
_DEFAULT_ASSETS = _SGML_DIR / 'assets'            # SGML/assets/ (local working copy)
sys.path.insert(0, str(_HERE))                     # for sgml_tools
e = html.escape

# Transparent pass-through containers (emit nothing for the element itself)
_PASS_THROUGH = {'VOLUME', 'GROUP', 'BODY', 'FRONT', 'BACK'}

# Block containers: opening/closing HTML tags, children rendered as blocks
_BLOCK_OPEN = {
  'VOLFRONT':  '<section class="pl-section pl-volfront">',
  'VOLBODY':   '<section class="pl-section pl-volbody">',
  'VOLBACK':   '<section class="pl-section pl-volback">',
  'SER.TP':    '<section class="pl-frontmatter pl-ser-tp">',
  'VOL.TP':    '<section class="pl-frontmatter pl-vol-tp">',
  'CONTENTS':  '<section class="pl-contents">',
  'LIST':      '<ul class="pl-list">',
  'LIST.GL':   '<ul class="pl-list pl-list-gl">',
}
_BLOCK_CLOSE = {
  'VOLFRONT':  '</section>\n',
  'VOLBODY':   '</section>\n',
  'VOLBACK':   '</section>\n',
  'SER.TP':    '</section>\n',
  'VOL.TP':    '</section>\n',
  'CONTENTS':  '</section>\n',
  'LIST':      '</ul>\n',
  'LIST.GL':   '</ul>\n',
}

# Inline-block containers: children rendered as flowing inline HTML
_INLINE_BLOCK_OPEN = {
  'P':       '<p class="pl-paragraph">',
  'HEAD':    '<div class="pl-head">',
  'CAPTION': '<p class="pl-caption">',
  'ITEM':    '<li class="pl-item">',
  'IMPRINT': '<div class="pl-imprint">',
}
_INLINE_BLOCK_CLOSE = {
  'P':       '</p>\n',
  'HEAD':    '</div>\n',
  'CAPTION': '</p>\n',
  'ITEM':    '</li>\n',
  'IMPRINT': '</div>\n',
}

# Front-matter text tags: rendered as their own block element
_FRONT_TEXT: dict[str, tuple[str, str]] = {
  'SER.TI':  ('h2', 'pl-front-ser-ti'),
  'SER.PT':  ('p',  'pl-front-ser-pt'),
  'VOL.NO':  ('p',  'pl-front-vol-no'),
  'AUTHOR':  ('p',  'pl-front-author'),
  'DOC.TI':  ('p',  'pl-front-doc-ti'),
  'AUTH.NO': ('p',  'pl-front-auth-no'),
  'DATE':    ('p',  'pl-front-date'),
  'SOURCE':  ('p',  'pl-source'),
}


# ── renderer ──────────────────────────────────────────────────────────────────

class Renderer:
  def __init__(
    self,
    decoder,
    output_path: Path | None = None,
    asset_dir:   Path | None = None,
  ) -> None:
    self._decoder   = decoder
    self._out_path  = output_path
    self._asset_dir = asset_dir
    self._note_ctr  = 0
    self._fig_ctr   = 0

  # ── helpers ──────────────────────────────────────────────────────────────

  def _decode_greek(self, text: str) -> str:
    if self._decoder is None:
      return text
    return self._decoder.decode(text).text

  @staticmethod
  def _norm(text: str | None) -> str:
    """Collapse whitespace (incl. newlines) to single spaces."""
    if not text:
      return ''
    return re.sub(r'\s+', ' ', text)

  def _resolve_figure(self, image_id: str) -> str | None:
    base = self._asset_dir or _DEFAULT_ASSETS
    figures_dir = base / 'FIGURES'
    if not figures_dir.exists():
      figures_dir = _REPO_ROOT / 'assets' / 'FIGURES'
    for ext in ('bmp', 'png', 'jpg', 'gif'):
      candidate = figures_dir / f'{image_id}.{ext}'
      if candidate.exists():
        if self._out_path:
          return os.path.relpath(candidate, self._out_path.parent).replace('\\', '/')
        return str(candidate)
    return None

  def _note_strings(self, label: str, note_type: str) -> tuple[str, str]:
    chip_title = (note_type and label and f'{note_type} {label}') or note_type or (label and f'Note {label}') or 'Note'
    button_text = f'{NOTE_SYMBOL} {label}' if label else NOTE_SYMBOL
    return chip_title, button_text

  # ── inline element rendering ──────────────────────────────────────────────

  def _render_inline_el(self, el: ET.Element) -> str:
    """Render el in inline context → HTML fragment (no trailing newline)."""
    tag = el.tag

    if tag == 'HI':
      rend  = el.get('REND', '').upper()
      inner = self._render_inline_content(el)
      if 'BOLD' in rend:
        return f'<strong>{inner}</strong>'
      if 'SMALLCAPS' in rend:
        return f'<span class="pl-smallcaps">{inner}</span>'
      return f'<em>{inner}</em>'  # ITALIC or any other REND

    if tag == 'FOREIGN':
      lang     = el.get('LANG', '').upper()
      raw_text = ''.join(el.itertext())
      if lang == 'GREEK' and self._decoder:
        return f'<span class="greek">{e(self._decode_greek(raw_text))}</span>'
      cls = 'foreign greek' if lang == 'GREEK' else 'foreign'
      return f'<span class="{cls}">{e(raw_text)}</span>'

    if tag == 'SUP':
      return f'<sup>{e("".join(el.itertext()))}</sup>'

    if tag == 'LACUNA':
      return '<span class="pl-lacuna">[…]</span>'

    if tag == 'CITN':
      return f'<cite>{e(self._norm("".join(el.itertext())))}</cite>'

    if tag == 'ED':
      return f'<span class="ed">{e(self._norm("".join(el.itertext())))}</span>'

    if tag == 'COL':
      n = el.get('N', '')
      return f'<span class="col">[Col. {e(n)}]</span> ' if n else ''

    if tag == 'NOTE':
      return self._render_note(el)

    if tag == 'ORNAMENT':
      return self._render_ornament_inline(el)

    if tag == 'L':
      return self._render_line(el)

    # Block elements that can appear inside notes/inline contexts
    if tag == 'POEM':
      return self._render_poem(el)

    if tag == 'TBL':
      return self._render_table(el)

    if tag == 'P':
      inner = self._render_inline_content(el)
      return f'<p class="pl-paragraph">{inner}</p>\n'

    # Unknown inline tag: emit text content only
    return e(self._norm(''.join(el.itertext())))

  def _render_inline_content(self, el: ET.Element, for_note: bool = False) -> str:
    """Render mixed content of el as flowing inline HTML."""
    parts: list[str] = []
    if el.text:
      parts.append(e(self._norm(el.text)))
    for child in el:
      parts.append(self._render_inline_el(child))
      if child.tail:
        parts.append(e(self._norm(child.tail)))
    return ''.join(parts)

  # ── note rendering ────────────────────────────────────────────────────────

  def _render_note(self, el: ET.Element) -> str:
    """Collapsible chip + overlay template (same compact-mode structure as gen_tree_page.py)."""
    label     = el.get('N', '')
    note_type = el.get('TYPE', '')
    note_id   = f'note-{self._note_ctr}'
    self._note_ctr += 1

    note_html = self._render_inline_content(el)
    if not note_html.strip():
      return ''  # empty notes silently dropped (matches gen_tree_page.py Task 3.2)

    chip_title, button_text = self._note_strings(label, note_type)
    return (
      f'<span class="note-anchor" data-note-anchor data-note-source="{note_id}">'
      f'<button type="button" class="overlay-chip overlay-chip-note"'
      f' data-overlay-source="{note_id}"'
      f' data-overlay-title="{e(chip_title)}"'
      f' aria-haspopup="dialog"'
      f' aria-label="{e(chip_title)}">{e(button_text)}</button>'
      f'<template id="{note_id}" class="overlay-source overlay-source-note">'
      f'{note_html}</template>'
      f'<span class="note-inline-host"></span>'
      f'</span>'
    )

  # ── ornament rendering ────────────────────────────────────────────────────

  def _ornament_html(self, el: ET.Element) -> tuple[str, str, str, str, str]:
    """Return (fig_id, chip_title, chip_text, overlay_content, inline_content)."""
    image_id   = el.get('IMAGE', '')
    text_label = el.get('TEXT', '') or (f'[Fig. {image_id}]' if image_id else '[Fig.]')
    fig_id        = f'fig-{self._fig_ctr}'
    fig_id_inline = f'{fig_id}-inline'
    self._fig_ctr += 1

    fig_path   = self._resolve_figure(image_id) if image_id else None
    label_h    = e(text_label)
    chip_title = e(f'Figure {image_id} {text_label}') if image_id else label_h
    chip_text  = f'{FIGURE_SYMBOL} {text_label}'

    if fig_path:
      fp = e(fig_path)
      overlay_content = (
        f'<figure class="overlay-ornament-figure">'
        f'<img class="overlay-ornament-display" src="{fp}" alt="{label_h}">'
        f'<figcaption class="overlay-ornament-caption">{label_h}</figcaption>'
        f'</figure>'
      )
      inline_content = (
        f'<span class="ornament" data-image="{e(image_id)}">'
        f'<img class="ornament-image" src="{fp}" alt="{label_h}" title="{e(image_id)}">'
        f'<span class="ornament-label">{label_h}</span>'
        f'</span>'
      )
    else:
      overlay_content = f'<p class="overlay-missing-ornament">[Figure not found: {e(image_id)}]</p>'
      inline_content  = f'<span class="ornament missing">{label_h}</span>'

    chip = (
      f'<button type="button" class="overlay-chip overlay-chip-ornament"'
      f' data-overlay-source="{fig_id}"'
      f' data-overlay-title="{chip_title}"'
      f' aria-haspopup="dialog"'
      f' aria-label="{chip_title}">{e(chip_text)}</button>'
      f'<template id="{fig_id}" class="overlay-source overlay-source-ornament">'
      f'{overlay_content}</template>'
      f'<template id="{fig_id_inline}" class="overlay-source overlay-source-ornament-inline">'
      f'{inline_content}</template>'
      f'<span class="ornament-inline-host"></span>'
    )
    anchor = (
      f'<span class="ornament-anchor" data-ornament-anchor'
      f' data-ornament-inline-source="{fig_id_inline}">'
      f'{chip}</span>'
    )
    return fig_id, chip_title, chip_text, overlay_content, anchor

  def _render_ornament_inline(self, el: ET.Element) -> str:
    _, _, _, _, anchor = self._ornament_html(el)
    return anchor

  def _render_ornament_block(self, el: ET.Element) -> str:
    _, _, _, _, anchor = self._ornament_html(el)
    return f'<div class="column-block">{anchor}</div>\n'

  # ── poem / verse rendering ────────────────────────────────────────────────

  def _render_line(self, el: ET.Element) -> str:
    """Single <L> verse line → inline span (block layout via CSS on pl-poem)."""
    try:
      em = int(el.get('INDENT', '0')) / 10
    except ValueError:
      em = 0
    style = f' style="margin-left:{em:.1f}em"' if em else ''
    inner = self._render_inline_content(el)
    return f'<div class="pl-line"{style}>{inner}</div>\n'

  def _render_poem(self, el: ET.Element) -> str:
    parts = ['<div class="pl-poem">\n']
    if el.text:
      parts.append(e(self._norm(el.text)))
    for child in el:
      if child.tag == 'L':
        parts.append(self._render_line(child))
      elif child.tag == 'COL':
        n = child.get('N', '')
        if n:
          parts.append(f'<div class="column-block"><span class="col">[Col. {e(n)}]</span></div>\n')
      elif child.tag == 'NOTE':
        parts.append(self._render_note(child))
      else:
        parts.append(self._render_inline_el(child))
      if child.tail:
        parts.append(e(self._norm(child.tail)))
    parts.append('</div>\n')
    return ''.join(parts)

  # ── table rendering ───────────────────────────────────────────────────────

  def _render_table(self, el: ET.Element) -> str:
    num_cols = max(1, int(el.get('COL', '1')))
    parts = ['<table class="ebt-table">\n<tbody>\n']
    for child in el:
      if child.tag == 'HEAD':
        title = self._render_inline_content(child)
        parts.append(
          f'<tr><td colspan="{num_cols}" class="ebt-table-span">'
          f'{title}</td></tr>\n'
        )
      elif child.tag == 'HR':
        cells = [
          f'<td class="ebt-table-cell ebt-align-{h.get("ALIGN","LEFT").lower()}">'
          f'{self._render_inline_content(h)}</td>'
          for h in child if h.tag == 'H'
        ]
        if cells:
          parts.append(f'<tr>\n{"".join(cells)}</tr>\n')
      elif child.tag == 'R':
        cells = [
          f'<td class="ebt-table-cell ebt-align-{c.get("ALIGN","LEFT").lower()}">'
          f'{self._render_inline_content(c)}</td>'
          for c in child if c.tag == 'C'
        ]
        if cells:
          parts.append(f'<tr>\n{"".join(cells)}</tr>\n')
    parts.append('</tbody>\n</table>\n')
    return ''.join(parts)

  # ── section rendering ─────────────────────────────────────────────────────

  def _render_doc(self, el: ET.Element) -> str:
    parts = ['<section class="pl-doc">\n']
    name   = el.get('NAME', '')
    author = el.get('AUTHOR', '')
    if name:
      parts.append(f'<h2 class="doc-title">{e(name)}</h2>\n')
    if author:
      parts.append(f'<p class="doc-author">{e(author)}</p>\n')
    parts.append(self._render_block_children(el))
    parts.append('</section>\n')
    return ''.join(parts)

  def _render_div(self, el: ET.Element) -> str:
    tag  = el.tag
    css  = {'DIV1': 'pl-div1', 'DIV2': 'pl-div2', 'DIV3': 'pl-div3'}.get(tag, 'pl-div')
    name = el.get('NAME', '')
    auth = el.get('AUTHOR', '')
    parts = [f'<section class="{css}">\n']
    if name:
      parts.append('<div class="section-meta">\n')
      parts.append(f'  <h3 class="section-meta-title">{e(name)}</h3>\n')
      if auth:
        parts.append(f'  <p class="section-meta-author">{e(auth)}</p>\n')
      parts.append('</div>\n')
    parts.append(self._render_block_children(el))
    parts.append('</section>\n')
    return ''.join(parts)

  # ── block dispatcher ──────────────────────────────────────────────────────

  def _render_block_children(self, el: ET.Element) -> str:
    """Render el's children in block context."""
    parts: list[str] = []
    if el.text:
      t = self._norm(el.text)
      if t:
        parts.append(f'<p class="pl-misc">{e(t)}</p>\n')
    for child in el:
      parts.append(self._render_element(child))
      if child.tail:
        t = self._norm(child.tail)
        if t:
          parts.append(f'<p class="pl-misc">{e(t)}</p>\n')
    return ''.join(parts)

  def _render_element(self, el: ET.Element) -> str:
    """Main dispatch: render el as a block-level unit."""
    tag = el.tag

    if tag in _PASS_THROUGH:
      return self._render_block_children(el)

    if tag == 'DOC':
      return self._render_doc(el)

    if tag in ('DIV1', 'DIV2', 'DIV3'):
      return self._render_div(el)

    if tag in _FRONT_TEXT:
      htag, cls = _FRONT_TEXT[tag]
      inner = self._render_inline_content(el)
      return f'<{htag} class="{cls}">{inner}</{htag}>\n'

    if tag == 'POEM':
      return self._render_poem(el)

    if tag == 'TBL':
      return self._render_table(el)

    if tag == 'NOTE':
      note_html = self._render_note(el)
      return f'<p class="pl-paragraph">{note_html}</p>\n' if note_html else ''

    if tag == 'ORNAMENT':
      return self._render_ornament_block(el)

    if tag == 'COL':
      n = el.get('N', '')
      return f'<div class="column-block"><span class="col">[Col. {e(n)}]</span></div>\n' if n else ''

    # Inline-block (mixed text + inline children)
    if tag in _INLINE_BLOCK_OPEN:
      inner = self._render_inline_content(el)
      return f'{_INLINE_BLOCK_OPEN[tag]}{inner}{_INLINE_BLOCK_CLOSE[tag]}'

    # Block containers (block children)
    if tag in _BLOCK_OPEN:
      body = self._render_block_children(el)
      return f'{_BLOCK_OPEN[tag]}\n{body}{_BLOCK_CLOSE[tag]}'

    # Fallback: render as generic block with children
    return self._render_block_children(el)

  def render(self, root: ET.Element) -> str:
    return self._render_element(root)


# ── asset loading ──────────────────────────────────────────────────────────────

def _asset_path(name: str, output_path: Path | None) -> str | None:
  asset = _DEFAULT_ASSETS / name
  if not asset.exists():
    asset = _REPO_ROOT / 'assets' / name
  if not asset.exists():
    return None
  if output_path:
    return os.path.relpath(asset, output_path.parent).replace('\\', '/')
  return str(asset)


def _load_text(name: str) -> str:
  for base in (_DEFAULT_ASSETS, _REPO_ROOT / 'assets'):
    asset = base / name
    if asset.exists():
      return asset.read_text(encoding='utf-8')
  return ''


def _rewrite_css_urls(css: str, output_path: Path) -> str:
  """Rewrite url(…) paths in CSS so they point from output_path's directory."""
  assets_dir = _DEFAULT_ASSETS if _DEFAULT_ASSETS.exists() else _REPO_ROOT / 'assets'

  def rewrite(m: re.Match) -> str:
    raw = m.group(1).strip('\'"')
    if raw.startswith(('http', 'data:')):
      return m.group(0)
    candidate = assets_dir / raw
    if candidate.exists():
      rel = os.path.relpath(candidate, output_path.parent).replace('\\', '/')
      return f'url("{rel}")'
    return m.group(0)

  return re.sub(r'url\(([^)]+)\)', rewrite, css)


# ── page template ─────────────────────────────────────────────────────────────

_PAGE_TOOLS = (
  '<div class="page-tools">\n'
  '  <label class="tool-toggle" data-tool-group="toc" '
  'title="Show or hide the table of contents.">'
  f'<input type="checkbox" data-toc-toggle checked> {TOC_SYMBOL}</label>\n'
  '  <div class="tool-cluster tool-cluster-notes">\n'
  '    <label class="tool-toggle" data-tool-group="notes" '
  'title="Expand inline note text for searching and browsing.">'
  f'<input type="checkbox" data-note-toggle> {NOTE_SYMBOL}</label>\n'
  '  </div>\n'
  '  <label class="tool-toggle" data-tool-group="figures" '
  'title="Expand inline figures for easier comparison while keeping popup access.">'
  f'<input type="checkbox" data-ornament-toggle> {FIGURE_SYMBOL}</label>\n'
  '  <div class="tool-cluster tool-cluster-font">\n'
  '    <label class="tool-select-wrap" '
  'title="Switch the main non-Greek reading font.">\n'
  f'      <span class="tool-select-text">{FONT_SYMBOL}</span>\n'
  '      <select class="tool-select" data-font-select '
  'aria-label="Select reading font">\n'
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
  '  <button type="button" class="tool-theme-btn" data-scroll-top '
  'title="Scroll to top" aria-label="Scroll to top">↑</button>\n'
  '  <button type="button" class="tool-theme-btn" data-theme-toggle '
  'title="Switch between light and dark theme" aria-label="Toggle dark theme">'
  '☀</button>\n'
  '</div>\n'
)

_OVERLAY = (
  '<div class="overlay-root" data-overlay-root hidden>\n'
  '  <div class="overlay-backdrop" data-overlay-close></div>\n'
  '  <div class="overlay-panel" role="dialog" aria-modal="true">\n'
  '    <button class="overlay-close" type="button" data-overlay-close>Close</button>\n'
  '    <div class="overlay-panel-content"></div>\n'
  '  </div>\n'
  '</div>\n'
)


def wrap_html(
    body:          str,
    title:         str,
    output_path:   Path | None = None,
    external_assets: bool = True,
  ) -> str:
  if external_assets and output_path:
    css_href = _asset_path('tree_style.css', output_path)
    js_href  = _asset_path('tree_scripts.js', output_path)
    css_block = f'  <link rel="stylesheet" href="{e(css_href)}">\n' if css_href else ''
    js_block  = f'<script src="{e(js_href)}" defer></script>\n'   if js_href  else ''
  else:
    css_text  = _load_text('tree_style.css')
    if output_path:
      css_text = _rewrite_css_urls(css_text, output_path)
    css_block = f'  <style>\n{css_text}\n  </style>\n'
    js_block  = f'<script>\n{_load_text("tree_scripts.js")}\n</script>\n'

  return (
    '<!DOCTYPE html>\n'
    '<html lang="la">\n'
    '<head>\n'
    '  <meta charset="utf-8">\n'
    f'  <title>{e(title)}</title>\n'
    f'{css_block}'
    '<link rel="stylesheet" href="../assets/whitakers-widget.css">\n'
    '<script src="../assets/whitakers-widget.js" defer></script>\n'
    '</head>\n'
    '<body>\n'
    '<script>!function(){try{var b=document.body,ls=localStorage,'
    "t=ls.getItem('pl-tree-theme'),f=ls.getItem('pl-tree-text-font'),"
    "s=parseInt(ls.getItem('pl-tree-font-size'),10),"
    "w=parseInt(ls.getItem('pl-tree-width'),10);"
    "if(t==='dark')b.setAttribute('data-theme','dark');"
    "if(f==='centaur')b.setAttribute('data-text-font','centaur');"
    "document.documentElement.style.fontSize=(isNaN(s)?150:s)+'%';"
    "if(!isNaN(w)&&w!==72)b.style.setProperty('--content-width',w*16+'px');"
    '}catch(e){}}();</script>\n'
    '<nav id="ebt-toc" class="toc-nav" aria-label="Table of contents" hidden></nav>\n'
    '<article class="pl-page">\n'
    f'<header><h1 class="tree-title">{e(title)}</h1></header>\n'
    f'{_PAGE_TOOLS}'
    '<main class="pl-tree">\n'
    f'{body}'
    '</main>\n'
    '</article>\n'
    f'{_OVERLAY}'
    f'{js_block}'
    '</body>\n'
    '</html>\n'
  )
#$ wrap_html

# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  parser.add_argument('--sgml',  required=True, type=Path, help='Source .sgml file.')
  parser.add_argument('--title', default='Patrologia Latina')
  parser.add_argument('--out',   required=True, type=Path, help='Output .html file.')
  parser.add_argument(
    '--no-external-assets', dest='external_assets',
    action='store_false', default=True,
    help='Inline CSS and JS instead of linking to asset files.',
  )
  parser.add_argument('--asset-dir', type=Path, default=None)
  return parser


def main(argv: list[str] | None = None) -> int:
  from greek_parser import default_greek_decoder
  from sgml_tools import sanitize_sgml

  parser = build_parser()
  args = parser.parse_args(argv)

  text = args.sgml.read_text(encoding='cp1252')
  root = ET.fromstring(sanitize_sgml(text))

  decoder = default_greek_decoder()

  out_path = args.out.resolve()
  out_path.parent.mkdir(parents=True, exist_ok=True)

  renderer = Renderer(
    decoder     = decoder,
    output_path = out_path,
    asset_dir   = args.asset_dir,
  )
  body   = renderer.render(root)
  result = wrap_html(body, args.title, output_path=out_path, external_assets=args.external_assets)
  out_path.write_text(result, encoding='utf-8')
  print(out_path)
  return 0


if __name__ == '__main__':
  sys.exit(main())
