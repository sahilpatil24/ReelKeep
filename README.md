# Reelkeep

A small local website that downloads YouTube and Instagram videos (or just
the audio) using a link you paste in. Runs entirely on your own machine —
Flask serves the page, [yt-dlp](https://github.com/yt-dlp/yt-dlp) does the
actual extraction/downloading.

```
reelkeep/
├── app.py                # Flask backend (routes: /, /api/info, /api/download)
├── requirements.txt      # Python dependencies
├── templates/
│   └── index.html        # The web page
├── static/
│   ├── style.css
│   └── script.js
└── downloads/            # Downloaded files land here
```

## Prerequisites

1. **Python 3.11+** (required by current yt-dlp releases)
   Check with: `python3 --version`
   Get it from https://www.python.org/downloads/ if needed.

2. **ffmpeg** — required so yt-dlp can merge separate video/audio streams
   into one MP4, and to convert to MP3. This is a system tool, not a Python
   package, so `pip` can't install it for you.

   - **macOS (Homebrew):** `brew install ffmpeg`
   - **Windows:** `choco install ffmpeg` (Chocolatey), or `winget install ffmpeg`,
     or download a build from https://www.gyan.dev/ffmpeg/builds/ and add its
     `bin` folder to your PATH.
   - **Linux (Debian/Ubuntu):** `sudo apt install ffmpeg`

   Verify it worked: `ffmpeg -version`

3. **pip** (comes with Python) to install the two Python libraries used here:
   - **Flask** — the web server/framework
   - **yt-dlp** — the library that talks to YouTube/Instagram and pulls the
     video down (actively maintained fork of youtube-dl, supports both sites)

## Setup

```bash
# 1. Move into the project folder
cd reelkeep

# 2. (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run it
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Using it

1. Paste a YouTube or Instagram link (a single video/reel, not a channel or
   playlist page).
2. Click **Look up** to preview the title/thumbnail (optional, just a sanity
   check that the link works).
3. Choose **MP4 video** or **MP3 audio**.
4. Click **Download** — the file is saved into `downloads/` and your browser
   also offers it as a normal download.

## Notes & limits

- **Playlists/channels** aren't handled — `noplaylist` is forced on so a
  channel link won't accidentally trigger a bulk download.
- yt-dlp is updated frequently to keep up with site changes. If downloads
  suddenly start failing, try `pip install -U yt-dlp` first.

### Instagram login and cookies

Instagram now blocks most requests that don't come from a logged-in
browser session — this happens with any tool that talks to Instagram this
way, not just this app. The fix is to let yt-dlp reuse cookies from a
browser on your computer that's already logged into Instagram:

1. Log into instagram.com in Chrome (or Edge/Firefox/Brave) normally.
2. Set `REELKEEP_COOKIES_FROM_BROWSER` to that browser name before starting the app:
   ```powershell
   $env:REELKEEP_COOKIES_FROM_BROWSER = "chrome"
   python app.py
   ```
   On macOS/Linux, use `REELKEEP_COOKIES_FROM_BROWSER=chrome python app.py`.
3. **Close that browser completely** before starting the app —
   Chrome locks its cookie database while running, which can make yt-dlp
   fail to read it on Windows.
4. Restart the app and try the link again. Leave the variable unset for
   public media that does not need a login.

If it still fails after that, run `pip install -U yt-dlp` (Instagram's
anti-bot measures change often and yt-dlp ships fixes frequently), and
double check the reel is public and the URL loads fine in a private/
incognito window.

### Updating yt-dlp

Install the supported current version with `pip install -U -r requirements.txt`.
The YouTube and Instagram extractors change as those sites change, so an older
installed yt-dlp can stop working even when the app code itself has not changed.

## Please use this responsibly

Only download videos you own, have explicit permission to save, or that are
licensed for reuse. Downloading copyrighted content without permission can
violate YouTube's and Instagram's Terms of Service and copyright law in your
country — this tool doesn't check permissions for you, so that judgment call
is on you.
