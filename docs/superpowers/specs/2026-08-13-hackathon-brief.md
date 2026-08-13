# Project Brief — MongoDB "Persistent Context Sprint" Hackathon

> Saved verbatim from the user-provided brief on 2026-08-13. This is the spec that
> `docs/superpowers/plans/2026-08-13-no-cold-start-person-b.md` implements.

---

## Instructions to the AI reading this

You are assisting a two-person team at a 3.5-hour hackathon. Time pressure is the dominant constraint. When you help:

- Prefer the smallest thing that works. No abstractions, no config layers, no premature structure.
- Write complete, runnable code. Don't hand back pseudocode or "you'd want to add error handling here."
- If a suggestion would take more than 20 minutes to implement, say so explicitly and offer a smaller version.
- If asked to add a feature that isn't in the "Must ship" list below, push back and ask whether it's worth the clock.
- Assume Python 3.11+, MongoDB Atlas, PyMongo.

---

## The event

**MongoDB Persistent Context Sprint Hackathon**, Pier 48, San Francisco (inside .local Build Fest, Embarcadero Stage).

- Check-in 1:00 PM PT, **hacking starts 1:30 PM, submissions due 5:00 PM.** That's 3 hours 30 minutes of build time.
- Round one is judged asynchronously on a **one-minute demo video** plus a public repo.
- Top six demo live on stage for ~3 minutes, and the winner is decided by audience vote.

**Judging criteria (round one weights):**
- Creativity and Originality — 35%
- Technologies Used (MongoDB depth + meaningful partner tool use) — 25%
- Impact Potential — 20%
- Live Demo — 20%

**Theme: "No Cold Start."** Every agent starts from nothing; build one that doesn't. The organizers are explicit that what you store and retrieve must *change what the system does next*, not just fill the prompt. A knowledge base with semantic search does not satisfy this. Behavior has to visibly differ because of stored state.

**Hard rules:**
- Repo must be public.
- Only present work built during the event. Contributions must be clearly identifiable or it's immediate disqualification.
- No use of code, data, or assets you don't have rights to.
- The build must live in the **Atlas Hackathon Sandbox cluster** created from the organizers' emailed link, or you're ineligible for the finalist round. Do not use a personal Atlas account out of habit.

**Explicitly banned project types (avoid resembling these):** basic RAG applications, Streamlit apps, anything where a dashboard is the main feature, AI mental health advisors, "AI for education" chatbots, job application screeners, personality analyzers.

---

## What we're building

**One-line pitch:** Insurance denial appeals that remember — every appeal filed makes the next one smarter, for you and for everyone else.

### The problem

US insurers deny roughly 20% of in-network claims. Fewer than 1% of denials get appealed. Of the ones that are appealed, a large share get overturned — roughly 44% at internal review for ACA marketplace claims, and for prior-authorization denials the overturn rates run 43% (ACA Marketplace), 47% (Medicaid managed care), and 67% (Medicare Advantage).

So: a fight most people would win, that almost nobody enters.

The reason is a **memory asymmetry**. The insurer has every appeal ever filed against them and knows which arguments work. The patient has one confusing letter, a deadline they probably don't know about, and no idea what worked for anyone else. Even their own second-stage appeal starts from scratch after the first one fails.

### Why this fits the theme

The stored state isn't reference material — it's outcomes. Which argument structures actually got denials reversed, in which situations, and which ones *this specific user has already tried and lost with*. The system's behavior demonstrably changes because of what it remembers.

### What already exists and why we're different

There are AI tools that generate appeal letters. **They write a good letter and forget you exist.** Nothing accumulates across appeal stages or across users. Our differentiator has to be stated in the first fifteen seconds of any demo:

> Existing tools generate a letter. Ours remembers what has already been tried — by you, and by everyone before you.

---

## The data (this is our unfair advantage)

We are **not using synthetic data.** California's Department of Managed Health Care publishes every Independent Medical Review decision it has administered since January 1, 2001, free and public, on the CHHS open data portal.

An IMR is an independent review of a service a health plan denied, delayed, or modified. Each row includes the determination (**overturned** or **upheld**) and a narrative **findings** field explaining the reviewer's reasoning. That's tens of thousands of real, labeled appeal outcomes with rationale text.

Dataset: "Independent Medical Review (IMR) Determinations, Trend" on data.chhs.ca.gov — available as CSV, PDF, and ZIP.

### Two cautions

**Licensing.** The terms state that users may not alter, enhance, or otherwise modify the data, and that reproducing it unmodified for noncommercial purposes requires no approval. Given the disqualification rule about asset rights, we handle it this way:

- Source rows go into `imr_decisions` **verbatim and unmodified**.
- Everything we derive (embeddings, extracted features, scores) lives in **separate collections** that reference source rows by ID.
- Credit DMHC and the Office of the Patient Advocate on the demo and in the README.
- State clearly that use is noncommercial.

