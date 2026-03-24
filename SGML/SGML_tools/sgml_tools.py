from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

_XML_BUILTIN_ENTITIES = {'amp', 'lt', 'gt', 'quot', 'apos'}
def sanitize_sgml(
    text: str
  ) -> str:
  """
    Handles:
    - Unquoted attribute values (e.g. TYPE=edit → TYPE="edit")
    - Invalid XML entity references (e.g. &*sub; → &amp;*sub;)
    - DOCTYPE declarations (stripped via _replace_declared_entities)
  """
  # Quote unquoted attribute values: ATTR=word → ATTR="word"
  # Only operate inside tag declarations (<...>) to avoid corrupting text content
  # that happens to contain '=' (e.g. "Virtus=vis." inside a NOTE body).
  def _fix_tag_attrs(m: re.Match) -> str:
    return re.sub(r'(=)([^"\'\s>][^\s>]*)', r'\1"\2"', m.group(0))
  text = re.sub(r'<[^>]*>', _fix_tag_attrs, text)

  # Escape entity refs whose names are not valid XML NCNames (e.g. &*sub;, &2star;)
  def _escape_invalid_entity(m: re.Match) -> str:
    name = m.group(1)
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9._-]*$', name):
      return m.group(0)  # valid XML entity name — leave as-is
    return f"&amp;{name};"  # escape the & so it becomes literal text
  text = re.sub(r'&([^;]+);', _escape_invalid_entity, text)
  def _replace_declared_entities(text: str) -> str:
    subset = re.search(r"<!DOCTYPE\b.*?\[(?P<subset>[\s\S]*?)\]\s*>", text, flags=re.IGNORECASE)
    entity_text = subset.group("subset") if subset else ""
    entities = {}
    for name, double_quoted, single_quoted in re.findall(
        r'<!ENTITY\s+([A-Za-z_:][\w:.-]*)\s+(?:"([^"]*)"|\'([^\']*)\')\s*>',
        entity_text,
        flags=re.IGNORECASE):
      entities[name] = double_quoted or single_quoted

    start = re.search(r"<!DOCTYPE\b", text, flags=re.IGNORECASE)
    if start:
      quote = None
      depth = 0
      end = start.end()
      while end < len(text):
        char = text[end]
        if quote:
          if char == quote:
            quote = None
        else:
          if char in {"'", '"'}:
            quote = char
          elif char == "[":
            depth += 1
          elif char == "]" and depth:
            depth -= 1
          elif char == ">" and depth == 0:
            end += 1
            break
        end += 1
      stripped = text[:start.start()] + text[end:]
    else:
      stripped = text
    for name, value in entities.items():
      stripped = stripped.replace(f"&{name};", value)

    # Escape any remaining valid-name entity references that are not XML builtins
    # (e.g. &short; used in prosody volumes but never declared in the DOCTYPE).
    safe = _XML_BUILTIN_ENTITIES | set(entities)
    stripped = re.sub(
      r'&([A-Za-z_][A-Za-z0-9._-]*);',
      lambda m: m.group(0) if m.group(1) in safe else f'&amp;{m.group(1)};',
      stripped,
    )
    return stripped
  return _replace_declared_entities(text)
#$ sanitize_sgml

def convert_sgml_to_html(
    source: str | Path,
    output_path: str | Path | None = None,
    structure: bool = False,
  ) -> Path:
  """
    Convert an SGML file into HTML and return the written path.
  """

  source = Path(source)
  root = ET.fromstring(sanitize_sgml(source.read_text(encoding="cp1252")))
  title = (root.findtext("./front-matter/title") or root.findtext("./title") or source.stem).strip()

  if structure:
    html_text = _render_structure_document(root, title, source.name)
  else:
    html_root = ET.Element("html")
    head = ET.SubElement(html_root, "head")
    ET.SubElement(head, "meta", charset="utf-8")
    ET.SubElement(head, "title").text = title
    body = ET.SubElement(html_root, "body")
    body.append(_convert_element(root))
    ET.indent(html_root, space="  ")
    html_text = "<!DOCTYPE html>\n" + ET.tostring(html_root, encoding="unicode", method="html")

  if structure:
    output_path = Path(output_path or source.with_name(f"{source.stem}_structure.html"))
  else:
    output_path = Path(output_path or source.with_suffix(".html"))
  output_path.parent.mkdir(parents=True, exist_ok=True)
  output_path.write_text(html_text, encoding="utf-8")
  return output_path




