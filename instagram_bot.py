#!/usr/bin/env python3
"""
Bot Telegram - Téléchargeur de Reels Instagram
Détecte les liens Instagram dans un groupe et télécharge + renvoie la vidéo.
"""

import os
import re
import logging
import tempfile
import asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# ─── Configuration ────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "METS_TON_TOKEN_ICI")

# Regex pour détecter les liens Instagram (reels, posts, vidéos)
INSTAGRAM_PATTERN = re.compile(
    r"https?://(?:www\.)?instagram\.com/"
    r"(?:reel|p|tv)/[A-Za-z0-9_\-]+/?(?:\?[^\s]*)?"
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# ─── Téléchargement avec yt-dlp ───────────────────────────────────────────────
def download_instagram_video(url: str, output_dir: str) -> str | None:
    """
    Télécharge la vidéo Instagram et retourne le chemin du fichier.
    Retourne None en cas d'échec.
    """
    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        # Contourner les restrictions basiques
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Assure l'extension .mp4
            if not filename.endswith(".mp4"):
                base = os.path.splitext(filename)[0]
                filename = base + ".mp4"
            if os.path.exists(filename):
                return filename
    except Exception as e:
        log.error("Erreur yt-dlp pour %s : %s", url, e)

    return None


# ─── Handler Telegram ─────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    urls = INSTAGRAM_PATTERN.findall(message.text)
    if not urls:
        return

    log.info("Lien(s) Instagram détecté(s) : %s", urls)

    for url in urls:
        # Message de statut
        status_msg = await message.reply_text(
            f"⏳ Téléchargement en cours…\n🔗 {url}"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Téléchargement (bloquant → thread pool)
            loop = asyncio.get_event_loop()
            filepath = await loop.run_in_executor(
                None, download_instagram_video, url, tmpdir
            )

            if not filepath:
                await status_msg.edit_text(
                    "❌ Impossible de télécharger cette vidéo.\n"
                    "Instagram a peut-être mis à jour ses protections, "
                    "ou le contenu est privé."
                )
                continue

            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            log.info("Vidéo téléchargée : %s (%.1f Mo)", filepath, file_size_mb)

            # Telegram limite les fichiers à 50 Mo via Bot API
            if file_size_mb > 49:
                await status_msg.edit_text(
                    f"⚠️ Vidéo trop lourde ({file_size_mb:.1f} Mo).\n"
                    "La limite Telegram est de 50 Mo."
                )
                continue

            # Envoi de la vidéo
            try:
                with open(filepath, "rb") as video_file:
                    await message.reply_video(
                        video=video_file,
                        caption="📥 Reel téléchargé ✅",
                        supports_streaming=True,
                    )
                await status_msg.delete()
            except Exception as e:
                log.error("Erreur lors de l'envoi : %s", e)
                await status_msg.edit_text(f"❌ Erreur lors de l'envoi : {e}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if BOT_TOKEN == "METS_TON_TOKEN_ICI":
        raise ValueError(
            "❌ Définis la variable d'environnement TELEGRAM_BOT_TOKEN "
            "ou remplace la valeur dans le script."
        )

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Écoute tous les messages texte (groupes + privé)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    log.info("🤖 Bot démarré. En attente de liens Instagram…")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
