import feedparser
import openai
import requests
import os
import re
from dotenv import load_dotenv
import html

print("🚀 Starte News-Bot ...")
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Nutze die IDs aus deinem WordPress-System!
KAT_IDS = {
    "Gaming": 2,
    "IT": 3,
    "Crafting": 4,
    "New Tech": 5,
}

RSS_FEEDS = [
    # 🎮 Gaming
    "https://kotaku.com/rss",
    "https://www.vg247.com/feed",
    "https://www.gamespot.com/feeds/mashup",
    "https://www.polygon.com/rss/index.xml",
    "https://www.rockpapershotgun.com/feed",
    "https://www.gameinformer.com/rss",

    # 💻 IT
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
    "https://www.techradar.com/rss",

    # ✂️ Crafting
    "https://craftgossip.com/feed/",
    "https://craftsbyamanda.com/feed",
    "https://www.thecraftpatchblog.com/feed",
    "https://modpodgerocksblog.com/feed",
    "https://www.delphiglass.com/page/main_rss",

    # 🚀 New Tech
    "https://www.technologyreview.com/feed/",
    "https://www.engadget.com/rss.xml",
    "https://venturebeat.com/feed/",
    "https://gizmodo.com/rss",
    "https://www.makeuseof.com/feed/"
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

def make_prompt(text):
    return (
        "Fasse die folgende News für ein technikaffines, meist männliches Publikum im Alter von 24 bis 40 Jahren auf DEUTSCH zusammen, "
        "egal in welcher Sprache der Originaltext ist. "
        "Nutze moderne, lockere, aber trotzdem seriöse Sprache ohne Emotes, Smileys oder Jugendslang. "
        "Verwende maximal 5 kurze, prägnante Sätze. "
        "Wähle ein aussagekräftiges SEO-Schlagwort ('Focus Keyword'), das am besten zu dieser News passt. "
        "Verwende dieses Schlagwort mehrfach sinnvoll im Text und schreibe suchmaschinenoptimiert, aber lesbar. "
        "Am Ende gib exakt eine der folgenden Kategorien für den Beitrag in der Form [Kategorie: <Name>] (ohne weiteren Text) an: "
        "Gaming, IT, Crafting, New Tech. "
        "Danach gib in der Form [Schlagwort: <Keyword>] (ohne weiteren Text) das gewählte SEO-Schlagwort an.\n\n"
        f"{text}"
    )

def get_or_create_tag_id(tag_name):
    if not tag_name:
        return None
    # Prüfe, ob Tag schon existiert
    response = requests.get(
        f"{WP_URL}/wp-json/wp/v2/tags",
        params={"search": tag_name},
        auth=(WP_USER, WP_APP_PASSWORD)
    )
    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            return data[0]['id']
    # Sonst Tag anlegen
    response = requests.post(
        f"{WP_URL}/wp-json/wp/v2/tags",
        json={"name": tag_name},
        auth=(WP_USER, WP_APP_PASSWORD)
    )
    if response.status_code == 201:
        return response.json()['id']
    return None

posted_titles = load_posted_titles()

for feed_url in RSS_FEEDS:
    print(f"\n🌐 Lese Feed: {feed_url}")
    feed = feedparser.parse(feed_url)
    if not feed.entries:
        print("⚠️ Keine Einträge gefunden.")
        continue

    for entry in feed.entries[:2]:
        title = html.unescape(entry.title.strip())
        if title in posted_titles:
            print(f"⏭️ Schon verarbeitet: {title}")
            continue

        summary = html.unescape(entry.summary.strip() if 'summary' in entry else entry.description.strip())
        link = entry.link.strip()
        print(f"📰 Hole News: {title}")

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Du bist ein moderner, deutschsprachiger Tech-Redakteur."},
                    {"role": "user", "content": make_prompt(summary)}
                ],
                temperature=0.8,
                max_tokens=500,
            )
            full_reply = response.choices[0].message.content.strip()
            print("✅ OpenAI-Antwort bekommen.")
            # Kategorie extrahieren
            kategorie_match = re.search(r"\[Kategorie:\s*(.*?)\]", full_reply)
            kategorie_name = kategorie_match.group(1).strip() if kategorie_match else "IT"
            # Schlagwort extrahieren
            keyword_match = re.search(r"\[Schlagwort:\s*(.*?)\]", full_reply)
            focus_keyword = keyword_match.group(1).strip() if keyword_match else ""
            # Text bereinigen
            rewritten = re.sub(r"\[Kategorie:.*?\]", "", full_reply)
            rewritten = re.sub(r"\[Schlagwort:.*?\]", "", rewritten).strip()
            print(f"⚡ Kategorie erkannt: {kategorie_name} / Schlagwort: {focus_keyword}")
        except Exception as e:
            print(f"❌ Fehler bei OpenAI: {e}")
            continue

        # Kategorie-ID holen, Default ist "IT"
        kat_id = KAT_IDS.get(kategorie_name, KAT_IDS["IT"])
        tag_id = get_or_create_tag_id(focus_keyword)

        post_data = {
            "title": title,
            "content": f"{rewritten}\n\n[Quelle]({link})",
            "status": "draft",
            "categories": [kat_id],
            "tags": [tag_id] if tag_id else [],
        }

        try:
            wp_response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/posts",
                json=post_data,
                auth=(WP_USER, WP_APP_PASSWORD)
            )
            if wp_response.status_code == 201:
                print(f"📝 Entwurf erstellt: {title} ({kategorie_name} / {focus_keyword})")
                save_posted_title(title)
                posted_titles.add(title)
            else:
                print(f"❌ WP-Fehler: {wp_response.status_code} – {wp_response.text}")
        except Exception as e:
            print(f"❌ Fehler beim Senden an WP: {e}")

print("\n🏁 Fertig!")
