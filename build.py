#!/usr/bin/env python3
"""
claudeCode Tutorial — Static Site Generator
============================================
Run this from the ROOT of your claudeCodeTutorial repo clone:

    python3 build.py

It reads all .md files, converts them to HTML with Mermaid support,
and writes a ready-to-deploy GitHub Pages site into ./docs/
"""

import os, re, shutil, sys, json
from pathlib import Path
from datetime import datetime
import subprocess

# ── Config ────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).parent          # where build.py lives == repo root
DOCS_OUT    = REPO_ROOT / "docs"             # GitHub Pages output folder
ASSETS_SRC  = REPO_ROOT / "_site_assets"    # our CSS, etc.
GITHUB_URL  = "https://github.com/adityasoni99/claudeCodeTutorial"

# All top-level chapters in order
CHAPTERS = [
    ("01_state_management.md",           "State Management",             "core"),
    ("02_ink_ui_framework.md",           "Ink UI Framework",             "core"),
    ("03_query_engine.md",               "Query Engine",                 "core"),
    ("04_fileedittool.md",               "FileEditTool",                 "tools"),
    ("05_git_integration.md",            "Git Integration",              "tools"),
    ("06_bashtool.md",                   "BashTool",                     "tools"),
    ("07_shell_safety_checks.md",        "Shell Safety Checks",          "security"),
    ("08_permission___security_system.md","Permission & Security System","security"),
    ("09_rule_matching.md",              "Rule Matching",                "security"),
    ("10_auto_mode_classifier.md",       "Auto-Mode Classifier",         "security"),
    ("11_notebookedittool.md",           "NotebookEditTool",             "tools"),
    ("12_websearchtool.md",              "WebSearchTool",                "tools"),
    ("13_feature_gating.md",             "Feature Gating",               "core"),
    ("14_model_context_protocol__mcp_.md","Model Context Protocol (MCP)","advanced"),
    ("15_agenttool.md",                  "AgentTool",                    "agents"),
    ("16_teammates.md",                  "Teammates",                    "agents"),
    ("17_unique_features.md",            "Unique Features",              "advanced"),
    ("18_computer_use.md",               "Computer Use",                 "advanced"),
    ("19_cost_tracking.md",              "Cost Tracking",                "core"),
]

CHAPTER_SET = {name for name, _, _ in CHAPTERS}

# All subsystem folders (name, display title, description, icon)
SUBSYSTEMS = [
    ("state",       "State",       "Core state definition, selectors, teammate view, React integration, and sync",  "🗂"),
    ("tools",       "Tools",       "Every tool implementation: Agent, Bash, FileEdit, WebSearch and 30+ more",       "🔧"),
    ("query",       "Query",       "Query engine internals: recursive agent runtime, task coordination, planning",   "⚙️"),
    ("components",  "Components",  "All UI components built on the Ink framework for terminal rendering",            "🖥"),
    ("services",    "Services",    "Background services: cost tracking, git, LSP, and more",                         "⚡"),
    ("hooks",       "Hooks",       "React hooks for state subscription and side-effects",                            "🪝"),
    ("schemas",     "Schemas",     "Zod schemas for all tool inputs and outputs",                                    "📐"),
    ("context",     "Context",     "Conversation context construction and trimming",                                 "💬"),
    ("coordinator", "Coordinator", "High-level agent coordination layer",                                            "🎯"),
    ("skills",      "Skills",      "Reusable skill definitions for the SkillTool",                                  "🎓"),
    ("plugins",     "Plugins",     "Plugin system for extending core behaviour",                                     "🔌"),
    ("assistant",   "Assistant",   "High-level assistant abstraction facing the user",                              "🤖"),
    ("bridge",      "Bridge",      "Remote bridge for external connections",                                         "🌉"),
    ("buddy",       "Buddy",       "Buddy system — paired agent assistance",                                         "👥"),
    ("cli",         "CLI",         "Command-line interface entry points and flag handling",                          "💻"),
    ("commands",    "Commands",    "Slash command definitions and routing",                                          "⌨️"),
    ("coordinator", "Coordinator", "High-level agent coordination layer",                                            "🎯"),
    ("ink",         "Ink",         "Ink framework extensions and custom components",                                 "🖊"),
    ("memdir",      "MemDir",      "Memory directory — persistent agent memory",                                     "🧠"),
    ("server",      "Server",      "Server mode and remote API surface",                                             "🖧"),
    ("tasks",       "Tasks",       "Task queue and scheduling internals",                                            "📋"),
    ("types",       "Types",       "TypeScript type definitions across the codebase",                               "📝"),
    ("utils",       "Utils",       "Shared utility functions and helpers",                                           "🛠"),
    ("voice",       "Voice",       "Voice input integration and speech processing",                                  "🎤"),
    ("vim",         "Vim",         "Vim keybinding integration layer",                                               "⌨️"),
]
# De-duplicate by folder name
seen = set()
SUBSYSTEMS = [s for s in SUBSYSTEMS if s[0] not in seen and not seen.add(s[0])]


# ── Markdown → HTML ───────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = re.sub(r'[^\w\s-]', '', text.lower())
    return re.sub(r'[\s_-]+', '-', text).strip('-')

def rewrite_md_link(href: str, page_kind: str, subsystem_folder: str = '') -> str:
  """Rewrite markdown links to generated HTML routes."""
  if not href:
    return href

  if re.match(r'^(?:https?:|mailto:|tel:|javascript:|#)', href):
    return href

  path, sep, anchor = href.partition('#')
  norm = path.strip()
  target = norm

  if norm.endswith('.md'):
    base = Path(norm).name
    stem = Path(base).stem

    if base in CHAPTER_SET:
      target = f"chapters/{chapter_slug(base)}.html"
    elif base == 'index.md':
      if page_kind == 'subsystems' and subsystem_folder:
        target = f"subsystems/{subsystem_folder}.html"
      else:
        target = 'index.html'
    elif page_kind == 'subsystems' and subsystem_folder and (REPO_ROOT / subsystem_folder / base).exists():
      target = f"subsystems/{subsystem_folder}-{stem.replace('_', '-')}.html"
    else:
      target = norm[:-3] + '.html'

  if page_kind == 'chapters':
    if target.startswith('chapters/'):
      target = target[len('chapters/'):]
    elif target.startswith('subsystems/') or target == 'index.html':
      target = '../' + target
  elif page_kind == 'subsystems':
    if target.startswith('subsystems/'):
      target = target[len('subsystems/'):]
    elif target.startswith('chapters/') or target == 'index.html':
      target = '../' + target

  return f"{target}{sep}{anchor}" if sep else target

