import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG = os.getenv("OPENAI_ORG")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")  # Falls du Unsplash nutzen willst

KAT_IDS = {
    "Gaming": 2,
    "IT": 3,
    "Mobile": 4,
    "Creator": 5,
}