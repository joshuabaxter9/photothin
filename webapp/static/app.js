"use strict";

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

const $ = (id) => document.getElementById(id);

const UPLOAD_CONCURRENCY = 4;
const POLL_ACTIVE_MS = 1000;
const PRELOAD_AHEAD = 2;

const REASONS = {
  blurry: ["Blurry", "bad"],
  low_contrast: ["Low contrast", "bad"],
  accidental_shot: ["Looks accidental", "bad"],
  too_dark: ["Too dark", "bad"],
  overexposed: ["Overexposed", "bad"],
  low_resolution: ["Low resolution", "bad"],
  low_significance: ["Not much going on", "bad"],
  ground_only: ["Ground only", "bad"],
  duplicate: ["Duplicate", "bad"],
  near_duplicate: ["Near duplicate", "bad"],
  exact_duplicate: ["Exact copy", "bad"],
  eyes_closed: ["Eyes closed", "bad"],
  contains_face: ["Faces", "good"],
  contains_person: ["People", "good"],
  scenic: ["Scenic", "good"],
};

function formatBytes(bytes) {
  if (!bytes) return "0 MB";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function plural(count, word, pluralWord = `${word}s`) {
  return `${count.toLocaleString()} ${count === 1 ? word : pluralWord}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (_) { /* not JSON */ }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

function postJson(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

let toastTimer = null;
function toast(message) {
  const element = $("toast");
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { element.hidden = true; }, 4000);
}

function showView(name) {
  for (const view of ["start", "upload", "review", "finish"]) {
    $(`view-${view}`).hidden = view !== name;
  }
}

// ---------------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------------

const app = {
  config: null,
  sessionId: null,
  state: null,          // last state from the server
  queue: [],            // photos waiting for a decision, in order
  inFlight: new Set(),  // ids with a decision being saved
  currentId: null,
  preferId: null,       // show this item next (used by undo)
  pollTimer: null,
  busy: false,          // true while a decision or undo request is starting
};

// ---------------------------------------------------------------------------
// Routing: #/ is the start screen, #/session/<id> is a review session
// ---------------------------------------------------------------------------

function route() {
  const match = location.hash.match(/^#\/session\/([0-9a-f]+)/);
  if (match) {
    if (match[1] !== app.sessionId) openSession(match[1]);
  } else {
    closeSession();
    showStart();
  }
}

function closeSession() {
  clearTimeout(app.pollTimer);
  app.sessionId = null;
  app.state = null;
  app.queue = [];
  app.inFlight.clear();
  app.currentId = null;
  app.preferId = null;
  $("topbar-session").hidden = true;
}

// ---------------------------------------------------------------------------
// Start screen
// ---------------------------------------------------------------------------

async function showStart() {
  showView("start");
  $("start-error").hidden = true;
  try {
    const sessions = await api("/api/sessions");
    renderSessionList(sessions);
  } catch (error) {
    $("sessions").hidden = true;
  }
}

function sessionStatusPill(session) {
  if (session.running || session.status === "analyzing") return ["Analyzing", "pill-active"];
  if (session.status === "interrupted" || session.status === "uploading") return ["Paused", "pill-active"];
  if (session.waiting > 0) return [`${session.waiting} to review`, "pill-active"];
  return ["Done", "pill-done"];
}

function renderSessionList(sessions) {
  const list = $("session-list");
  list.replaceChildren();
  $("sessions").hidden = sessions.length === 0;

  for (const session of sessions.slice(0, 12)) {
    const row = document.createElement("li");
    row.className = "session-row";

    const info = document.createElement("div");
    info.className = "session-info";
    const name = document.createElement("div");
    name.className = "session-name";
    name.textContent = session.name;
    const meta = document.createElement("div");
    meta.className = "session-meta";
    const created = new Date(session.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    meta.textContent = `${created} · ${plural(session.total, "file")} · ${session.approved} approved · ${session.discarded} discarded`;
    info.append(name, meta);

    const [label, pillClass] = sessionStatusPill(session);
    const pill = document.createElement("span");
    pill.className = `pill ${pillClass}`;
    pill.textContent = label;

    const open = document.createElement("a");
    open.className = "button";
    open.href = `#/session/${session.id}`;
    open.textContent = "Open";

    const remove = document.createElement("button");
    remove.className = "button button-danger-quiet";
    remove.type = "button";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => deleteSession(session.id, session.name));

    row.append(info, pill, open, remove);
    list.append(row);
  }
}