def md_to_html(md: str, link_transform=None) -> tuple[str, list[tuple[str,str]]]:
    """
    Convert markdown to HTML, handling Mermaid fences specially.
    Returns (html, toc_entries) where toc_entries = [(level, text, anchor), ...]
    """
    toc: list[tuple[str,str]] = []

    # 1. Extract & protect mermaid blocks
    mermaid_blocks: list[str] = []
    def protect_mermaid(m):
        code = m.group(1).strip()
        idx = len(mermaid_blocks)
        mermaid_blocks.append(code)
        return f"%%MERMAID_{idx}%%"

    md = re.sub(r'```mermaid\n(.*?)```', protect_mermaid, md, flags=re.DOTALL)

    # 2. Extract & protect generic fenced code blocks
    code_blocks: list[tuple[str,str]] = []
    def protect_code(m):
        lang = m.group(1) or ''
        code = m.group(2)
        idx = len(code_blocks)
        code_blocks.append((lang, code))
        return f"%%CODE_{idx}%%"

    md = re.sub(r'```(\w*)\n(.*?)```', protect_code, md, flags=re.DOTALL)

    # 3. Protect inline code
    inline_codes: list[str] = []
    def protect_inline(m):
        idx = len(inline_codes)
        inline_codes.append(m.group(1))
        return f"%%INLINE_{idx}%%"

    md = re.sub(r'`([^`]+)`', protect_inline, md)

    # 4. Line-by-line HTML conversion
    lines = md.split('\n')
    html_parts: list[str] = []
    in_ul = in_ol = in_table = in_p = False

    def flush_list():
        nonlocal in_ul, in_ol
        if in_ul:  html_parts.append('</ul>'); in_ul = False
        if in_ol:  html_parts.append('</ol>'); in_ol = False

    def flush_table():
        nonlocal in_table
        if in_table: html_parts.append('</tbody></table>'); in_table = False

    def flush_p():
        nonlocal in_p
        if in_p: html_parts.append('</p>'); in_p = False

    def restore_inline_tokens(text: str) -> str:
      def repl(m):
        idx = int(m.group(1))
        return inline_codes[idx] if 0 <= idx < len(inline_codes) else m.group(0)
      return re.sub(r'%%INLINE_(\d+)%%', repl, text)

    def fmt_emphasis(text: str) -> str:
      text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
      text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
      text = re.sub(r'(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)', r'<em>\1</em>', text)
      text = re.sub(r'(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)', r'<em>\1</em>', text)
      return text

    def inline_fmt(text: str) -> str:
      links: list[str] = []

      def protect_link(m):
        label = m.group(1)
        href = m.group(2).strip()
        href = link_transform(href) if link_transform else href
        idx = len(links)
        links.append(f'<a href="{href}">{fmt_emphasis(label)}</a>')
        return f"%%LINK_{idx}%%"

      text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', protect_link, text)
      text = fmt_emphasis(text)

      for idx, link_html in enumerate(links):
        text = text.replace(f"%%LINK_{idx}%%", link_html)
      return text

    i = 0
    while i < len(lines):
        line = lines[i]

        # Headings
        m = re.match(r'^(#{1,6})\s+(.+)', line)
        if m:
            flush_list(); flush_table(); flush_p()
            level = len(m.group(1))
            text  = inline_fmt(m.group(2).strip())
            plain = re.sub(r'<[^>]+>', '', text)
            plain = restore_inline_tokens(plain)
            anchor = slugify(plain)
            if level <= 3:
                toc.append((level, plain, anchor))
            html_parts.append(f'<h{level} id="{anchor}">{text}</h{level}>')
            i += 1; continue

        # HR
        if re.match(r'^---+$', line.strip()):
            flush_list(); flush_table(); flush_p()
            html_parts.append('<hr>')
            i += 1; continue

        # Blockquote
        if line.startswith('> '):
            flush_list(); flush_table(); flush_p()
            html_parts.append(f'<blockquote><p>{inline_fmt(line[2:])}</p></blockquote>')
            i += 1; continue

        # Protected mermaid
        mm = re.match(r'^%%MERMAID_(\d+)%%$', line.strip())
        if mm:
            flush_list(); flush_table(); flush_p()
            code = mermaid_blocks[int(mm.group(1))]
            safe = code.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            html_parts.append(f'<div class="mermaid-wrap"><div class="mermaid">{safe}</div></div>')
            i += 1; continue

        # Protected code block
        cb = re.match(r'^%%CODE_(\d+)%%$', line.strip())
        if cb:
            flush_list(); flush_table(); flush_p()
            lang, code = code_blocks[int(cb.group(1))]
            safe = code.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            html_parts.append(f'<pre data-lang="{lang}"><code>{safe}</code></pre>')
            i += 1; continue

        # Unordered list
        m_ul = re.match(r'^(\s*)[-*+]\s+(.+)', line)
        if m_ul:
          flush_table(); flush_p()
          if in_ol:
            html_parts.append('</ol>')
            in_ol = False
          if not in_ul:
            html_parts.append('<ul>')
            in_ul = True
          html_parts.append(f'<li>{inline_fmt(m_ul.group(2))}</li>')
          i += 1
          continue

        # Ordered list
        m_ol = re.match(r'^\d+\.\s+(.+)', line)
        if m_ol:
          flush_table(); flush_p()
          if in_ul:
            html_parts.append('</ul>')
            in_ul = False
          if not in_ol:
            html_parts.append('<ol>')
            in_ol = True
          html_parts.append(f'<li>{inline_fmt(m_ol.group(1))}</li>')
          i += 1
          continue

        # Table row
        if '|' in line and re.match(r'^\s*\|', line):
            flush_list(); flush_p()
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if not cells:
                i += 1; continue
            # Check if next line is separator
            next_line = lines[i+1] if i+1 < len(lines) else ''
            if re.match(r'^[\s|:\-]+$', next_line) and not in_table:
                html_parts.append('<table><thead><tr>')
                for c in cells:
                    html_parts.append(f'<th>{inline_fmt(c)}</th>')
                html_parts.append('</tr></thead><tbody>')
                in_table = True
                i += 2; continue
            else:
                if not in_table:
                    html_parts.append('<table><tbody>'); in_table = True
                if not re.match(r'^[\s|:\-]+$', line):
                    html_parts.append('<tr>')
                    for c in cells:
                        html_parts.append(f'<td>{inline_fmt(c)}</td>')
                    html_parts.append('</tr>')
            i += 1; continue

        # Empty line
        if not line.strip():
            flush_list(); flush_table()
            if in_p: html_parts.append('</p>'); in_p = False
            i += 1; continue

        # Default: paragraph
        flush_list(); flush_table()
        fmtd = inline_fmt(line)
        if not in_p:
            html_parts.append('<p>'); in_p = True
        else:
            html_parts.append(' ')
        html_parts.append(fmtd)
        i += 1

    flush_list(); flush_table(); flush_p()

    html = '\n'.join(html_parts)

    # Restore inline code
    for idx, code in enumerate(inline_codes):
        safe = code.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        html = html.replace(f'%%INLINE_{idx}%%', f'<code>{safe}</code>')

    return html, toc


