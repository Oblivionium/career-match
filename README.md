# RepoTrail

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

RepoTrail is a codebase learning agent built for **Fetch-A-Thon 3.0** with Fetch.ai uAgents and ASI:One. Give it a public GitHub repository and a question; it retrieves relevant repository context and returns a source-linked walkthrough, a suggested next step, and a small learning exercise.

## Overview

The primary workflow runs inside an ASI:One conversation through the Agent Chat Protocol (ACP). The agent reads public repository metadata, the README, the file tree, and a small set of likely relevant source files through GitHub's REST API. ASI:One explains the retrieved evidence and cites file paths.

The uAgent is named `repo_trail`; its Agentverse address is assigned from `AGENT_SEED` at runtime and is printed when it starts. Register/deploy it through Agentverse to make it discoverable in ASI:One.

## Tech Stack

- **Language:** Python
- **Agent Framework:** Fetch.ai uAgents
- **Agent Communication:** Agent Chat Protocol (ACP)
- **LLM:** ASI:One Chat Completions API
- **Repository data:** GitHub REST API
- **Testing:** pytest
- **Version Control:** Git and GitHub

## Getting Started

### Prerequisites

- Git
- Python 3.12
- Ubuntu on WSL2
- zsh shell
- Access to the private GitHub repository

### 1. Clone the repository

Open your WSL Ubuntu terminal:

```zsh
git clone https://github.com/Oblivionium/agent.git
cd agent
```

GitHub authentication is required because this repository is private. Use your configured Git credentials or SSH authentication if prompted.

### 2. Create a virtual environment

```zsh
python3 -m venv .venv
source .venv/bin/activate
```

If virtual environment creation fails, install the required Ubuntu package:

```zsh
sudo apt update
sudo apt install python3-venv
```

### 3. Install dependencies

```zsh
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create your local environment file:

```zsh
cp .env.example .env
```

Set `ASI_ONE_API_KEY` from your ASI:One developer account and choose a private, unique `AGENT_SEED`. `GITHUB_TOKEN` is optional and raises GitHub's API rate limit for public repository reads.

**Never commit `.env` or expose API keys in source code.**

### 5. Verify the setup

```zsh
python -m pip check
python -c "from uagents import Agent, Context, Protocol; print('uAgents setup OK')"
```

### Run RepoTrail

```zsh
python -m agents.agent
```

In ASI:One, ask a question with a public repository URL, for example:

```text
https://github.com/pallets/flask — explain how a request reaches a route handler
```

Then ask follow-up questions in the same conversation; RepoTrail remembers the repository for that sender while the agent process is running. Private repositories and writing to GitHub are not supported in this MVP.

## Development Workflow

We use feature branches to allow team members to work in parallel.

### Create a feature branch

```zsh
git switch main
git pull --ff-only origin main
git switch -c feat/your-feature
```

Choose a descriptive branch name, such as `feat/agent-core` or `feat/tools-api`.

### Commit and push changes

```zsh
git add .
git commit -m "feat: describe your change"
git push -u origin feat/your-feature
```

### Submit changes

1. Open a pull request on GitHub targeting `main`.
2. Request a review from a teammate.
3. Resolve review comments and ensure tests pass.
4. Merge the pull request after approval.

**Do not push directly to `main`.**

Before starting a new task, synchronize your local branch with the latest `main`.

## Project Structure

```text
agent/
├── agents/          # RepoTrail uAgent and GitHub analysis workflow
├── tools/           # External APIs and executable tools
├── workflows/       # Task orchestration
├── models/          # Request and response schemas
├── tests/           # Automated tests
├── .env.example     # Environment variable template
├── .gitignore
├── requirements.txt
├── README.md
└── LICENSE
```

## Team Guidelines

- Keep changes focused and commits descriptive.
- Coordinate before modifying shared interfaces.
- Write tests for new functionality.
- Keep dependencies documented in `requirements.txt`.
- Never commit credentials, private keys, or local virtual environments.
- Prefer small pull requests that are easy to review.

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.
