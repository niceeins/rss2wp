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

def make_prompt(text, original_title):
    return (
        f"Übersetze den folgenden englischen Titel ins Deutsche, aber lasse Eigennamen, Marken, Produktnamen und Eventtitel (wie 'Snowflake Summit') IMMER im Original stehen. "
        f"Gib ausschließlich den so übersetzten deutschen Titel als erste Zeile aus: '{original_title}'. "
        f"Darunter schreibe einen ausführlichen, modernen, sachlichen News-Text auf Deutsch (ca. 200–300 Wörter), suchmaschinenoptimiert, für technikaffine Männer zwischen 24 und 40 Jahren. "
        f"Baue ein aussagekräftiges SEO-Schlagwort sinnvoll mehrfach in den Text ein. "
        f"Absätze bitte durch Leerzeilen trennen. "
        f"Am Ende ANTWORTE NUR mit [Kategorie: <Name>] (eine aus: Gaming, IT, Crafting, New Tech) und darunter [Schlagwort: <Keyword>]. "
        f"KEINE weiteren Erklärungen oder Zusatzinfos! "
        f"Gib NUR den deutschen Titel (ohne Sternchen, Anführungszeichen oder andere Sonderzeichen am Anfang/Ende), darunter den Fließtext, dann Kategorie und Schlagwort zurück.\n\n"
        f"{text}"
    )

def make_image_prompt(de_title, focus_keyword, kategorie_name):
    return (
        f"Erzeuge ein modernes, ansprechendes Titelbild für einen deutschen Blogbeitrag aus dem Bereich '{kategorie_name}' zum Thema '{de_title}'. "
        f"Das Motiv soll das Schlagwort '{focus_keyword}' visuell aufnehmen. "
        f"Bitte im Stil eines hochwertigen Magazin-Covers, ohne Text, ohne Menschen, farbenfroh, technologie- oder themenbezogen."
    )

def generate_openai_image(prompt):
    try:
        dalle_response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="standard"
        )
        image_url = dalle_response.data[0].url
        print("🖼️ Bild von DALL·E erzeugt:", image_url)
        return image_url
    except Exception as e:
        print(f"❌ Fehler bei DALL·E: {e}")
        return None

def upload_image_to_wp(image_url, wp_title):
    try:
        img_data = requests.get(image_url).content
        media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"
        headers = {
            "Content-Disposition": f'attachment; filename="{wp_title[:30].replace(" ", "_")}.png"'
        }
        response = requests.post(
            media_endpoint,
            headers=headers,
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
                max_tokens=1200,
            )
            full_reply = response.choices[0].message.content.strip()
            print("✅ OpenAI-Antwort bekommen.")

            # Parsing: 1. Zeile ist deutscher Titel, Rest ist Fließtext, Kategorie, Schlagwort
            lines = [l for l in full_reply.split("\n") if l.strip() != ""]
            if len(lines) < 4:
                print("⚠️ GPT-Output zu kurz, wird übersprungen.")
                continue

            de_title = lines[0].strip(" *\"'\n\r\t`")
            rest = "\n".join(lines[1:]).strip()

            # Kategorie extrahieren
            kategorie_match = re.search(r"\[Kategorie:\s*(.*?)\]", rest)
            kategorie_name = kategorie_match.group(1).strip() if kategorie_match else "IT"

            # Schlagwort extrahieren
            keyword_match = re.search(r"\[Schlagwort:\s*(.*?)\]", rest)
            focus_keyword = keyword_match.group(1).strip() if keyword_match else ""

            # Fließtext ohne Kategorie/Schlagwort-Tag
            rewritten = re.sub(r"\[Kategorie:.*?\]", "", rest)
            rewritten = re.sub(r"\[Schlagwort:.*?\]", "", rewritten).strip()

            html_content = to_html_paragraphs(rewritten)
            html_content += f'<p><strong>Quelle:</strong> <a href="{link}" target="_blank" rel="noopener">{title}</a></p>'

            print(f"⚡ Kategorie erkannt: {kategorie_name} / Schlagwort: {focus_keyword}")
        except Exception as e:
            print(f"❌ Fehler bei OpenAI: {e}")
            continue

        kat_id = KAT_IDS.get(kategorie_name, KAT_IDS["IT"])
        tag_id = get_or_create_tag_id(focus_keyword)

        # ==== NEU: Bildgenerierung & Upload ====
        image_prompt = make_image_prompt(de_title, focus_keyword, kategorie_name)
        image_url = generate_openai_image(image_prompt)
        media_id = upload_image_to_wp(image_url, de_title) if image_url else None

        post_data = {
            "title": de_title,
            "content": html_content,
            "status": "draft",
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
                print(f"📝 Entwurf erstellt: {de_title} ({kategorie_name} / {focus_keyword})")
                save_posted_title(title)
                posted_titles.add(title)
            else:
                print(f"❌ WP-Fehler: {wp_response.status_code} – {wp_response.text}")
        except Exception as e:
            print(f"❌ Fehler beim Senden an WP: {e}")

print("\n🏁 Fertig!")