def _convert_element(node: ET.Element, parent_tag: str | None = None) -> ET.Element:
  tag = node.tag
  html_tag = _html_tag_for(tag, parent_tag)
  element = ET.Element(html_tag)
  element.set("data-sgml-tag", tag)
  _copy_attributes(node, element)

  current = element.get("class")
  if tag == "subtitle":
    element.set("class", "subtitle" if not current else f"{current} subtitle")
  elif tag == "table":
    element.set("class", "table-block" if not current else f"{current} table-block")
  elif tag == "note" and node.get("type"):
    element.set("class", f"note-{node.get('type')}" if not current else f"{current} note-{node.get('type')}")

  if tag == "email":
    value = (node.text or "").strip()
    element.set("href", f"mailto:{value}")
    element.text = value
    return element

  if tag == "xref":
    linkend = node.get("linkend", "")
    if linkend:
      element.set("href", f"#{linkend}")
    element.text = linkend or (node.text or "")
    return element

  if tag == "graphic":
    if node.get("fileref"):
      element.set("src", node.get("fileref", "missing fileref"))
      element.set("alt", Path(node.get("fileref", "missing fileref")).name)
    if node.get("format"):
      element.set("data-format", node.get("format", "missing format"))
    return element

  if tag == "entityref":
    element.text = f"&{node.get('name', '')};"
    return element

  if tag == "codeblock":
    element.text = node.text or ""
    return element

  if node.text:
    element.text = node.text

  for child in node:
    child_parent = parent_tag if tag == "row" else tag
    converted = _convert_element(child, child_parent)
    element.append(converted)
    if child.tail:
      converted.tail = child.tail
  return element


def _html_tag_for(tag: str, parent_tag: str | None) -> str:
  if tag == "technical-manual":
    return "article"
  if tag == "front-matter":
    return "header"
  if tag == "body":
    return "main"
  if tag in {"chapter", "section", "subsection", "appendix"}:
    return "section"
  if tag == "title":
    return {
      "front-matter": "h1",
      "chapter":      "h2",
      "appendix":     "h2",
      "section":      "h3",
      "subsection":   "h4",
      "note":         "h5",
      "figure":       "h3",
      "table":        "h3",
    }.get(parent_tag, "h2") if parent_tag is not None else "title"
  if tag == "subtitle":
    return "p"
  if tag == "author-group":
    return "section"
  if tag == "author":
    return "address"
  if tag in {"abstract", "publication-data", "revision-history"}:
    return "section"
  if tag == "revision":
    return "article"
  if tag == "name":
    return "strong"
  if tag == "email":
    return "a"
  if tag in {"publisher", "pubdate", "edition", "affiliation", "revnumber", "revdate", "revremark"}:
    return "p"
  if tag == "para":
    return "p"
  if tag == "emph":
    return "em"
  if tag == "xref":
    return "a"
  if tag == "codeblock":
    return "pre"
  if tag == "code":
    return "code"
  if tag == "entityref":
    return "span"
  if tag == "itemizedlist":
    return "ul"
  if tag == "orderedlist":
    return "ol"
  if tag == "listitem":
    return "li"
  if tag == "note":
    return "aside"
  if tag == "figure":
    return "figure"
  if tag == "graphic":
    return "img"
  if tag == "caption":
    return "figcaption"
  if tag == "table":
    return "section"
  if tag == "tgroup":
    return "table"
  if tag == "thead":
    return "thead"
  if tag == "tbody":
    return "tbody"
  if tag == "row":
    return "tr"
  if tag == "entry":
    return "th" if parent_tag == "thead" else "td"
  return "div"


def _copy_attributes(source: ET.Element, target: ET.Element) -> None:
  for name, value in source.attrib.items():
    if name == "id":
      target.set("id", value)
    elif name not in {"fileref", "format", "linkend", "name"}:
      target.set(f"data-{name.replace('_', '-')}", value)




