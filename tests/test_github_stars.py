import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stars", ROOT / "scripts/update_github_stars.py")
stars = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stars)
DATE = "2026-10-11T10:31:00+00:00"


def paper(repo=None):
    attribute = f' data-github-repo="{repo}"' if repo else ""
    return f'<article class="paper"{attribute}><p class="paper-links">code</p></article>'


def page(*repos):
    return "<!-- github-stars:summary:start --><!-- github-stars:summary:end -->" + "".join(map(paper, repos))


class GitHubStarsTests(unittest.TestCase):
    def test_selected_duplicates_and_renamed_repositories_count_once(self):
        names = stars.repositories_in(page("Owner/Old", "owner/old", "Owner/New", "Owner/Zero", None))
        self.assertEqual(names, ["owner/new", "owner/old", "owner/zero"])
        repo = {"id": 1, "name": "Owner/New", "stars": 768}
        snapshot = stars.build_snapshot(names, {
            "owner/new": repo, "owner/old": repo,
            "owner/zero": {"id": 2, "name": "Owner/Zero", "stars": 0},
        }, DATE)
        self.assertEqual(snapshot["total_stars"], 768)
        self.assertEqual(snapshot["repository_count"], 2)

    def test_render_new_entries_zero_counts_and_unlinked_papers(self):
        source = page("Owner/Repo", "Owner/Repo", "Owner/Zero", None)
        snapshot = stars.build_snapshot(stars.repositories_in(source), {
            "owner/repo": {"id": 1, "name": "Owner/Repo", "stars": 1234},
            "owner/zero": {"id": 2, "name": "Owner/Zero", "stars": 0},
        }, DATE)
        rendered = stars.render_html(source, snapshot)
        self.assertEqual(rendered.count('class="paper-stars"'), 3)
        self.assertIn("<strong>1,234</strong>", rendered)
        self.assertIn('class="github-stars-total" href="github-stars.html"', rendered)
        self.assertIn('src="https://img.shields.io/github/stars/Owner/Zero?style=social"', rendered)
        self.assertIn('alt="Owner/Zero GitHub stars"', rendered)
        self.assertIn(paper(None), rendered)
        self.assertEqual(stars.render_html(rendered, snapshot), rendered)

    def test_failed_fetch_preserves_all_saved_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            source = page("Owner/Good", "Owner/Unavailable")
            saved = '{"last": "successful snapshot"}\n'
            (root / "index.html").write_text(source)
            (root / "data/github-stars.json").write_text(saved)
            (root / "github-stars.html").write_text("previous repository list")

            def fetch(name):
                if name == "owner/unavailable":
                    raise RuntimeError("GitHub unavailable")
                return {"id": 1, "name": "Owner/Good", "stars": 99}

            with patch.object(stars, "fetch_repository", side_effect=fetch):
                with self.assertRaises(RuntimeError):
                    stars.refresh(root)
            self.assertEqual((root / "index.html").read_text(), source)
            self.assertEqual((root / "data/github-stars.json").read_text(), saved)
            self.assertEqual((root / "github-stars.html").read_text(), "previous repository list")

    def test_hidden_summary_keeps_homepage_unchanged(self):
        source = page("Owner/Repo").replace("<!-- github-stars:summary:start --><!-- github-stars:summary:end -->", "")
        snapshot = stars.build_snapshot(stars.repositories_in(source), {
            "owner/repo": {"id": 1, "name": "Owner/Repo", "stars": 7},
        }, DATE)
        rendered = stars.render_html(source, snapshot)
        self.assertNotIn("github-stars:summary:start", rendered)
        self.assertIn("class=\"paper-stars\"", rendered)

    def test_incomplete_snapshot_is_not_treated_as_zero(self):
        with self.assertRaises(KeyError):
            stars.build_snapshot(["owner/missing"], {}, DATE)
        for invalid in (-1, True, "12", None):
            with self.assertRaises(ValueError):
                stars.build_snapshot(["owner/repo"], {
                    "owner/repo": {"id": 1, "name": "Owner/Repo", "stars": invalid},
                }, DATE)

    def test_edits_made_during_fetch_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            source = page("Owner/Repo")
            edited = source + "<!-- new user edit -->"
            (root / "index.html").write_text(source)
            (root / "data/github-stars.json").write_text("saved snapshot")

            def fetch(name):
                (root / "index.html").write_text(edited)
                return {"id": 1, "name": "Owner/Repo", "stars": 7}

            with patch.object(stars, "fetch_repository", side_effect=fetch):
                with self.assertRaisesRegex(RuntimeError, "homepage changed"):
                    stars.refresh(root)
            self.assertEqual((root / "index.html").read_text(), edited)
            self.assertEqual((root / "data/github-stars.json").read_text(), "saved snapshot")

    def test_generated_pages_match_saved_snapshot(self):
        source = (ROOT / "index.html").read_text()
        saved = json.loads((ROOT / "data/github-stars.json").read_text())
        checked = stars.build_snapshot(stars.repositories_in(source), saved["repositories"], saved["updated_at"])
        self.assertEqual(checked, saved)
        self.assertEqual(stars.render_html(source, checked), source)
        self.assertEqual(stars.render_repository_list(checked), (ROOT / "github-stars.html").read_text())

    def test_repository_list_is_sorted_and_deduplicated(self):
        repo = {"id": 1, "name": "Owner/Most", "stars": 99}
        snapshot = stars.build_snapshot(["owner/old", "owner/most", "owner/zero", "owner/less"], {
            "owner/old": repo, "owner/most": repo,
            "owner/zero": {"id": 2, "name": "Owner/Zero", "stars": 0},
            "owner/less": {"id": 3, "name": "Owner/Less", "stars": 20},
        }, DATE)
        result = stars.render_repository_list(snapshot)
        self.assertEqual(result.count('<li>'), 3)
        self.assertEqual(result.count('href="https://github.com/Owner/Most"'), 1)
        self.assertLess(result.index('>Most</a>'), result.index('>Less</a>'))
        self.assertLess(result.index('>Less</a>'), result.index('>Zero</a>'))
        self.assertIn('0 stars', result)


if __name__ == "__main__":
    unittest.main()
