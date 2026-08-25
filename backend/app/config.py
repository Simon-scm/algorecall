
import os
from dotenv import load_dotenv

load_dotenv()

SESSION_SECRET = os.environ["SESSION_SECRET"]
GITHUB_AUTHORIZE_URL = os.getenv("GITHUB_AUTHORIZE_URL")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI")