"""
Reelkeep — a small local web app for downloading YouTube / Instagram videos
using yt-dlp.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

import os
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
DOWNLOAD_JOBS = {}
DOWNLOAD_JOBS_LOCK = threading.Lock()

ALLOWED_DOMAINS = ("youtube.com", "youtu.be", "instagram.com")

# Instagram (and occasionally YouTube) blocks requests that don't look like
# a logged-in browser. Point this at a browser you're logged into Instagram
# with, and yt-dlp will reuse those cookies — same as viewing the reel
# normally in that browser. Leave as None if you don't need this.
#
# Set REELKEEP_COOKIES_FROM_BROWSER to a browser name (for example "chrome")
# when Instagram requires an authenticated session.
COOKIES_FROM_BROWSER = os.environ.get("REELKEEP_COOKIES_FROM_BROWSER")


def is_allowed_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)
    )


def base_opts() -> dict:
    """Options shared by every yt-dlp call."""
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
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

    job_id = uuid.uuid4().hex
    with DOWNLOAD_JOBS_LOCK:
        DOWNLOAD_JOBS[job_id] = {
            "status": "starting",
            "percent": 0,
            "message": "Starting download…",
        }

    worker = threading.Thread(
        target=run_download, args=(job_id, url, fmt), daemon=True
    )
    worker.start()
    return jsonify({"job_id": job_id}), 202


def run_download(job_id: str, url: str, fmt: str) -> None:
    """Download media in the background and publish yt-dlp progress."""
    outtmpl = str(DOWNLOAD_DIR / f"{job_id}_%(title).80s.%(ext)s")

    def update_job(**updates):
        with DOWNLOAD_JOBS_LOCK:
            DOWNLOAD_JOBS[job_id].update(updates)

    def progress_hook(data):
        if data.get("status") == "downloading":
            downloaded = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            percent = round(downloaded * 100 / total) if total else None
            update_job(
                status="downloading",
                percent=min(percent, 99) if percent is not None else None,
                downloaded=downloaded,
                total=total,
                speed=data.get("speed"),
                eta=data.get("eta"),
                message="Downloading media…",
            )
        elif data.get("status") == "finished":
            update_job(status="processing", percent=99, message="Finalizing media…")

    if fmt == "audio":
        ydl_opts = {
            **base_opts(),
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "progress_hooks": [progress_hook],
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
            "progress_hooks": [progress_hook],
            "merge_output_format": "mp4",
        }

    try:
        update_job(status="starting", percent=0, message="Connecting to source…")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        candidates = [
            path for path in DOWNLOAD_DIR.glob(f"{job_id}_*") if path.is_file()
        ]
        if fmt == "audio":
            candidates = [path for path in candidates if path.suffix.lower() == ".mp3"]
        if len(candidates) != 1:
            raise FileNotFoundError("yt-dlp did not produce one downloadable output file")

        output = candidates[0]
        update_job(
            status="complete",
            percent=100,
            message="Download ready",
            filename=str(output),
            download_name=output.name.split("_", 1)[-1],
        )
    except Exception as exc:
        message = str(exc)
        if COOKIES_FROM_BROWSER and "cookie" in message.lower():
            message += " Close the selected browser and confirm you are logged in."
        update_job(status="error", message=f"Download failed: {message}")


@app.route("/api/progress/<job_id>")
def download_progress(job_id: str):
    with DOWNLOAD_JOBS_LOCK:
        job = DOWNLOAD_JOBS.get(job_id)
        if not job:
            return jsonify({"error": "Download job not found."}), 404
        return jsonify({key: value for key, value in job.items() if key not in {"filename", "download_name"}})


@app.route("/api/download/<job_id>")
def download_file(job_id: str):
    with DOWNLOAD_JOBS_LOCK:
        job = DOWNLOAD_JOBS.get(job_id)
        if not job or job.get("status") != "complete":
            return jsonify({"error": "Download is not ready."}), 404
        filename = job["filename"]
        download_name = job["download_name"]
    if not os.path.exists(filename):
        return jsonify({"error": "Download file is no longer available."}), 404
    return send_file(filename, as_attachment=True, download_name=download_name)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
