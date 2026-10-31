# nzl-thu.github.io

Source of [nzl-thu.github.io](https://nzl-thu.github.io), Zanlin Ni's homepage: a home page (bio, news, publications) and a CV page, in English at `/` and Chinese at `/zh/`.

## Editing

All text is in `content/`:

| File | What it holds |
| --- | --- |
| `content/site.toml` | name, links, bio (en / zh), number of news items on the homepage |
| `content/news.toml` | news items, newest first |
| `content/publications.toml` | every paper (all listed on the homepage); list order is display order |
| `content/cv.toml` | education, experience, grants, honors |

Inline text supports `**bold**`, `[label](https://…)` and internal links such as `[label](page:cv)` or `[label](page:home#publications)`.
Styles are in `static/css/site.css`; the portrait is `static/img/zanlin-ni.jpg`.

## Building

```sh
uv run --python 3.12 build.py                 # production build -> dist/
uv run --python 3.12 build.py --relative --out /tmp/site   # open /tmp/site/index.html from disk
```

`build.py` uses only the Python standard library (3.11+). Pushing to `main` runs `.github/workflows/deploy.yml`, which builds the site and publishes `dist/` to the `gh-pages` branch.
