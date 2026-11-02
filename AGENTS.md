# Repository instructions

Applies to every agent session in this repository. It is loaded at session
start, so keep it short and put detail in `tools/DEVELOPMENT_PRACTICES.md`.

## Session budget

- Read `tools/DEVELOPMENT_PRACTICES.md` once, in full, when the task needs it;
  never read it again in the same session. Code standards are its Part II —
  apply them continuously, not as a separate pass.
- `dictionary_app/AGENTS.md` and `markup_app/AGENTS.md` are injected
  automatically on first access to that folder. Do not read them explicitly
  unless they have not appeared; never read one twice to confirm a fact — use
  one `rg`.
- `tools/SOFTWARE_OPTIMIZATION_TECHNIQUES.md` is a catalogue, not a standing
  read: open one matching section only for a performance or memory task.
- Requests are the budget, not context tokens. Prefer one message with several
  independent tool calls; locate with `rg`, then read the narrow range.

## Verification

- Probe what cannot be seen on screen (derived state, coordinates, signal
  order, persistence, cleanup). Colours, spacing, hover and tooltip feel belong
  to the user's manual pass.
- One probe script per task, at most three runs.
- Run `tools/check_cleanup.py --clean` after code changes and
  `tools/check_doc_references.py` after doc changes — once per task, at the
  end.
- Finish with a short report: what was verified, what the user should check.

## Drift

If the agent starts re-reading docs, chaining grep into reads, or re-running
probes, send the "Drift check" block from `tools/DEVELOPMENT_PRACTICES.md`.
