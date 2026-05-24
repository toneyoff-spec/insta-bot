#!/usr/bin/env python3
import os, re, logging, tempfile, asyncio, requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "METS_TON_TOKEN_ICI")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "METS_TA_CLE_ICI")
RAPIDAPI_HOST = "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com"

INSTAGRAM_PATTERN = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:reel|p|tv|reels)/[A-Za-z0-9_\-]+/?(?:\?[^\s]*)?"
)

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

def download_via_rapidapi(url, output_dir):
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    resp = requests.get(
        f"https://{RAPIDAPI_HOST}/convert",
        headers=headers,
        params={"url": url},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    log.info("Réponse API: %s", data)

    video_url = None
    if isinstance(data, list) and data:
        video_url = data[0].get("url") or data[0].get("video_url") or data[0].get("src")
    elif isinstance(data, dict):
        video_url = (data.get("url") or data.get("video_url")
                     or data.get("download_url") or data.get("src"))
        if not video_url:
            for key in ("data", "result", "medias", "videos"):
                d = data.get(key)
                if isinstance(d, list) and d:
                    video_url = d[0].get("url") or d[0].get("video_url") or d[0].get("src")
                    break
                elif isinstance(d, dict):
                    video_url = d.get("url") or d.get("video_url") or d.get("src")
                    break

    if not video_url:
        log.error("Pas de video_url dans: %s", data)
        return None

    video_resp = requests.get(video_url, timeout=60, stream=True)
    video_resp.raise_for_status()
    filepath = os.path.join(output_dir, "reel.mp4")
    with open(filepath, "wb") as f:
        for chunk in video_resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return filepath

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    urls = INSTAGRAM_PATTERN.findall(message.text)
    if not urls:
        return
    for url in urls:
        status_msg = await message.reply_text(f"⏳ Téléchargement en cours…\n🔗 {url}")
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = asyncio.get_event_loop()
            try:
                filepath = await loop.run_in_executor(None, download_via_rapidapi, url, tmpdir)
            except Exception as e:
                log.error("Erreur API: %s", e)
                await status_msg.edit_text(f"❌ Erreur API: {e}")
                continue
            if not filepath:
                await status_msg.edit_text("❌ Impossible de télécharger.")
                continue
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if file_size_mb > 49:
                await status_msg.edit_text(f"⚠️ Vidéo trop lourde ({file_size_mb:.1f} Mo).")
                continue
            try:
                with open(filepath, "rb") as vf:
                    await message.reply_video(video=vf, caption="📥 Reel téléchargé ✅", supports_streaming=True)
                await status_msg.delete()
            except Exception as e:
                await status_msg.edit_text(f"❌ Erreur envoi: {e}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("🤖 Bot démarré.")
    app.run_polling(allowed_updates=["message"])

if __name__ == "__main__":
    main()
