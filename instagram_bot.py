#!/usr/bin/env python3
import os
import re
import logging
import tempfile
import asyncio
import requests

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "METS_TON_TOKEN_ICI")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "METS_TA_CLE_ICI")

INSTAGRAM_PATTERN = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:reel|p|tv|reels)/[A-Za-z0-9_\-]+/?(?:\?[^\s]*)?"
)

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)


def download_via_rapidapi(url: str, output_dir: str):
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "instagram-reels-downloader-api.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    resp = requests.get(
        "https://instagram-reels-downloader-api.p.rapidapi.com/download",
        headers=headers,
        params={"url": url},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    video_url = None
    if isinstance(data, dict):
        video_url = (
            data.get("url")
            or data.get("video_url")
            or data.get("download_url")
        )
        if not video_url and "data" in data:
            d = data["data"]
            if isinstance(d, list) and d:
                video_url = d[0].get("url") or d[0].get("video_url")
            elif isinstance(d, dict):
                video_url = d.get("url") or d.get("video_url")

    if not video_url:
        log.error("Réponse API inattendue: %s", data)
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
                filepath = await loop.run_in_executor(
                    None, download_via_rapidapi, url, tmpdir
                )
            except Exception as e:
                log.error("Erreur API: %s", e)
                await status_msg.edit_text(f"❌ Erreur API: {e}")
                continue

            if not filepath:
                await status_msg.edit_text("❌ Impossible de télécharger cette vidéo.")
                continue

            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if file_size_mb > 49:
                await status_msg.edit_text(f"⚠️ Vidéo trop lourde ({file_size_mb:.1f} Mo).")
                continue

            try:
                with open(filepath, "rb") as video_file:
                    await message.reply_video(
                        video=video_file,
                        caption="📥 Reel téléchargé ✅",
                        supports_streaming=True,
                    )
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
