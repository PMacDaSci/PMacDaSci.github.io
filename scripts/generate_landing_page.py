#!/usr/bin/env python3
"""
Generate the PMacDaSci GitHub Pages landing page from public organisation repositories.

The generated page keeps the polished static-page layout:
- hero section
- current workshop materials section
- historical/other materials section
- scheduled workshops call-to-action

Workshop cards are populated from GitHub repository metadata:
- repository name
- repository description
- homepage / website link
- GitHub repository URL
"""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ORG = "PMacDaSci"
LANDING_REPO = "PMacDaSci.github.io"
CONNECT_PAGE_URL = os.environ.get("CONNECT_PAGE_URL", "TODO_CONNECT_PAGE_URL")

# Curate display names and grouping while still pulling descriptions and links from GitHub.
# Set hidden=True to omit a repository from the landing page.
WORKSHOP_OVERRIDES: dict[str, dict[str, str | bool]] = {
    "docker-intro": {
        "title": "Reproducible Computational Environments using Containers",
        "group": "current",
    },
    "shell-novice": {
        "title": "Unix Shell / Bash",
        "group": "current",
    },
    "IntroPython-Bio": {
        "title": "Introduction to Python for Biological Data",
        "group": "current",
    },
    "REDCap_R": {
        "title": "Working with REDCap Data in R",
        "group": "current",
    },
    "nextflow-intro-workshop": {
        "title": "Introduction to Nextflow",
        "group": "current",
    },
    "IntroPython-pandas": {
        "title": "Introduction to Python and pandas",
        "group": "current",
    },
    "IntroR": {
        "title": "Introduction to R",
        "group": "current",
    },
    "R4CancerSci": {
        "title": "R Skills Building for Cancer Scientists",
        "group": "current",
    },
    "survival-analysis-intro": {
        "title": "Introduction to Survival Analysis",
        "group": "current",
    },
    "AI_Beyond_Omics_Workshop": {
        "title": "AI Beyond Omics Workshop",
        "group": "current",
    },
    "plotting_challenges": {
        "title": "Plotting Challenges",
        "group": "current",
    },
    "r-intro-tidyverse": {
        "title": "Introduction to R Tidyverse",
        "group": "current",
    },
}


@dataclass
class Repo:
    name: str
    title: str
    description: str
    repo_url: str
    homepage: str
    updated_at: str
    group: str


def github_api(url: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PMacDaSci.github.io landing-page-generator",
    }

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data, dict(response.headers)
    except urllib.error.HTTPError as exc:
        print(f"GitHub API request failed: {exc.code} {exc.reason}", file=sys.stderr)
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        raise


def parse_next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None

    for part in link_header.split(","):
        section = part.strip().split(";")
        if len(section) < 2:
            continue
        if section[1].strip() == 'rel="next"':
            return section[0].strip().strip("<>")
    return None


def fetch_repositories() -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    url = f"https://api.github.com/orgs/{ORG}/repos?type=public&per_page=100&sort=updated"

    while url:
        page, headers = github_api(url)
        repos.extend(page)
        url = parse_next_link(headers.get("Link"))

    return repos


def humanise_repo_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").strip().title()


def normalise_homepage(homepage: str | None) -> str:
    homepage = (homepage or "").strip()
    if homepage and not homepage.startswith(("http://", "https://")):
        homepage = f"https://{homepage}"
    return homepage


def infer_group(repo_name: str, homepage: str, archived: bool) -> str:
    if archived:
        return "historical"
    if repo_name in WORKSHOP_OVERRIDES:
        return str(WORKSHOP_OVERRIDES[repo_name].get("group", "current"))
    if homepage:
        return "current"
    return "historical"


