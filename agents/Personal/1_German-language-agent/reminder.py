"""Daily practice reminder via Gmail SMTP.

cron-job.org hits:  https://<your-app>.streamlit.app/?action=remind&token=<REMINDER_TOKEN>
Streamlit executes the reminder block at the top of app.py on page load.
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_reminder(
    recipient_email: str,
    session_count_today: int = 0,
    streak: int = 0,
    app_url: str = "",
) -> bool:
    smtp_user = os.environ.get("GMAIL_USER", "")
    smtp_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    app_url = app_url or os.environ.get("APP_URL", "http://localhost:8501")

    if not smtp_user or not smtp_password or not recipient_email:
        print("Reminder: missing credentials or recipient – skipped.")
        return False

    hour = datetime.now().hour
    greeting = "Guten Morgen! 🌅" if hour < 12 else "Guten Abend! 🌙"

    if session_count_today == 0:
        subject = "🇩🇪 Deutsch – Ma még nem gyakoroltál!"
        body_intro = "Ma még nem volt gyakorlás – most jó alkalom!"
        cta = "Indítsd el a napi sessiont →"
    elif session_count_today == 1:
        subject = f"🇩🇪 Deutsch – Még egy kör! (1/2 kész ✅)"
        body_intro = "Az első session megvan – már csak egy hiányzik a napi célból!"
        cta = "Második session →"
    else:
        subject = f"🇩🇪 Deutsch – Mai cél teljesítve! 🎉"
        body_intro = f"Fantasztikus! {session_count_today} session mögötted van ma. Ha van kedved, gyakorolhatsz tovább."
        cta = "Megnyitás →"

    streak_badge = (
        f'<span style="background:#FF6B35;color:white;padding:4px 10px;border-radius:20px;font-weight:bold;">'
        f"🔥 {streak} napos streak!</span>"
        if streak >= 2
        else ""
    )

    html = f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f9f9f9;padding:0;margin:0;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table width="560" style="background:#ffffff;border-radius:8px;overflow:hidden;
               box-shadow:0 2px 8px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background:#2E4057;padding:24px 32px;">
              <h1 style="color:#ffffff;margin:0;font-size:22px;letter-spacing:1px;">
                🇩🇪 Deutsch Üben
              </h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:28px 32px;">
              <p style="font-size:18px;color:#333;margin:0 0 8px;">{greeting}</p>
              <p style="font-size:15px;color:#555;margin:0 0 20px;">{body_intro}</p>

              {f'<p style="margin:0 0 20px;">{streak_badge}</p>' if streak_badge else ''}

              <!-- Progress bar -->
              <div style="background:#eee;border-radius:4px;height:8px;margin-bottom:20px;">
                <div style="background:#4CAF50;width:{min(session_count_today * 50, 100)}%;
                     height:8px;border-radius:4px;"></div>
              </div>
              <p style="font-size:13px;color:#888;margin:0 0 24px;">
                Napi haladás: {session_count_today}/2 session
              </p>

              <!-- CTA Button -->
              <a href="{app_url}"
                 style="background:#2E4057;color:#ffffff;text-decoration:none;
                        padding:14px 28px;border-radius:6px;font-size:15px;
                        font-weight:bold;display:inline-block;">
                {cta}
              </a>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f5f5f5;padding:16px 32px;border-top:1px solid #eee;">
              <p style="font-size:12px;color:#aaa;margin:0;">
                Napi 2×30 perc – B2 elérhető közelségben van. 💪<br>
                Ez egy automatikus emlékeztető. Leállításhoz töröld a cron-job.org feladatot.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Deutsch Üben <{smtp_user}>"
    msg["To"] = recipient_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipient_email, msg.as_string())
        print(f"Reminder sent → {recipient_email}")
        return True
    except Exception as exc:
        print(f"Reminder failed: {exc}")
        return False