# ── Templates ─────────────────────────────────────────────────────────────────

GOOGLE_FONTS = 'https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;1,9..144,300&family=JetBrains+Mono:wght@400;500;700&display=swap'
MERMAID_CDN  = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js'

def depth_prefix(depth: int) -> str:
    """Return relative path prefix based on nesting depth."""
    return '../' * depth

def html_page(
    title: str,
    body: str,
    breadcrumb: str = '',
    nav_tag: str = '',
    nav_tag_class: str = 'tag-core',
    depth: int = 1,
    prev_link: str = '',
    prev_title: str = '',
    next_link: str = '',
    next_title: str = '',
    toc: list = None,
    extra_head: str = '',
) -> str:
    p = depth_prefix(depth)
    bc = f'<span class="nav-sep">/</span><span class="nav-breadcrumb">{breadcrumb}</span>' if breadcrumb else ''
    tag_html = f'<span class="nav-tag {nav_tag_class}">{nav_tag}</span>' if nav_tag else ''

    toc_html = ''
    if toc:
        items = '\n'.join(
            f'<li style="padding-left:{(lv-2)*10}px"><a href="#{a}">{t}</a></li>'
            for lv, t, a in toc if lv >= 2
        )
        toc_html = f'''
        <aside class="toc-sidebar">
          <div class="toc-title">On this page</div>
          <ul class="toc-list">{items}</ul>
        </aside>'''

    prev_html = next_html = ''
    if prev_link:
        prev_html = f'''<a class="chapter-nav-card prev" href="{prev_link}">
          <div class="chapter-nav-label">← Previous</div>
          <div class="chapter-nav-title">{prev_title}</div>
        </a>'''
    if next_link:
        next_html = f'''<a class="chapter-nav-card next" href="{next_link}">
          <div class="chapter-nav-label">Next →</div>
          <div class="chapter-nav-title">{next_title}</div>
        </a>'''
    nav_cards = f'<div class="chapter-nav">{prev_html}{next_html}</div>' if (prev_html or next_html) else ''

    if toc:
        content_wrap = f'<div class="page-with-toc"><div class="prose">{body}{nav_cards}</div>{toc_html}</div>'
    else:
        content_wrap = f'<div class="page-wrap"><div class="prose">{body}{nav_cards}</div></div>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{title} — claudeCode Tutorial</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="{GOOGLE_FONTS}" rel="stylesheet"/>
<link rel="stylesheet" href="{p}assets/style.css"/>
{extra_head}
</head>
<body>
<div class="reading-bar" id="rb"></div>
<nav class="site-nav">
  <a class="nav-home" href="{p}index.html">
    <span class="dot"></span>
    <span>claudeCode</span>
  </a>
  {bc}
  <div class="nav-right">
    <ul class="nav-links-sm">
      <li><a href="{p}index.html#chapters">Chapters</a></li>
      <li><a href="{p}index.html#subsystems">Subsystems</a></li>
      <li><a href="{GITHUB_URL}" target="_blank">GitHub</a></li>
    </ul>
    {tag_html}
  </div>
</nav>
{content_wrap}
<footer class="site-footer">
  <span>claudeCode Tutorial · <a href="{GITHUB_URL}" target="_blank">GitHub</a></span>
  <span>Generated by <a href="https://github.com/adityasoni99/Code-IQ" target="_blank">Code IQ</a> · Built {datetime.now().year}</span>
</footer>
<script src="{MERMAID_CDN}"></script>
<script>
mermaid.initialize({{
  startOnLoad: true,
  theme: 'dark',
  flowchart: {{
    useMaxWidth: false,
    nodeSpacing: 55,
    rankSpacing: 70,
  }},
  themeVariables: {{
    primaryColor: '#1a1c2a',
    primaryTextColor: '#e8e4da',
    primaryBorderColor: '#f5a623',
    lineColor: '#7a7670',
    secondaryColor: '#13141f',
    tertiaryColor: '#0b0c13',
    edgeLabelBackground: '#0b0c13',
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: '16px',
  }}
}});
window.addEventListener('scroll', () => {{
  const bar = document.getElementById('rb');
  if (bar) bar.style.width = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight) * 100) + '%';
}});
</script>
</body>
</html>'''


# ── Chapter page builder ───────────────────────────────────────────────────────

def chapter_slug(filename: str) -> str:
    return filename.replace('.md', '').replace('_', '-')

def extract_index_overview_md(md: str) -> str:
  """Keep only the intro + mermaid part of index.md before the chapters section."""
  lines = md.splitlines()
  cut = len(lines)
  for i, line in enumerate(lines):
    if re.match(r'^##\s+chapters\s*$', line.strip(), re.IGNORECASE):
      cut = i
      break

  overview = '\n'.join(lines[:cut]).strip()
  return overview

def build_chapters(src_root: Path, out_dir: Path):
    chapters_dir = out_dir / 'chapters'
    chapters_dir.mkdir(exist_ok=True)

    for idx, (filename, title, category) in enumerate(CHAPTERS):
        md_path = src_root / filename
        if not md_path.exists():
            print(f"  [SKIP] {filename} not found")
            continue

        md = md_path.read_text(encoding='utf-8')
        body_html, toc = md_to_html(
          md,
          link_transform=lambda href: rewrite_md_link(href, page_kind='chapters')
        )

        # prev / next
        prev_link = prev_title = next_link = next_title = ''
        if idx > 0:
            pf, pt, _ = CHAPTERS[idx - 1]
            prev_link  = chapter_slug(pf) + '.html'
            prev_title = pt
        if idx < len(CHAPTERS) - 1:
            nf, nt, _ = CHAPTERS[idx + 1]
            next_link  = chapter_slug(nf) + '.html'
            next_title = nt

        tag_class = f'tag-{category}'
        slug = chapter_slug(filename)
        out_path = chapters_dir / f'{slug}.html'

        num = filename[:2]
        chapter_header = f'''
