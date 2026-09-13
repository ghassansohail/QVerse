    # 1. Plain text payload for clean copy/pasting to WhatsApp
    text_content = f"""*Surah {surah_name} ({verse_key})*

{arabic_text}

*اردو:*
{urdu_text}

*English:*
{english_text}"""

    # 2. Print-optimized, large-font HTML
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
    
    <!-- Header -->
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

    <!-- Arabic Indo-Pak Text -->
    <div class="arabic" style="font-family:'Noto Nastaliq Urdu', 'PDMS Saleem Quranic', serif; font-size:32px; line-height:2.4; text-align:right; direction:rtl; color:#000000; margin-bottom:28px; word-spacing:3px;">
      {arabic_text}
    </div>

    <!-- Urdu Translation -->
    <div class="urdu" style="font-family:'Noto Nastaliq Urdu', serif; font-size:22px; line-height:2.2; text-align:right; direction:rtl; color:#0f172a; background-color:#f1f5f9; padding:18px 22px; border-radius:8px; border-right:5px solid #0f172a; margin-bottom:28px;">
      {urdu_text}
    </div>

    <!-- English Translation -->
    <div class="english" style="font-size:16px; line-height:1.7; color:#334155; padding-top:5px;">
      <strong style="color:#0f172a;">Translation:</strong> {english_text}
    </div>

  </div>
</body>
</html>"""

    # Assemble alternative parts: client picks HTML for display/print, text fallback works cleanly
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Ayah — Surah {surah_name} ({verse_key})"
    msg["From"] = os.environ["EMAIL_FROM"]
    msg["To"] = os.environ["EMAIL_TO"]

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