def _render_structure_document(root: ET.Element, title: str, source_name: str) -> str:
  return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)} · Structure View</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #11151a;
        --bg-soft: #161b21;
        --panel: rgba(23, 28, 34, 0.94);
        --panel-edge: rgba(164, 176, 189, 0.1);
        --muted: #89939d;
        --attrs: #b39d8b;
        --line-a: rgba(167, 131, 105, 1);
        --line-a-soft: rgba(167, 131, 105, 0.05);
        --line-a-strong: rgba(167, 131, 105, 1);
        --line-b: rgba(118, 144, 131, 1);
        --line-b-soft: rgba(118, 144, 131, 0.05);
        --line-b-strong: rgba(118, 144, 131, 1);
        --line-c: rgba(115, 137, 165, 1);
        --line-c-soft: rgba(115, 137, 165, 0.05);
        --line-c-strong: rgba(115, 137, 165, 1);
        --line-d: rgba(135, 122, 153, 1);
        --line-d-soft: rgba(135, 122, 153, 0.05);
        --line-d-strong: rgba(135, 122, 153, 1);
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        font-family: "IBM Plex Mono", "SFMono-Regular", Menlo, Consolas, monospace;
        font-size: 12px;
        color: var(--muted);
        background:
          radial-gradient(circle at top left, rgba(92, 116, 145, 0.1), transparent 28rem),
          radial-gradient(circle at top right, rgba(115, 104, 132, 0.08), transparent 30rem),
          linear-gradient(180deg, var(--bg-soft), var(--bg));
      }}

      .page {{
        padding: 12px clamp(10px, 1.6vw, 18px) 18px;
      }}

      .summary {{
        margin: 0 0 8px;
        line-height: 1.3;
      }}

      .tree {{
        padding: 10px 12px;
        border: 1px solid var(--panel-edge);
        border-radius: 14px;
        background: var(--panel);
        box-shadow: 0 16px 36px rgba(0, 0, 0, 0.24);
        backdrop-filter: blur(10px);
      }}

      .node {{ padding: 1px 0; }}

      .row {{
        display: inline-flex;
        flex-wrap: wrap;
        max-width: 100%;
        gap: 6px;
        align-items: baseline;
        padding: 1px 7px 2px;
        line-height: 1.2;
        border: 1px solid var(--node-color);
        border-radius: 8px;
        background: var(--node-bg);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
      }}

      .tag {{
        font-weight: 700;
      }}

      .attrs {{
        color: var(--attrs);
      }}

      .children {{
        margin-left: 6px;
        padding-left: 10px;
        border-left: 2px solid var(--line);
      }}

      @media (max-width: 720px) {{
        .page {{
          padding: 10px 8px 14px;
        }}

        .tree {{
          padding: 8px 8px;
          border-radius: 12px;
        }}

        .row {{
          padding: 1px 6px 2px;
          border-radius: 7px;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <p class="summary">{escape(source_name)}</p>
      <section class="tree" aria-label="SGML structure">
        {_render_structure_node(root)}
      </section>
    </main>
  </body>
</html>
"""


def _render_structure_node(node: ET.Element, depth: int = 0) -> str:
  color, background, color_strong = (
    ("var(--line-a)", "var(--line-a-soft)", "var(--line-a-strong)"),
    ("var(--line-b)", "var(--line-b-soft)", "var(--line-b-strong)"),
    ("var(--line-c)", "var(--line-c-soft)", "var(--line-c-strong)"),
    ("var(--line-d)", "var(--line-d-soft)", "var(--line-d-strong)"),
  )[depth % 4]

  attrs = " ".join(f'{name}="{value}"' for name, value in node.attrib.items())
  preview = _node_preview(node)
  row = [f'<div class="row"><span class="tag" style="color:{color_strong};">&lt;{escape(node.tag)}&gt;</span>']
  if attrs:
    row.append(f'<span class="attrs">{escape(attrs)}</span>')
  if preview:
    row.append(f"<span>{escape(preview)}</span>")
  row.append("</div>")
  row_html = "".join(row)
  node_open = f'<div class="node" style="--line: {color}; --node-color: {color}; --node-bg: {background};">'
  children = "".join(_render_structure_node(child, depth + 1) for child in node)
  if not children:
    return f"{node_open}{row_html}</div>"
  return f"{node_open}{row_html}<div class=\"children\">{children}</div></div>"


def _node_preview(node: ET.Element) -> str:
  parts: list[str] = []
  if node.text and node.text.strip():
    parts.append(node.text.strip())
  for child in node:
    if child.tail and child.tail.strip():
      parts.append(child.tail.strip())

  if not parts:
    return ""

  text = re.sub(r"\s+", " ", " ".join(parts))
  if len(text) > 88:
    text = f"{text[:85]}..."
  return f'"{text}"'
