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
const progress = document.getElementById("downloadProgress");
const progressMessage = document.getElementById("progressMessage");
const progressPercent = document.getElementById("progressPercent");
const progressTrack = document.getElementById("progressTrack");
const progressFill = document.getElementById("progressFill");
const progressDetails = document.getElementById("progressDetails");
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

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function updateProgress(data) {
  progressMessage.textContent = data.message || "Downloading media…";
  const hasPercent = Number.isFinite(data.percent);
  progress.classList.toggle("indeterminate", !hasPercent);
  progressFill.style.width = hasPercent ? `${data.percent}%` : "35%";
  progressPercent.textContent = hasPercent ? `${data.percent}%` : "…";
  if (hasPercent) progressTrack.setAttribute("aria-valuenow", data.percent);
  else progressTrack.removeAttribute("aria-valuenow");

  const details = [];
  const downloaded = formatBytes(data.downloaded);
  const total = formatBytes(data.total);
  if (downloaded && total) details.push(`${downloaded} of ${total}`);
  else if (downloaded) details.push(`${downloaded} downloaded`);
  if (Number.isFinite(data.speed) && data.speed > 0) {
    details.push(`${formatBytes(data.speed)}/s`);
  }
  if (Number.isFinite(data.eta) && data.eta >= 0 && data.status === "downloading") {
    details.push(`${Math.ceil(data.eta)}s left`);
  }
  progressDetails.textContent = details.join(" · ");
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
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
  progress.classList.remove("hidden");
  progressDetails.textContent = "";
  updateProgress({ status: "starting", percent: 0, message: "Starting download…" });
  setStatus("Connecting to the video source…");

  try {
    const startRes = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, format }),
    });
    const startData = await startRes.json();
    if (!startRes.ok) throw new Error(startData.error || "Download failed to start.");

    let job;
    do {
      await wait(700);
      const progressRes = await fetch(`/api/progress/${encodeURIComponent(startData.job_id)}`);
      const data = await progressRes.json();
      if (!progressRes.ok) throw new Error(data.error || "Could not read download progress.");
      updateProgress(data);
      if (data.status === "error") throw new Error(data.message || "Download failed.");
      job = data;
    } while (job.status !== "complete");

    setStatus("Preparing your file for download…");
    const fileRes = await fetch(`/api/download/${encodeURIComponent(startData.job_id)}`);
    if (!fileRes.ok) {
      const data = await fileRes.json();
      throw new Error(data.error || "Could not retrieve the downloaded file.");
    }

    const blob = await fileRes.blob();
    const disposition = fileRes.headers.get("Content-Disposition") || "";
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
    progress.classList.add("hidden");
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