async function deleteSession(sessionId, name) {
  const confirmed = confirm(
    `Delete "${name}" from this computer?\n\n` +
    "This removes the uploaded copies in its approved and discarded folders. " +
    "Your original folder is not touched."
  );
  if (!confirmed) return;
  try {
    await api(`/api/sessions/${sessionId}`, { method: "DELETE" });
    if (location.hash === "#/" || !location.hash) showStart();
    else location.hash = "#/";
    toast("Session deleted");
  } catch (error) {
    toast(`Could not delete: ${error.message}`);
  }
}

// ---------------------------------------------------------------------------
// Reading a dropped or chosen folder
// ---------------------------------------------------------------------------

function readEntryFile(entry) {
  return new Promise((resolve, reject) => entry.file(resolve, reject));
}

function readDirectoryBatch(reader) {
  return new Promise((resolve, reject) => reader.readEntries(resolve, reject));
}

async function walkEntry(entry, prefix, output) {
  if (entry.isFile) {
    output.push({ file: await readEntryFile(entry), path: prefix + entry.name });
  } else if (entry.isDirectory) {
    const reader = entry.createReader();
    // readEntries returns results in batches, so keep reading until empty.
    for (;;) {
      const batch = await readDirectoryBatch(reader);
      if (batch.length === 0) break;
      for (const child of batch) await walkEntry(child, `${prefix}${entry.name}/`, output);
    }
  }
}

async function filesFromDrop(dataTransfer) {
  // Entries must be collected before the first await, because the browser
  // clears the drop data once the event handler yields.
  const entries = [...dataTransfer.items]
    .map((item) => (item.webkitGetAsEntry ? item.webkitGetAsEntry() : null))
    .filter(Boolean);
  if (entries.length === 0) {
    return [...dataTransfer.files].map((file) => ({ file, path: file.name }));
  }
  const output = [];
  for (const entry of entries) await walkEntry(entry, "", output);
  return output;
}

function filesFromInput(input) {
  return [...input.files].map((file) => ({ file, path: file.webkitRelativePath || file.name }));
}

function isSupported(path) {
  const dot = path.lastIndexOf(".");
  if (dot < 0) return false;
  const extension = path.slice(dot).toLowerCase();
  return app.config.image_extensions.includes(extension) || app.config.video_extensions.includes(extension);
}

function splitRootFolder(entries) {
  // When everything sits inside one top folder, use it as the session name
  // and store paths relative to it.
  const roots = new Set(entries.map(({ path }) => (path.includes("/") ? path.split("/")[0] : "")));
  if (roots.size === 1 && !roots.has("")) {
    const [root] = roots;
    return {
      name: root,
      entries: entries.map(({ file, path }) => ({ file, path: path.slice(root.length + 1) })),
    };
  }
  return { name: entries.length ? `Upload ${new Date().toLocaleDateString()}` : "", entries };
}

// ---------------------------------------------------------------------------
// Uploading
// ---------------------------------------------------------------------------

