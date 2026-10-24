# Job Scout

Searches live job and internship listings across several public job APIs (Adzuna, JSearch,
Remotive, Arbeitnow) in parallel, then normalizes, deduplicates and caches them. Keeps working
when individual sources fail. Part of the CareerMatch multi-agent system.

**Input:** `JobQuery(role, location, remote_only, kind)`  **Output:** `JobResults`

Keywords: job search, internships, live job listings, remote jobs, hiring, careers
