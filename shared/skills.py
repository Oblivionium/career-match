"""Skill vocabulary and normalization, shared by the resume parser and the matcher."""

import re

# canonical name -> aliases (lowercase)
SKILL_ALIASES: dict[str, list[str]] = {
    "Python": ["python", "python3"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "es6"],
    "TypeScript": ["typescript"],
    "C++": ["c++", "cpp"],
    "C": ["c language", "c programming"],
    "C#": ["c#", "csharp", ".net"],
    "Go": ["golang"],
    "Rust": ["rust"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "sqlite"],
    "MongoDB": ["mongodb", "mongo"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "tailwind", "bootstrap"],
    "React": ["react", "reactjs", "react.js"],
    "Next.js": ["next.js", "nextjs"],
    "Angular": ["angular"],
    "Vue": ["vue", "vuejs", "vue.js"],
    "Node.js": ["node", "nodejs", "node.js", "express.js", "expressjs"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring": ["spring boot", "springboot", "spring framework"],
    "Android": ["android"],
    "Flutter": ["flutter", "dart"],
    "Git": ["git", "github", "gitlab"],
    "Docker": ["docker", "containers"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services", "ec2", "s3", "lambda"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Linux": ["linux", "ubuntu", "bash", "shell scripting"],
    "REST APIs": ["rest api", "rest apis", "restful", "api development"],
    "GraphQL": ["graphql"],
    "Machine Learning": ["machine learning", "ml", "scikit-learn", "sklearn"],
    "Deep Learning": ["deep learning", "neural networks", "cnn", "rnn"],
    "TensorFlow": ["tensorflow", "keras"],
    "PyTorch": ["pytorch", "torch"],
    "NLP": ["nlp", "natural language processing"],
    "LLMs": ["llm", "llms", "langchain", "rag", "prompt engineering", "generative ai", "genai"],
    "Computer Vision": ["computer vision", "opencv"],
    "Data Analysis": ["data analysis", "data analytics", "pandas", "numpy"],
    "Excel": ["excel", "spreadsheets"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Statistics": ["statistics", "statistical"],
    "Figma": ["figma"],
    "UI/UX": ["ui/ux", "ux", "ui design", "user experience"],
    "DSA": ["data structures", "algorithms", "dsa", "competitive programming", "leetcode"],
    "OOP": ["oop", "object oriented", "object-oriented"],
    "Cybersecurity": ["cybersecurity", "penetration testing", "network security"],
    "Blockchain": ["blockchain", "solidity", "web3", "smart contracts"],
    "Agile": ["agile", "scrum", "jira"],
    "Communication": ["communication", "public speaking", "presentation"],
    "Marketing": ["marketing", "seo", "social media", "content writing"],
}

_PATTERNS = {
    canon: [re.compile(r"(?<![a-z0-9+#.])" + re.escape(a) + r"(?![a-z0-9+#])") for a in aliases]
    for canon, aliases in SKILL_ALIASES.items()
}
_ALIAS_TO_CANON = {a: c for c, al in SKILL_ALIASES.items() for a in al + [c.lower()]}


def extract_skills(text: str) -> list[str]:
    """Find known skills in free text. Order follows the vocabulary for stable output."""
    low = text.lower()
    return [canon for canon, pats in _PATTERNS.items() if any(p.search(low) for p in pats)]


def normalize_skill(skill: str) -> str:
    s = skill.strip()
    return _ALIAS_TO_CANON.get(s.lower(), s)


def normalize_skills(skills: list[str]) -> list[str]:
    seen, out = set(), []
    for s in skills:
        n = normalize_skill(s)
        if n and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out
