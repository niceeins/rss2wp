import feedparser
import openai
import requests
import os
import re
import time
from dotenv import load_dotenv
import html
import random

print("🚀 Starte News-Bot ...")
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG = os.getenv("OPENAI_ORG")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    organization=OPENAI_ORG
)

KAT_IDS = {
    "Gaming": 2,
    "IT": 3,
    "Mobile": 4,
    "Creator": 5,
}


def load_rss_feeds(filename="rss_feeds.txt"):
    feeds = []
    if not os.path.exists(filename):
        print(f"⚠️ RSS-Feed-Datei '{filename}' nicht gefunden!")
        return feeds
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            feeds.append(line)
    print(f"🔗 {len(feeds)} RSS-Feeds geladen.")
    return feeds

RSS_FEEDS = load_rss_feeds()


POSTED_TITLES_FILE = "posted_titles.txt"

def load_posted_titles():
    if not os.path.exists(POSTED_TITLES_FILE):
        return set()
    with open(POSTED_TITLES_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_posted_title(title):
    with open(POSTED_TITLES_FILE, "a", encoding="utf-8") as f:
        f.write(title + "\n")

def make_prompt(text, original_title):
    return (
        f"Übersetze den folgenden englischen Titel ins Deutsche, aber lasse Eigennamen, Marken, Produktnamen und Eventtitel (wie 'Snowflake Summit') IMMER im Original stehen. "
        f"Gib ausschließlich den so übersetzten deutschen Titel als erste Zeile aus: '{original_title}'. "
        f"Darunter schreibe einen ausführlichen, modernen, sachlichen News-Text auf Deutsch (mindestens 300 Wörter), suchmaschinenoptimiert, für technikaffine Männer zwischen 24 und 40 Jahren. "
        f"Baue ein aussagekräftiges SEO-Schlagwort sinnvoll mehrfach in den Text ein. "
        f"Absätze bitte durch Leerzeilen trennen. "
        f"Am Ende ANTWORTE NUR mit [Kategorie: <Name>] (eine aus: Gaming, IT, Mobile, Creator) und darunter [Schlagwort: <Keyword>]. "
        f"KEINE weiteren Erklärungen oder Zusatzinfos! "
        f"Gib NUR den deutschen Titel (ohne Sternchen, Anführungszeichen oder andere Sonderzeichen am Anfang/Ende), darunter den Fließtext, dann Kategorie und Schlagwort zurück.\n\n"
        f"{text}"
    )

def get_pixabay_image(keyword, kategorie_name, de_title):
    # Versuche zuerst die präziseste Suche, dann immer generischer.
    queries = [
        de_title,                                    # ganzer deutscher Titel
        f"{keyword} {kategorie_name}",               # SEO-Schlagwort + Kategorie
        keyword,                                     # nur SEO-Schlagwort
        kategorie_name,                              # nur Kategorie
    ]
    url = "https://pixabay.com/api/"
    for query in queries:
        clean_query = query.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        params = {
            "key": PIXABAY_API_KEY,
            "q": clean_query,
            "image_type": "photo",
            "orientation": "horizontal",
            "safesearch": "true",
            "per_page": 10,
            "lang": "de"
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['hits']:
                img = random.choice(data['hits'])
                print(f"📷 Pixabay-Bild gefunden für Query '{clean_query}': {img['pageURL']}")
                return img['largeImageURL'], img['pageURL']
            else:
                print(f"⚠️ Kein Treffer bei Query: {clean_query}")
        else:
            print(f"❌ Pixabay-Fehler: {response.status_code} – {response.text}")
    print("❌ Kein Pixabay-Bild gefunden für alle Suchvarianten.")
    return None, None


def upload_image_to_wp(image_url, wp_title, pixabay_link):
    try:
        img_data = requests.get(image_url).content
        media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"
        headers = {
            "Content-Disposition": f'attachment; filename="{wp_title[:30].replace(" ", "_")}.jpg"',
            "Content-Type": "image/jpeg"
        }
        params = {
            "alt_text": f"Bild von Pixabay: {pixabay_link}" if pixabay_link else "Bild von Pixabay"
        }
        response = requests.post(
            media_endpoint,
            headers=headers,
            params=params,
            data=img_data,
            auth=(WP_USER, WP_APP_PASSWORD)
        )
        if response.status_code in [200, 201]:
            media_id = response.json()['id']
            print(f"📸 Bild hochgeladen, ID: {media_id}")
            return media_id
        else:
            print(f"❌ Fehler beim WP-Upload: {response.status_code} – {response.text}")
            return None
    except Exception as e:
        print(f"❌ Fehler beim Bild-Upload: {e}")
        return None

def get_or_create_tag_id(tag_name):
    if not tag_name:
        return None
    response = requests.get(
        f"{WP_URL}/wp-json/wp/v2/tags",
        params={"search": tag_name},
        auth=(WP_USER, WP_APP_PASSWORD)
    )
    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            return data[0]['id']
    response = requests.post(
        f"{WP_URL}/wp-json/wp/v2/tags",
        json={"name": tag_name},
        auth=(WP_USER, WP_APP_PASSWORD)
    )
    if response.status_code == 201:
        return response.json()['id']
    return None

def to_html_paragraphs(text):
    parts = [p.strip() for p in text.split('\n') if p.strip()]
    return ''.join(f'<p>{p}</p>' for p in parts)

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
                    {"role": "user", "content": make_prompt(summary, title)}
                ],
                temperature=0.8,
                max_tokens=1500,
            )
            full_reply = response.choices[0].message.content.strip()
            print("✅ OpenAI-Antwort bekommen.")

            lines = [l for l in full_reply.split("\n") if l.strip() != ""]
            if len(lines) < 4:
                print("⚠️ GPT-Output zu kurz, wird übersprungen.")
                continue

            de_title = lines[0].strip(" *\"'\n\r\t`")
            rest = "\n".join(lines[1:]).strip()

            kategorie_match = re.search(r"\[Kategorie:\s*(.*?)\]", rest)
            kategorie_name = kategorie_match.group(1).strip() if kategorie_match else "IT"

            keyword_match = re.search(r"\[Schlagwort:\s*(.*?)\]", rest)
            focus_keyword = keyword_match.group(1).strip() if keyword_match else ""

            rewritten = re.sub(r"\[Kategorie:.*?\]", "", rest)
            rewritten = re.sub(r"\[Schlagwort:.*?\]", "", rewritten).strip()
            rewritten = rewritten.strip(" *\"'\n\r\t[]")

            html_content = to_html_paragraphs(rewritten)
            html_content += f'<p><strong>Quelle:</strong> <a href="{link}" target="_blank" rel="noopener">{title}</a></p>'

            print(f"⚡ Kategorie erkannt: {kategorie_name} / Schlagwort: {focus_keyword}")
        except Exception as e:
            print(f"❌ Fehler bei OpenAI: {e}")
            continue

        kat_id = KAT_IDS.get(kategorie_name, KAT_IDS["IT"])
        tag_id = get_or_create_tag_id(focus_keyword)

        # ==== Pixabay als Bildquelle (ohne Markenfilter) ====
        image_url, pixabay_link = get_pixabay_image(focus_keyword, kategorie_name, de_title)
        media_id = upload_image_to_wp(image_url, de_title, pixabay_link) if image_url else None

        # Quellenlink zu Pixabay im Beitrag hinzufügen
        if pixabay_link:
            html_content += f'<p><strong>Bildquelle:</strong> <a href="{pixabay_link}" target="_blank" rel="noopener">Pixabay</a></p>'

        post_data = {
            "title": de_title,
            "content": html_content,
            "status": "publish",
            "categories": [kat_id],
            "tags": [tag_id] if tag_id else [],
        }
        if media_id:
            post_data["featured_media"] = media_id

        try:
            wp_response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/posts",
                json=post_data,
                auth=(WP_USER, WP_APP_PASSWORD)
            )
            if wp_response.status_code == 201:
                print(f"📝 Artikel veröffentlicht: {de_title} ({kategorie_name} / {focus_keyword})")
                save_posted_title(title)
                posted_titles.add(title)
                print("⏳ Warte 60 Sekunden, bevor der nächste Post verarbeitet wird...")
                time.sleep(60)
            else:
                print(f"❌ WP-Fehler: {wp_response.status_code} – {wp_response.text}")
        except Exception as e:
            print(f"❌ Fehler beim Senden an WP: {e}")

print("\n🏁 Fertig!")
