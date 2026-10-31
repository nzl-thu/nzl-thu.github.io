#!/usr/bin/env python3
"""Build the homepage into a static site.

    uv run --python 3.12 build.py                          # production build -> dist/
    uv run --python 3.12 build.py --out /tmp/site --relative

--relative writes page-relative links (…/index.html) so the output can be opened
from disk; production builds use root-absolute clean URLs for GitHub Pages.
Content lives in content/*.toml, styles, fonts and the portrait in static/. Python >= 3.11.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import posixpath
import re
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
STATIC = ROOT / "static"

LANGS = ("en", "zh")
PAGE_PATHS = {"home": "", "cv": "cv/"}
# Old URLs kept alive as redirects: path -> (page, lang, anchor)
REDIRECTS = {
    "honors/": ("cv", "en", "#honors"),
    "news/": ("home", "en", ""),
    "publications/": ("home", "en", "#publications"),
    "zh/publications/": ("home", "zh", "#publications"),
}
LINK_ORDER = ("paper", "arxiv", "code", "project", "model")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

UI = {
    "en": {
        "html_lang": "en",
        "og_locale": "en_US",
        "home": "Home",
        "publications": "Publications",
        "cv": "CV",
        "switch": "中文",
        "switch_lang": "zh-CN",
        "skip": "Skip to content",
        "news": "News",
        "scholar_link": "Google Scholar →",
        "equal": "* denotes equal contribution.",
        "group_first": "First / co-first author",
        "group_collab": "Collaborations",
        "interests": "Research Interests",
        "education": "Education",
        "experience": "Research Experience",
        "grants": "Grants and Programs",
        "honors": "Honors and Awards",
        "pubs_summary": "{total} works, {first} as first or co-first author. [See all publications →](page:home#publications)",
        "links": {"paper": "Paper", "arxiv": "arXiv", "code": "Code", "project": "Project", "model": "Model"},
        "email": "Email",
        "updated": "Updated {month}",
        "not_found": "Page not found",
        "not_found_body": "The page you are looking for does not exist. [Back to the homepage](page:home).",
        "moved": "This page has moved.",
    },
    "zh": {
        "html_lang": "zh-CN",
        "og_locale": "zh_CN",
        "home": "首页",
        "publications": "论文",
        "cv": "简历",
        "switch": "EN",
        "switch_lang": "en",
        "skip": "跳到正文",
        "news": "动态",
        "scholar_link": "Google Scholar →",
        "equal": "* 表示共同第一作者。",
        "group_first": "第一 / 共同第一作者",
        "group_collab": "合作论文",
        "interests": "研究方向",
        "education": "教育经历",
        "experience": "研究实习",
        "grants": "科研项目与人才计划",
        "honors": "荣誉奖励",
        "pubs_summary": "共 {total} 项成果，其中第一 / 共同第一作者 {first} 项。[查看全部论文 →](page:home#publications)",
        "links": {"paper": "论文", "arxiv": "arXiv", "code": "代码", "project": "项目主页", "model": "模型"},
        "email": "邮箱",
        "updated": "更新于 {month}",
        "not_found": "页面不存在",
        "not_found_body": "你访问的页面不存在。[返回首页](page:home)。",
        "moved": "页面已移动。",
    },
}

ICONS = {
    "email": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m4 7.5 8 5.5 8-5.5"/></svg>',
    "scholar": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M5.242 13.769 0 9.5 12 0l12 9.5-5.242 4.269C17.548 11.249 14.978 9.5 12 9.5c-2.977 0-5.548 1.748-6.758 4.269zM12 10a7 7 0 1 0 0 14 7 7 0 0 0 0-14z"/></svg>',
    "github": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>',
}

FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" rx="14" fill="#1f4f99"/>'
    '<text x="32" y="42" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" '
    'font-size="26" font-weight="700" fill="#fff">ZN</text></svg>'
)


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


class Site:
    def __init__(self, out: Path, relative: bool):
        self.out = out
        self.relative = relative
        self.site = load("site")
        self.news = load("news")["news"]
        self.pubs = load("publications")["pub"]
        self.cv = load("cv")
        self.css_version = ""

    # ------------------------------------------------------------------ urls

    def page_path(self, page: str, lang: str) -> str:
        """Output path (relative to site root) of a page's index.html."""
        prefix = "zh/" if lang == "zh" else ""
        return f"{prefix}{PAGE_PATHS[page]}index.html"

    def href(self, target: str, current: str) -> str:
        """Link from the page written at `current` to the site path `target`.

        `target` is a site-root path such as "publications/index.html" or
        "static/css/site.css"; production builds drop the index.html.
        """
        if self.relative:
            return posixpath.relpath(target, posixpath.dirname(current) or ".")
        if target.endswith("index.html"):
            target = target[: -len("index.html")]
        return "/" + target

    def absolute(self, target: str) -> str:
        if target.endswith("index.html"):
            target = target[: -len("index.html")]
        return f"{self.site['url']}/{target}"

    # --------------------------------------------------------------- inline

    def inline(self, text: str, lang: str, current: str) -> str:
        """Escape text and render **bold** and [label](url) links."""
        out = esc(text)

        def link(m: re.Match) -> str:
            label, url = m.group(1), html.unescape(m.group(2))
            if url.startswith("page:"):
                page, _, anchor = url[5:].partition("#")
                url = self.href(self.page_path(page, lang), current) + (f"#{anchor}" if anchor else "")
            return f'<a href="{esc(url)}">{label}</a>'

        out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, out)
        out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
        return out

    # ------------------------------------------------------------ fragments

    def authors(self, pub: dict) -> str:
        names = []
        for name in pub["authors"]:
            name = esc(name)
            name = re.sub(r"Zanlin Ni(\*?)", r'<span class="me">Zanlin Ni\1</span>', name)
            names.append(name)
        return ", ".join(names)

    def pub_primary(self, pub: dict) -> str | None:
        links = pub.get("links", {})
        for key in ("project", "paper", "arxiv", "code"):
            if key in links:
                return links[key]
        return None

    def pub_html(self, pub: dict, lang: str) -> str:
        ui = UI[lang]
        links = pub.get("links", {})
        primary = self.pub_primary(pub)
        title = esc(pub["title"])
        if primary:
            title = f'<a href="{esc(primary)}">{title}</a>'

        venue = pub.get("venue_zh") if lang == "zh" and pub.get("venue_zh") else pub["venue"]
        venue_attr = f' title="{esc(pub["venue_full"])}"' if pub.get("venue_full") else ""
        meta = [f'<span class="venue"{venue_attr}>{esc(venue)}</span>']
        note = pub.get(f"note_{lang}")
        if note:
            meta.append(f'<span class="venue-note">{esc(note)}</span>')
        for award in pub.get("awards", []):
            detail = f' <span class="badge-detail">{esc(award["detail"])}</span>' if award.get("detail") else ""
            meta.append(f'<span class="badge badge-{esc(award["kind"])}">{esc(award[lang])}{detail}</span>')
        link_items = "".join(
            f'<a href="{esc(links[key])}">{esc(ui["links"][key])}</a>' for key in LINK_ORDER if key in links
        )
        if link_items:
            meta.append(f'<span class="pub-links">{link_items}</span>')

        return (
            f'<article class="pub" id="{esc(pub["id"])}">'
            f'<h4 class="pub-title">{title}</h4>'
            f'<p class="pub-authors">{self.authors(pub)}</p>'
            f'<p class="pub-meta">{"".join(meta)}</p>'
            "</article>"
        )

    def profile_html(self, lang: str, current: str, is_home: bool) -> str:
        s, t = self.site, self.site[lang]
        photo = self.href(f"static/img/{s['photo']}", current)
        tag = "h1" if is_home else "p"
        alt_lang = "zh-CN" if lang == "en" else "en"
        contact = [
            f'<li><a href="mailto:{esc(s["email"])}">{ICONS["email"]}<span>{esc(s["email"])}</span></a></li>',
            f'<li><a href="{esc(s["scholar"])}">{ICONS["scholar"]}<span>Google Scholar</span></a></li>',
            f'<li><a href="{esc(s["github"])}">{ICONS["github"]}<span>GitHub</span></a></li>',
        ]
        return (
            '<aside class="profile">'
            f'<img class="portrait" src="{esc(photo)}" alt="{esc(t["name"])}" width="512" height="512">'
            '<div class="profile-text">'
            f'<{tag} class="name">{esc(t["name"])} <span class="alt-name" lang="{alt_lang}">{esc(t["alt_name"])}</span></{tag}>'
            f'<p class="role">{'<span class="sep"> · </span>'.join(f"<span>{esc(part)}</span>" for part in t["role"].split(" · "))}</p>'
            f'<ul class="contact">{"".join(contact)}</ul>'
            "</div></aside>"
        )

    def news_date(self, iso: str, lang: str) -> str:
        year, month, _ = iso.split("-")
        return f"{year}.{month}" if lang == "zh" else f"{MONTHS[int(month) - 1]} {year}"

    def month_label(self, lang: str) -> str:
        year, month = self.site["updated"].split("-")
        return f"{year} 年 {int(month)} 月" if lang == "zh" else f"{MONTHS[int(month) - 1]} {year}"

    # ----------------------------------------------------------------- pages

    def home_main(self, lang: str, current: str) -> str:
        ui, t = UI[lang], self.site[lang]
        bio = "".join(f"<p>{self.inline(p, lang, current)}</p>" for p in t["bio"])
        news = "".join(
            f'<li><time datetime="{n["date"]}">{self.news_date(n["date"], lang)}</time>'
            f'<p>{self.inline(n[lang], lang, current)}</p></li>'
            for n in self.news[: self.site["news_limit"]]
        )
        groups = []
        for group in ("first", "collab"):
            items = [p for p in self.pubs if p["group"] == group]
            groups.append(
                f'<h3 class="subhead">{ui["group_" + group]} <span class="count">{len(items)}</span></h3>'
                f'<div class="pub-list">{"".join(self.pub_html(p, lang) for p in items)}</div>'
            )
        return (
            f'<section class="bio">{bio}</section>'
            f'<section class="section" aria-labelledby="news"><h2 id="news">{ui["news"]}</h2>'
            f'<ul class="news-list">{news}</ul></section>'
            f'<section class="section" aria-labelledby="publications">'
            f'<div class="section-head"><h2 id="publications">{ui["publications"]}</h2>'
            f'<a class="more" href="{esc(self.site["scholar"])}">{ui["scholar_link"]}</a></div>'
            f'<p class="section-note">{ui["equal"]}</p>'
            + "".join(groups)
            + "</section>"
        )

    def counts(self) -> dict:
        return {"total": len(self.pubs), "first": sum(p["group"] == "first" for p in self.pubs)}

    def timeline(self, entries: list, lang: str, current: str) -> str:
        rows = []
        for e in entries:
            period = e.get("period_zh") if lang == "zh" and e.get("period_zh") else e["period"]
            d = e[lang]
            detail = f'<p class="entry-detail">{self.inline(d["detail"], lang, current)}</p>' if d.get("detail") else ""
            rows.append(
                f'<li><div class="period">{esc(period)}</div><div class="entry">'
                f'<p class="entry-title">{esc(d["title"])}</p>'
                f'<p class="entry-org">{esc(d["org"])}</p>{detail}</div></li>'
            )
        return f'<ol class="timeline">{"".join(rows)}</ol>'

    def cv_main(self, lang: str, current: str) -> str:
        ui, cv = UI[lang], self.cv
        honors = "".join(
            f'<li><div class="period">{esc(h.get("year_zh") if lang == "zh" and h.get("year_zh") else h["year"])}</div>'
            f'<div class="entry"><p>{self.inline(h[lang], lang, current)}</p></div></li>'
            for h in cv["honors"]
        )
        summary = self.inline(ui["pubs_summary"].format(**self.counts()), lang, current)

        def section(key: str, body: str) -> str:
            return f'<section class="section" aria-labelledby="{key}"><h2 id="{key}">{ui[key]}</h2>{body}</section>'

        return (
            f'<h1 class="page-title">{ui["cv"]}</h1>'
            + section("interests", f'<p>{esc(cv["interests"][lang])}</p>')
            + section("education", self.timeline(cv["education"], lang, current))
            + section("experience", self.timeline(cv["experience"], lang, current))
            + section("grants", self.timeline(cv["grants"], lang, current))
            + section("honors", f'<ol class="timeline timeline--honors">{honors}</ol>')
            + section("publications", f"<p>{summary}</p>")
        )

    # ---------------------------------------------------------------- layout

    def document(self, page: str, lang: str, main: str, *, title: str, description: str) -> str:
        current = self.page_path(page, lang)
        ui, s, t = UI[lang], self.site, self.site[lang]
        other = "zh" if lang == "en" else "en"
        css = self.href("static/css/site.css", current) + f"?v={self.css_version}"
        font_href = self.href("static/fonts/inter-latin-wght-normal.woff2", current)
        favicon = self.href("static/favicon.svg", current)
        canonical = self.absolute(current)
        alternates = "".join(
            f'<link rel="alternate" hreflang="{UI[l]["html_lang"]}" href="{esc(self.absolute(self.page_path(page, l)))}">'
            for l in LANGS
        )
        photo_abs = f"{s['url']}/static/img/{s['photo']}"

        home = self.href(self.page_path("home", lang), current)
        nav = [
            (f'<a class="nav-home" href="{esc(home)}"' + (' aria-current="page"' if page == "home" else "") + f'>{ui["home"]}</a>'),
            f'<a class="nav-publications" href="{esc(home)}#publications">{ui["publications"]}</a>',
            (f'<a class="nav-cv" href="{esc(self.href(self.page_path("cv", lang), current))}"'
             + (' aria-current="page"' if page == "cv" else "") + f'>{ui["cv"]}</a>'),
        ]
        switch = self.href(self.page_path(page, other), current)
        nav.append(
            f'<a class="lang-switch" href="{esc(switch)}" lang="{ui["switch_lang"]}" hreflang="{ui["switch_lang"]}">{ui["switch"]}</a>'
        )

        jsonld = ""
        if page == "home":
            person = {
                "@context": "https://schema.org",
                "@type": "Person",
                "name": s["en"]["name"],
                "alternateName": s["zh"]["name"],
                "url": s["url"] + "/",
                "image": photo_abs,
                "email": "mailto:" + s["email"],
                "jobTitle": "Ph.D. Student",
                "affiliation": {"@type": "CollegeOrUniversity", "name": "Tsinghua University"},
                "sameAs": [s["scholar"], s["github"]],
            }
            jsonld = f'<script type="application/ld+json">{json.dumps(person, ensure_ascii=False)}</script>'

        return f"""<!DOCTYPE html>
<html lang="{ui["html_lang"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="{esc(canonical)}">
{alternates}
<meta property="og:type" content="profile">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(photo_abs)}">
<meta property="og:locale" content="{ui["og_locale"]}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="{esc(favicon)}" type="image/svg+xml">
<link rel="preload" href="{esc(font_href)}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{esc(css)}">
{jsonld}
</head>
<body class="page-{page}">
<a class="skip-link" href="#main">{ui["skip"]}</a>
<header class="topbar"><div class="topbar-inner">
<a class="brand" href="{esc(self.href(self.page_path("home", lang), current))}">{esc(t["name"])}</a>
<nav class="nav" aria-label="Main">{"".join(nav)}</nav>
</div></header>
<div class="layout">
{self.profile_html(lang, current, page == "home")}
<main id="main" class="content">
{main}
</main>
</div>
<footer class="footer"><div class="footer-inner">
<span>© {self.site["updated"][:4]} {esc(t["name"])}</span>
<span>{ui["updated"].format(month=self.month_label(lang))}</span>
</div></footer>
</body>
</html>
"""

    # ----------------------------------------------------------------- build

    def write(self, path: str, text: str) -> None:
        target = self.out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def build(self) -> None:
        if self.out.exists():
            shutil.rmtree(self.out)
        shutil.copytree(STATIC, self.out / "static", ignore=shutil.ignore_patterns(".DS_Store"))
        css = (STATIC / "css" / "site.css").read_bytes()
        self.css_version = hashlib.sha256(css).hexdigest()[:10]
        (self.out / "static" / "favicon.svg").write_text(FAVICON, encoding="utf-8")

        for lang in LANGS:
            ui, t = UI[lang], self.site[lang]
            pages = {
                "home": (self.home_main, t["title"], t["description"]),
                "cv": (self.cv_main, f'{ui["cv"]} · {t["name"]}', t["description"]),
            }
            for page, (render, title, description) in pages.items():
                current = self.page_path(page, lang)
                main = render(lang, current)
                self.write(current, self.document(page, lang, main, title=title, description=description))

        for old, (page, lang, anchor) in REDIRECTS.items():
            current = f"{old}index.html"
            target = self.href(self.page_path(page, lang), current) + anchor
            self.write(
                current,
                f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{UI["en"]["moved"]}</title>'
                f'<meta http-equiv="refresh" content="0; url={esc(target)}">'
                f'<link rel="canonical" href="{esc(self.absolute(self.page_path(page, lang)) + anchor)}">'
                f'<meta name="robots" content="noindex"></head>'
                f'<body><p><a href="{esc(target)}">{UI["en"]["moved"]}</a></p></body></html>\n',
            )

        if not self.relative:
            not_found = f'<h1 class="page-title">{UI["en"]["not_found"]}</h1><p>{self.inline(UI["en"]["not_found_body"], "en", "404.html")}</p>'
            doc = self.document("home", "en", not_found, title=UI["en"]["not_found"], description=self.site["en"]["description"])
            doc = (
                doc.replace('<body class="page-home">', '<body class="page-404">')
                .replace(' aria-current="page"', "")
                .replace('<h1 class="name">', '<p class="name">')
                .replace("</h1><p class=\"role\">", '</p><p class="role">')
            )
            self.write("404.html", doc)
            urls = [self.absolute(self.page_path(p, l)) for l in LANGS for p in PAGE_PATHS]
            self.write(
                "sitemap.xml",
                '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in urls)
                + "</urlset>\n",
            )
            self.write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {self.site['url']}/sitemap.xml\n")
            self.write(".nojekyll", "")


def load(name: str) -> dict:
    with open(CONTENT / f"{name}.toml", "rb") as f:
        return tomllib.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--relative", action="store_true", help="page-relative links for opening from disk")
    args = parser.parse_args()
    Site(args.out.resolve(), args.relative).build()
    print(f"built {args.out}")


if __name__ == "__main__":
    main()
