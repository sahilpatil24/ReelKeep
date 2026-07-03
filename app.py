"""
Reelkeep — a small local web app for downloading YouTube / Instagram videos
using yt-dlp.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

import os
import uuid
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

ALLOWED_DOMAINS = ("youtube.com", "youtu.be", "instagram.com")

# Instagram (and occasionally YouTube) blocks requests that don't look like
# a logged-in browser. Point this at a browser you're logged into Instagram
# with, and yt-dlp will reuse those cookies — same as viewing the reel
# normally in that browser. Leave as None if you don't need this.
#
# Options: "chrome", "edge", "firefox", "brave", "opera", "vivaldi", "safari"
COOKIES_FROM_BROWSER = None  # e.g. "chrome"


def is_allowed_url(url: str) -> bool:
    return bool(url) and any(domain in url for domain in ALLOWED_DOMAINS)


def base_opts() -> dict:
    """Options shared by every yt-dlp call."""
    opts = {"quiet": True, "noplaylist": True}
    if COOKIES_FROM_BROWSER:
        opts["cookiesfrombrowser"] = (COOKIES_FROM_BROWSER,)
    return opts


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def info():
    """Look up title/thumbnail/duration before downloading, so the UI can
    show a preview card."""
    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()

    if not is_allowed_url(url):
        return jsonify({"error": "Please paste a valid YouTube or Instagram link."}), 400

    ydl_opts = {**base_opts(), "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(url, download=False)
    except Exception as exc:
        return jsonify({"error": f"Couldn't read that link: {exc}"}), 400

    return jsonify(
        {
            "title": meta.get("title"),
            "duration": meta.get("duration"),
            "thumbnail": meta.get("thumbnail"),
            "uploader": meta.get("uploader"),
        }
    )


@app.route("/api/download", methods=["POST"])
def download():
    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    fmt = data.get("format", "video")  # "video" or "audio"

    if not is_allowed_url(url):
        return jsonify({"error": "Please paste a valid YouTube or Instagram link."}), 400

    # unique prefix avoids filename collisions between different downloads
    job_id = str(uuid.uuid4())[:8]
    outtmpl = str(DOWNLOAD_DIR / f"{job_id}_%(title).80s.%(ext)s")

    if fmt == "audio":
        ydl_opts = {
            **base_opts(),
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
    else:
        ydl_opts = {
            **base_opts(),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(meta)
            if fmt == "audio":
                filename = str(Path(filename).with_suffix(".mp3"))
    except Exception as exc:
        return jsonify({"error": f"Download failed: {exc}"}), 400

    if not os.path.exists(filename):
        return jsonify({"error": "Download failed: file was not created."}), 500

    # Files stay in /downloads as a local library. The name sent to the
    # browser strips the internal job-id prefix.
    download_name = os.path.basename(filename).split("_", 1)[-1]
    return send_file(filename, as_attachment=True, download_name=download_name)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
