# Fetch-A-Thon

A collaborative agentic AI project built for **Fetch-A-Thon 3.0**, using the Fetch.ai ecosystem.

## Overview

This repository contains the source code for our hackathon project. The goal is to build an agentic AI application that can reason about user requests, execute tasks using tools, and coordinate agent workflows.

> Project details and architecture will be documented as development progresses.

## Tech Stack

- **Language:** Python
- **Agent Framework:** Fetch.ai uAgents
- **Agent Communication:** Agent Chat Protocol (ACP)
- **LLM Client:** OpenAI-compatible API client for ASI1
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

Add the required API keys and configuration values to `.env` when they are defined by the project.

**Never commit `.env` or expose API keys in source code.**

### 5. Verify the setup

```zsh
python -m pip check
python -c "from uagents import Agent, Context, Protocol; print('uAgents setup OK')"
pytest
```

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
├── agents/          # Agent definitions and handlers
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