**Verify the schema in the first ten minutes.** The public file may not include the health plan / carrier name. If it doesn't, our segmentation key becomes diagnosis category + treatment category instead of carrier. This changes nothing architecturally — decide it early and move on.

---

## Architecture

### Collections

| Collection | Contents | Owner |
|---|---|---|
| `imr_decisions` | Raw public IMR rows, unmodified. Findings text vector-indexed. | A |
| `denial_profiles` | Derived per decision: denial category, service type, the reasoning pattern the reviewer used, the evidence the reviewer treated as decisive. References source by ID. **This is what we actually search.** | A |
| `strategies` | Argument archetypes extracted from overturned cases, each with rolling stats: attempts, overturns, segment. | A |
| `evidence_types` | Documentation categories scored by how often they appear in overturned vs. upheld cases within a segment. Produces the "here's the document you're missing" output. | A |
| `cases` | The live user: their denial, current stage, what's been filed, what came back, deadlines. | B |
| `attempts` | Every strategy this user has already deployed and how it landed. **Makes round two different from round one.** | B |

### The core pipeline — this is the whole project

One aggregation, and everything depends on it:

```
$vectorSearch on denial_profiles (embedded text of the user's denial letter)
  → $lookup into imr_decisions for determinations
  → $match to EXCLUDE any strategy already recorded as failed in this user's attempts
  → $group by strategy → overturn rate + sample size
  → $sort
```

**The `$match` exclusion stage is the product.** Without it we have a search engine. With it we have something that behaves differently because of what it remembers. If everything else slips, this must work.

Acceptance test: the same denial letter must return **different rankings** before and after a recorded loss. Verify this explicitly — don't assume.

### Deadlines are real and worth encoding

Standard internal appeal window is 180 days from the date on the denial letter; roughly four months after that to request external review. People lose by default on these.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | LangGraph's MongoDB checkpointer is most mature here; PyMongo is frictionless |
| API | **FastAPI, single `main.py`** | No project structure, no framework ceremony |
| UI | **Plain HTML + vanilla JS served by FastAPI** | No build step, no npm install eating 15 minutes |
| DB | **MongoDB Atlas — hackathon sandbox cluster only** | Eligibility requirement |
| Search | **Atlas Vector Search with automated embeddings** | Removes an entire embedding pipeline from a 3.5-hour build; scores directly on the MongoDB criterion |

**Do not use Streamlit.** It's on the banned list. Even as an innocent UI layer it pattern-matches to the thing they told us not to build.

**Keep the UI thin.** "Any project where a dashboard is the main feature" is also banned. No charts. The intelligence should be the visible thing.

### Sponsor tools

- **Fireworks — structural.** Runs the batch extraction pass over thousands of IMR findings into structured strategy/evidence records. High-volume, low-latency, cheap-model work. Credits: code `MONGODB813` ($50).
- **LangChain / LangGraph — structural.** Specifically `langgraph-checkpoint-mongodb`. The appeal lifecycle is a genuine long-running state machine (classify → gather → draft → file → suspend → resume on response → escalate) spanning months. Checkpoints persist to Atlas. **Turn LangSmith tracing on** — two lines, and it will save us when the aggregation returns something inexplicable at 3:15.
- **OpenRouter — one line.** $10 is too small to build on. Use it as the fallback provider on the drafting call so a Fireworks hiccup during a live stage demo doesn't kill us.
- **ElevenLabs — skipped.** Two people can't build a real voice agent and the core in 3.5 hours. Voice adds nothing to our creativity or impact score.
- **Cursor — dev tool, not an integration.** Use the credits; don't cite it as architecture.

### Setup to do in the first 20 minutes

1. Atlas sandbox cluster from the organizers' emailed link
2. **Install MongoDB Agent Skills into Cursor**
3. **Connect the MongoDB MCP Server to the live cluster** — letting the coding assistant inspect real collections and indexes instead of guessing at schema is worth real minutes when writing the aggregation under pressure
4. Download the DMHC CSV, load raw into `imr_decisions`
5. Create the vector index on the findings field
6. Redeem the Fireworks code

---

## Work split (2 people)

**Person A owns the corpus.** Real IMR data into Atlas, turned into something searchable.
**Person B owns the intelligence.** Aggregation pipeline, exclusion logic, UI, demo.

**B is on the critical path.** A's secondary job is to never block B and to hand over spare capacity the moment their lane is done.

### 1:30–1:50 — together, do not split yet

Two things, in this order:

1. **Write the schema contract** in a shared `schema.py` — exact field names for `denial_profiles`, `strategies`, `evidence_types`. Both code against those names all day. Ten minutes arguing about field names now saves an hour of integration pain at 3:30. **Nobody edits this file after 1:50.**

