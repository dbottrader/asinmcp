/* ASINMCP Console (CP-0025) — vanilla JS, no dependencies.
 *
 * Honesty rules baked in:
 * - Every panel renders data fetched from the same repo files the agents use.
 *   If a fetch fails, the panel says so; nothing is faked or pre-filled.
 * - The verify tools recompute SHA-256 hashes in-browser (real). They NEVER
 *   display "signature OK": Ed25519 checking is delegated, in writing, to the
 *   repo's own tools (pngbind.py / crypto.py), exactly as EXAMPLE.md does.
 */
"use strict";

/* ---------- pure helpers (no DOM) ---------- */

function bufToHex(buf) {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return bufToHex(digest);
}

/* Parse a PNG byte array the same way pngbind.py does: walk chunks,
 * collect tEXt keyword->value pairs, and keep the raw IDAT payloads so the
 * caller can hash their concatenation (the image-content hash). */
function parsePng(bytes) {
  const SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  if (bytes.length < 8 || !SIG.every((v, i) => bytes[i] === v)) {
    return { isPng: false, texts: {}, idatParts: [] };
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const latin1 = new TextDecoder("iso-8859-1");
  const texts = {};
  const idatParts = [];
  let pos = 8;
  while (pos + 8 <= bytes.length) {
    const len = view.getUint32(pos);
    const type = latin1.decode(bytes.subarray(pos + 4, pos + 8));
    const dataStart = pos + 8;
    const dataEnd = dataStart + len;
    if (dataEnd > bytes.length) break;
    const payload = bytes.subarray(dataStart, dataEnd);
    if (type === "IDAT") {
      idatParts.push(payload.slice());
    } else if (type === "tEXt") {
      const nul = payload.indexOf(0);
      if (nul > 0) {
        const keyword = latin1.decode(payload.subarray(0, nul));
        texts[keyword] = latin1.decode(payload.subarray(nul + 1));
      }
    }
    pos = dataEnd + 4; /* skip CRC */
    if (type === "IEND") break;
  }
  return { isPng: true, texts, idatParts };
}

function concatParts(parts) {
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const p of parts) { out.set(p, off); off += p.length; }
  return out;
}

function parseJsonl(text) {
  return text.split("\n").filter((l) => l.trim().length > 0).map((l) => JSON.parse(l));
}

/* ---------- DOM helpers ---------- */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function escRow(label, value, mono) {
  const tr = el("tr");
  tr.appendChild(el("th", null, label));
  const td = el("td", mono ? "mono" : null, value);
  tr.appendChild(td);
  return tr;
}

function showLoadError(id, path, err) {
  const box = document.getElementById(id);
  box.hidden = false;
  box.textContent = "Could not load " + path + " (" + err.message + "). " +
    "This panel reads the live repo file; if you opened this page from disk, serve the " +
    "repo over HTTP instead — e.g. `python3 -m http.server` in the repo root.";
}

/* ---------- header glyph fallback ---------- */

(function initGlyph() {
  const img = document.getElementById("glyphImg");
  const fallback = document.getElementById("glyphFallback");
  img.addEventListener("error", () => {
    img.hidden = true;
    fallback.hidden = false;
  });
  /* If the image already failed before this script ran: */
  if (img.complete && img.naturalWidth === 0 && img.src) {
    img.hidden = true;
    fallback.hidden = false;
  }
})();

/* ---------- START HERE actions ---------- */

document.getElementById("startVerifyBtn").addEventListener("click", () => {
  const hint = document.getElementById("startVerifyHint");
  hint.hidden = false;
  document.getElementById("verify").scrollIntoView({ behavior: "smooth", block: "start" });
  const dz = document.getElementById("pngDrop");
  dz.classList.add("pulse");
  setTimeout(() => dz.classList.remove("pulse"), 1600);
  dz.focus({ preventScroll: true });
});

document.getElementById("startBountiesLink").addEventListener("click", (ev) => {
  ev.preventDefault();
  document.getElementById("bounties").scrollIntoView({ behavior: "smooth", block: "start" });
});

