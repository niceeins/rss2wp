import feedparser
import openai
import requests
import html
import logging
import time
import argparse

from config import (
    OPENAI_API_KEY, OPENAI_ORG, WP_URL, WP_USER, WP_APP_PASSWORD,
    PIXABAY_API_KEY, KAT_IDS
)
from utils import (
    load_rss_feeds, load_posted_titles, save_posted_title, save_posted_hash,
    make_prompt, upload_image_to_wp,
    get_or_create_tag_id, to_html_paragraphs, hash_content, send_health_report
)

from image_search import get_pixabay_image

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("newsbot.log"),
        logging.StreamHandler()
    ]
)

client = openai.OpenAI(api_key=OPENAI_API_KEY, organization=OPENAI_ORG)
RSS_FEEDS = load_rss_feeds()
POSTED_TITLES = load_posted_titles()
POSTED_HASHES = load_posted_titles(filename="posted_hashes.txt")

success_count, error_count = 0, 0

def process_entry(entry, feed_url):
    global success_count, error_count
    try:
        title = html.unescape(entry.title.strip())
        summary = html.unescape(entry.summary.strip() if 'summary' in entry else entry.description.strip())
        link = entry.link.strip()
        if title in POSTED_TITLES:
            logging.info(f"Schon verarbeitet: {title}")
            return
        content_hash = hash_content(summary)
        if content_hash in POSTED_HASHES:
            logging.info(f"Doppelter Inhalt (Hash) erkannt, wird übersprungen: {title}")
            return
        prompt_txt = make_prompt(summary, title)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Du bist ein moderner, deutschsprachiger Tech-Redakteur."},
                {"role": "user", "content": prompt_txt}
            ],
            temperature=0.7,
            max_tokens=1500,
        )
        full_reply = response.choices[0].message.content.strip()
        print(f"\n--- GPT-Output Start ---\n{full_reply}\n--- GPT-Output Ende ---\n")
        lines = [l for l in full_reply.split("\n") if l.strip()]
        if len(lines) < 4:
            logging.warning("GPT-Output zu kurz, wird übersprungen.")
            error_count += 1
            return
        de_title = lines[0].strip(" *\"'\n\r\t`")
        rest = "\n".join(lines[1:]).strip()
        import re
        kategorie_match = re.search(r"\[Kategorie:\s*(.*?)\]", rest)
        kategorie_name = kategorie_match.group(1).strip() if kategorie_match else "IT"
        keyword_match = re.search(r"\[Schlagwort:\s*(.*?)\]", rest)
        focus_keyword = keyword_match.group(1).strip() if keyword_match else ""
        rewritten = re.sub(r"\[Kategorie:.*?\]", "", rest)
        rewritten = re.sub(r"\[Schlagwort:.*?\]", "", rewritten).strip()
        rewritten = rewritten.strip(" *\"'\n\r\t[]")
        html_content = to_html_paragraphs(rewritten)
        html_content += (
            f'<p><strong>Quelle:</strong> '
            f'<a href="{link}" target="_blank" rel="noopener">{title}</a></p>'
            '<div style="margin-top:24px;">'
            '<a href="https://niceeins.de/newsletter/" target="_blank">📰 Jetzt Nice Eins KI-Newsletter abonnieren!</a>'
            '</div>'
            '<div style="margin-top:8px;">'
            'Teile diesen Artikel: <a href="https://twitter.com/intent/tweet?text='
            f'{de_title} - {link}">Twitter</a></div>'
        )
        logging.info(f"Kategorie erkannt: {kategorie_name} / Schlagwort: {focus_keyword}")
        kat_id = KAT_IDS.get(kategorie_name, KAT_IDS["IT"])
        tag_id = get_or_create_tag_id(focus_keyword)
        # Bilder-Logik: Versuche mit mehreren Anläufen bessere Bilder zu bekommen
        max_image_tries = 3
        image_url = None
        pixabay_link = None
        for i in range(max_image_tries):
            image_url, pixabay_link = get_pixabay_image(focus_keyword, kategorie_name, de_title)
            if image_url:
                logging.info(f"Pixabay-Bild gefunden (Versuch {i+1}): {image_url}")
                break
            else:
                logging.warning(f"Kein passendes Pixabay-Bild (Versuch {i+1}) für {focus_keyword}/{kategorie_name}/{de_title}")
                time.sleep(1)
        media_id = upload_image_to_wp(image_url, de_title, pixabay_link) if image_url else None
        if pixabay_link:
            html_content += f'<p><strong>Bildquelle:</strong> <a href="{pixabay_link}" target="_blank" rel="noopener">Bildquelle</a></p>'
        post_data = {
            "title": de_title,
            "content": html_content,
            "status": "publish",
            "categories": [kat_id],
            "tags": [tag_id] if tag_id else [],
        }
        if media_id:
            post_data["featured_media"] = media_id
            time.sleep(10)
        wp_response = requests.post(
            f"{WP_URL}/wp-json/wp/v2/posts",
            json=post_data,
            auth=(WP_USER, WP_APP_PASSWORD),
            timeout=20
        )
        if wp_response.status_code == 201:
            logging.info(f"Artikel veröffentlicht: {de_title} ({kategorie_name} / {focus_keyword})")
            save_posted_title(title)
            save_posted_hash(content_hash)
            success_count += 1
            time.sleep(10)
        else:
            logging.error(f"WP-Fehler: {wp_response.status_code} – {wp_response.text}")
            error_count += 1
    except Exception as e:
        logging.error(f"Fehler im Artikel-Prozess: {e}")
        error_count += 1

def main(max_entries=2):
    logging.info("🚀 Starte News-Bot ...")
    start_time = time.time()
    for feed_url in RSS_FEEDS:
        logging.info(f"Lese Feed: {feed_url}")
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            logging.warning("Keine Einträge gefunden.")
            continue
        for entry in feed.entries[:max_entries]:
            process_entry(entry, feed_url)
    end_time = time.time()
    send_health_report(success_count, error_count, int(end_time-start_time))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--max', type=int, default=2, help='Wie viele News pro Feed?')
    args = parser.parse_args()
    main(max_entries=args.max)