2. **Hand-write 20 fake `denial_profiles` documents** matching the contract and insert them. B builds the entire pipeline against these fixtures while A's real extraction is still running. Without this, B sits idle until 2:35 and we lose the project.

Setup tasks above happen in parallel during this window.

### Person A — corpus lane

- **1:50–2:15** — Load DMHC CSV raw into `imr_decisions`. Create the vector index on findings with automated embeddings. Sanity-check that a plain vector search returns something sensible.
- **2:15–3:15** — The extraction pass. Batch findings text through Fireworks to populate `denial_profiles`, `strategies`, `evidence_types`. **Cap at ~2,000 rows** — we need meaningful sample sizes in a few segments, not the whole file. Pick rows concentrated in 3–4 diagnosis categories so those segments have real density.
- **3:15–3:30** — Swap B's fixtures for real data.
- **3:30 onward** — A is free. Join B, and take over the video script and the DMHC attribution slide.

**A's failure mode to watch for:** if every extracted strategy comes back as generic mush ("provided more documentation"), the demo dies. Strategies must be specific and distinguishable — e.g. *"cited treating physician's documented failure of the plan-preferred alternative"* or *"established the requested service is standard of care per named clinical guideline."* Tighten the extraction prompt toward that specificity.

**A's fallback if extraction is still mush at 3:15:** stop trying to fix it broadly. Hand-curate 8 good strategies from 30 findings read manually, seed the stats from real determinations, ship that. A small honest corpus beats a large incoherent one.

### Person B — intelligence lane

- **1:50–2:40** — The aggregation pipeline against fixtures. Vector search → lookup → group by strategy with overturn rate and sample size → sort. Get it returning ranked output.
- **2:40–3:20** — **The exclusion logic.** `cases` and `attempts` collections, and the `$match` stage that drops strategies this user has already lost with. This is the project. Test that the same input returns different rankings before and after a recorded loss.
- **3:20–3:50** — Thin UI: paste box, ranked strategies with sample sizes, missing-evidence callout, the draft.
- **3:50–4:15** — LangGraph checkpointing to Atlas, plus the OpenRouter fallback line on the drafting call.

### 4:15–5:00 — together

- **4:15–4:35** — Record the video. Both stop coding. One drives, one watches for what the driver can't see. One minute total; the second beat gets 30 of those seconds.
- **4:35–4:50** — Repo public. README naming what we built today vs. what came from the public dataset — required, or we risk disqualification.
- **4:50–5:00** — Submit. Both names on the submission page. **Do not leave this to 4:58.**

### Coordination rules

- **Two files, minimal overlap.** A owns `ingest.py`, B owns `main.py`. Both import from `schema.py`. Push often; conflicts should be rare.
- **One check-in at 3:15, five minutes, standing up.** Not a meeting. One question: is the exclusion logic working, yes or no? If no, A drops everything and joins B.

---

## Must ship / cut order

**Must ship (in priority order):**
1. The exclusion logic — same input, different output after a recorded loss
2. Real IMR data behind the rankings, with sample sizes shown
3. The missing-evidence callout
4. The one-minute video

**Cut in this order if we slip:** LangGraph checkpointing → UI polish → extraction volume.

**Never cut:** the exclusion logic, or the video.

> The failure mode for a two-person team is both people building interesting things and neither building the demo. A working project nobody recorded scores zero in round one.

---

## The demo (3 minutes, stage version)

**Beat one — 40s.** Paste a denial letter. System shows: *N* semantically similar cases from real California IMR records, the overturn rate, the three argument structures that worked and how often, and the one document you don't have that appears in most of the overturned cases.

**Beat two — 60s.** The appeal comes back upheld. Instead of regenerating, the system writes the loss, the strategy's score visibly drops on screen, and the next draft is built from a *different* argument — because the failed one is now excluded for this user. Say out loud: **"Every other tool in this space would hand you the same letter again."**

**Beat three — 30s.** Show the raw MongoDB documents. Provenance, sample sizes, the exclusion.

**Close — 20s.** The number: fewer than 1% of denied claims get appealed, and when people do, 43–67% get overturned depending on plan type. Most people would win a fight they never enter.

Beat two is the whole demo. Everything else is setup.

---

## Prepared answers for Q&A

**"Isn't this legal advice?"** It reports outcome statistics from public regulatory records and drafts correspondence. It doesn't represent anyone. One sentence, then move on.

**"There are startups doing this."** Yes — they generate letters, and every one of them forgets you the moment it's done. Nothing else accumulates across stages or across users. **Raise this before a judge does.**

**"California only?"** Other states publish external review outcomes too; California's is the largest and cleanest. The architecture is state-agnostic — the corpus grows, the model doesn't change.

**"Where does real data come from at scale?"** It already exists — this is public regulatory data, and every state with an external review process generates more of it.
