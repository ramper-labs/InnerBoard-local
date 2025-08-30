# InnerBoard-local — “Best Local Agent” Winning Plan

**Goal:** Evolve InnerBoard-local from a great private journaling CLI into a *must‑have* offline onboarding coach that uniquely requires local LLMs — and demonstrate it crisply for the OpenAI Open Model Hackathon judges.

---

## 1) The (Real) User Problem & Why Local Is Non‑Negotiable
**New hires** (ICs & managers) need trusted space to think clearly, triage blockers, and prepare for 1:1s — but:
- Their raw reflections include **PII, secrets, unreleased code**, and candid opinions. Cloud tools break trust.
- Onboarding context sits **on the device**: local repos, docs, emails/ICS, Slack exports, terminal history, VSCode notes.
- Tactical help is needed **in the moment**: write a Slack message, summarize a PR, prep a 1:1 — all using local context.

**Therefore**: the agent must live entirely offline, with *provable* air‑gapping and OS‑level integrations. That’s the product moat and the category fit (Best Local Agent).

---

## 2) One‑Sentence Positioning
> **InnerBoard-local** is an *air‑gapped onboarding agent* that turns your private reflections **and** local work artifacts (docs, git logs, ICS, Slack exports) into **micro‑advice, 1:1 packets, and ask‑templates** — all verified to run **100% offline** with cryptographic “privacy receipts.”

---

## 3) What We’ll Ship for Hackathon (v1.5)
### A. “Requires‑Local” Capabilities (MVP)
1) **Private Context Fusion (PCF)**  
   - Opt‑in ingestion of: a) a watched folder (handbook.md, arch docs, tickets), b) **Slack export ZIP** (user‑provided), c) **Calendar ICS** files, d) **git logs** of current repo.  
   - Local FTS index (SQLite FTS5) + lightweight chunking & embeddings (CPU‑friendly) — *no network*.
2) **RAG‑grounded SRE/MAC**  
   - SRE (Structured Reflection Extraction) now includes an **evidence field** with local source paths + line ranges.  
   - MAC (Micro‑Advice Composer) must cite which *local* artifact informed each step.
3) **1:1 Packet Generator**  
   - `innerboard packet --week N` → PDF/Markdown summary: wins, blockers, deltas, asks, links to local files.
4) **Ask‑Template Builder**  
   - `innerboard ask --topic "auth flow"` → tailored Slack/Email draft that references local evidence.
5) **Meeting Prep from ICS**  
   - `innerboard prep --event path/to/event.ics` → agenda, questions, and doc pointers, all offline.

### B. Verifiable Privacy & Safety
6) **Airgap Guard + Privacy Receipts**  
   - `innerboard proof` emits a signed JSON receipt: network egress disabled + only loopback:11434 allowed, NIC states, allowed ports, process list, model hash, and SHA256 of indexed files (no content).  
   - `innerboard run --airgapped` launches a subprocess with egress blocked; demo‑friendly.
7) **Red‑Team Mode (Local)**  
   - `innerboard redteam` runs prompt‑injection & PII leak checks against the agent, logs mitigations — all offline.

### C. Delight & UX
8) **Demo Seed**  
   - `innerboard demo-seed` creates a synthetic but realistic /data workspace (handbook.md, arch/diagram.md, sprint_notes.md, slack_export.zip, calendar.ics, git history) so judges can reproduce the flow in 60s.
9) **Reasoning Effort Toggle**  
   - Surface gpt‑oss “thinking effort” levels: `--effort low|med|high` with cached traces (for repeatability).

---

## 4) Agent Design (Tools & Policy)
- **Tools (local only):** `fs.search`, `fs.read`, `git.log`, `git.diff`, `ics.read`, `slack.read_export`, `python.eval` (sandboxed), `time.now`, `summarize.local`.  
- **No browser tool**. Model is trained for tool‑use, but we stub network calls to ensure zero egress.
- **Reasoning policy:** Extract → Ground (RAG) → Propose → Verify (self‑check against sources) → Emit with citations.

---

