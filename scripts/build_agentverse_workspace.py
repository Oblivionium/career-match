"""Build a self-contained AVCTL workspace from the CareerMatch source tree.

The generated workspace is ignored by git because AVCTL writes deployment metadata
there. Source packages are copied into each hosted agent so every project can build
independently in Agentverse.
"""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".agentverse-workspace"

PROJECTS = {
    "CareerCoordinator": {
        "entry": "coordinator.agent",
        "description": "CareerMatch is the user-facing coordinator that reads resumes, finds suitable roles, ranks jobs, and prepares application packs.",
        "packages": ["coordinator", "shared", "models", "resume_analyst", "job_scout", "match_apply"],
        "dependencies": [
            "uagents==0.26.1",
            "uagents-core==0.4.12",
            "google-genai==2.33.0",
            "httpx>=0.27",
            "python-dotenv>=1.0",
            "cosmpy>=0.9.2",
        ],
        "env": {
            "RESUME_ADDR": "{{ .ResumeAnalyst.Address }}",
            "SCOUT_ADDR": "{{ .JobScout.Address }}",
            "MATCH_ADDR": "{{ .MatchApply.Address }}",
            "PAYMENTS_ENABLED": "true",
            "FET_USE_TESTNET": "true",
        },
        "readme": "coordinator.md",
    },
    "ResumeAnalyst": {
        "entry": "resume_analyst.agent",
        "description": "Extracts skills, education, experience level, and suitable roles from student and early-career resumes.",
        "packages": ["resume_analyst", "shared", "models"],
        "dependencies": [
            "uagents==0.26.1",
            "uagents-core==0.4.12",
            "google-genai==2.33.0",
            "httpx>=0.27",
            "python-dotenv>=1.0",
        ],
        "env": {},
        "readme": "resume_analyst.md",
    },
    "JobScout": {
        "entry": "job_scout.agent",
        "description": "Searches and normalizes live job and internship listings from public sources.",
        "packages": ["job_scout", "shared", "models"],
        "dependencies": [
            "uagents==0.26.1",
            "uagents-core==0.4.12",
            "httpx>=0.27",
            "python-dotenv>=1.0",
        ],
        "env": {},
        "readme": "job_scout.md",
    },
    "MatchApply": {
        "entry": "match_apply.agent",
        "description": "Ranks job listings against a candidate profile and writes tailored application packs.",
        "packages": ["match_apply", "shared", "models"],
        "dependencies": [
            "uagents==0.26.1",
            "uagents-core==0.4.12",
            "google-genai==2.33.0",
            "httpx>=0.27",
            "python-dotenv>=1.0",
        ],
        "env": {},
        "readme": "match_apply.md",
    },
}


def write_project(name: str, spec: dict) -> None:
    dest = OUTPUT / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for package in spec["packages"]:
        shutil.copytree(
            ROOT / package,
            dest / package,
            ignore=shutil.ignore_patterns("agent.py", "__pycache__"),
        )

    package, module = spec["entry"].split(".")
    shutil.copyfile(ROOT / package / f"{module}.py", dest / "agent.py")

    normalized_name = "career-match-" + name.lower()
    dependencies = ",\n    ".join(f'"{item}"' for item in spec["dependencies"])
    (dest / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["setuptools>=68"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[project]\n"
        f'name = "{normalized_name}"\n'
        'version = "0.1.0"\n'
        f'description = "{spec["description"]}"\n'
        'requires-python = ">=3.10,<3.14"\n'
        "dependencies = [\n    "
        + dependencies
        + "\n]\n\n"
        "[tool.setuptools.packages.find]\n"
        'where = ["."]\n'
        'include = ["coordinator*", "resume_analyst*", "job_scout*", "match_apply*", "shared*", "models*"]\n',
        encoding="utf-8",
    )

    env_lines = [f"{key}={value}" for key, value in spec["env"].items()]
    # These are environment-variable names only; values are entered as AVCTL secrets.
    env_lines.extend(
        [
            "GEMINI_API_KEY=",
            "ASI_ONE_API_KEY=",
            "ADZUNA_APP_ID=",
            "ADZUNA_APP_KEY=",
            "JSEARCH_API_KEY=",
        ]
    )
    (dest / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    readme = ROOT / "docs" / "agentverse_readmes" / spec["readme"]
    shutil.copyfile(readme, dest / "README.md")


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    for name, spec in PROJECTS.items():
        write_project(name, spec)
    print(f"Built AVCTL workspace at {OUTPUT}")
    print("The generated .env files contain no API key values; add keys as Agentverse secrets.")


if __name__ == "__main__":
    main()
