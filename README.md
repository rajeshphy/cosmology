# Cosmology Brief

A GitHub Actions + Jekyll project that generates a daily **Cosmology Brief** with two sections:

1. **Cosmology News** — up to 5 selected items.
2. **Jobs and Fellowships** — up to 5 selected India-relevant opportunities for postdocs, scientists, faculty, and assistant-professor-style academic roles.

The researcher profile assumed in the source ranking is: **resident of India**. Therefore, Indian institutes and India-eligible fellowships are weighted highest, while global portals are retained as useful awareness links but are not allowed to break the build.

## Important key name

Set the Gemini API key in GitHub Secrets as:

```text
COSMOLOGY_API_KEY
```

You can run without AI:

```bash
./run.sh no-ai
```

You can run with Gemini:

```bash
./run.sh generate
```

## GitHub Pages baseurl

The Jekyll base URL is set to:

```yaml
baseurl: /cosmology
```

This is present in both:

- `docs/_config.yml`
- `config/sources.yml`
- compatibility copy: `config/settings.yml`

## Source configuration

Main source file:

```text
config/sources.yml
```

Compatibility copies are also generated:

```text
config/settings.yml
config/news_sources.yml
config/job_sources.yml
```

The Python loader prefers `config/sources.yml`, so that is the main file to edit.

## Why some job portals are marked as `portal`

Many academic job boards block automated fetches, require JavaScript, or produce SSL problems on local Python installations. Examples include AAS, FindAPostDoc, Nature Careers, and some institutional pages.

To avoid failed runs like:

```text
HTTP Error 403: Forbidden
SSL: CERTIFICATE_VERIFY_FAILED
HTTP Error 404: Not Found
```

these sources are retained as **portal cards** and are not fetched automatically. They still appear in the source index and can be clicked manually. Machine-readable or more stable sources, such as INSPIRE API and RSS/Atom feeds, remain actively fetched.

## Fixed sources from the reported errors

- Sky & Telescope RSS was changed to a portal page because the feed can return 403.
- PRL URL corrected to `https://www.prl.res.in/prl-eng/job_vacancies`.
- RRI URL corrected to `https://www.rri.res.in/careers/regular-other-openings`.
- IIA URL corrected to `https://www.iiap.res.in/iia_jobs/?q=job_postings`.
- HRI retained as portal/static India-relevant opportunity pages to avoid local SSL-chain failures.
- AAS and FindAPostDoc are retained as portal links because they can block automated fetches.

## Project structure

```text
.
├── config/
│   ├── sources.yml
│   ├── settings.yml
│   ├── news_sources.yml
│   └── job_sources.yml
├── docs/
│   ├── _config.yml
│   ├── index.md
│   ├── assets/main.css
│   ├── _layouts/
│   └── _posts/
├── src/
│   ├── ai.py
│   ├── common.py
│   ├── fetch.py
│   ├── filter.py
│   ├── main.py
│   ├── markdown.py
│   └── validate_sources.py
├── .github/workflows/daily.yml
├── run.sh
├── requirements.txt
└── Gemfile
```

## Validation

Check Python syntax:

```bash
python3 -m py_compile src/*.py
```

Run generation without AI:

```bash
./run.sh no-ai
```

Optional source validator:

```bash
python3 -m src.validate_sources
```

Portal-only sources are intentionally skipped by the validator.

## Notes

- The fallback system prevents bad sources from stopping the whole daily build.
- For job links, always verify deadline, nationality rules, host requirements, and visa eligibility on the original page.
- The output is generated under `docs/_posts/` for GitHub Pages/Jekyll.
