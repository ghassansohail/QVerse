import argparse
import html
import json
import os
import re
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from playwright.sync_api import sync_playwright

PROGRESS_FILE = "progress.json"

SURAH_LENGTHS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128,
    111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73,
    54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
    49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52,
    44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19,
    26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3,
    6, 3, 5, 4, 5, 6
]

def load_dotenv():
    """Lightweight .env loader if .env file exists in the directory."""
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip("'\""))

def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    cleanr = re.compile(r"<.*?>")
    cleaned = re.sub(cleanr, "", raw_html)
    return html.unescape(cleaned).strip()

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("surah", 1), data.get("ayah", 1)
    return 1, 1

def save_next_progress(surah, ayah):
    if ayah < SURAH_LENGTHS[surah - 1]:
        next_surah, next_ayah = surah, ayah + 1
    else:
        next_surah, next_ayah = (surah + 1 if surah < 114 else 1), 1

    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"surah": next_surah, "ayah": next_ayah}, f, indent=2)

def is_large_ayah(arabic_text: str, urdu_text: str, english_text: str) -> bool:
    """
    Determines whether an Ayah is large enough that placing Arabic and translations
    on a single vertical image card compromises readability and causes excessive vertical stretch.
    """
    return len(arabic_text) > 350 or len(urdu_text) > 450 or len(english_text) > 450

def generate_ayah_cards(surah_name: str, surah_arabic: str, verse_key: str, ayah: int, total_ayahs: int,
                        arabic_text: str, urdu_text: str, english_text: str, split: bool = False) -> list[bytes]:
    """
    Renders social-media ready high-resolution cards (1080px wide) at 2x Retina scale.
    If split=True, generates 2 dedicated cards:
      - Card 1: Arabic verse in large, elegant typography.
      - Card 2: Urdu and English translations with clear, legible text blocks.
    If split=False, generates a single combined card.
    """
    base_css = """
    @import url('https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400&family=Noto+Nastaliq+Urdu:wght@500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      width: 1080px;
      margin: 0;
      padding: 48px;
      background: #030d0a;
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      text-rendering: optimizeLegibility;
    }

    .card {
      width: 100%;
      background: linear-gradient(150deg, #09251c 0%, #0d3529 45%, #061e16 100%);
      border: 1.5px solid rgba(212, 175, 55, 0.45);
      border-radius: 32px;
      padding: 56px 64px;
      position: relative;
      box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.8), inset 0 1px 2px rgba(212, 175, 55, 0.35);
      overflow: hidden;
    }

    .card::before {
      content: "";
      position: absolute;
      top: -100px;
      right: -100px;
      width: 340px;
      height: 340px;
      background: radial-gradient(circle, rgba(212, 175, 55, 0.15) 0%, rgba(212, 175, 55, 0) 70%);
      border-radius: 50%;
      pointer-events: none;
    }

    .card::after {
      content: "";
      position: absolute;
      bottom: -90px;
      left: -90px;
      width: 320px;
      height: 320px;
      background: radial-gradient(circle, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0) 70%);
      border-radius: 50%;
      pointer-events: none;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 24px;
      border-bottom: 1px solid rgba(212, 175, 55, 0.25);
      margin-bottom: 36px;
    }

    .badge-wrap {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .badge {
      background: rgba(212, 175, 55, 0.12);
      border: 1px solid rgba(212, 175, 55, 0.45);
      color: #f3e5ab;
      padding: 8px 20px;
      border-radius: 9999px;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
    }

    .part-badge {
      background: rgba(16, 185, 129, 0.18);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #a7f3d0;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 1px;
    }

    .part-badge-trans {
      background: rgba(56, 189, 248, 0.18);
      border: 1px solid rgba(56, 189, 248, 0.4);
      color: #bae6fd;
    }

    .surah-arabic {
      font-family: 'Amiri', serif;
      font-size: 34px;
      font-weight: 700;
      color: #f3e5ab;
      direction: rtl;
    }

    .divider {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 16px;
      margin: 30px 0 26px 0;
    }

    .divider-line {
      flex: 1;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.35), transparent);
    }

    .divider-star {
      color: #d4af37;
      font-size: 18px;
    }

    .footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 32px;
      padding-top: 22px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
    }

    .branding {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #94a3b8;
      font-size: 14px;
      font-weight: 600;
      letter-spacing: 1px;
    }

    .branding-accent {
      color: #d4af37;
      font-weight: 700;
    }

    .counter {
      color: #cbd5e1;
      font-size: 13px;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.06);
      padding: 4px 12px;
      border-radius: 999px;
    }
    """

    html_pages = []

    if split:
        # Part 1: Arabic Card
        arabic_font_size = "34px" if len(arabic_text) > 800 else ("38px" if len(arabic_text) > 400 else "42px")
        arabic_line_height = "2.2" if len(arabic_text) > 800 else "2.35"

        part1_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    {base_css}
    .arabic-box {{
      margin: 10px 0 32px 0;
      text-align: justify;
      text-align-last: center;
    }}

    .arabic-text {{
      font-family: 'Amiri', serif;
      font-size: {arabic_font_size};
      line-height: {arabic_line_height};
      color: #ffffff;
      direction: rtl;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.45);
      word-spacing: 5px;
    }}
  </style>