<div class="chapter-header">
  <div class="chapter-eyebrow">Chapter {int(num)} · <span class="tag {tag_class}">{category.upper()}</span></div>
  <h1 class="chapter-title-h1">{title}</h1>
  <div class="chapter-meta">
    <span>📄 {filename}</span>
    <span>🏷 {category.capitalize()}</span>
  </div>
</div>
'''
        full_body = chapter_header + body_html

        page = html_page(
            title=f'Ch.{num} {title}',
            body=full_body,
            breadcrumb=f'Ch.{num} — {title}',
            nav_tag=category.upper(),
            nav_tag_class=tag_class,
            depth=1,
            prev_link=prev_link, prev_title=prev_title,
            next_link=next_link, next_title=next_title,
            toc=toc,
        )
        out_path.write_text(page, encoding='utf-8')
        print(f"  ✓ chapters/{slug}.html")


# ── Subsystem pages ───────────────────────────────────────────────────────────

def build_subsystems(src_root: Path, out_dir: Path):
    sub_dir = out_dir / 'subsystems'
    sub_dir.mkdir(exist_ok=True)

    for (folder, display, desc, icon) in SUBSYSTEMS:
        folder_path = src_root / folder
        if not folder_path.is_dir():
            print(f"  [SKIP] subsystem/{folder}/ not found")
            continue

        # Find all markdown files in the folder
        md_files = sorted(folder_path.glob('*.md'))
        if not md_files:
            print(f"  [SKIP] subsystem/{folder}/ has no .md files")
            continue

        # Try to find an index.md
        index_md = folder_path / 'index.md'
        other_mds = [f for f in md_files if f.name != 'index.md']

        # Build the index page for this subsystem
        page_body_parts = []

        # Header
        page_body_parts.append(f'''
<div class="chapter-header">
  <div class="chapter-eyebrow">{icon} Subsystem Deep Dive</div>
  <h1 class="chapter-title-h1">{folder}/</h1>
  <div class="chapter-meta">
    <span>📁 {folder}/</span>
    <span>📄 {len(md_files)} file{"s" if len(md_files)!=1 else ""}</span>
  </div>
</div>
''')

        # Render index.md if present
        if index_md.exists():
            idx_html, toc = md_to_html(
              index_md.read_text(encoding='utf-8'),
              link_transform=lambda href, f=folder: rewrite_md_link(href, page_kind='subsystems', subsystem_folder=f)
            )
            page_body_parts.append(idx_html)
        else:
            toc = []
            page_body_parts.append(f'<p>{desc}</p>')

        # File grid linking to sub-pages
        if other_mds:
            page_body_parts.append('<h2 id="files-in-this-section">Files in this section</h2>')
            page_body_parts.append('<div class="subsystem-grid">')
            for mf in other_mds:
                slug = mf.stem.replace('_', '-')
                file_title = mf.stem.replace('_', ' ').replace('-', ' ').title()
                # Try to read first heading for better title
                try:
                    content = mf.read_text(encoding='utf-8')
                    m = re.search(r'^#\s+(.+)', content, re.MULTILINE)
                    if m:
                        file_title = m.group(1).strip()
                    # First paragraph as description
                    paras = re.findall(r'\n\n([^#\n][^\n]+)', content)
                    file_desc = paras[0].strip()[:120] + '…' if paras else ''
                except:
                    file_desc = ''
                page_body_parts.append(f'''
<a class="sub-file-card" href="{folder}-{slug}.html">
  <div class="sub-file-name">{mf.name}</div>
  <div class="sub-file-title">{file_title}</div>
  <div class="sub-file-desc">{file_desc}</div>
</a>''')
            page_body_parts.append('</div>')

        full_body = '\n'.join(page_body_parts)
        page = html_page(
            title=f'{display} — {folder}/',
            body=full_body,
            breadcrumb=f'Subsystem: {folder}/',
            nav_tag='SUBSYSTEM',
            nav_tag_class='tag-advanced',
            depth=1,
            toc=toc,
        )
        out_path = sub_dir / f'{folder}.html'
        out_path.write_text(page, encoding='utf-8')
        print(f"  ✓ subsystems/{folder}.html")

        # Now build individual pages for each non-index md file
        for idx, mf in enumerate(other_mds):
            slug = mf.stem.replace('_', '-')
            try:
                md_content = mf.read_text(encoding='utf-8')
            except Exception as e:
                print(f"    [ERR] {mf}: {e}")
                continue

            file_html, file_toc = md_to_html(
              md_content,
              link_transform=lambda href, f=folder: rewrite_md_link(href, page_kind='subsystems', subsystem_folder=f)
            )

            # Extract title from first h1
            m = re.search(r'^#\s+(.+)', md_content, re.MULTILINE)
            file_title = m.group(1).strip() if m else mf.stem.replace('_', ' ').title()

            prev_link = prev_title = next_link = next_title = ''
            if idx == 0:
              prev_link = f'{folder}.html'
              prev_title = f'{folder}/ index'
            else:
              prev_file = other_mds[idx - 1]
              prev_slug = prev_file.stem.replace('_', '-')
              prev_link = f'{folder}-{prev_slug}.html'
              prev_title = prev_file.stem.replace('_', ' ').replace('-', ' ').title()

            if idx < len(other_mds) - 1:
              next_file = other_mds[idx + 1]
              next_slug = next_file.stem.replace('_', '-')
              next_link = f'{folder}-{next_slug}.html'
              next_title = next_file.stem.replace('_', ' ').replace('-', ' ').title()

            sub_page = html_page(
                title=f'{file_title} — {folder}/',
                body=f'''