/* ---------- VERIFY A: glyph-bound PNG ---------- */

async function checkPngFile(file) {
  const out = document.getElementById("pngResult");
  out.innerHTML = "";
  if (!file) return;
  const bytes = new Uint8Array(await file.arrayBuffer());
  const parsed = parsePng(bytes);
  if (!parsed.isPng) {
    out.appendChild(el("p", "verdict bad", "✗ Not a PNG file — no chunks to parse."));
    return;
  }
  const rawBinding = parsed.texts["asinmcp:binding"];
  const sig = parsed.texts["asinmcp:binding.sig"];
  if (!rawBinding) {
    out.appendChild(el("p", "verdict bad",
      "✗ This PNG carries no asinmcp:binding record. It is not a glyph-bound artifact " +
      "(platforms strip metadata on upload — use the canonical file from the release)."));
    return;
  }
  let binding;
  try {
    binding = JSON.parse(rawBinding);
  } catch (e) {
    out.appendChild(el("p", "verdict bad", "✗ Binding record present but not valid JSON: " + e.message));
    return;
  }
  const contentHash = await sha256Hex(concatParts(parsed.idatParts));
  const match = contentHash === binding.content_sha256;

  const table = el("table", "kv");
  const body = el("tbody");
  body.appendChild(escRow("File", file.name + " (" + bytes.length + " bytes)"));
  body.appendChild(escRow("Artifact", binding.artifact || "—"));
  body.appendChild(escRow("Lattice snapshot", binding.snapshot_id || "—"));
  body.appendChild(escRow("Release class", binding.release_class || "—"));
  body.appendChild(escRow("Bound at", binding.bound_at || "—"));
  body.appendChild(escRow("Signer pubkey (in binding)", binding.pubkey || "—", true));
  body.appendChild(escRow("Content SHA-256, recomputed here", contentHash, true));
  body.appendChild(escRow("Content SHA-256, in binding", binding.content_sha256 || "—", true));
  table.appendChild(body);
  out.appendChild(table);

  out.appendChild(el("p", "verdict " + (match ? "good" : "bad"),
    match
      ? "✓ CONTENT HASH MATCH — these pixels are exactly the content that was bound."
      : "✗ CONTENT HASH MISMATCH — this image content is NOT what the binding describes."));

  if (sig) {
    out.appendChild(el("p", null,
      "Signature: PRESENT in the file (asinmcp:binding.sig, " + sig.length +
      " hex chars, begins " + sig.slice(0, 16) + "…)."));
  } else {
    out.appendChild(el("p", "verdict bad", "Signature chunk: MISSING (asinmcp:binding.sig not found)."));
  }
  out.appendChild(el("p", "note",
    "What this page did not do: check the Ed25519 signature itself. Hash equality is " +
    "recomputed here, live; signature validity is a separate cryptographic check. " +
    "Run it with the repo’s own tool:  python3 pngbind.py verify <file>  — it also " +
    "confirms the signer is the pinned fleet key, not merely any key."));
}

(function initPngDrop() {
  const dz = document.getElementById("pngDrop");
  const input = document.getElementById("pngFile");
  input.addEventListener("change", () => checkPngFile(input.files[0]));
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) checkPngFile(f);
  });
})();

/* ---------- VERIFY B: registry snapshot ---------- */

