import html
import json
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests

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

def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    cleanr = re.compile(r"<.*?>")
    cleaned = re.sub(cleanr, "", raw_html)
    return html.unescape(cleaned).strip()

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"surah": 1, "ayah": 1}

def save_next_progress(surah, ayah):
    if ayah < SURAH_LENGTHS[surah - 1]:
        next_surah, next_ayah = surah, ayah + 1
    else:
        next_surah, next_ayah = (surah + 1 if surah < 114 else 1), 1

    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"surah": next_surah, "ayah": next_ayah}, f, indent=2)

def main():
    state = load_progress()
    surah = state["surah"]
    ayah = state["ayah"]
    verse_key = f"{surah}:{ayah}"

    # 1. Fetch Surah Details
    ch_res = requests.get(f"https://api.quran.com/api/v4/chapters/{surah}", timeout=15)
    ch_res.raise_for_status()
    surah_data = ch_res.json()["chapter"]
    surah_name = surah_data["name_simple"]
    surah_arabic = surah_data["name_arabic"]

    # 2. Fetch Indo-Pak Script
    indopak_res = requests.get(f"https://api.quran.com/api/v4/quran/verses/indopak?verse_key={verse_key}", timeout=15)
    indopak_res.raise_for_status()
    arabic_text = indopak_res.json()["verses"][0]["text_indopak"]

    # 3. Fetch English Translation (ID 131: Saheeh International)
    en_res = requests.get(f"https://api.quran.com/api/v4/verses/by_key/{verse_key}?translations=131", timeout=15).json()
    translations_en = en_res.get("verse", {}).get("translations", [])
    english_text = clean_html(translations_en[0]["text"]) if translations_en else "Translation unavailable."

    # 4. Fetch Urdu Translation (ID 234: Fateh Muhammad Jalandhri)
    ur_res = requests.get(f"https://api.quran.com/api/v4/verses/by_key/{verse_key}?translations=234", timeout=15).json()
    translations_ur = ur_res.get("verse", {}).get("translations", [])
    urdu_text = clean_html(translations_ur[0]["text"]) if translations_ur else "اردو ترجمہ دستیاب نہیں ہے۔"

    # 5. Build Styled Email
    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Nastaliq+Urdu:wght@400;600;700&display=swap');
    body {{
      background-color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 620px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 32px 28px;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      font-weight: 600;
      letter-spacing: 1px;
      color: #64748b;
      text-transform: uppercase;
      border-bottom: 1px solid #f1f5f9;
      padding-bottom: 12px;
      margin-bottom: 24px;
    }}
    .arabic {{
      font-family: 'Noto Nastaliq Urdu', 'PDMS Saleem Quranic', serif;
      font-size: 26px;
      line-height: 2.3;
      text-align: right;
      direction: rtl;
      color: #0f172a;
      margin: 20px 0 28px 0;
      word-spacing: 2px;
    }}
    .urdu {{
      font-family: 'Noto Nastaliq Urdu', serif;
      font-size: 18px;
      line-height: 2.2;
      text-align: right;
      direction: rtl;
      color: #1e293b;
      margin-bottom: 24px;
      background-color: #f8fafc;
      padding: 16px;
      border-radius: 8px;
      border-right: 4px solid #0f172a;
    }}
    .english {{
      font-size: 15px;
      line-height: 1.7;
      color: #334155;
      padding-top: 8px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span>Surah {surah_name} ({surah}:{ayah})</span>
      <span style="font-family: 'Noto Nastaliq Urdu', serif; font-size: 15px;">{surah_arabic}</span>
    </div>
    
    <div class="arabic">{arabic_text}</div>
    <div class="urdu">{urdu_text}</div>
    <div class="english"><strong>English:</strong> {english_text}</div>
  </div>
</body>
</html>"""

    # 6. Send Email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Ayah — Surah {surah_name} ({verse_key})"
    msg["From"] = os.environ["EMAIL_FROM"]
    msg["To"] = os.environ["EMAIL_TO"]
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 465))) as server:
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        server.sendmail(os.environ["EMAIL_FROM"], [os.environ["EMAIL_TO"]], msg.as_string())

    # 7. Update Progress
    save_next_progress(surah, ayah)
    print(f"Sent {verse_key}. Progress updated.")

if __name__ == "__main__":
    main()