<div class="chapter-header">
  <div class="chapter-eyebrow">{icon} {folder}/ · {mf.name}</div>
  <h1 class="chapter-title-h1">{file_title}</h1>
  <div class="chapter-meta"><span>📄 {folder}/{mf.name}</span></div>
</div>
''' + file_html,
                breadcrumb=f'{folder}/{mf.name}',
                nav_tag='SUBSYSTEM',
                nav_tag_class='tag-advanced',
                depth=1,
                prev_link=prev_link,
                prev_title=prev_title,
                next_link=next_link,
                next_title=next_title,
                toc=file_toc,
            )
            sub_out = sub_dir / f'{folder}-{slug}.html'
            sub_out.write_text(sub_page, encoding='utf-8')
            print(f"    ✓ subsystems/{folder}-{slug}.html")


# ── Main index.html ───────────────────────────────────────────────────────────

def build_index(src_root: Path, out_dir: Path):
    """Generate the beautiful landing page index.html"""

    index_md_html = ''
    index_md_path = src_root / 'index.md'
    if index_md_path.exists():
        index_md_text = index_md_path.read_text(encoding='utf-8')
        overview_md = extract_index_overview_md(index_md_text)
        if overview_md:
            overview_html, _ = md_to_html(
                overview_md,
                link_transform=lambda href: rewrite_md_link(href, page_kind='root')
            )
            # Avoid repeating the page title from imported markdown in the landing overview.
            overview_html = re.sub(r'^\s*<h1[^>]*>.*?</h1>\s*', '', overview_html, count=1, flags=re.DOTALL)
            index_md_html = f'''
<section class="section" id="overview">
  <div class="container">
    <div class="sec-label">Repository Overview</div>
    <h2 class="sec-h2">Intro and Architecture Diagram</h2>
    <div class="prose">{overview_html}</div>
  </div>
</section>'''

    # Chapter cards
    chapter_cards = ''
    tag_labels = {'core':'CORE','tools':'TOOLS','security':'SECURITY','advanced':'ADVANCED','agents':'AGENTS'}
    for idx, (filename, title, category) in enumerate(CHAPTERS):
        slug = chapter_slug(filename)
        tag_cls = f'tag-{category}'
        tag_lbl = tag_labels.get(category, category.upper())
        num = filename[:2]

        # Short descriptions (curated)
        descs = {
            '01': 'The foundational data store. Tasks, permissions, and live session data — all in one place.',
            '02': 'React for the terminal. How the CLI interface is rendered using familiar component patterns.',
            '03': 'The heart of claudeCode. The conversation loop that orchestrates LLM calls and executes tools.',
            '04': 'Precise file patching with permission checks and diff computation. How the AI edits code safely.',
            '05': 'Context-aware assistance using git history, diffs, and blame. The AI that understands your repo.',
            '06': 'Safe shell command execution with injection protection. How the agent runs commands without going rogue.',
            '07': 'Command risk classification and user confirmation workflows. Defense-in-depth for shell access.',
            '08': 'Granular allow/deny rules governing every tool action. The full security architecture explained.',
            '09': 'How permission rules are evaluated against incoming tool calls using pattern matching algorithms.',
            '10': 'LLM-driven decision engine for automatic permission delegation. When the AI decides for itself.',
            '11': 'Cell-level Jupyter notebook editing with output tracking. AI meets data science workflows.',
            '12': 'Gated web search with feature-flag control. How the agent reaches beyond the codebase.',
            '13': 'Runtime capability flags that enable or disable experimental features on the fly.',
            '14': 'External tool server protocol for plugging in third-party capabilities and extending the agent.',
            '15': 'Spawning and managing sub-agents for delegated tasks. The inception layer of AI agents.',
            '16': 'Background agents running in parallel. Multitasking as a first-class architectural feature.',
            '17': 'Buddy System, Kairos, Ultraplan, Auto-Dream, and Remote Bridge — the exotic capabilities.',
            '18': 'GUI automation — screenshot, mouse, and keyboard control. The agent takes over the desktop.',
            '19': 'Per-session token and dollar cost accounting. How the agent stays fiscally responsible.',
        }
        desc = descs.get(num, '')
        chapter_cards += f'''
<a class="ch-card" href="chapters/{slug}.html">
  <div class="ch-num">Ch.{int(num):02d} <span class="tag {tag_cls}">{tag_lbl}</span></div>
  <div class="ch-title">{title}</div>
  <div class="ch-desc">{desc}</div>
  <span class="ch-arrow">↗</span>
</a>'''

    # Subsystem cards (only those that actually exist)
    sub_cards = ''
    for (folder, display, desc, icon) in SUBSYSTEMS:
        folder_path = src_root / folder
        if not folder_path.is_dir(): continue
        n_files = len(list(folder_path.glob('*.md')))
        sub_cards += f'''
<a class="sub-card" href="subsystems/{folder}.html">
  <div class="sub-icon">{icon}</div>
  <div class="sub-folder">{folder}/</div>
  <div class="sub-title">{display}</div>
  <div class="sub-desc">{desc}</div>
  <div class="sub-count">{n_files} file{"s" if n_files!=1 else ""}</div>