document.getElementById("snapCheckBtn").addEventListener("click", async () => {
  const out = document.getElementById("snapResult");
  out.innerHTML = "";
  const cpbin = document.getElementById("cpbinFile").files[0];
  const sigFile = document.getElementById("sigFile").files[0];
  if (!cpbin || !sigFile) {
    out.appendChild(el("p", "verdict bad", "Pick both files first: the snapshot and its .sig.json record."));
    return;
  }
  let sigRec;
  try {
    sigRec = JSON.parse(await sigFile.text());
  } catch (e) {
    out.appendChild(el("p", "verdict bad", "✗ Signature record is not valid JSON: " + e.message));
    return;
  }
  const bytes = new Uint8Array(await cpbin.arrayBuffer());
  const computed = await sha256Hex(bytes);
  const match = computed === sigRec.sha256;

  const table = el("table", "kv");
  const body = el("tbody");
  body.appendChild(escRow("Snapshot file", cpbin.name + " (" + bytes.length + " bytes)"));
  body.appendChild(escRow("SHA-256, recomputed here", computed, true));
  body.appendChild(escRow("SHA-256, in signature record", sigRec.sha256 || "—", true));
  body.appendChild(escRow("Signer pubkey", sigRec.pubkey || "—", true));
  body.appendChild(escRow("Signed at", sigRec.signed_at || "—"));
  table.appendChild(body);
  out.appendChild(table);
  out.appendChild(el("p", "verdict " + (match ? "good" : "bad"),
    match
      ? "✓ HASH MATCH — this snapshot is byte-for-byte the artifact the signature record describes."
      : "✗ HASH MISMATCH — this file is not the snapshot that record was issued for."));
  out.appendChild(el("p", "note",
    "Not checked here: the Ed25519 signature over those bytes, and whether the signer is " +
    "the pinned fleet key. Both are checked by the repo tool:  python3 crypto.py verify registry.cpbin"));
});

/* ---------- REGISTRY ---------- */

const registryState = { records: [], kind: "all", query: "" };

function renderRegistry() {
  const body = document.getElementById("registryBody");
  body.innerHTML = "";
  const q = registryState.query.toLowerCase();
  const rows = registryState.records.filter((r) => {
    if (registryState.kind !== "all" && r.type !== registryState.kind) return false;
    if (!q) return true;
    return [r.id, r.name, r.status, r.anchor, r.type]
      .join(" ").toLowerCase().includes(q);
  });
  for (const r of rows) {
    const tr = el("tr");
    tr.appendChild(el("td", "mono", r.id));
    tr.appendChild(el("td", null, r.type));
    tr.appendChild(el("td", null, r.name));
    tr.appendChild(el("td", null, r.status));
    const anchorTd = el("td", "mono truncate", r.anchor || "—");
    anchorTd.title = r.anchor || "";
    tr.appendChild(anchorTd);
    tr.appendChild(el("td", null, r.created || "—"));
    body.appendChild(tr);
  }
  document.getElementById("registryCount").textContent =
    "— " + rows.length + " of " + registryState.records.length + " records shown";
}

(async function loadRegistry() {
  try {
    const res = await fetch("../registry.jsonl");
    if (!res.ok) throw new Error("HTTP " + res.status);
    registryState.records = parseJsonl(await res.text());
    renderRegistry();
  } catch (err) {
    showLoadError("registryError", "../registry.jsonl", err);
  }
})();

document.querySelectorAll(".filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    registryState.kind = btn.dataset.kind;
    renderRegistry();
  });
});
document.getElementById("registrySearch").addEventListener("input", (e) => {
  registryState.query = e.target.value;
  renderRegistry();
});

/* ---------- LATTICE ---------- */

const latticeState = { nodes: new Map() };

