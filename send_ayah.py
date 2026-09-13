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

def main():
    surah, ayah = load_progress()

    max_ayahs = SURAH_LENGTHS[surah - 1]
    if ayah > max_ayahs:
        surah = surah + 1 if surah < 114 else 1
        ayah = 1

    verse_key = f"{surah}:{ayah}"

    # Fetch Arabic Indo-Pak, English, and Urdu translations
    url = f"https://api.alquran.cloud/v1/ayah/{verse_key}/editions/quran-indopak,en.sahih,ur.jalandhry"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    payload = resp.json().get("data", [])

    arabic_text = payload[0].get("text", "")
    english_text = clean_html(payload[1].get("text", ""))
    urdu_text = clean_html(payload[2].get("text", ""))

    surah_name = payload[0].get("surah", {}).get("englishName", f"Surah {surah}")
    surah_arabic = payload[0].get("surah", {}).get("name", "")

    # Plain text for clean copy-pasting to WhatsApp
    text_content = (
        f"*Surah {surah_name} ({verse_key})*\n\n"
        f"{arabic_text}\n\n"
        f"*اردو:*\n{urdu_text}\n\n"
        f"*English:*\n{english_text}"
    )

    # Large print-friendly HTML template
    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Surah {surah_name} ({verse_key})</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Nastaliq+Urdu:wght@500;700&display=swap');
    
    @page {{
      size: A4 portrait;
      margin: 15mm;
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

    <div class="arabic" style="font-family:'Noto Nastaliq Urdu', 'PDMS Saleem Quranic', serif; font-size:32px; line-height:2.4; text-align:right; direction:rtl; color:#000000; margin-bottom:28px; word-spacing:3px;">
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

    # Assemble email parts
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Ayah — Surah {surah_name} ({verse_key})"
    msg["From"] = os.environ["EMAIL_FROM"]
    msg["To"] = os.environ["EMAIL_TO"]

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Send through SMTP
    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 465))) as server:
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        server.sendmail(os.environ["EMAIL_FROM"], [os.environ["EMAIL_TO"]], msg.as_string())

    save_next_progress(surah, ayah)
    print(f"Successfully sent {verse_key}. Progress updated.")

if __name__ == "__main__":
    main()