</a>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>claudeCode — Codebase Knowledge Tutorial</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="{GOOGLE_FONTS}" rel="stylesheet"/>
<link rel="stylesheet" href="assets/style.css"/>
<style>
/* ── Landing page extras ── */
.hero {{
  min-height: 100vh;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 100px 2rem 5rem;
  text-align: center;
  position: relative;
}}
.hero-grid {{
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(245,166,35,.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(245,166,35,.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 80% 70% at 50% 50%, black 40%, transparent 100%);
}}
.eyebrow {{
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 10px; letter-spacing: .2em;
  text-transform: uppercase; color: var(--amber);
  border: 1px solid rgba(245,166,35,.25);
  padding: 6px 18px; border-radius: 2px;
  margin-bottom: 2.5rem;
  background: var(--amber-glow);
  position: relative;
}}
.eyebrow::before {{
  content: ''; width: 6px; height: 6px;
  background: var(--amber); border-radius: 50%;
  animation: blink 1.4s ease-in-out infinite;
}}
.hero-h1 {{
  font-family: 'Fraunces', Georgia, serif;
  font-size: clamp(3rem, 8vw, 6.5rem);
  font-weight: 300; line-height: 1.0;
  letter-spacing: -.02em; color: #fff;
  margin-bottom: 1.5rem; position: relative;
}}
.hero-h1 em {{ font-style: italic; color: var(--amber); }}
.hero-sub {{
  max-width: 620px; font-size: 14px;
  color: var(--muted); line-height: 1.9;
  margin-bottom: 3rem; position: relative;
}}
.hero-stats {{
  display: flex; gap: 3rem;
  justify-content: center;
  position: relative; margin-bottom: 3rem;
}}
.stat {{ text-align: center; }}
.stat-n {{
  font-family: 'Fraunces', Georgia, serif;
  font-size: 2.5rem; font-weight: 400;
  color: var(--text); line-height: 1;
}}
.stat-l {{
  font-size: 10px; letter-spacing: .15em;
  text-transform: uppercase; color: var(--muted); margin-top: 4px;
}}
.hero-btns {{ display: flex; gap: 12px; justify-content: center; position: relative; }}
.btn {{
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 28px; font-family: 'JetBrains Mono', monospace;
  font-size: 12px; font-weight: 700; letter-spacing: .1em;
  text-decoration: none; border-radius: 2px; transition: all .2s; cursor: pointer;
}}
.btn-p {{ background: var(--amber); color: #0b0c13; }}
.btn-p:hover {{ background: #ffc04a; transform: translateY(-2px); }}
.btn-s {{ background: transparent; color: var(--text); border: 1px solid var(--border); }}
.btn-s:hover {{ border-color: var(--border-hover); color: var(--amber); }}

/* terminal */
.terminal-wrap {{ padding: 3rem 2rem; }}
.terminal {{
  max-width: 720px; margin: 0 auto;
  border: 1px solid var(--border); border-radius: 8px;
  background: var(--surface); overflow: hidden;
}}
.t-bar {{
  background: var(--surface2); padding: 10px 16px;
  display: flex; align-items: center; gap: 8px;
  border-bottom: 1px solid var(--border);
}}
.t-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.t-title {{
  flex: 1; text-align: center; font-size: 11px;
  color: var(--muted); letter-spacing: .05em;
}}
.t-body {{ padding: 1.25rem 1.5rem; font-size: 12px; line-height: 2.1; }}
.t-ln {{ display: flex; gap: 8px; }}
.t-pr {{ color: var(--amber); }}
.t-out {{ color: var(--muted); padding-left: 1rem; }}
.t-g {{ color: var(--green); }}
.t-c {{ color: var(--cyan); }}
.t-cursor {{
  display: inline-block; width: 8px; height: 14px;
  background: var(--amber); vertical-align: middle;
  animation: cur 1.2s step-end infinite;
}}
@keyframes cur {{ 0%,100%{{opacity:1}} 50%{{opacity:0}} }}

/* sections */
.section {{ padding: 5rem 2rem; }}
.section-alt {{ background: var(--surface); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }}
.container {{ max-width: 1180px; margin: 0 auto; }}
.sec-label {{
  font-size: 10px; letter-spacing: .2em;
  text-transform: uppercase; color: var(--amber);
  margin-bottom: 1.5rem;
  display: flex; align-items: center; gap: 10px;
}}
.sec-label::after {{
  content: ''; flex: 1; max-width: 60px;
  height: 1px; background: var(--amber); opacity: .4;
}}
.sec-h2 {{
  font-family: 'Fraunces', Georgia, serif;
  font-size: clamp(1.8rem, 3.5vw, 2.8rem);
  font-weight: 300; color: #fff; margin-bottom: .8rem;
}}
.sec-intro {{
  color: var(--muted); font-size: 13px; line-height: 1.9;
  max-width: 580px; margin-bottom: 3rem;
}}

/* chapter cards grid */
.chapters-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: 4px; overflow: hidden;
}}
.ch-card {{
  background: var(--surface); padding: 1.75rem;
  transition: background .2s; position: relative;
  cursor: pointer; text-decoration: none; display: block;
}}
.ch-card::before {{
  content: ''; position: absolute;
  left: 0; top: 0; bottom: 0; width: 2px;
  background: transparent; transition: background .2s;
}}
.ch-card:hover {{ background: var(--surface2); }}
.ch-card:hover::before {{ background: var(--amber); }}
.ch-num {{
  font-size: 10px; letter-spacing: .2em;
  color: var(--muted2); margin-bottom: 10px;
  display: flex; align-items: center; gap: 8px;
}}
.ch-title {{
  font-family: 'Fraunces', Georgia, serif;
  font-size: 1.15rem; font-weight: 400;
  color: #fff; margin-bottom: 8px; line-height: 1.2;
}}
.ch-desc {{ font-size: 11px; color: var(--muted); line-height: 1.7; }}
.ch-arrow {{
  position: absolute; right: 1.75rem; bottom: 1.75rem;
  color: var(--muted2); font-size: 16px; transition: all .2s;
}}
.ch-card:hover .ch-arrow {{ color: var(--amber); transform: translate(3px,-3px); }}

/* subsystem cards */
.sub-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}}
.sub-card {{
  border: 1px solid var(--border); border-radius: 4px;
  padding: 1.5rem; background: var(--bg);
  text-decoration: none; display: block;
  transition: border-color .2s, transform .2s;
}}
.sub-card:hover {{ border-color: var(--border-hover); transform: translateY(-2px); }}
.sub-icon {{ font-size: 20px; margin-bottom: 8px; display: block; }}
.sub-folder {{
  font-size: 10px; letter-spacing: .15em;
  color: var(--amber); margin-bottom: 6px;
}}
.sub-title {{
  font-family: 'Fraunces', Georgia, serif;
  font-size: 1rem; font-weight: 400; color: #fff; margin-bottom: 6px;
}}
.sub-desc {{ font-size: 10px; color: var(--muted); line-height: 1.6; margin-bottom: 8px; }}
.sub-count {{
  font-size: 9px; letter-spacing: .1em;
  color: var(--muted2); text-transform: uppercase;
}}

/* architecture mosaic */
.arch-mosaic {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: 4px; overflow: hidden;
}}
.arch-node {{
  background: var(--surface2); padding: 1.25rem;
  transition: background .2s;
}}
.arch-node:hover {{ background: var(--surface3); }}
.arch-ic {{ font-size: 18px; margin-bottom: 8px; display: block; }}
.arch-nm {{ font-size: 11px; font-weight: 700; margin-bottom: 4px; }}
.arch-ds {{ font-size: 10px; color: var(--muted); line-height: 1.5; }}
.aa {{ color: var(--amber); }}
.ac {{ color: var(--cyan); }}
.ag {{ color: var(--green); }}
.ap {{ color: var(--purple); }}
.ar {{ color: var(--coral); }}

