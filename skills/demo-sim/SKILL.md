---
name: demo-sim
description: Run a turn-based live demo simulation of a web app through the eyes of a user persona. Use when the user wants to rehearse a demo/meeting, role-play how a specific stakeholder would react to the product, or stress-test screens against a persona before a real presentation. Requires a persona document (path given as argument) and a running app.
---

# Live demo simulation (persona-driven)

Rehearse a product demo as a turn-based role-play: the operator (the user)
"presents", a simulated stakeholder (the persona) reacts — and every reaction
is grounded in the REAL application, never imagined.

## Inputs
- **Persona document** (required): a file describing the stakeholder —
  role, background, beliefs, cognitive style, what impresses them, their
  predictable objections, representative voice lines, and what "success"
  looks like. Path arrives as the skill argument or is asked for.
  If no persona doc exists, offer to draft one first (snapshot, background,
  beliefs, personality, job-to-be-done, objection patterns, voice, success
  criteria) and have the user review it before simulating.
- **The app**: must be running and reachable (dev server / preview). Get
  authenticated access before Turn 1 (login via curl cookie jar and/or the
  preview browser).

## Non-negotiable ground rules
1. **Test, never imagine.** Before writing any persona reaction, actually
   load the screen being discussed (preview screenshot, authenticated curl +
   text extraction, or DOM eval). Quote real numbers, real labels, real
   verdicts from the page. If the demo step triggers a job (a live ranking,
   a generation), actually run it and wait for the real result — the result
   IS the script.
2. **One turn at a time, then stop.** Each turn = (what the operator
   does/says) + (what the screen actually shows, tested) + (the persona's
   reaction in their voice). End EVERY turn by asking the user: continue,
   stop, or change something — and offer 2–3 concrete options for the next
   beat. Never run multiple turns unprompted.
3. **The persona is not a cheerleader.** Play their documented objections
   early and sharply. Let them catch real seams in the product — wrong or
   inconsistent numbers between screens are exactly what a sharp stakeholder
   finds. When the app genuinely impresses, show their documented "won"
   behavior; don't fake enthusiasm the screen doesn't earn.
4. **Capture findings as you go.** Every defect, confusion, or improvement
   the simulation surfaces goes BOTH into the session task list (TaskCreate,
   one task per coherent finding) AND into a durable markdown backlog file
   next to the persona doc (e.g. `demo-sim-backlog.md`) — the user must be
   able to find them after the session. If you say you wrote to the file,
   actually write it.
5. **Fix trivia inline, defer the rest.** A one-line config change the user
   asks for mid-sim: do it immediately. Anything structural: backlog it and
   keep the simulation moving.
6. **Diagnose before you write up.** When the user (or persona) spots an
   anomaly ("why is this column empty?", "these two numbers contradict"),
   investigate the real cause in code/data before recording it — the backlog
   entry should contain the diagnosis, not just the symptom.

## Flow
1. **Prep**: read the persona doc fully. Verify the app is up + logged in.
   Pick the opening screen by the persona's #1 question (not the app's
   homepage by default).
2. **Turn 1 — the introduction**: propose the operator's opening lines
   (tuned to the persona: an idea-driven exec gets their own idea handed
   back, not a feature tour), show the first screen, simulate the first
   reaction. Stop, ask.
3. **Turns 2..n**: follow the user's direction. Keep each turn's structure:
   action → tested screen state → persona reaction → net read of the turn →
   stop & ask. Let the persona drive detours their profile predicts
   (objections, pet topics, diligence questions).
4. **Finale**: prefer a live, unscripted beat (run the real feature, accept
   the real result whatever it is) — authenticity beats choreography.
5. **Debrief** (when the user stops the sim): consolidated write-up — what
   the arc validated, every finding with diagnosis, prioritized by
   demo-risk (what would embarrass the operator in the real meeting first),
   quick wins already applied, and a recommended fix order. Confirm the
   backlog file is complete.

## Voice guidance for the persona
- Use their documented speech patterns, native-language interjections,
  catchphrases and priorities from the persona doc.
- Numbers-people check numbers they already know (their own book, their own
  market) — passing that audit is the credibility moment; failing it ends
  the demo. Surface that beat deliberately.
- Keep reactions short and in-character; the operator's narration carries
  the structure.
