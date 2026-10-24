import asyncio

import httpx
import pytest
from tools import github as repo_trail


def test_parse_repository_url_accepts_repo_and_git_urls():
    assert repo_trail.parse_repository_url("https://github.com/octocat/hello-world") == (
        "octocat",
        "hello-world",
    )
    assert repo_trail.parse_repository_url("https://github.com/octocat/hello-world.git") == (
        "octocat",
        "hello-world",
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com.evil.example/octocat/hello-world",
        "https://gitlab.com/octocat/hello-world",
        "not a URL",
        "https://github.com/octocat",
    ],
)
def test_parse_repository_url_rejects_invalid_urls(url):
    with pytest.raises(repo_trail.RepositoryError):
        repo_trail.parse_repository_url(url)


def test_rank_source_paths_prefers_matching_files_and_skips_secrets():
    paths = [
        "src/app.py",
        "src/login_handler.py",
        "src/payment.py",
        ".env",
        "config/credentials.json",
        "README.md",
    ]

    selected = repo_trail.rank_source_paths(paths, "explain the login handler")

    assert selected[0] == "src/login_handler.py"
    assert ".env" not in selected
    assert "config/credentials.json" not in selected
    assert "README.md" not in selected


def test_get_repository_context_reads_public_repo_with_github_api(monkeypatch):
    async def github_handler(request):
        path = request.url.path
        if path == "/repos/octocat/hello-world":
            return httpx.Response(
                200,
                json={
                    "full_name": "octocat/hello-world",
                    "description": "A sample project",
                    "default_branch": "main",
                },
            )
        if path == "/repos/octocat/hello-world/git/trees/main":
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {"path": "src/login_handler.py", "type": "blob"},
                        {"path": "src/app.py", "type": "blob"},
                        {"path": ".env", "type": "blob"},
                    ]
                },
            )
        if path == "/repos/octocat/hello-world/readme":
            return httpx.Response(200, text="# Sample project")
        if path.endswith("/contents/src/login_handler.py"):
            return httpx.Response(200, text="def login():\n    return True")
        if path.endswith("/contents/src/app.py"):
            return httpx.Response(200, text="from login_handler import login")
        pytest.fail(f"Unexpected GitHub API request: {request.url}")

    transport = httpx.MockTransport(github_handler)
    real_async_client = httpx.AsyncClient

    def mocked_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(repo_trail.httpx, "AsyncClient", mocked_async_client)

    context = asyncio.run(
        repo_trail.get_repository_context(
            "https://github.com/octocat/hello-world", "explain login"
        )
    )

    assert "Repository: octocat/hello-world" in context
    assert "# Sample project" in context
    assert "Source file: src/login_handler.py" in context
    assert "def login():" in context
    assert "Source file: .env" not in context