/* footer */
footer {{
  border-top: 1px solid var(--border);
  padding: 2.5rem 2rem;
  display: flex; align-items: center;
  justify-content: space-between; flex-wrap: wrap; gap: 1rem;
}}
footer span {{ font-size: 11px; color: var(--muted2); }}
footer a {{ color: var(--muted); text-decoration: none; transition: color .2s; }}
footer a:hover {{ color: var(--amber); }}
</style>
</head>
<body>
<div class="reading-bar" id="rb"></div>
<nav class="site-nav">
  <a class="nav-home" href="index.html">
    <span class="dot"></span><span>claudeCode</span>
  </a>
  <div class="nav-right">
    <ul class="nav-links-sm">
      <li><a href="#chapters">Chapters</a></li>
      <li><a href="#subsystems">Subsystems</a></li>
      <li><a href="#about">About</a></li>
      <li><a href="{GITHUB_URL}" target="_blank">GitHub ↗</a></li>
    </ul>
    <span class="nav-tag tag-core">19 Chapters</span>
  </div>
</nav>

<!-- HERO -->
<section class="hero" id="top">
  <div class="hero-grid"></div>
  <div class="eyebrow">Generated by Code IQ · v1.0</div>
  <h1 class="hero-h1"><em>claudeCode</em><br>Knowledge Tutorial</h1>
  <p class="hero-sub">
    A chapter-by-chapter deep-dive into the internal architecture of claudeCode —
    an autonomous AI software engineer. Plain language, analogies, and real code walkthroughs.
  </p>
  <div class="hero-stats">
    <div class="stat"><div class="stat-n">19</div><div class="stat-l">Chapters</div></div>
    <div class="stat"><div class="stat-n">30+</div><div class="stat-l">Subsystems</div></div>
    <div class="stat"><div class="stat-n">∞</div><div class="stat-l">Rabbit Holes</div></div>
  </div>
  <div class="hero-btns">
    <a class="btn btn-p" href="chapters/01-state-management.html">▶ Start Reading</a>
    <a class="btn btn-s" href="{GITHUB_URL}" target="_blank">⎇ View on GitHub</a>
  </div>
</section>

<!-- ARCHITECTURE -->
<section class="section section-alt" id="architecture">
  <div class="container">
    <div class="sec-label">System Architecture</div>
    <h2 class="sec-h2">How the pieces fit</h2>
    <p class="sec-intro">claudeCode is built from interlocking subsystems, each with a clear responsibility.</p>
    <div class="arch-mosaic">
      <div class="arch-node"><span class="arch-ic">⚙️</span><div class="arch-nm aa">Query Engine</div><div class="arch-ds">Core conversation loop. Drives LLM calls and tool execution.</div></div>
      <div class="arch-node"><span class="arch-ic">🗂</span><div class="arch-nm ac">State Management</div><div class="arch-ds">Single source of truth for tasks, permissions, and session data.</div></div>
      <div class="arch-node"><span class="arch-ic">🖥</span><div class="arch-nm ac">Ink UI Framework</div><div class="arch-ds">React-for-terminals rendering layer powering the CLI.</div></div>
      <div class="arch-node"><span class="arch-ic">✏️</span><div class="arch-nm aa">FileEditTool</div><div class="arch-ds">Precise file patching with diff computation and permission checks.</div></div>
      <div class="arch-node"><span class="arch-ic">💻</span><div class="arch-nm aa">BashTool</div><div class="arch-ds">Safe shell command execution with injection protection.</div></div>
      <div class="arch-node"><span class="arch-ic">🛡</span><div class="arch-nm ag">Permission System</div><div class="arch-ds">Granular allow/deny rules governing every tool action.</div></div>
      <div class="arch-node"><span class="arch-ic">🔍</span><div class="arch-nm ag">Rule Matching</div><div class="arch-ds">Evaluates permission rules against tool calls.</div></div>
      <div class="arch-node"><span class="arch-ic">🤖</span><div class="arch-nm ag">Auto-Mode Classifier</div><div class="arch-ds">LLM-driven automatic permission delegation.</div></div>
      <div class="arch-node"><span class="arch-ic">🔌</span><div class="arch-nm ap">MCP Protocol</div><div class="arch-ds">External tool server protocol extending capabilities.</div></div>
      <div class="arch-node"><span class="arch-ic">👥</span><div class="arch-nm ar">Teammates</div><div class="arch-ds">Background sub-agents running parallel tasks.</div></div>
      <div class="arch-node"><span class="arch-ic">🧩</span><div class="arch-nm ar">AgentTool</div><div class="arch-ds">Spawns and manages sub-agents for delegated tasks.</div></div>
      <div class="arch-node"><span class="arch-ic">🖱</span><div class="arch-nm ap">Computer Use</div><div class="arch-ds">GUI automation — screenshot, mouse, keyboard control.</div></div>
    </div>
  </div>
</section>

<!-- TERMINAL -->
<div class="terminal-wrap">
  <div class="terminal">
    <div class="t-bar">
      <span class="t-dot" style="background:#ff5f57"></span>
      <span class="t-dot" style="background:#febc2e"></span>
      <span class="t-dot" style="background:#28c840"></span>
      <span class="t-title">claudeCode — bash</span>
    </div>
    <div class="t-body">
      <div class="t-ln"><span class="t-pr">➜</span><span>claude "Fix the auth bug in server.js"</span></div>
      <div class="t-out t-c">◆ Reading server.js (284 lines)</div>
      <div class="t-out t-c">◆ Checking git blame for recent changes</div>
      <div class="t-out">◆ Found: missing await in verifyToken()</div>
      <div class="t-out" style="color:var(--amber)">◆ Requesting permission to edit server.js…</div>
      <div class="t-ln"><span class="t-pr">?</span><span class="t-g">Allow file edit? [Y/n] y</span></div>
      <div class="t-out t-g">✓ Applied patch (3 lines changed)</div>
      <div class="t-out t-g">✓ All 47 tests passed</div>
      <div class="t-out t-g">✓ Committed: "fix: await verifyToken in auth middleware"</div>
      <div class="t-ln" style="margin-top:4px"><span class="t-pr">➜</span><span class="t-cursor"></span></div>
    </div>
  </div>
