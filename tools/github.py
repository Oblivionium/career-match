import os
import re
from urllib.parse import quote, urlparse

import httpx

IGNORED_FILE_NAMES = {
    ".env",
    ".env.example",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.json",
}
SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".c", ".h", ".cpp", ".cs", ".rb", ".php", ".swift", ".kt",
    ".vue", ".svelte", ".sql", ".sh",
}
MAX_TREE_FILES = 500
MAX_SOURCE_FILES = 6
MAX_FILE_CHARS = 9_000
MAX_CONTEXT_CHARS = 34_000


class RepositoryError(Exception):
    """An expected GitHub lookup or repository-content failure."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def parse_repository_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
        raise RepositoryError("Please share a repository URL from github.com.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise RepositoryError("I need a repository URL in the form https://github.com/owner/repo.")

    owner, repository = parts[0], parts[1]
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository:
        raise RepositoryError("I couldn't read the owner and repository from that URL.")
    return owner, repository


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "RepoTrail-uAgent",
    }
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


async def _github_get(client: httpx.AsyncClient, url: str, *, raw: bool = False) -> httpx.Response:
    headers = _github_headers()
    if raw:
        headers["Accept"] = "application/vnd.github.raw+json"
    try:
        response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise RepositoryError("I couldn't reach GitHub just now. Please try again shortly.") from exc

    if response.status_code == 404:
        raise RepositoryError(
            "I couldn't find that public repository or file. Check the URL; private repositories aren't supported yet.",
            status_code=404,
        )
    if response.status_code in {403, 429}:
        raise RepositoryError(
            "GitHub is rate limiting requests. Add a GitHub token in GITHUB_TOKEN or try again later.",
            status_code=response.status_code,
        )
    if response.is_error:
        raise RepositoryError(f"GitHub returned an error ({response.status_code}) while I was reading the repository.")
    return response


def rank_source_paths(paths: list[str], question: str) -> list[str]:
    words = set(re.findall(r"[a-z0-9]+", question.lower()))
    scored: list[tuple[int, str]] = []
    for path in paths:
        lower_path = path.lower()
        basename = lower_path.rsplit("/", 1)[-1]
        if basename in IGNORED_FILE_NAMES or basename.startswith(".env"):
            continue
        if not any(lower_path.endswith(suffix) for suffix in SOURCE_SUFFIXES):
            continue

        path_words = set(re.findall(r"[a-z0-9]+", lower_path.replace("_", " ").replace("-", " ")))
        score = len(words & path_words) * 4
        if any(word in lower_path for word in ("main", "app", "index", "route", "handler")):
            score += 1
        if lower_path.startswith(("src/", "app/", "agents/", "agent/")):
            score += 1
        scored.append((score, path))

    scored.sort(key=lambda entry: (-entry[0], len(entry[1]), entry[1]))
    return [path for _, path in scored[:MAX_SOURCE_FILES]]


async def get_repository_context(repository_url: str, question: str) -> str:
    owner, repository = parse_repository_url(repository_url)
    api_root = f"https://api.github.com/repos/{quote(owner)}/{quote(repository)}"

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        repo_response = await _github_get(client, api_root)
        repo = repo_response.json()
        branch = repo.get("default_branch") or "main"

        tree_response = await _github_get(
            client,
            f"{api_root}/git/trees/{quote(branch, safe='')}?recursive=1",
        )
        tree_data = tree_response.json()
        entries = tree_data.get("tree", [])
        paths = [
            item["path"]
            for item in entries[:MAX_TREE_FILES]
            if item.get("type") == "blob" and isinstance(item.get("path"), str)
        ]

        context_parts = [
            f"Repository: {repo.get('full_name', f'{owner}/{repository}')}",
            f"Description: {repo.get('description') or 'No description provided.'}",
            f"Default branch: {branch}",
            "Top-level files: " + ", ".join(path for path in paths if "/" not in path)[:3_000],
            "Repository file tree (truncated):\n" + "\n".join(paths[:MAX_TREE_FILES]),
        ]

        try:
            readme_response = await _github_get(client, f"{api_root}/readme", raw=True)
            readme = readme_response.text[:8_000]
            if readme.strip():
                context_parts.append(f"README (excerpt):\n{readme}")
        except RepositoryError as exc:
            # Some repositories do not have a README; source files can still explain them.
            if exc.status_code != 404:
                raise

        for path in rank_source_paths(paths, question):
            encoded_path = quote(path, safe="/")
            file_url = f"{api_root}/contents/{encoded_path}?ref={quote(branch, safe='')}"
            try:
                file_response = await _github_get(client, file_url, raw=True)
            except RepositoryError as exc:
                context_parts.append(f"Could not load {path}: {exc}")
                continue
            source = file_response.text[:MAX_FILE_CHARS]
            if source.strip():
                context_parts.append(f"Source file: {path}\n```\n{source}\n```")

    return "\n\n".join(context_parts)[:MAX_CONTEXT_CHARS]
