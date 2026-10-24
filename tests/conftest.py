import os
import sys
from pathlib import Path

# Tests never hit real LLM/payment/job APIs.
os.environ["USE_MAILBOX"] = "false"
os.environ["ASI_ONE_API_KEY"] = ""
os.environ["PAYMENTS_ENABLED"] = "false"
os.environ["ADZUNA_APP_ID"] = ""
os.environ["JSEARCH_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