def build_workshops(raw_repos: list[dict[str, Any]]) -> list[Repo]:
    workshops: list[Repo] = []

    for raw in raw_repos:
        name = raw["name"]
        if name == LANDING_REPO:
            continue

        override = WORKSHOP_OVERRIDES.get(name, {})
        if override.get("hidden") is True:
            continue

        homepage = normalise_homepage(str(override.get("homepage") or raw.get("homepage") or ""))
        description = str(
            override.get("description")
            or raw.get("description")
            or "Workshop materials from the PMacDaSci GitHub organisation."
        )

        workshops.append(
            Repo(
                name=name,
                title=str(override.get("title") or humanise_repo_name(name)),
                description=description,
                repo_url=str(raw["html_url"]),
                homepage=homepage,
                updated_at=str(raw.get("updated_at") or ""),
                group=infer_group(name, homepage, bool(raw.get("archived", False))),
            )
        )

    return sorted(workshops, key=lambda repo: repo.title.lower())


def render_cards(workshops: list[Repo]) -> str:
    cards: list[str] = []

    for workshop in workshops:
        material_url = workshop.homepage or workshop.repo_url
        badge = "Workshop site" if workshop.homepage else "Repository"

        cards.append(f"""        <article class="card">
          <div class="card-header">
            <span class="badge">{html.escape(badge)}</span>
            <span class="repo-name">{html.escape(workshop.name)}</span>
          </div>
          <h3>{html.escape(workshop.title)}</h3>
          <p>{html.escape(workshop.description)}</p>
          <div class="card-links">
            <a href="{html.escape(material_url)}">Open materials</a>
            <a href="{html.escape(workshop.repo_url)}">View repository</a>
          </div>
        </article>""")

    return "\n".join(cards)


def render_index(workshops: list[Repo]) -> str:
    current = [workshop for workshop in workshops if workshop.group == "current"]
    historical = [workshop for workshop in workshops if workshop.group != "current"]

    current_cards = render_cards(current)
    historical_cards = render_cards(historical)

    historical_section = ""
    if historical_cards:
        historical_section = f"""
    <section class="section compact-section">
      <h2>Other and historical materials</h2>
      <p class="section-intro">
        Additional repositories from previous workshops and related training activities.
      </p>

      <div class="cards">
{historical_cards}
      </div>
    </section>
"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Peter Mac Informatics Consulting Training</title>
  <meta name="description" content="Training workshops from the Research Computing Facility at the Peter MacCallum Cancer Centre.">
  <link rel="stylesheet" href="assets/styles.css">
</head>
<body>
  <header class="hero">
    <div class="container">
      <p class="eyebrow">Research Computing Facility</p>
      <h1>Peter Mac Informatics Consulting Training</h1>
      <p class="lead">
        This is an initiative led by the Research Computing Facility at the Peter MacCallum Cancer Centre
        to empower researchers and students with the data science tools and skills needed to analyse
        their own data.
      </p>
      <div class="actions">
        <a class="button primary" href="#workshops">View current materials</a>
        <a class="button secondary" href="{html.escape(CONNECT_PAGE_URL)}">Scheduled workshops</a>
      </div>
    </div>
  </header>

  <main class="container">
    <section id="workshops" class="section">
      <h2>Current workshop materials</h2>
      <p class="section-intro">
        Browse current training materials automatically generated from the public repositories in the
        <a href="https://github.com/{ORG}">{ORG} GitHub organisation</a>.
      </p>

      <div class="cards">
{current_cards}
      </div>
    </section>
{historical_section}
    <section class="section schedule">
      <h2>Scheduled workshops</h2>
      <p>
        Upcoming sessions are listed on the Peter Mac Connect page.
      </p>
      <a class="button primary" href="{html.escape(CONNECT_PAGE_URL)}">View scheduled workshops</a>
    </section>
  </main>

  <footer>
    <div class="container">
      <p>Peter MacCallum Cancer Centre · Research Computing Facility</p>
      <p><a href="https://github.com/{ORG}">GitHub organisation</a></p>
    </div>
  </footer>
</body>
</html>
"""


def main() -> None:
    raw_repos = fetch_repositories()
    workshops = build_workshops(raw_repos)
    Path("index.html").write_text(render_index(workshops), encoding="utf-8")
    print(f"Generated index.html with {len(workshops)} workshop/repository cards.")


if __name__ == "__main__":
    main()
