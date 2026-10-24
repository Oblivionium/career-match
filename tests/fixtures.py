from shared.models import JobListing

RESUME_STRONG = """Priya Sharma
priya.sharma@example.com | github.com/priya
EDUCATION
B.Tech Computer Science, ABC Institute of Technology, 2023 - present (expected 2027), CGPA 8.7
SKILLS
Python, PyTorch, scikit-learn, SQL, Git, Docker, Flask, pandas, NumPy
PROJECTS
Resume classifier: trained a PyTorch model to categorise 5,000 resumes (91% accuracy).
Movie recommender: Flask REST API with collaborative filtering, deployed with Docker.
EXPERIENCE
ML research intern, college AI lab (summer 2025): built data pipelines in pandas.
"""

RESUME_WEAK = """Rahul Verma
rahul@example.com
EDUCATION
B.Com, XYZ College, 2022 - 2025
SKILLS
Excel, communication, social media
PROJECTS
Ran the college fest Instagram page and grew it to 3k followers.
"""

JOBS = [
    JobListing(id="job_aaaaaaaaaa", title="Machine Learning Intern", company="DeepCo",
               location="Bangalore", url="https://example.com/1", source="Test",
               description="Work with Python, PyTorch and SQL. Docker is a plus. Kubernetes nice to have.",
               is_internship=True, posted=""),
    JobListing(id="job_bbbbbbbbbb", title="Senior Backend Engineer", company="BigCorp",
               location="Pune", url="https://example.com/2", source="Test",
               description="Java, Spring Boot, Kubernetes, AWS. 6+ years of experience required."),
    JobListing(id="job_cccccccccc", title="Data Analyst Intern", company="DataHouse",
               location="Remote", url="https://example.com/3", source="Test", remote=True,
               description="Excel, SQL, Power BI and Python for reporting.", is_internship=True),
    JobListing(id="job_dddddddddd", title="Social Media Marketing Intern", company="BrandLab",
               location="Delhi", url="https://example.com/4", source="Test", is_internship=True,
               description="Social media, content writing, Excel reports, communication."),
]