</div>

{index_md_html}

<!-- CHAPTERS -->
<section class="section" id="chapters">
  <div class="container">
    <div class="sec-label">Tutorial Chapters</div>
    <h2 class="sec-h2">All 19 chapters</h2>
    <p class="sec-intro">Follow sequentially or jump to any topic. Start with State Management — everything else builds on it.</p>
    <div class="chapters-grid">{chapter_cards}</div>
  </div>
</section>

<!-- SUBSYSTEMS -->
<section class="section section-alt" id="subsystems">
  <div class="container">
    <div class="sec-label">Subsystem Deep Dives</div>
    <h2 class="sec-h2">Beyond the chapters</h2>
    <p class="sec-intro">Each major subsystem has its own folder with granular breakdowns and individual file pages.</p>
    <div class="sub-grid">{sub_cards}</div>
  </div>
</section>

<!-- ABOUT -->
<section class="section" id="about">
  <div class="container">
    <div class="sec-label">About This Project</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:3rem;align-items:center;border:1px solid var(--border);border-radius:4px;padding:3rem;background:var(--surface)">
      <div>
        <h2 class="sec-h2" style="margin-bottom:1rem">Generated by <em style="color:var(--amber);font-style:normal">Code IQ</em></h2>
        <p style="color:var(--muted);font-size:12px;line-height:1.9;margin-bottom:1rem">
          This tutorial was automatically generated by Code IQ — a tool that analyses any GitHub repository
          and produces beginner-friendly, structured documentation directly from its source code.
        </p>
        <a class="btn btn-s" href="https://github.com/adityasoni99/Code-IQ" target="_blank" style="display:inline-flex">View Code IQ ↗</a>
      </div>
      <div style="background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:1.5rem;font-size:11px;line-height:2;color:var(--muted)">
        <span style="color:var(--purple)">import</span> &#123; <span style="color:var(--cyan)">analyzeRepo</span> &#125; <span style="color:var(--purple)">from</span> <span style="color:var(--green)">'code-iq'</span>;<br/><br/>
        <span style="color:var(--purple)">const</span> tutorial = <span style="color:var(--purple)">await</span> <span style="color:var(--cyan)">analyzeRepo</span>(&#123;<br/>
        &nbsp;&nbsp;repo: <span style="color:var(--green)">'anthropics/claude-code'</span>,<br/>
        &nbsp;&nbsp;style: <span style="color:var(--green)">'beginner-friendly'</span>,<br/>
        &#125;);<br/><br/>
        <span style="color:var(--muted2)">// → 19 chapters, 30+ deep dives</span>
      </div>
    </div>
  </div>
</section>

<footer>
  <span>claudeCode Tutorial · <a href="{GITHUB_URL}" target="_blank">GitHub Repo</a></span>
  <span>Built with <a href="https://github.com/adityasoni99/Code-IQ" target="_blank">Code IQ</a> · {datetime.now().year}</span>
</footer>

<script src="{MERMAID_CDN}"></script>
<script>
mermaid.initialize({{
  startOnLoad: true,
  theme: 'dark',
  flowchart: {{
    useMaxWidth: false,
    nodeSpacing: 55,
    rankSpacing: 70,
  }},
  themeVariables: {{
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: '16px',
  }}
}});
window.addEventListener('scroll', () => {{
  const bar = document.getElementById('rb');
  if (bar) bar.style.width = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight) * 100) + '%';
}});
</script>
</body>
</html>'''
    (out_dir / 'index.html').write_text(html, encoding='utf-8')
    print("  ✓ index.html")


# ── Copy assets ───────────────────────────────────────────────────────────────

def copy_assets(build_py_dir: Path, out_dir: Path):
    """Copy CSS and any static assets from _site_assets/ if it exists."""
    assets_out = out_dir / 'assets'
    assets_out.mkdir(exist_ok=True)
    # The CSS is already placed by our template — but also check for user assets
    src = build_py_dir / '_site_assets'
    if src.is_dir():
        for f in src.glob('*'):
            shutil.copy2(f, assets_out / f.name)
            print(f"  ✓ assets/{f.name}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("\n🚀 claudeCode Tutorial — Static Site Builder")
    print("=" * 50)
    print(f"  Source : {REPO_ROOT}")
    print(f"  Output : {DOCS_OUT}")
    print()

    # Install markdown dependency if needed (optional, we use our own parser)
    # But DO install mermaid if someone wants to pre-render

    DOCS_OUT.mkdir(exist_ok=True)
    (DOCS_OUT / 'assets').mkdir(exist_ok=True)
    (DOCS_OUT / 'chapters').mkdir(exist_ok=True)
    (DOCS_OUT / 'subsystems').mkdir(exist_ok=True)

    # Write CSS
    css_src = REPO_ROOT / '_site_assets' / 'style.css'
    css_out = DOCS_OUT / 'assets' / 'style.css'
    if css_src.exists():
        shutil.copy2(css_src, css_out)
    else:
        print("  [WARN] _site_assets/style.css not found — CSS will be missing!")
    print("  ✓ assets/style.css")

    print("\n📄 Building chapter pages…")
    build_chapters(REPO_ROOT, DOCS_OUT)

    print("\n📁 Building subsystem pages…")
    build_subsystems(REPO_ROOT, DOCS_OUT)

    print("\n🏠 Building index.html…")
    build_index(REPO_ROOT, DOCS_OUT)

    # GitHub Pages config
    (DOCS_OUT / '.nojekyll').write_text('')
    print("\n  ✓ .nojekyll")

    print(f"\n✅ Site built → {DOCS_OUT}/")
    print("   Open docs/index.html in a browser to preview.\n")


if __name__ == '__main__':
    main()
