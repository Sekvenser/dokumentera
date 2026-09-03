#!/usr/bin/env python3
"""dokumentera -- CLI for the Dokumentera archive of discontinued/out-of-print
Swedish comic publications (albums, magazines, fanzines no longer available).

Each entry is one data/entries/<id>.md: YAML frontmatter for the metadata,
then the page's body text below it -- markdown is the source of truth for
the prose, not a scraped field. `build` compiles data/entries.json (for the
list page) and a static web/dokument/<id>/index.html per entry (for the
detail page), mirroring the sibling tecknade-serier repo.

Commands: add, update, list, build.
"""
import argparse
import datetime
import html
import json
import os
import re
import sys

import markdown
import yaml

ENTRIES_DIR = "data/entries"
JSON_OUT = "web/data/entries.json"
PAGES_DIR = "web/dokument"
SITEMAP_OUT = "web/sitemap.xml"
SITE_URL = "https://dokumentera.sekvenser.se"

ENTRY_FIELD_ORDER = [
    "id", "title", "creators", "publisher", "year", "type", "language", "pages",
    "cover_image", "example_pages", "more_info_url", "author", "added_at",
]


def slugify(value):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip().lower()).strip("-")


def entry_path(slug):
    return os.path.join(ENTRIES_DIR, f"{slug}.md")


# --- frontmatter -----------------------------------------------------------
#
# One entry = one .md file: "---\n<yaml frontmatter>\n---\n\n<body markdown>".
# Small enough to parse by hand with the PyYAML we already depend on -- no
# need for a separate frontmatter library for a format this simple.

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)


