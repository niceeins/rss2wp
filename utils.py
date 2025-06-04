import os
import requests
import random
import hashlib
import logging

def load_rss_feeds(filename="rss_feeds.txt"):
    feeds = []
    if not os.path.exists(filename):
        logging.warning(f"RSS-Feed-Datei '{filename}' nicht gefunden!")
        return feeds
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            feeds.append(line)
    logging.info(f"{len(feeds)} RSS-Feeds geladen.")
    return feeds

def load_posted_titles(filename="posted_titles.txt"):
    if not os.path.exists(filename):
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_posted_title(title, filename="posted_titles.txt"):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(title + "\n")

def save_posted_hash(hashvalue, filename="posted_hashes.txt"):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(hashvalue + "\n")

def hash_content(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def make_prompt(text, original_title, prompt_file="prompt.txt"):
    if os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            base = f.read()
        return base.replace("{original_title}", original_title).replace("{text}", text)
    # Fallback:
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
    from config import PIXABAY_API_KEY
    queries = [
        de_title,
        f"{keyword} {kategorie_name}",
        keyword,
        kategorie_name,
    ]
    url = "https://pixabay.com/api/"
    for query in queries:
        clean_query = query.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        clean_query = clean_query[:100]
        params = {
            "key": PIXABAY_API_KEY,
            "q": clean_query,
            "image_type": "photo",
            "orientation": "horizontal",
            "safesearch": "true",
            "per_page": 10,
            "lang": "de"
        }
        try:
            response = requests.get(url, params=params, timeout=8)
            if response.status_code == 200:
                data = response.json()
                if data['hits']:
                    img = random.choice(data['hits'])
                    logging.info(f"Pixabay-Bild gefunden für Query '{clean_query}': {img['pageURL']}")
                    return img['largeImageURL'], img['pageURL']
                else:
                    logging.info(f"Kein Treffer bei Query: {clean_query}")
            else:
                logging.warning(f"Pixabay-Fehler: {response.status_code} – {response.text}")
        except Exception as e:
            logging.warning(f"Pixabay-Fehler: {e}")
    logging.warning("Kein Pixabay-Bild gefunden für alle Suchvarianten.")
    return None, None

def get_unsplash_image(keyword, kategorie_name):
    from config import UNSPLASH_ACCESS_KEY
    url = "https://api.unsplash.com/search/photos"
    queries = [f"{keyword} {kategorie_name}", keyword, kategorie_name]
    headers = {"Accept-Version": "v1", "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
    for query in queries:
        params = {"query": query, "orientation": "landscape", "per_page": 10}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=8)
            if response.status_code == 200:
                data = response.json()
                if data['results']:
                    img = random.choice(data['results'])
                    return img['urls']['regular'], img['links']['html']
            else:
                logging.info(f"Unsplash-Fehler: {response.status_code} – {response.text}")
        except Exception as e:
            logging.info(f"Unsplash-Fehler: {e}")
    logging.info("Kein Unsplash-Bild gefunden.")
    return None, None

def upload_image_to_wp(image_url, wp_title, source_link):
    from config import WP_URL, WP_USER, WP_APP_PASSWORD
    if not image_url:
        return None
    try:
        img_data = requests.get(image_url, timeout=10).content
        media_endpoint = f"{WP_URL}/wp-json/wp/v2/media"
        headers = {
            "Content-Disposition": f'attachment; filename="{wp_title[:30].replace(" ", "_")}.jpg"',
            "Content-Type": "image/jpeg"
        }
        params = {
            "alt_text": f"Bildquelle: {source_link}" if source_link else "Bild von Pixabay"
        }
        time.sleep(10)
        response = requests.post(
            media_endpoint,
            headers=headers,
            params=params,
            data=img_data,
            auth=(WP_USER, WP_APP_PASSWORD),
            timeout=20
        )
        if response.status_code in [200, 201]:
            media_id = response.json()['id']
            logging.info(f"Bild hochgeladen, ID: {media_id}")
            return media_id
        else:
            logging.warning(f"Fehler beim WP-Upload: {response.status_code} – {response.text}")
            return None
    except Exception as e:
        logging.warning(f"Fehler beim Bild-Upload: {e}")
        return None

def get_or_create_tag_id(tag_name):
    from config import WP_URL, WP_USER, WP_APP_PASSWORD
    if not tag_name:
        return None
    try:
        response = requests.get(
            f"{WP_URL}/wp-json/wp/v2/tags",
            params={"search": tag_name},
            auth=(WP_USER, WP_APP_PASSWORD),
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0]['id']
        response = requests.post(
            f"{WP_URL}/wp-json/wp/v2/tags",
            json={"name": tag_name},
            auth=(WP_USER, WP_APP_PASSWORD),
            timeout=10
        )
        if response.status_code == 201:
            return response.json()['id']
    except Exception as e:
        logging.warning(f"Fehler beim Tag-Handling: {e}")
    return None

def to_html_paragraphs(text):
    parts = [p.strip() for p in text.split('\n') if p.strip()]
    return ''.join(f'<p>{p}</p>' for p in parts)

def send_health_report(success_count, error_count, runtime):
    # Hier könntest du optional Telegram/Mail/Discord/Slack einbauen.
    # Als Standard nur Log:
    logging.info(f"FERTIG! {success_count} Artikel erfolgreich, {error_count} Fehler, Laufzeit: {runtime}s")