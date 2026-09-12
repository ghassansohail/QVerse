import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests

PROGRESS_FILE = "progress.json"

# Surah lengths across the 114 Surahs
SURAH_LENGTHS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128,
    111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73,
    54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
    49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52,
    44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19,
    26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3,
    6, 3, 5, 4, 5, 6
]

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

    # 1. Fetch Surah Name & Indo-Pak script from Quran.com API
    chapter_info = requests.get(f"https://api.quran.com/api/v4/chapters/{surah}").json()["chapter"]
    surah_name = chapter_info["name_simple"]

    ar_res = requests.get(f"https://api.quran.com/api/v4/quran/verses/indopak?verse_key={verse_key}").json()
    arabic_text = ar_res["verses"][0]["text_indopak"]

    # 2. Fetch Translation (131: Saheeh International English | 234: Jalandhri Urdu)
    tr_res = requests.get(f"https://api.quran.com/api/v4/quran/translations/131?verse_key={verse_key}").json()
    translation_text = tr_res["translations"][0]["text"]

    # 3. Compile Pakistani-Styled HTML
    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Nastaliq+Urdu:wght@500;700&display=swap');
    body {{
      background-color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 580px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 32px 28px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }}
    .header {{
      font-size: 13px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      color: #64748b;
      margin-bottom: 24px;
      border-bottom: 1px solid #f1f5f9;
      padding-bottom: 12px;
    }}
    .arabic {{
      font-family: 'Noto Nastaliq Urdu', 'PDMS Saleem Quranic', serif;
      font-size: 28px;
      line-height: 2.3;
      text-align: right;
      direction: rtl;
      color: #0f172a;
      margin: 20px 0 30px 0;
      word-spacing: 2px;
    }}
    .translation {{
      font-size: 16px;
      line-height: 1.7;
      color: #334155;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">Surah {surah_name} ({surah}:{ayah})</div>
    <div class="arabic">{arabic_text}</div>
    <div class="translation">{translation_text}</div>
  </div>
</body>
</html>"""

    # 4. Dispatch Email via SMTP
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Ayah — Surah {surah_name} ({verse_key})"
    msg["From"] = os.environ["EMAIL_FROM"]
    msg["To"] = os.environ["EMAIL_TO"]
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 465))) as server:
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        server.sendmail(os.environ["EMAIL_FROM"], [os.environ["EMAIL_TO"]], msg.as_string())

    # 5. Persist progress for tomorrow
    save_next_progress(surah, ayah)
    print(f"Sent {verse_key}. Updated progress.json.")

if __name__ == "__main__":
    main()