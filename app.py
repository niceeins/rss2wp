import feedparser
import openai
import requests
import os
from dotenv import load_dotenv

print("🚀 Starte News-Bot ...")
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

RSS_FEEDS = [
    "https://www.gamestar.de/rss/news.xml",
    "https://feeds.feedburner.com/Polygon",
    "https://www.pcgames.de/rss/rss.xml",
    "https://www.golem.de/rss.php?feed=ATOM1.0",
    "https://www.heise.de/rss/heise-atom.xml",
    "https://rss.engadget.com/rss.xml",
]

POSTED_TITLES_FILE = "posted_titles.txt"

def load_posted_titles():
    if not os.path.exists(POSTED_TITLES_FILE):
        return set()
    with open(POSTED_TITLES_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_posted_title(title):
    with open(POSTED_TITLES_FILE, "a", encoding="utf-8") as f:
        f.write(title + "\n")

posted_titles = load_posted_titles()

def make_prompt(text):
    return (
        "Fasse folgende News sehr kurz, modern, locker und verständlich zusammen. "
        "Streiche unnötige Infos und schreibe wie für ein junges Publikum:\n\n"
        f"{text}"
    )

for feed_url in RSS_FEEDS:
    print(f"\n🌐 Lese Feed: {feed_url}")
    feed = feedparser.parse(feed_url)
    if not feed.entries:
        print("⚠️ Keine Einträge gefunden.")
        continue

    for entry in feed.entries[:2]:
        title = entry.title.strip()
        if title in posted_titles:
            print(f"⏭️ Schon verarbeitet: {title}")
            continue

        summary = entry.summary.strip() if 'summary' in entry else entry.description.strip()
        link = entry.link.strip()
        print(f"📰 Hole News: {title}")

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Du bist ein cooler Tech- und Gaming-Redakteur für Social Media."},
                    {"role": "user", "content": make_prompt(summary)}
                ],
                temperature=0.9,
                max_tokens=300,
            )
            rewritten = response.choices[0].message.content.strip()
            print("✅ OpenAI-Antwort bekommen.")
        except Exception as e:
            print(f"❌ Fehler bei OpenAI: {e}")
            continue

        post_data = {
            "title": title,
            "content": f"{rewritten}\n\n[Quelle]({link})",
            "status": "draft"
        }

        try:
            wp_response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/posts",
                json=post_data,
                auth=(WP_USER, WP_APP_PASSWORD)
            )
            if wp_response.status_code == 201:
                print(f"📝 Entwurf erstellt: {title}")
                save_posted_title(title)
                posted_titles.add(title)
            else:
                print(f"❌ WP-Fehler: {wp_response.status_code} – {wp_response.text}")
        except Exception as e:
            print(f"❌ Fehler beim Senden an WP: {e}")

print("\n🏁 Fertig!")