## 5) Architecture Updates
- Keep your core modules; add:
  - `ingest/` with connectors: **watch_folder**, **ics**, **git**, **slack_export**.  
  - `index/` with SQLite FTS5 + optional local embeddings (e.g., `all-MiniLM` via CPU; pluggable).  
  - `proof/` for airgap checks & signed privacy receipts (Ed25519 keypair generated locally).  
  - `export/` for PDF/Markdown (WeasyPrint/ReportLab) and **/out/** artifacts.
- Ollama client stays; add **effort parameter** passthrough and **tool schema**.

---

## 6) Prompts v2 (SRE & MAC)
- **SRE**: return `{ key_points[], blockers[{desc,impact,owner_hint}], confidence_delta, resources[], evidence[{path, start,end, why}] }`  
- **MAC**: return `{ steps[{text, why, evidence[]}], checklist[], urgency, comms_templates[{channel, message}] }`  
- Hard‑fail if no evidence; degrade gracefully to reflection‑only.

---

## 7) 3‑Minute Judge Demo (Script)
1) **Prove Airgap**: `innerboard proof` → show “No egress” + only `127.0.0.1:11434`.  
2) **Seed Workspace**: `innerboard demo-seed && innerboard init` (enter pwd)  
3) **Pull Model**: `ollama pull gpt-oss:20b` (or show pre‑pulled list).  
4) **Add Reflection**: `innerboard add "Stuck on JWT; docs outdated; need help before Thursday 1:1" --effort high`  
5) **Auto‑RAG**: UI shows cited local sources.  
6) **Generate Packet**: `innerboard packet --week 1` → open PDF; crisp, manager‑ready.  
7) **Ask Draft**: `innerboard ask --topic jwt` → copyable Slack draft referencing evidence.  
8) **Kill Network** (optional): run with Docker `--network none` or OS Wi‑Fi off → repeat step 4 to prove offline.

---

## 8) README Revamp (Top Sections)
1) **Why Local Matters (Trust & Compliance)** — one screen with the privacy receipt screenshot.  
2) **60‑Second Quickstart** — `demo-seed`, `init`, `add`, `packet`, `ask`.  
3) **Category Fit: Best Local Agent** — bullet mapping to tools and airgap proof.  
4) **Repro Steps for Judges** — deterministic seed, sample data, commands.  
5) **Safety & Design** — egress block, sandboxed Python, content hashing, consented connectors.

*(Full README skeleton provided later in this doc.)*

---

## 9) Scoring Alignment Matrix
- **Application of gpt‑oss**: Reasoning‑effort toggle, offline tool‑calling, RAG with local evidence, self‑check.  
- **Design**: Rich CLI, manager‑grade PDF, safe defaults, receipts, deterministic demo.  
- **Potential Impact**: Every new hire; also audits, regulated teams, air‑gapped orgs.  
- **Novelty**: Privacy receipts + ICS/Slack/git fusion for onboarding is rare; “Ask‑Template Builder” is practical & new.

---

## 10) Build Plan (13 Days)
**D1–2**: Ingestion (ICS, git, folder), demo‑seed, FTS index.  
**D3–4**: RAG service + SRE/MAC prompts v2 with evidence fields.  
**D5**: Packet & Ask generators (Markdown → PDF).  
**D6**: Airgap Guard + Privacy Receipts (Ed25519 signing).  
**D7**: Red‑Team mode; PII regex checks; jailbreak tests.  
**D8**: Effort toggle & caching polish; CLI UX.  
**D9**: README revamp + repo polish; sample data.  
**D10**: 3‑min video script; dry‑run.  
**D11–12**: Bug bash & stabilization; cross‑platform sanity.  
**D13**: Final recording; submission packaging.

---

## 11) Risks & Mitigations
- **Model quality on CPU** → cache, reduce context, allow 20B by default; quantized variant note.  
- **OS differences** → confine to user space; avoid privileged ops; Docker `--network none` path for airgap demo.  
- **User data sensitivity** → all connectors are opt‑in, explicit folder, hashes not contents in receipts.

---

## 12) Stretch (If Time)
- **For Humanity** variant: local career‑transition onboarding for NGOs/healthcare with PHI‑safe mode.  
- **Manager Mode**: Produce a shareable packet with redacted content.

---

## 13) README Revamp — Draft Skeleton
### Title & Badges
- Add **“Air‑gapped Verified”** badge (local script produces badge SVG) and “Privacy Receipts” badge.

### TL;DR
> Onboarding coach that stays on your device. Pull gpt‑oss, seed demo data, add a reflection, generate a manager packet — all offline.

### Quickstart (60s)
```bash
pip install innerboard-local
ollama pull gpt-oss:20b
innerboard demo-seed && innerboard init
innerboard add "Struggling with the auth service; 1:1 on Thu"
innerboard packet --week 1
```

### Why Local (and Proof)
- Screenshot + sample JSON of `innerboard proof`.

### Key Features
- Private Context Fusion · RAG‑grounded advice with citations · 1:1 Packet · Ask‑Templates · Meeting Prep from ICS · Privacy Receipts.

### Connectors
- **Watch Folder**, **ICS Import**, **Slack Export ZIP**, **git logs**. All opt‑in. No network.

### Model Setup
- Ollama; `gpt-oss:20b` default; `--effort` toggle; local caches.

### Reproduce the Judge Demo
- Step list from Section 7; deterministic seed; artifacts saved under `/out`.

### Security Notes
- Airgap guard; signed receipts; sandboxed Python; encrypted vault; checksum integrity.

### Contributing & License
- Standard sections with Apache‑2.0.

---

## 14) Implementation Checklist (Engineering)
- [ ] `ingest/ics.py` (RFC 5545)  
- [ ] `ingest/git.py` (shortlog, commit msgs, touched paths)  
- [ ] `ingest/slack_export.py` (channels, DMs metadata)  
- [ ] `index/fts.py` + embeddings optional  
- [ ] `rag/select.py` (BM25/FTS → rerank)  
- [ ] `proof/airgap.py` + `proof/sign.py`  
- [ ] `export/packet.py` (MD → PDF)  
- [ ] `commands/ask.py`, `commands/packet.py`, `commands/proof.py`  
- [ ] Prompts v2 with evidence enforcement  
- [ ] `demo-seed` generator

---

## 15) Example JSON Receipt (Sketch)
```json
{
  "timestamp": "2025-09-01T19:12:33-07:00",
  "process": "innerboard run --airgapped",
  "net": {"egress": false, "allowed": ["127.0.0.1:11434"]},
  "model": {"name": "gpt-oss:20b", "digest": "sha256:..."},
  "sources": [
    {"path": "./data/handbook.md", "sha256": "..."},
    {"path": "./data/slack_export.zip", "sha256": "..."}
  ],
  "signature": "ed25519:..."
}
```

---

## 16) Demo Video Beat Sheet (<=3 min)
1) Hook: “Onboarding is private. Cloud tools aren’t.” (2‑3 sentences)  
2) Pull model → prove airgap → add reflection → instant cited advice → generate 1:1 packet → show PDF → ask‑template.  
3) Close: privacy receipts + offline by design.

---

## 17) Final Notes
This turns InnerBoard‑local into a *category‑defining* local agent: it fuses private context only the device can access, generates manager‑ready outcomes, and proves privacy with receipts. That’s hard to copy without true local‑first architecture — exactly what this hackathon wants.

