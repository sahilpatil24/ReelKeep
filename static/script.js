const urlInput = document.getElementById("url");
const previewBtn = document.getElementById("previewBtn");
const preview = document.getElementById("preview");
const previewThumb = document.getElementById("previewThumb");
const previewTitle = document.getElementById("previewTitle");
const previewSub = document.getElementById("previewSub");
const downloadBtn = document.getElementById("downloadBtn");
const btnLabel = downloadBtn.querySelector(".btn-label");
const spinner = downloadBtn.querySelector(".reel-spinner");
const statusEl = document.getElementById("status");
const toggle = document.getElementById("formatToggle");

let format = "video";

toggle.addEventListener("click", (e) => {
  const opt = e.target.closest(".toggle-opt");
  if (!opt) return;
  toggle.querySelectorAll(".toggle-opt").forEach(o => o.classList.remove("active"));
  opt.classList.add("active");
  format = opt.dataset.format;
});

function setStatus(msg, type = "") {
  statusEl.textContent = msg;
  statusEl.className = "status" + (type ? " " + type : "");
}

function formatDuration(sec) {
  if (!sec) return "";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

previewBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  if (!url) return setStatus("Paste a link first.", "error");

  setStatus("Looking up video…");
  preview.classList.add("hidden");

  try {
    const res = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Lookup failed.");

    previewThumb.src = data.thumbnail || "";
    previewTitle.textContent = data.title || "Untitled";
    previewSub.textContent = [data.uploader, formatDuration(data.duration)]
      .filter(Boolean)
      .join(" · ");
    preview.classList.remove("hidden");
    setStatus("");
  } catch (err) {
    setStatus(err.message, "error");
  }
});

downloadBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  if (!url) return setStatus("Paste a link first.", "error");

  downloadBtn.disabled = true;
  btnLabel.textContent = "Downloading…";
  spinner.classList.remove("hidden");
  setStatus("Fetching and saving — this can take a moment for longer videos.");

  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, format }),
    });

    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || "Download failed.");
    }

    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `download.${format === "audio" ? "mp3" : "mp4"}`;

    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();

    setStatus(`Saved: ${filename}`, "success");
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    downloadBtn.disabled = false;
    btnLabel.textContent = "Download";
    spinner.classList.add("hidden");
  }
});

urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") previewBtn.click();
});
