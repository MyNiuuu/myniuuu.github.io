# myniuuu.github.io

Personal academic homepage.

## GitHub star counts

The `data-github-repo="owner/repository"` attribute on each paper in `index.html`
is the repository list. Selected and full publication entries can share the same
attribute; counts are summed once per GitHub repository ID, including after renames.
Works without a confirmed repository have no attribute and no star count.

`data/github-stars.json` holds the last complete snapshot. The updater renders the
same snapshot into the top summary, every paper, and `github-stars.html`, so counts are immediately
visible without JavaScript or third-party badge requests. If any API request fails,
the updater fails without replacing the snapshot or the HTML. The visible update
date is in Japan time.

The homepage total links to `github-stars.html`, a text-only repository list sorted
by descending stars. Repository IDs are deduplicated here too. This page is generated
by the updater; do not edit it directly. Short work names normally come from the
repository name; `WORK_LABELS` in the script handles a few differently named projects.

```sh
python3 scripts/update_github_stars.py           # Fetch all counts and render
python3 scripts/update_github_stars.py --offline # Render the saved snapshot
python3 -m unittest discover -s tests           # Check deduplication and failures
```

When adding a paper, include its `data-github-repo` attribute and the usual
`<p class="paper-links">` row. The updater adds the star link automatically.
Keep the `github-stars:summary` markers in place. To remove a repository, remove
its attribute and generated badge block from all entries, then run the updater.

## Daily updates on GitHub

`.github/workflows/update-github-stars.yml` runs daily at approximately 10:23 JST,
on relevant pushes to `main`, and manually through **Actions → Update GitHub stars
→ Run workflow**. It uses the built-in `GITHUB_TOKEN`; no personal token is needed.
The workflow commits the JSON and both rendered HTML pages together, then explicitly requests
a Pages rebuild because bot commits do not trigger branch-based Pages builds.

This workflow is for **Settings → Pages → Deploy from a branch → main / (root)**.
It preserves that publishing setup and does not change repository settings. After
pushing these files, check the first workflow run: repository policies must allow
the workflow's `contents: write` and `pages: write` permissions and a direct bot push
to the publishing branch. The remote run/deployment cannot be tested by a local preview.
GitHub may delay scheduled jobs and disables schedules in public repositories after
60 days without repository activity; the manual run remains available.
