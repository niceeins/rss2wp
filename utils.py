import hashlib
import os
import requests
import logging

def load_rss_feeds(filename="rss_feeds.txt"):
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_posted_titles(filename="posted_titles.txt"):
    if not os.path.exists(filename):
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_posted_title(title, filename="posted_titles.txt"):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(title + "\n")

def save_posted_hash(content_hash, filename="posted_hashes.txt"):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(content_hash + "\n")

def hash_content(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def to_html_paragraphs(text):
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return ''.join(f"<p>{line}</p>" for line in lines)

def upload_image_to_wp(image_url, alt_text, source_link):
    try:
        if not image_url:
            return None
        img_data = requests.get(image_url).content
        headers = {
            "Content-Disposition": f'attachment; filename="{os.path.basename(image_url)}"',
            "Content-Type": "image/jpeg",
        }
        response = requests.post(
            f"{WP_URL}/wp-json/wp/v2/media?alt_text=Bildquelle%3A+{source_link}",
            headers=headers,
            auth=(WP_USER, WP_APP_PASSWORD),
            data=img_data,
            timeout=60
        )
        if response.status_code == 201:
            media_id = response.json()["id"]
            logging.info(f"Bild hochgeladen, ID: {media_id}")
            return media_id
        else:
            logging.warning(f"Bild-Upload fehlgeschlagen: {response.status_code} {response.text}")
    except Exception as e:
        logging.warning(f"Fehler beim Bild-Upload: {e}")
    return None

def get_or_create_tag_id(keyword):
    # Dummy (immer None) – ergänze hier ggf. echte Logik, falls Tags benutzt werden sollen!
    return None

def send_health_report(success, error, dauer):
    print(f"[Health] Success: {success} | Error: {error} | Dauer: {dauer}s")