def parse_entry_file(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("saknar frontmatter (filen måste börja med ett '---'-block)")
    front, body = m.groups()
    entry = yaml.safe_load(front) or {}
    entry["id"] = str(entry["id"])  # guard against an unquoted numeric id
    entry["_body"] = body.lstrip("\n")
    return entry


def ordered_entry(entry):
    fields = {k: v for k, v in entry.items() if not k.startswith("_")}
    ordered = {k: fields[k] for k in ENTRY_FIELD_ORDER if k in fields}
    ordered.update((k, v) for k, v in fields.items() if k not in ordered)
    return ordered


def render_entry_file(entry):
    front = yaml.safe_dump(ordered_entry(entry), allow_unicode=True, sort_keys=False, width=100)
    body = entry.get("_body", "").strip("\n")
    parts = ["---", front.rstrip("\n"), "---"]
    if body:
        parts += ["", body]
    return "\n".join(parts) + "\n"


def load_store():
    store = {}
    if not os.path.isdir(ENTRIES_DIR):
        return store
    for name in sorted(os.listdir(ENTRIES_DIR)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(ENTRIES_DIR, name), encoding="utf-8") as f:
            entry = parse_entry_file(f.read())
        store[entry["id"]] = entry
    return store


def save_entry(entry):
    os.makedirs(ENTRIES_DIR, exist_ok=True)
    path = entry_path(entry["id"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_entry_file(entry))
    return path


def apply_common_fields(entry, args, appending_examples=False):
    if getattr(args, "title", None):
        entry["title"] = args.title
    if getattr(args, "creators", None) is not None:
        entry["creators"] = [c.strip() for c in args.creators.split(",") if c.strip()]
    if getattr(args, "publisher", None):
        entry["publisher"] = args.publisher
    if getattr(args, "year", None):
        entry["year"] = args.year
    if getattr(args, "type", None):
        entry["type"] = args.type
    if getattr(args, "language", None):
        entry["language"] = args.language
    if getattr(args, "pages", None):
        entry["pages"] = args.pages
    if getattr(args, "cover", None):
        entry["cover_image"] = args.cover
    if getattr(args, "more_info_url", None):
        entry["more_info_url"] = args.more_info_url
    if getattr(args, "author", None):
        entry["author"] = args.author
    example_pages = getattr(args, "example_page", None)
    if example_pages:
        if appending_examples:
            entry.setdefault("example_pages", []).extend(example_pages)
        else:
            entry["example_pages"] = list(example_pages)


def cmd_add(args):
    slug = args.id or slugify(args.title)
    if not slug:
        sys.exit("error: kunde inte härleda ett id från --title, ange --id explicit")
    if os.path.exists(entry_path(slug)):
        sys.exit(f"error: {slug} finns redan (använd 'update' istället)")

    entry = {
        "id": slug,
        "title": args.title,
        "added_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "_body": "Skriv en beskrivning av utgåvan här.\n",
    }
    apply_common_fields(entry, args)
    path = save_entry(entry)

    print(f"Skapade {path}")
    print("Redigera filens text under frontmatter-blocket, kör sedan 'build'.")


def cmd_update(args):
    store = load_store()
    entry = store.get(args.id)
    if entry is None:
        sys.exit(f"error: hittar ingen post med id '{args.id}'")

    apply_common_fields(entry, args, appending_examples=True)
    path = save_entry(entry)
    print(f"Uppdaterade {path}")


def cmd_list(args):
    store = load_store()
    if not store:
        print("Inga poster ännu. Lägg till en med 'add'.")
        return
    entries = sorted(store.values(), key=lambda e: (-(e.get("year") or 0), e["title"]))
    for e in entries:
        bits = [e["id"], e["title"]]
        if e.get("year"):
            bits.append(str(e["year"]))
        if e.get("publisher"):
            bits.append(e["publisher"])
        if e.get("type"):
            bits.append(e["type"])
        print(" | ".join(bits))
    print(f"\n{len(entries)} poster")


# --- build -------------------------------------------------------------
#
# Compiles data/entries.json (consumed by web/app.js for the list/search
# page) and one static web/dokument/<id>/index.html per entry (the detail
# page). There is no client-side detail route -- app.js only lists/searches
# and links straight to /dokument/<id>/, same approach as the sibling
# tecknade-serier repo.

def truncate(text, limit=200):
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def strip_tags(text):
    return re.sub(r"<[^>]+>", " ", text)


def cover_src(cover_image):
    return f"/assets/covers/{cover_image}" if cover_image else ""


def page_src(filename):
    return f"/assets/pages/{filename}"


ENTRY_META_TEMPLATE = """<title>{title}</title>
<link rel="canonical" href="{canonical_url}">
<meta name="description" content="{description}">

<meta property="og:type" content="book">
<meta property="og:site_name" content="Dokumentera">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:image" content="{image_url}">
<meta property="og:locale" content="sv_SE">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image_url}">"""


# This markup has no JS equivalent (app.js never renders a detail view) --
# same content as the sibling tecknade-serier repo's ad slot.
AD_SLOT_HTML = """<aside class="ad-slot" id="ad-slot" aria-label="Annonsplats">
        <div class="ad-label">Annonser</div>
        <a class="ad-unit" href="https://sekvenser.se" target="_blank" rel="noopener">
          <img src="/assets/blurb-news-cropped.png" alt="Sekvenser">
          <p>Sekvenser 2&ndash;3 ute nu. Sveriges enda oberoende tidskrift om tecknade serier och sekventiell konst. Köp den på sekvenser.se</p>
        </a>
        <a class="ad-unit ad-unit-text" href="mailto:mikkeschiren@gmail.com">
          Vill du annonsera här? Kontakta mikkeschiren@gmail.com
        </a>
      </aside>"""


def render_entry_detail_html(entry, body_html):
    if entry.get("cover_image"):
        src = html.escape(cover_src(entry["cover_image"]))
        cover_html = (f'<div class="cover" role="button" tabindex="0" aria-label="Visa omslag i fullstorlek" '
                      f'data-cover="{src}"><img src="{src}" alt=""></div>')
    else:
        cover_html = f'<div class="cover">{html.escape(entry["title"])}</div>'

    rows = [
        ("Upphovspersoner", ", ".join(entry.get("creators") or []) or "–"),
        ("Förlag", entry.get("publisher") or "–"),
        ("Utgivningår", str(entry.get("year") or "–")),
        ("Typ", entry.get("type") or "–"),
        ("Språk", entry.get("language") or "–"),
        ("Sidor", str(entry.get("pages") or "–")),
    ]
    dl_html = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in rows)

    more_info_html = ""
    if entry.get("more_info_url"):
        more_info_html = (f'<div class="links"><a href="{html.escape(entry["more_info_url"])}" '
                           f'target="_blank" rel="noopener">Mer information</a></div>')

    body_section = body_html or '<p class="empty">Ingen textinformation tillgänglig ännu.</p>'

    author_html = ""
    if entry.get("author"):
        author_html = f'<p class="byline">Text: {html.escape(entry["author"])}</p>'

    gallery_html = ""
    pages = entry.get("example_pages") or []
    if pages:
        thumbs = "".join(
            f'<div class="page-thumb" role="button" tabindex="0" aria-label="Visa sida i fullstorlek" '
            f'data-cover="{html.escape(page_src(p))}"><img src="{html.escape(page_src(p))}" alt="" loading="lazy"></div>'
            for p in pages
        )
        gallery_html = (f'<h3 class="pages-heading">Sidor ur utgåvan</h3>'
                         f'<div class="pages-gallery">{thumbs}</div>')

    return f"""<a class="back" href="/#/">&larr; Tillbaka</a>
    <div class="detail-layout">
      <div class="detail">
        <div class="detail-head">
          {cover_html}
          <div>
            <h1>{html.escape(entry['title'])}</h1>
            <dl>{dl_html}</dl>
            {more_info_html}
          </div>
        </div>
        <div class="body">{body_section}</div>
        {author_html}
        {gallery_html}
      </div>
      {AD_SLOT_HTML}
    </div>"""


def build_pages(store, template_path="web/index.html", site_url=SITE_URL):
    with open(template_path, encoding="utf-8") as f:
        template = f.read()
    if ("<!--BOOK_META_START-->" not in template or '<main id="app"></main>' not in template
            or "<!--TOOLBAR_START-->" not in template):
        raise ValueError(f"{template_path} saknar en förväntad BOOK_META/#app/TOOLBAR-markering")

    # A single entry page has no list to filter -- drop the search/year toolbar.
    template = re.sub(r"<!--TOOLBAR_START-->.*?<!--TOOLBAR_END-->", "", template, flags=re.S)

    for entry in store.values():
        slug = entry["id"]
        body_md = entry.get("_body", "")
        body_html = markdown.markdown(body_md) if body_md.strip() else ""
        plain = strip_tags(body_html)
        description = truncate(plain) if plain.strip() else f"{entry['title']} – dokumenterad i Dokumentera."

        image_url = (f"{site_url}{cover_src(entry['cover_image'])}" if entry.get("cover_image")
                     else f"{site_url}/assets/og-image.png")
        meta = ENTRY_META_TEMPLATE.format(
            title=html.escape(f"{entry['title']} – Dokumentera"),
            description=html.escape(description),
            canonical_url=html.escape(f"{site_url}/dokument/{slug}/"),
            image_url=html.escape(image_url),
        )

        page = re.sub(r"<!--BOOK_META_START-->.*?<!--BOOK_META_END-->", meta, template, flags=re.S)
        page = page.replace('<main id="app"></main>', f'<main id="app">{render_entry_detail_html(entry, body_html)}</main>')

        page_dir = os.path.join(PAGES_DIR, slug)
        os.makedirs(page_dir, exist_ok=True)
        with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)


