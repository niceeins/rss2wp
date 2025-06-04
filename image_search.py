import requests
import random
import logging
from config import PIXABAY_API_KEY

def optimize_keywords(keyword, category, title, retries=3):
    # Kombiniere Keyword, Kategorie und ggf. den Titel für eine bessere Suche
    base_queries = [keyword, category, title]
    tried = set()
    for _ in range(retries):
        # Query-Variante bauen
        q = " ".join(filter(None, [random.choice(base_queries), category]))
        q = q.strip()
        if q and q not in tried:
            tried.add(q)
            yield q
    # Fallback
    yield keyword or category or "Technologie"

def get_pixabay_image(keyword, category, title):
    # Versuche bis zu 4 Varianten (Schleife!)
    for q in optimize_keywords(keyword, category, title, retries=4):
        url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={q}&image_type=photo&lang=de&per_page=20&safesearch=true"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            hits = data.get("hits", [])
            if hits:
                # Zufaelliges Bild auswählen (mehr Abwechslung)
                pic = random.choice(hits)
                img_url = pic.get("largeImageURL")
                if img_url:
                    logging.info(f"Pixabay-Bild gefunden: {img_url} für Query '{q}'")
                    return img_url, pic.get("pageURL")
        except Exception as e:
            logging.warning(f"Pixabay-Fehler für Query '{q}': {e}")
    # Falls nix gefunden
    logging.warning("Kein passendes Pixabay-Bild gefunden.")
    return None, None