async function startFromFiles(allEntries) {
  $("start-error").hidden = true;
  const visible = allEntries.filter(({ path }) => !path.split("/").some((part) => part.startsWith(".")));
  const supported = visible.filter(({ path }) => isSupported(path));
  const skipped = visible.length - supported.length;

  if (supported.length === 0) {
    $("start-error").textContent = allEntries.length
      ? "That folder has no photos or videos this app can read."
      : "No files found. Try dropping a folder, or use Choose folder.";
    $("start-error").hidden = false;
    return;
  }

  const { name, entries } = splitRootFolder(supported);
  let session;
  try {
    session = await postJson("/api/sessions", { name });
  } catch (error) {
    $("start-error").textContent = `Could not start: ${error.message}`;
    $("start-error").hidden = false;
    return;
  }

  app.sessionId = session.id;
  history.replaceState(null, "", `#/session/${session.id}`);
  setTopbar(session.name);
  showView("upload");
  $("upload-title").textContent = `Uploading ${session.name}`;
  $("upload-skipped").hidden = skipped === 0;
  $("upload-skipped").textContent = skipped === 1
    ? "1 file skipped because it isn't a photo or video."
    : `${skipped.toLocaleString()} files skipped because they aren't photos or videos.`;

  const failures = await uploadAll(session.id, entries);
  if (app.sessionId !== session.id) return; // user left during upload

  if (failures.length === entries.length) {
    $("upload-title").textContent = "Upload failed";
    $("upload-detail").textContent = failures[0]?.error || "No files could be uploaded.";
    return;
  }
  if (failures.length) toast(`${plural(failures.length, "file")} could not be uploaded and will be skipped.`);

  try {
    await postJson(`/api/sessions/${session.id}/analyze`);
  } catch (error) {
    toast(`Could not start analysis: ${error.message}`);
  }
  showView("review");
  poll();
}

async function uploadAll(sessionId, entries) {
  const totalBytes = entries.reduce((sum, { file }) => sum + file.size, 0);
  let doneFiles = 0;
  let doneBytes = 0;
  let next = 0;
  const failures = [];

  const update = () => {
    $("upload-bar").style.width = `${totalBytes ? (doneBytes / totalBytes) * 100 : 100}%`;
    $("upload-detail").textContent =
      `${doneFiles.toLocaleString()} of ${plural(entries.length, "file")} · ${formatBytes(doneBytes)} of ${formatBytes(totalBytes)}`;
  };
  update();

  async function uploadOne({ file, path }) {
    const form = new FormData();
    form.append("rel_path", path);
    form.append("file", file, file.name);
    for (let attempt = 1; ; attempt += 1) {
      try {
        await api(`/api/sessions/${sessionId}/files`, { method: "POST", body: form });
        return;
      } catch (error) {
        // Retry network hiccups once. Rejections from the server won't change.
        if (attempt >= 2 || (error.status && error.status < 500)) throw error;
      }
    }
  }

  async function worker() {
    while (next < entries.length && app.sessionId === sessionId) {
      const entry = entries[next];
      next += 1;
      try {
        await uploadOne(entry);
      } catch (error) {
        failures.push({ path: entry.path, error: error.message });
      }
      doneFiles += 1;
      doneBytes += entry.file.size;
      update();
    }
  }

  await Promise.all(Array.from({ length: UPLOAD_CONCURRENCY }, worker));
  return failures;
}

// ---------------------------------------------------------------------------
// Review session
// ---------------------------------------------------------------------------

function setTopbar(name) {
  $("topbar-name").textContent = name;
  $("topbar-session").hidden = false;
  document.title = `${name} · PhotoThin`;
}

async function openSession(sessionId) {
  closeSession();
  app.sessionId = sessionId;
  showView("review");
  try {
    const state = await api(`/api/sessions/${sessionId}`);
    setTopbar(state.session.name);
    // A session paused by a server restart or a closed tab picks up where
    // it left off.
    if (!state.running && ["interrupted", "uploading", "analyzing"].includes(state.session.status)) {
      await postJson(`/api/sessions/${sessionId}/analyze`);
    }
  } catch (error) {
    if (error.status === 404) {
      toast("That session no longer exists.");
      location.hash = "#/";
      return;
    }
    toast(`Could not open session: ${error.message}`);
  }
  poll();
}