def build_json(store):
    entries = [ordered_entry(e) for e in store.values()]
    entries.sort(key=lambda e: (-(e.get("year") or 0), e["title"]))
    os.makedirs(os.path.dirname(JSON_OUT), exist_ok=True)
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def build_sitemap(store, sitemap_path=SITEMAP_OUT, site_url=SITE_URL):
    urls = [(f"{site_url}/", None)]
    for entry in store.values():
        lastmod = (entry.get("added_at") or "")[:10] or None
        urls.append((f"{site_url}/dokument/{entry['id']}/", lastmod))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{html.escape(loc)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    os.makedirs(os.path.dirname(sitemap_path) or ".", exist_ok=True)
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def cmd_build(args):
    store = load_store()
    build_json(store)
    build_pages(store)
    build_sitemap(store)
    print(f"Byggde {JSON_OUT}, {SITEMAP_OUT} och {len(store)} sida(or) under {PAGES_DIR}/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_entry_fields(p, examples_help):
        p.add_argument("--creators", help="kommaseparerad lista, t.ex. \"Anna Andersson, Bo Berg\"")
        p.add_argument("--publisher")
        p.add_argument("--year", type=int)
        p.add_argument("--type", help="t.ex. Seriealbum, Fanzine, Tidning, Antologi")
        p.add_argument("--language")
        p.add_argument("--pages", type=int, help="antal sidor i utgåvan")
        p.add_argument("--cover", help="filnamn under web/assets/covers/, t.ex. mitt-fanzin.jpg")
        p.add_argument("--example-page", action="append", help=examples_help)
        p.add_argument("--more-info-url", help="länk till mer information om utgåvan")
        p.add_argument("--author", help="vem som skrivit/dokumenterat den här posten")

    p_add = sub.add_parser("add", help="lägg till en ny post")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--id", help="valfritt; härleds annars från titeln")
    add_entry_fields(p_add, "filnamn under web/assets/pages/ (kan upprepas)")
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="uppdatera en befintlig post")
    p_update.add_argument("id")
    p_update.add_argument("--title")
    add_entry_fields(p_update, "filnamn under web/assets/pages/ att lägga till (kan upprepas)")
    p_update.set_defaults(func=cmd_update)

    sub.add_parser("list", help="lista alla poster").set_defaults(func=cmd_list)
    sub.add_parser("build", help="bygg web/data/entries.json och sidorna under web/dokument/").set_defaults(func=cmd_build)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
