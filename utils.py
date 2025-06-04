import os
import requests
import random
import hashlib
import logging

def send_health_report(msg):
    # Dummy für späteres Monitoring
    print("[Health] " + msg)

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

def get_pixabay_image(keyword, kategorie_name, de_title, openai_client=None):
    from config import PIXABAY_API_KEY
    import requests
    import logging
    import re

    def clean_kw(kw):
        # Entfernt Sonderzeichen und überflüssige Leerzeichen
        return re.sub(r'[^a-zA-Z0-9äöüÄÖÜß\- ]', '', kw).strip()

    url = "https://pixabay.com/api/"
    queries = []
    if keyword and len(keyword) > 2:
        queries.append(clean_kw(keyword))
    if kategorie_name:
        queries.append(clean_kw(kategorie_name))

    for query in queries:
        if not query:
            continue
        q = query.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        q = q[:100]
        params = {
            "key": PIXABAY_API_KEY,
            "q": q,
            "image_type": "photo",
            "orientation": "horizontal",
            "safesearch": "true",
            "per_page": 5,
            "lang": "de"
        }
        try:
            response = requests.get(url, params=params, timeout=8)
            if response.status_code == 200:
                data = response.json()
                hits = data.get('hits', [])
                if not hits:
                    continue

                # KI-Check für jeden Treffer
                for img in hits:
                    tags = img.get('tags', '')
                    image_url = img.get('largeImageURL', '')
                    if openai_client:
                        is_relevant, new_keyword = ai_image_relevance_check(
                            tags, image_url, keyword, openai_client, kategorie_name
                        )
                        if is_relevant:
                            logging.info(f"Pixabay-Bild durch KI bestätigt für Query '{q}': {img['pageURL']}")
                            return image_url, img['pageURL']
                        elif new_keyword and new_keyword.lower() != keyword.lower():
                            # Neuer Versuch mit KI-Schlagwort!
                            logging.info(f"KI schlägt neues Schlagwort vor: {new_keyword}")
                            nq = new_keyword.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
                            nq = nq[:100]
                            alt_params = params.copy()
                            alt_params["q"] = nq
                            alt_resp = requests.get(url, params=alt_params, timeout=8)
                            if alt_resp.status_code == 200:
                                alt_data = alt_resp.json()
                                if alt_data['hits']:
                                    alt_img = alt_data['hits'][0]
                                    logging.info(f"Pixabay-Bild für Alternativ-Query '{nq}': {alt_img['pageURL']}")
                                    return alt_img['largeImageURL'], alt_img['pageURL']
                    else:
                        # Kein OpenAI: Nimm das erste Bild
                        return image_url, img['pageURL']
            else:
                logging.warning(f"Pixabay-Fehler: {response.status_code} – {response.text}")
        except Exception as e:
            logging.warning(f"Pixabay-Fehler: {e}")
    logging.warning("Kein (passendes) Pixabay-Bild gefunden.")
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

def ai_image_relevance_check(image_tags, image_url, keyword, openai_client, kategorie_name):
    """
    Fragt GPT: Passt das Bild zu unserem News-Schlagwort? Wenn nein, schlage ein neues, generischeres Keyword vor.
    Gibt (True/False, neues_keyword) zurück.
    """
    system_msg = (
        "Du bist ein KI-Bild-Checker. "
        "Analysiere, ob ein Pixabay-Bild (mit Tags, URL) zu einem bestimmten Schlagwort passt. "
        "Wenn das Bild passt, antworte nur mit 'OK'. "
        "Wenn das Bild nicht passt, antworte mit 'Alternative: <neues schlagwort>' "
        f"(ein relevantes, allgemeineres deutsches Keyword aus dem Bereich der Kategorie: {kategorie_name}). "
        "Sei kurz, keine Erklärungen!"
    )
    prompt = (
        f"Schlagwort: {keyword}\n"
        f"Bild-Tags: {image_tags}\n"
        f"Bild-URL: {image_url}\n"
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=20,
        )
        reply = response.choices[0].message.content.strip().lower()
        if reply.startswith("ok"):
            return True, keyword
        elif "alternative:" in reply:
            alt_kw = reply.split("alternative:")[1].strip()
            return False, alt_kw
        else:
            return False, None
    except Exception as e:
        import logging
        logging.warning(f"Fehler bei AI-Bildcheck: {e}")
        return False, None