async function poll() {
  clearTimeout(app.pollTimer);
  const sessionId = app.sessionId;
  if (!sessionId) return;
  try {
    const state = await api(`/api/sessions/${sessionId}`);
    if (sessionId !== app.sessionId) return;
    applyState(state);
  } catch (error) {
    if (error.status === 404) {
      toast("This session was deleted.");
      location.hash = "#/";
      return;
    }
  }
  if (sessionId === app.sessionId && !isFinished()) {
    app.pollTimer = setTimeout(poll, POLL_ACTIVE_MS);
  }
}

function applyState(state) {
  app.state = state;
  app.queue = state.queue.filter((item) => !app.inFlight.has(item.id));
  chooseCurrent();
  render();
}

function chooseCurrent() {
  const ids = new Set(app.queue.map((item) => item.id));
  if (app.preferId && ids.has(app.preferId)) {
    app.currentId = app.preferId;
    app.preferId = null;
  } else if (!ids.has(app.currentId)) {
    app.currentId = app.queue.length ? app.queue[0].id : null;
  }
}

function isFinished() {
  return Boolean(app.state?.finished) && app.queue.length === 0 && app.inFlight.size === 0;
}

function currentItem() {
  return app.queue.find((item) => item.id === app.currentId) || null;
}

function render() {
  const state = app.state;
  if (!state) return;

  if (isFinished()) {
    renderFinish();
    return;
  }
  showView("review");

  const { counts, session } = state;
  const analyzing = state.running || session.status === "analyzing";
  const analyzedShare = counts.total ? counts.analyzed / counts.total : 1;
  $("analysis-bar").style.width = `${analyzedShare * 100}%`;
  $("analysis-bar").classList.toggle("is-done", !analyzing && counts.analyzed === counts.total);
  $("analysis-text").textContent = analyzing
    ? "Analyzing…"
    : session.status === "ready" ? "Analysis complete" : "Analysis paused";
  $("analysis-count").textContent = `${counts.analyzed.toLocaleString()} of ${plural(counts.total, "file")}`;

  const pendingDecisions = app.inFlight.size;
  $("stat-waiting").textContent = app.queue.length.toLocaleString();
  $("stat-approved").textContent = counts.approved.toLocaleString();
  $("stat-discarded").textContent = counts.discarded.toLocaleString();
  $("stat-auto").textContent = counts.auto_kept.toLocaleString();
  $("undo-button").disabled = !(state.can_undo || pendingDecisions > 0) || app.busy;

  const item = currentItem();
  $("review").hidden = !item;
  $("review-empty").hidden = Boolean(item);
  if (!item) {
    if (!analyzing && session.status !== "ready") {
      $("review-empty").querySelector("h2").textContent = "Analysis is paused";
    } else {
      $("review-empty").querySelector("h2").textContent = "Looking for photos to review…";
    }
    return;
  }
  renderItem(item);
}