function renderLatticeDetail(node, indexEntry) {
  const box = document.getElementById("latticeDetail");
  box.innerHTML = "";
  box.appendChild(el("h3", "mono", node.snapshot_id));
  const table = el("table", "kv");
  const body = el("tbody");
  body.appendChild(escRow("Status", node.status || "—"));
  body.appendChild(escRow("Parent", node.parent || "— (genesis)"));
  body.appendChild(escRow("Created", node.created || "—"));
  body.appendChild(escRow("Index SHA-256", (indexEntry && indexEntry.sha256) || "—", true));
  table.appendChild(body);
  box.appendChild(table);
  box.appendChild(el("h4", null, "Source"));
  box.appendChild(el("p", null, node.source || "—"));
  box.appendChild(el("h4", null, "Anchors"));
  const ul = el("ul", "anchors");
  const anchors = Array.isArray(node.anchors) ? node.anchors : [];
  if (anchors.length === 0) ul.appendChild(el("li", null, "—"));
  for (const a of anchors) {
    if (a && typeof a === "object") {
      const li = el("li");
      li.appendChild(el("strong", "mono", a.key + ": "));
      li.appendChild(document.createTextNode(a.value || ""));
      ul.appendChild(li);
    } else {
      ul.appendChild(el("li", null, String(a)));
    }
  }
  box.appendChild(ul);
  box.appendChild(el("h4", null, "Forecast"));
  const fc = el("ul", "anchors");
  const forecasts = Array.isArray(node.forecast) ? node.forecast : (node.forecast ? [node.forecast] : []);
  if (forecasts.length === 0) fc.appendChild(el("li", null, "—"));
  for (const f of forecasts) fc.appendChild(el("li", null, String(f)));
  box.appendChild(fc);
  if (Array.isArray(node.links) && node.links.length) {
    box.appendChild(el("p", "hint", "Links: " + node.links.join(" · ")));
  }
}

(async function loadLattice() {
  try {
    const res = await fetch("../lattice/INDEX.jsonl");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const entries = parseJsonl(await res.text());
    document.getElementById("latticeCount").textContent = "— " + entries.length + " nodes";
    const list = document.getElementById("latticeList");
    for (const entry of entries) {
      latticeState.nodes.set(entry.snapshot_id, entry);
      const li = el("li");
      const btn = el("button", "node-btn", entry.snapshot_id);
      btn.type = "button";
      const anchorsLine = el("span", "node-anchors",
        (entry.anchors || []).join(" · "));
      li.appendChild(btn);
      li.appendChild(anchorsLine);
      btn.addEventListener("click", async () => {
        document.querySelectorAll(".node-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const detail = document.getElementById("latticeDetail");
        detail.innerHTML = "";
        detail.appendChild(el("p", "hint", "Loading " + entry.file + "…"));
        try {
          const r = await fetch("../lattice/" + entry.file);
          if (!r.ok) throw new Error("HTTP " + r.status);
          renderLatticeDetail(await r.json(), entry);
        } catch (err) {
          detail.innerHTML = "";
          detail.appendChild(el("p", "verdict bad",
            "✗ Could not load ../lattice/" + entry.file + " (" + err.message + ")"));
        }
      });
      list.appendChild(li);
    }
  } catch (err) {
    showLoadError("latticeError", "../lattice/INDEX.jsonl", err);
  }
})();

/* ---------- BOUNTIES ---------- */

(async function loadBounties() {
  try {
    /* Snapshot of ~/workspace/proof-of-pay/bounties.json (public data),
     * synced into console/data/bounties.json on 2026-10-29. */
    const res = await fetch("data/bounties.json");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const bounties = await res.json();
    document.getElementById("bountyCount").textContent =
      "— " + bounties.length + " escrowed, " +
      bounties.reduce((n, b) => n + (b.price || 0), 0).toFixed(1) + " HHC total";
    const wrap = document.getElementById("bountyCards");
    for (const b of bounties) {
      const card = el("article", "card");
      card.appendChild(el("h3", null, b.title));
      const table = el("table", "kv");
      const body = el("tbody");
      body.appendChild(escRow("Price", (b.price != null ? b.price.toFixed(1) : "—") + " HHC"));
      body.appendChild(escRow("State", "escrowed — open for an agent to claim and complete"));
      body.appendChild(escRow("Publisher", b.publisher || "—"));
      body.appendChild(escRow("Work ID", b.work_id || "—", true));
      body.appendChild(escRow("Escrow ID", b.escrow_id || "—", true));
      body.appendChild(escRow("Lock receipt", b.receipt || "—", true));
      table.appendChild(body);
      card.appendChild(table);
      wrap.appendChild(card);
    }
  } catch (err) {
    showLoadError("bountyError", "data/bounties.json", err);
  }
})();
