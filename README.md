# Dokumentera

Ett arkiv över svenska seriealbum, tidningar och fanzin som inte längre finns
att få tag på — utgångna upplagor, nedlagda förlag, publikationer som aldrig
trycktes om.

## Struktur

```
data/entries/<id>.md      en post: YAML-frontmatter för metadata + fri text i markdown, git-spårad
web/                      statisk sajt: index.html, app.js, style.css, git-spårade
web/data/entries.json     byggd av `cli.py build` — gitignorad, inte källa
web/dokument/<id>/index.html en färdig, statisk sida per post, också från `build` — gitignorad
web/sitemap.xml           sitemap, också från `build` — gitignorad
web/robots.txt            pekar på sitemap.xml, git-spårad
```

`web/data/entries.json`, `web/dokument/*` och `web/sitemap.xml` är
byggartefakter, skrivna direkt under `web/` (inga symlänkar) så att `web/`
kan serveras som den är, av vilken statisk filserver som helst. Redigera dem
aldrig för hand — kör `python3 cli.py build` efter varje ändring i
`data/entries/`. Varje sida har en `<link rel="canonical">` mot sin
`https://dokumentera.sekvenser.se/...`-URL.

## Kom igång

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python cli.py build
cd web && python3 -m http.server 8005
```

## CLI

- `add --title "..." [--id ...] [--creators "A, B"] [--publisher ...] [--year ...] [--type ...] [--language ...] [--pages ...] [--cover FILNAMN] [--example-page FILNAMN ...] [--more-info-url URL] [--author "..."]`
  Skapar `data/entries/<id>.md` med ifylld frontmatter och en textplatshållare
  att skriva vidare på för hand. `--author` är vem som skrivit/dokumenterat
  posten (skiljt från `--creators`, som är upphovspersonerna bakom själva
  utgåvan) och visas som en byline under texten.
- `update <id> [samma flaggor som add]`
  Uppdaterar fält i frontmatter på en befintlig post, texten under lämnas
  orörd. `--example-page` lägger till fler sidor (ersätter inte listan).
- `list`
  Listar alla poster.
- `build`
  Kompilerar `web/data/entries.json`, `web/sitemap.xml` och en statisk sida
  per post under `web/dokument/`.

Det finns ingen nedladdnings- eller scraping-logik i verktyget — bilder ska
läggas lokalt för hand, inga externa länkar. Lägg omslag under
`web/assets/covers/<filnamn>` och ange bara filnamnet i `--cover`
(`cover_image` i frontmatter), t.ex. `--cover mitt-fanzin.jpg` för
`web/assets/covers/mitt-fanzin.jpg`. Exempelsidor läggs på samma sätt under
`web/assets/pages/<filnamn>` och anges bara med filnamnet i `--example-page`
(`example_pages` i frontmatter).

## Deployment

Push till `main` kör `.github/workflows/pages.yml`: den installerar
`requirements.txt`, kör `python3 cli.py build` och publicerar hela `web/`
(byggartefakterna ovan ingår) via GitHub Pages. Kräver att repots
Pages-källa är satt till "GitHub Actions" (Settings → Pages).

Alla länkar och tillgångar i sajten är rotabsoluta (`/style.css`, `/app.js`,
`/data/...`, `/dokument/...`, `/assets/...`) och förutsätter att sajten körs
från domänens rot — precis som `SITE_URL` i `cli.py`, `robots.txt` och varje
`<link rel="canonical">` redan pekar mot `dokumentera.sekvenser.se`.
`web/CNAME` deklarerar den domänen åt GitHub Pages, men du måste även: peka
en DNS-post för `dokumentera.sekvenser.se` mot GitHub Pages, och sätta samma
domän under Settings → Pages → Custom domain. Utan det serveras sajten på
`https://<org>.github.io/dokumentera/` istället — då 404:ar allt utom
`index.html` självt, eftersom de rotabsoluta sökvägarna pekar fel.