function renderItem(item) {
  const preview = $("preview");
  const source = `/api/items/${item.id}/preview`;
  if (preview.dataset.itemId !== String(item.id)) {
    preview.dataset.itemId = String(item.id);
    preview.classList.add("is-loading");
    $("stage-message").hidden = true;
    preview.alt = item.name;
    preview.src = source;
  }

  const suggestedDiscard = item.classification === "DISCARD_CANDIDATE";
  const badge = $("item-badge");
  badge.textContent = suggestedDiscard ? "Suggested discard" : "Needs review";
  badge.className = `badge${suggestedDiscard ? " badge-discard" : ""}`;

  const position = app.queue.findIndex((queued) => queued.id === item.id) + 1;
  $("item-position").textContent = `${position} of ${app.queue.length} waiting`;
  $("item-name").textContent = item.name;
  $("item-path").textContent = item.rel_path.includes("/") ? item.rel_path : "";
  $("item-score").textContent = Math.round(item.final_score ?? 0);

  const reasons = $("item-reasons");
  reasons.replaceChildren();
  for (const reason of item.reasons) {
    const [label, tone] = REASONS[reason] || [reason.replaceAll("_", " "), ""];
    const chip = document.createElement("li");
    chip.className = `reason${tone ? ` reason-${tone}` : ""}`;
    chip.textContent = label;
    reasons.append(chip);
  }

  const details = $("item-details");
  details.replaceChildren();
  const rows = [
    ["Size", item.width && item.height ? `${item.width} × ${item.height}` : "—"],
    ["File", formatBytes(item.size_bytes)],
    ["Faces", item.face_count ?? 0],
    ["People", item.person_count ?? 0],
  ];
  for (const [term, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    details.append(dt, dd);
  }

  preloadAfter(item.id);
}

function preloadAfter(itemId) {
  const index = app.queue.findIndex((item) => item.id === itemId);
  for (const item of app.queue.slice(index + 1, index + 1 + PRELOAD_AHEAD)) {
    const image = new Image();
    image.src = `/api/items/${item.id}/preview`;
  }
}

$("preview").addEventListener("load", () => $("preview").classList.remove("is-loading"));
$("preview").addEventListener("error", () => {
  $("preview").classList.remove("is-loading");
  $("stage-message").textContent = "No preview available for this photo. You can still keep or discard it.";
  $("stage-message").hidden = false;
});

function flashStage(decision) {
  const stage = document.querySelector(".stage");
  const className = decision === "keep" ? "flash-keep" : "flash-discard";
  stage.classList.add(className);
  setTimeout(() => stage.classList.remove(className), 180);
}

async function decide(decision) {
  const item = currentItem();
  if (!item || app.busy) return;
  const sessionId = app.sessionId;

  flashStage(decision);
  app.inFlight.add(item.id);
  const index = app.queue.findIndex((queued) => queued.id === item.id);
  app.queue.splice(index, 1);
  app.currentId = app.queue[Math.min(index, app.queue.length - 1)]?.id ?? null;
  render();

  try {
    await postJson(`/api/items/${item.id}/decision`, { decision });
  } catch (error) {
    toast(`Could not save that decision: ${error.message}`);
    app.preferId = item.id;
  } finally {
    app.inFlight.delete(item.id);
  }
  if (sessionId === app.sessionId) poll();
}

async function undo() {
  if (app.busy || !app.sessionId) return;
  app.busy = true;
  render();
  try {
    // Let decisions that are still saving finish, so undo reverses the
    // decision the user actually made last.
    while (app.inFlight.size) await new Promise((resolve) => setTimeout(resolve, 50));
    const item = await postJson(`/api/sessions/${app.sessionId}/undo`);
    app.preferId = item.id;
    toast(`Undid: ${item.name} is back in the queue`);
  } catch (error) {
    toast(error.status === 409 ? "Nothing to undo" : `Could not undo: ${error.message}`);
  } finally {
    app.busy = false;
  }
  poll();
}

$("keep-button").addEventListener("click", () => decide("keep"));
$("discard-button").addEventListener("click", () => decide("discard"));
$("undo-button").addEventListener("click", undo);

document.addEventListener("keydown", (event) => {
  if (event.target.closest("input, textarea, select") || event.altKey || event.metaKey) return;
  const reviewing = !$("view-review").hidden;
  const finishing = !$("view-finish").hidden;
  const key = event.key.toLowerCase();

  if (reviewing && !event.ctrlKey && (key === "k" || event.key === "ArrowRight")) {
    event.preventDefault();
    decide("keep");
  } else if (reviewing && !event.ctrlKey && (key === "d" || event.key === "ArrowLeft")) {
    event.preventDefault();
    decide("discard");
  } else if ((reviewing || finishing) && key === "z") {
    event.preventDefault();
    undo();
  }
});

// ---------------------------------------------------------------------------
// Finish screen and downloads
// ---------------------------------------------------------------------------

function renderFinish() {
  clearTimeout(app.pollTimer);
  showView("finish");
  const { counts, folders } = app.state;

  const parts = [`${plural(counts.total, "file")} sorted`];
  parts.push(`${counts.approved.toLocaleString()} approved (${counts.auto_kept.toLocaleString()} automatically)`);
  parts.push(counts.auto_discarded
    ? `${counts.discarded.toLocaleString()} discarded (${counts.auto_discarded.toLocaleString()} automatically)`
    : `${counts.discarded.toLocaleString()} discarded`);
  if (counts.failed) parts.push(`${plural(counts.failed, "file")} couldn't be analyzed and were kept`);
  $("finish-summary").textContent = `${parts.join(" · ")}.`;

  setDownloadOption("approved", counts.approved, counts.approved_bytes);
  setDownloadOption("discarded", counts.discarded, counts.discarded_bytes);

  const paths = $("folder-paths");
  paths.replaceChildren();
  for (const [label, key] of [["Approved", "approved"], ["Discarded", "discarded"]]) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = folders[key];
    paths.append(dt, dd);
  }
}