</head>
<body>
  <div class="card" id="ayah-card">
    <div class="header">
      <div class="badge-wrap">
        <div class="badge">Surah {surah_name} &bull; {verse_key}</div>
        <div class="part-badge">1 / 2 &bull; Arabic</div>
      </div>
      <div class="surah-arabic">{surah_arabic}</div>
    </div>

    <div class="arabic-box">
      <div class="arabic-text">
        {arabic_text}
      </div>
    </div>

    <div class="divider">
      <div class="divider-line"></div>
      <div class="divider-star">&#10022; &#1758; &#10022;</div>
      <div class="divider-line"></div>
    </div>

    <div class="footer">
      <div class="branding">
        <span class="branding-accent">&#10022; QVerse</span> &bull; Daily Quran Dispatch
      </div>
      <div class="counter">
        Ayah {ayah} of {total_ayahs} (Part 1/2)
      </div>
    </div>
  </div>
</body>
</html>"""

        # Part 2: Translations Card
        urdu_font_size = "22px" if len(urdu_text) > 900 else "24px"
        english_font_size = "19px" if len(english_text) > 900 else "20px"

        part2_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    {base_css}
    .translation-section {{
      display: flex;
      flex-direction: column;
      gap: 26px;
    }}

    .trans-card {{
      background: rgba(3, 16, 12, 0.62);
      border: 1px solid rgba(212, 175, 55, 0.18);
      border-radius: 20px;
      padding: 26px 30px;
      box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05);
    }}

    .trans-label {{
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #d4af37;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .urdu-label {{
      text-align: right;
      direction: rtl;
      justify-content: flex-end;
    }}

    .urdu-text {{
      font-family: 'Noto Nastaliq Urdu', serif;
      font-size: {urdu_font_size};
      line-height: 2.3;
      color: #f8fafc;
      direction: rtl;
      text-align: right;
    }}

    .english-text {{
      font-size: {english_font_size};
      line-height: 1.75;
      color: #f1f5f9;
      font-weight: 400;
      letter-spacing: 0.2px;
    }}
  </style>
</head>
<body>
  <div class="card" id="ayah-card">
    <div class="header">
      <div class="badge-wrap">
        <div class="badge">Surah {surah_name} &bull; {verse_key}</div>
        <div class="part-badge part-badge-trans">2 / 2 &bull; Translations</div>
      </div>
      <div class="surah-arabic">{surah_arabic}</div>
    </div>

    <div class="translation-section">
      <div class="trans-card">
        <div class="trans-label urdu-label">&#10022; اردو ترجمہ — مولانا فتح محمد جالندھری</div>
        <div class="urdu-text">
          {urdu_text}
        </div>
      </div>

      <div class="trans-card">
        <div class="trans-label">&#10022; English Translation — Saheeh International</div>
        <div class="english-text">
          {english_text}
        </div>
      </div>
    </div>

    <div class="footer">
      <div class="branding">
        <span class="branding-accent">&#10022; QVerse</span> &bull; Daily Quran Dispatch
      </div>
      <div class="counter">
        Ayah {ayah} of {total_ayahs} (Part 2/2)
      </div>
    </div>
  </div>
</body>
</html>"""
        html_pages = [part1_html, part2_html]

    else:
        # Single Combined Card
        arabic_font_size = "34px" if len(arabic_text) > 320 else "40px"
        arabic_line_height = "2.1" if len(arabic_text) > 320 else "2.3"

        single_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    {base_css}
    .arabic-box {{
      margin-bottom: 34px;
      text-align: center;
    }}

    .arabic-text {{
      font-family: 'Amiri', serif;
      font-size: {arabic_font_size};
      line-height: {arabic_line_height};
      color: #ffffff;
      direction: rtl;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.45);
      word-spacing: 4px;
    }}

    .translation-section {{
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}

    .trans-card {{
      background: rgba(3, 16, 12, 0.58);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 20px;
      padding: 24px 28px;
    }}

    .trans-label {{
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #d4af37;
      margin-bottom: 12px;
    }}

    .urdu-label {{
      text-align: right;
      direction: rtl;
    }}

    .urdu-text {{
      font-family: 'Noto Nastaliq Urdu', serif;
      font-size: 23px;
      line-height: 2.3;
      color: #f8fafc;
      direction: rtl;
      text-align: right;
    }}

    .english-text {{
      font-size: 18px;
      line-height: 1.7;
      color: #e2e8f0;
      font-weight: 400;
    }}
  </style>
</head>
<body>
  <div class="card" id="ayah-card">
    <div class="header">
      <div class="badge">Surah {surah_name} &bull; {verse_key}</div>
      <div class="surah-arabic">{surah_arabic}</div>
    </div>

    <div class="arabic-box">
      <div class="arabic-text">
        {arabic_text}
      </div>
    </div>

    <div class="divider">
      <div class="divider-line"></div>
      <div class="divider-star">&#10022; &#1758; &#10022;</div>
      <div class="divider-line"></div>
    </div>

    <div class="translation-section">
      <div class="trans-card">
        <div class="trans-label urdu-label">اردو ترجمہ — مولانا فتح محمد جالندھری</div>
        <div class="urdu-text">
          {urdu_text}
        </div>
      </div>

      <div class="trans-card">
        <div class="trans-label">English Translation — Saheeh International</div>
        <div class="english-text">
          {english_text}
        </div>
      </div>
    </div>

    <div class="footer">
      <div class="branding">
        <span class="branding-accent">&#10022; QVerse</span> &bull; Daily Quran Dispatch
      </div>
      <div class="counter">
        Ayah {ayah} of {total_ayahs}
      </div>
    </div>
  </div>
</body>
</html>"""
        html_pages = [single_html]

    # Render images via Playwright
    rendered_images = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)

        for html_content in html_pages:
            page = browser.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=2)
            page.set_content(html_content, wait_until="networkidle")
            page.evaluate("() => document.fonts.ready")

            card = page.locator("#ayah-card")
            rendered_images.append(card.screenshot(type="jpeg", quality=95))
            page.close()

        browser.close()

    return rendered_images

# Alias for backwards compatibility
generate_ayah_card = generate_ayah_cards

def upload_image_to_host(image_bytes: bytes, filename: str = "qverse_ayah.jpg", api_key: str = None) -> str:
    """
    Uploads JPEG card to ImgBB to generate a public URL required by Meta Instagram API.
    Get a free API key at https://api.imgbb.com/
    """
    if not api_key:
        api_key = os.environ.get("IMGBB_API_KEY")

    if not api_key:
        raise ValueError("IMGBB_API_KEY environment variable is required to host the image for Instagram API.")

    url = "https://api.imgbb.com/1/upload"
    payload = {"key": api_key}
    files = {"image": (filename, image_bytes, "image/jpeg")}
    
    resp = requests.post(url, data=payload, files=files, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("success"):
        return data["data"]["url"]
    else:
        raise Exception(f"ImgBB upload failed: {data}")

def post_to_instagram(image_urls: str | list[str], caption: str, ig_user_id: str = None, access_token: str = None) -> str:
    """
    Publishes a photo post or carousel album to an Instagram Creator/Business account via Meta Graph API.
    """
    import time

    if not ig_user_id:
        ig_user_id = os.environ.get("IG_USER_ID")
    if not access_token:
        access_token = os.environ.get("IG_ACCESS_TOKEN")

    if not ig_user_id or not access_token:
        raise ValueError("IG_USER_ID and IG_ACCESS_TOKEN are required to post to Instagram.")

    if isinstance(image_urls, str):
        image_urls = [image_urls]

    if len(image_urls) == 1:
        # Single Image Post
        container_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
        container_params = {
            "image_url": image_urls[0],
            "caption": caption,
            "access_token": access_token
        }
        resp = requests.post(container_url, data=container_params, timeout=30)
        if not resp.ok:
            raise Exception(f"Failed to create Instagram media container ({resp.status_code}): {resp.text}")
        creation_id = resp.json().get("id")

        time.sleep(4)

        publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
        publish_params = {
            "creation_id": creation_id,
            "access_token": access_token
        }
        pub_resp = requests.post(publish_url, data=publish_params, timeout=30)
        if not pub_resp.ok:
            raise Exception(f"Failed to publish Instagram media ({pub_resp.status_code}): {pub_resp.text}")
        return pub_resp.json().get("id")

    else:
        # Multi-Image Carousel (Album) Post
        child_container_ids = []
        for i, url in enumerate(image_urls):
            container_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
            child_params = {
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": access_token
            }
            resp = requests.post(container_url, data=child_params, timeout=30)
            if not resp.ok:
                raise Exception(f"Failed to create carousel item {i+1} ({resp.status_code}): {resp.text}")
            child_id = resp.json().get("id")
            child_container_ids.append(child_id)
            time.sleep(2)

        # Allow Meta servers time to process child images
        time.sleep(4)

        # Create Carousel Container
        parent_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
        parent_params = {
            "media_type": "CAROUSEL",
            "children": ",".join(child_container_ids),
            "caption": caption,
            "access_token": access_token
        }
        resp = requests.post(parent_url, data=parent_params, timeout=30)
        if not resp.ok:
            raise Exception(f"Failed to create carousel container ({resp.status_code}): {resp.text}")
        carousel_creation_id = resp.json().get("id")

        time.sleep(4)

        # Publish Carousel
        publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
        publish_params = {
            "creation_id": carousel_creation_id,
            "access_token": access_token
        }
        pub_resp = requests.post(publish_url, data=publish_params, timeout=30)
        if not pub_resp.ok:
            raise Exception(f"Failed to publish carousel ({pub_resp.status_code}): {pub_resp.text}")
        return pub_resp.json().get("id")

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Fetch daily Ayah, generate shareable picture cards, and send email.")
    parser.add_argument("--dry-run", action="store_true", help="Generate card and mock email without sending via SMTP")
    parser.add_argument("--surah", type=int, default=None, help="Surah number to generate (defaults to progress.json)")
    parser.add_argument("--ayah", type=int, default=None, help="Ayah number to generate (defaults to progress.json)")
    parser.add_argument("--output", type=str, default=None, help="Save generated card image to file path")
    parser.add_argument("--instagram", action="store_true", help="Post generated card to Instagram Graph API")
    parser.add_argument("--split", action="store_true", help="Force split into two pictures (Arabic + Translations)")
    parser.add_argument("--no-split", action="store_true", help="Force single picture card even for large verses")
    args = parser.parse_args()

    if args.surah is not None and args.ayah is not None:
        surah, ayah = args.surah, args.ayah
        use_custom_verse = True
    else:
        surah, ayah = load_progress()
        use_custom_verse = False

    max_ayahs = SURAH_LENGTHS[surah - 1]
    if ayah > max_ayahs:
        surah = surah + 1 if surah < 114 else 1
        ayah = 1

    verse_key = f"{surah}:{ayah}"
    print(f"Fetching Ayah {verse_key}...")

    # Fetch Arabic Simple (clean universal diacritics), English (Saheeh Intl), and Urdu (Jalandhry)
    url = f"https://api.alquran.cloud/v1/ayah/{verse_key}/editions/quran-simple,en.sahih,ur.jalandhry"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    payload = resp.json().get("data", [])

    arabic_text = payload[0].get("text", "")
    english_text = clean_html(payload[1].get("text", ""))
    urdu_text = clean_html(payload[2].get("text", ""))

    surah_name = payload[0].get("surah", {}).get("englishName", f"Surah {surah}")
    surah_arabic = payload[0].get("surah", {}).get("name", "")

    # Determine whether to split into two cards
    if args.split:
        should_split = True
    elif args.no_split:
        should_split = False
    else:
        should_split = is_large_ayah(arabic_text, urdu_text, english_text)

    # 1. Generate high-resolution social-ready picture cards
    split_info = " (split into Arabic & Translations cards)" if should_split else ""
    print(f"Rendering social card{split_info} for Surah {surah_name} ({verse_key})...")
    rendered_cards = generate_ayah_cards(
        surah_name=surah_name,
        surah_arabic=surah_arabic,
        verse_key=verse_key,
        ayah=ayah,
        total_ayahs=max_ayahs,
        arabic_text=arabic_text,
        urdu_text=urdu_text,
        english_text=english_text,
        split=should_split
    )

    if args.output:
        base, ext = os.path.splitext(args.output)
        if not ext:
            ext = ".png"
        if len(rendered_cards) == 1:
            with open(args.output, "wb") as f:
                f.write(rendered_cards[0])
            print(f"Card image saved to {args.output}")
        else:
            for i, card_bytes in enumerate(rendered_cards):
                part_name = "arabic" if i == 0 else "translations"
                out_path = f"{base}_part{i+1}_{part_name}{ext}"
                with open(out_path, "wb") as f:
                    f.write(card_bytes)
                print(f"Card part {i+1} ({part_name}) saved to {out_path}")

    # 2. Plain text content for clean copy-pasting to WhatsApp
    text_content = (
        f"*Surah {surah_name} ({verse_key})*\n\n"
        f"{arabic_text}\n\n"
        f"*اردو (مولانا جالندھری):*\n{urdu_text}\n\n"
        f"*English (Saheeh Intl):*\n{english_text}"
    )

    # 3. HTML email body embedding inline image(s) + readable text below
    if len(rendered_cards) == 1:
        email_cards_html = f"""
    <div style="text-align:center; margin-bottom:28px;">
      <img src="cid:daily_ayah_image" alt="Surah {surah_name} ({verse_key})" style="max-width:100%; height:auto; border-radius:16px; box-shadow:0 12px 36px rgba(0,0,0,0.16); display:block; margin:0 auto; border:1px solid #cbd5e1;" />
      <p style="margin:10px 0 0 0; font-size:12px; color:#64748b; font-style:italic;">
        Tip: Long-press or right-click the image above to save and share to WhatsApp or social platforms.
      </p>
    </div>"""
    else:
        email_cards_html = f"""
    <div style="text-align:center; margin-bottom:28px;">
      <div style="margin-bottom:16px;">
        <img src="cid:daily_ayah_image_1" alt="Surah {surah_name} ({verse_key}) - Arabic" style="max-width:100%; height:auto; border-radius:16px; box-shadow:0 12px 36px rgba(0,0,0,0.16); display:block; margin:0 auto; border:1px solid #cbd5e1;" />
      </div>
      <div style="margin-bottom:12px;">
        <img src="cid:daily_ayah_image_2" alt="Surah {surah_name} ({verse_key}) - Translations" style="max-width:100%; height:auto; border-radius:16px; box-shadow:0 12px 36px rgba(0,0,0,0.16); display:block; margin:0 auto; border:1px solid #cbd5e1;" />
      </div>
      <p style="margin:10px 0 0 0; font-size:12px; color:#64748b; font-style:italic;">
        Tip: Long-press or right-click any image above to save and share to WhatsApp or social platforms.
      </p>
    </div>"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Surah {surah_name} ({verse_key})</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Noto+Nastaliq+Urdu:wght@500;700&display=swap');
    
    @page {{
      size: A4 portrait;
      margin: 15mm;
    }}

    @media only screen and (max-width: 600px) {{
      body {{
        padding: 10px !important;
      }}
      .page-card {{
        padding: 18px !important;
        border-radius: 8px !important;
      }}
      .arabic {{
        font-size: 26px !important;
        line-height: 2.1 !important;
        margin-bottom: 20px !important;
      }}
      .urdu {{
        font-size: 19px !important;
        line-height: 2.0 !important;
        padding: 14px 16px !important;
        margin-bottom: 20px !important;
      }}
      .english {{
        font-size: 15px !important;
        line-height: 1.6 !important;
      }}
    }}

    @media print {{
      body, html {{
        background: #ffffff !important;
        padding: 0 !important;
        margin: 0 !important;
        width: 100% !important;
      }}
      .no-print {{ display: none !important; }}
      .page-card {{
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        width: 100% !important;
        max-width: 100% !important;
      }}
      .arabic {{
        font-size: 38pt !important;
        line-height: 2.2 !important;
        margin-bottom: 25pt !important;
      }}
      .urdu {{
        font-size: 24pt !important;
        line-height: 2.1 !important;
        padding: 15pt !important;
        border-right: 6px solid #000000 !important;
        margin-bottom: 25pt !important;
      }}
      .english {{
        font-size: 18pt !important;
        line-height: 1.6 !important;
      }}
      .header {{
        font-size: 16pt !important;
        margin-bottom: 20pt !important;
      }}
    }}
  </style>
</head>
<body style="margin:0; padding:20px; background-color:#f8fafc; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <div class="page-card" style="max-width:700px; margin:0 auto; background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:32px;">

    <!-- Inline Daily Ayah Picture Cards -->
    {email_cards_html}

    <!-- Text Format for Clean Copying & Accessibility -->
    <table style="width:100%; border-bottom:2px solid #e2e8f0; padding-bottom:12px; margin-bottom:25px;">
      <tr>
        <td style="text-align:left; font-size:16px; font-weight:700; color:#475569; text-transform:uppercase; letter-spacing:1px;">
          Surah {surah_name} ({verse_key})
        </td>
        <td style="text-align:right; font-family:'Noto Nastaliq Urdu', serif; font-size:20px; font-weight:700; color:#0f172a;">
          {surah_arabic}
        </td>
      </tr>
    </table>

    <div class="arabic" style="font-family:'Amiri', 'Traditional Arabic', 'Scheherazade New', 'Noto Naskh Arabic', serif; font-size:30px; line-height:2.3; text-align:right; direction:rtl; color:#000000; margin-bottom:28px; word-spacing:2px;">
      {arabic_text}
    </div>

    <div class="urdu" style="font-family:'Noto Nastaliq Urdu', serif; font-size:22px; line-height:2.2; text-align:right; direction:rtl; color:#0f172a; background-color:#f1f5f9; padding:18px 22px; border-radius:8px; border-right:5px solid #0f172a; margin-bottom:28px;">
      {urdu_text}
    </div>

    <div class="english" style="font-size:16px; line-height:1.7; color:#334155; padding-top:5px;">
      <strong style="color:#0f172a;">Translation:</strong> {english_text}
    </div>

  </div>
</body>
</html>"""

    # 4. Assemble multipart/related email with inline image(s) + text alternative
    msg_root = MIMEMultipart("related")
    msg_root["Subject"] = f"Daily Ayah — Surah {surah_name} ({verse_key})"
    msg_root["From"] = os.environ.get("EMAIL_FROM", "qverse@local")
    msg_root["To"] = os.environ.get("EMAIL_TO", "recipient@local")

    msg_alt = MIMEMultipart("alternative")
    msg_root.attach(msg_alt)

    msg_alt.attach(MIMEText(text_content, "plain", "utf-8"))
    msg_alt.attach(MIMEText(html_body, "html", "utf-8"))

    # Attach picture(s) both as inline CID (for email view) and downloadable JPEG
    if len(rendered_cards) == 1:
        img_attachment = MIMEImage(rendered_cards[0], _subtype="jpeg")
        img_attachment.add_header("Content-ID", "<daily_ayah_image>")
        img_attachment.add_header("Content-Disposition", "inline", filename=f"QVerse_Surah_{surah}_{ayah}.jpg")
        msg_root.attach(img_attachment)
    else:
        for i, card_bytes in enumerate(rendered_cards):
            part_name = "Arabic" if i == 0 else "Translations"
            cid = f"daily_ayah_image_{i+1}"
            filename = f"QVerse_Surah_{surah}_{ayah}_part{i+1}_{part_name}.jpg"
            img_attachment = MIMEImage(card_bytes, _subtype="jpeg")
            img_attachment.add_header("Content-ID", f"<{cid}>")
            img_attachment.add_header("Content-Disposition", "inline", filename=filename)
            msg_root.attach(img_attachment)

    # Prepare Instagram Caption
    clean_surah_name = surah_name.replace(" ", "").replace("-", "")
    carousel_hint = "\n(Swipe left for Urdu & English translations ➡️)\n" if len(rendered_cards) > 1 else ""
    ig_caption = (
        f"✨ Daily Ayah — Surah {surah_name} ({verse_key}) ✨{carousel_hint}\n\n"
        f"{arabic_text}\n\n"
        f"اردو ترجمہ (مولانا فتح محمد جالندھری):\n{urdu_text}\n\n"
        f"English Translation (Saheeh International):\n{english_text}\n\n"
        f"—\n"
        f"#Quran #DailyAyah #QVerse #Islam #AyahOfTheDay #Surah{clean_surah_name} #IslamicReminder #QuranQuotes"
    )

    should_post_instagram = args.instagram or (bool(os.environ.get("IG_USER_ID")) and bool(os.environ.get("IG_ACCESS_TOKEN")))

    total_bytes = sum(len(c) for c in rendered_cards)
    if args.dry_run:
        print(f"[DRY RUN] Generated email MIME package for {verse_key} ({len(rendered_cards)} card(s), {total_bytes} bytes total).")
        print("[DRY RUN] Email not sent via SMTP (dry-run mode).")
        if should_post_instagram:
            post_type = f"Carousel Album ({len(rendered_cards)} images)" if len(rendered_cards) > 1 else "Single Image Post"
            print(f"[DRY RUN] Would upload card image(s) and publish Instagram {post_type} with caption:\n---\n{ig_caption}\n---")
        return

    # Check for required SMTP environment variables
    required_env = ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_FROM", "EMAIL_TO"]
    missing_env = [var for var in required_env if not os.environ.get(var)]
    if missing_env:
        print(f"Error: Missing required environment variables for Email: {', '.join(missing_env)}")
        print("Tip: Add them to your environment or a .env file, or use '--dry-run' to test without sending an email.")
    else:
        # Send through SMTP
        smtp_host = os.environ["SMTP_HOST"]
        smtp_port = int(os.environ.get("SMTP_PORT", 465))
        smtp_user = os.environ["SMTP_USER"]
        smtp_pass = os.environ["SMTP_PASS"]
        email_from = os.environ["EMAIL_FROM"]
        email_to = os.environ["EMAIL_TO"]

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(email_from, [email_to], msg_root.as_string())
        print(f"Successfully sent email for {verse_key}.")

    # Post to Instagram if requested or configured
    if should_post_instagram:
        print(f"Uploading {len(rendered_cards)} card image(s) to ImgBB for Instagram API...")
        try:
            hosted_urls = []
            for i, card_bytes in enumerate(rendered_cards):
                fn = f"qverse_{surah}_{ayah}_p{i+1}.jpg"
                hosted_url = upload_image_to_host(card_bytes, filename=fn)
                print(f"Card image {i+1} hosted at: {hosted_url}")
                hosted_urls.append(hosted_url)

            if len(hosted_urls) > 1:
                print(f"Publishing carousel album ({len(hosted_urls)} images) to Instagram Creator/Business account...")
            else:
                print("Publishing post to Instagram Creator/Business account...")

            media_id = post_to_instagram(hosted_urls, ig_caption)
            print(f"Successfully posted {verse_key} to Instagram! (Media ID: {media_id})")
        except Exception as e:
            print(f"Error posting to Instagram: {e}")

    if not use_custom_verse:
        save_next_progress(surah, ayah)

    print(f"Progress updated to next verse.")

if __name__ == "__main__":
    main()