function setDownloadOption(bucket, count, bytes) {
  const option = $(`option-${bucket}`);
  const checkbox = option.querySelector("input");
  const empty = count === 0;
  option.classList.toggle("is-empty", empty);
  checkbox.disabled = empty;
  if (empty) checkbox.checked = false;
  $(`${bucket}-detail`).textContent = empty
    ? "Empty"
    : `${plural(count, "file")} · ${formatBytes(bytes)} zip`;
  updateDownloadButton();
}

function updateDownloadButton() {
  const anyChecked = [...document.querySelectorAll('#download-form input[name="bucket"]')].some((box) => box.checked);
  $("download-button").disabled = !anyChecked;
}

$("download-form").addEventListener("change", updateDownloadButton);

$("download-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const buckets = [...document.querySelectorAll('#download-form input[name="bucket"]:checked')].map((box) => box.value);
  if (!buckets.length || !app.sessionId) return;
  $("download-status").textContent = buckets.length > 1
    ? "Preparing two downloads. Your browser may ask to allow multiple downloads."
    : "Preparing your download…";
  for (const [index, bucket] of buckets.entries()) {
    const link = document.createElement("a");
    link.href = `/api/sessions/${app.sessionId}/download/${bucket}`;
    link.download = "";
    document.body.append(link);
    link.click();
    link.remove();
    if (index < buckets.length - 1) await new Promise((resolve) => setTimeout(resolve, 800));
  }
  setTimeout(() => { $("download-status").textContent = "Download started. Check your browser's downloads."; }, 1200);
});

$("delete-session").addEventListener("click", () => {
  if (app.state) deleteSession(app.sessionId, app.state.session.name);
});

// ---------------------------------------------------------------------------
// Folder input and drag and drop
// ---------------------------------------------------------------------------

const dropzone = $("dropzone");

$("folder-input").addEventListener("change", (event) => {
  const entries = filesFromInput(event.target);
  event.target.value = "";
  startFromFiles(entries);
});

dropzone.addEventListener("dragenter", (event) => { event.preventDefault(); dropzone.classList.add("is-dragging"); });
dropzone.addEventListener("dragover", (event) => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; });
dropzone.addEventListener("dragleave", (event) => {
  if (!dropzone.contains(event.relatedTarget)) dropzone.classList.remove("is-dragging");
});
dropzone.addEventListener("drop", async (event) => {
  event.preventDefault();
  dropzone.classList.remove("is-dragging");
  const entries = await filesFromDrop(event.dataTransfer);
  startFromFiles(entries);
});

// A file dropped anywhere else would make the browser navigate away to it.
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => event.preventDefault());

// ---------------------------------------------------------------------------
// Start up
// ---------------------------------------------------------------------------

(async function init() {
  try {
    app.config = await api("/api/config");
  } catch (error) {
    app.config = { image_extensions: [], video_extensions: [] };
    toast("Could not reach the PhotoThin server.");
  }
  window.addEventListener("hashchange", route);
  route();
})();
