# Development Practices

How we work in this repository. **Part I** (sections 1–7) is working practice:
environment, tooling, context discipline, verification, collaboration, git, and
docs. **Part II** (section 8) is the code standard: the target state of the
code, applied continuously and walked in full as the end-of-cycle cleanup
checklist. **Part III** (sections 9–11) documents the scripts in this folder.
There is no separate checklist — Part II is it.

Read Part I before starting a task; read Part II before changing structure,
naming, or organizing files. This file complements `dictionary_app/AGENTS.md`
(what the code is and how it is wired) and `markup_app/AGENTS.md` (markup-only
behavior). Keep it short and factual; update it when a practice changes.

---

# Part I — Working practice

## 1. Environment

- **OS:** Windows. **Shell:** PowerShell 5.1 (`win32`).
- **Python:** invoke as `py -3`.
- **Cyrillic / Unicode safety:** set `$env:PYTHONUTF8="1"` before running any
  Python that touches Belarusian text or XML, or output/read may be mangled.
- **Scratch space:** write throwaway scripts and probe files to
  `C:\Users\User\AppData\Local\Temp\opencode\` — never clutter the repo.
  A probe worth keeping moves to `tools/` at the repo root instead
  (see §4.1) — the only sanctioned repo location for scripts outside the two apps;
  the scripts are documented in Part III.
- **No secrets** in code, docs, commits, or logs, ever.

### PowerShell 5.1 quirks (no PowerShell 7 features)

- `&&` is **not** supported. Chain with `;`, or use
  `cmd1; if ($?) { cmd2 }` when the second step depends on the first.
- **No heredoc.** Build multi-line text by writing a file with the editor tools.
- Prefer full cmdlet names (`Get-ChildItem`, `Set-Content`, `Remove-Item`).
- Quote paths with spaces and use the call operator: `& "path/to/exe" args`.
- Watch backticks and the `"` terminator when a command string is itself quoted.

## 2. Tooling

- **Search file contents with `ripgrep` (`rg`), not `Select-String`.**
  Installed via `winget install --id BurntSushi.ripgrep.MSVC` (v15.2.0). If `rg`
  is not yet on `PATH` (needs a shell restart after install), call it by full
  path:
  `C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\BurntSushi.ripgrep.MSVC_Microsoft.Winget.Source_8wekyb3d8bbwe\ripgrep-15.2.0-x86_64-pc-windows-msvc\rg.exe`
- Prefer the dedicated editor tools (`Read`, `Grep`, `Glob`, `Edit`, `Write`)
  over shell file/content cmdlets.
- **Glob brace expansion is unreliable** on this setup; pass an explicit `path`
  and avoid `{a,b}` patterns.

## 3. Context discipline

File size costs **context tokens**, not ability to work on the file.

- Don't read a large file end-to-end when you only need part of it. Locate the
  region with `Grep`, then `Read` just that range.
- **Targeted reads cost reply time, not only tokens.** `Grep` → narrow `Read`
  is 2–3 *dependent* round-trips. For a small file where most of it is needed
  (roughly >50%), one full `Read` finishes sooner despite the extra tokens;
  reserve `Grep` → narrow `Read` for large files or genuinely narrow regions.
  Batch independent reads/shell calls into one message — parallel calls cost a
  single round-trip.
- A file must be `Read` at least once before it can be `Edit`ed. A partial
  top-of-file read is enough to satisfy this.
- For open-ended exploration, delegate to the **explore/Task** agent instead of
  pulling many files into the main context.
- Keep outputs and command result sizes small; reason from targeted evidence.

### 3.1 Anti-overreading (keep cycles short)

Diagnosing a bug or wiring change should take minutes, not a long read-through.
The sequence that keeps cycles fast:

- **One hypothesis → one targeted probe.** Write a minimal probe (a few lines)
  that tests the single suspected mechanism; run it; read its `repr()` output;
  only then open production code. Do not re-read whole files to "confirm by
  eye" — the probe is the confirmation.
- **Batch reads and shell calls.** Independent `Read`/`Grep`/shell calls go in
  ONE message (parallel calls cost a single round-trip). Sequential grep→read
  chains are for genuinely dependent steps only.
- **`rg`/Grep first, always.** Find the line number with one `rg` call, then
  `Read` ±30 lines around it. Never open a 500+ line file without knowing the
  region you need.
- **Skip doc round-trips mid-task.** Facts needed mid-diagnosis (env quirks,
  paths, invariants) are already in `dictionary_app/AGENTS.md`,
  `markup_app/AGENTS.md`, or this file — grep them with `rg` instead of
  `Read`ing the whole file; write/update docs only at task end (with user
  consent).
- **Do not re-verify settled ground.** After a green probe/check run, move
  on; re-running the same probe "to be sure" doubles wall-clock time for zero
  new information. Re-run only after a NEW change touches the same layer.

### 3.2 Project docs: read once, reuse; requests are the budget

The binding budget is the **number of requests (turns)**, not the context
window. Every turn re-sends the cached conversation, so one extra round-trip
costs more than a few thousand tokens of reading.

- **Read `dictionary_app/AGENTS.md` and `markup_app/AGENTS.md` only if they are
  not already in context.** The harness injects the folder's `AGENTS.md`
  automatically after the first file access in that folder; reading it again
  duplicates it. Read it explicitly only when working in a folder whose
  `AGENTS.md` has not appeared yet.
- **Read this file and the project docs in full, once per session**, at the
  point they become relevant — not repeatedly, and not section-by-section.
  They are rule systems; a partial read silently misses the rule that governs
  the case at hand, and splitting the read into `Grep` → `Read` chains adds a
  round-trip per step for a few hundred tokens saved.
- **Do not re-read docs to answer a mid-task question.** The invariants,
  paths, and quirks are already in context or reachable by one `rg` for a
  single term. Re-reading a 15k-token doc to confirm one fact is the most
  expensive way to get it.
- **`tools/SOFTWARE_OPTIMIZATION_TECHNIQUES.md` is a catalogue, not a
  standing read.** Only for a performance/memory task, open the one section
  that matches the symptom; it is generic taxonomy and does not belong in
  every session's context.
- **Fewer, larger steps.** Prefer one message with several independent tool
  calls over several dependent ones; fold doc updates into the final
  verification step instead of a separate pass.

### 3.3 Drift check (restatement)

Long sessions erode §3.2 and §4.4: the rules stay in context but lose weight,
and a compaction summary keeps the gist while dropping the details. The
symptoms are visible — re-reading `AGENTS.md`, grep→read chains on a small
file, re-running a probe "to be sure", a fourth probe run, checks after every
edit.

When that happens, send this block as a new message. It is a compressed
restatement of §3.2 and §4.4; on conflict, those sections win.

```text
Rules still apply; re-align:
- Do not read AGENTS.md or tools/DEVELOPMENT_PRACTICES.md again — both are
  already in context. One `rg` for a single fact.
- Requests are the budget, not tokens: batch independent tool calls in one
  message; locate with `rg`, then read the narrow range.
- Probe only the invisible. One probe script per task, at most three runs.
  Colours, spacing, hover and tooltip feel are mine to check.
- Run `tools/check_cleanup.py --clean` (code) or
  `tools/check_doc_references.py` (docs) once, at the end.
- Finish with what was verified and what I need to look at.
```

## 4. Probes and verification

### 4.1 Probes: minimal, and honest about the fixture

Complexity is not a reason to skip probes; it is a reason to make them smaller.
This app is text-layout sensitive (Qt document positions, scan/placeholder
positions, and clean XML are three different coordinate spaces) and its index is
derived state, so a targeted probe is usually the cheapest reliable check.
What must stay small is the number of probes and the size of each.

- **One mechanism per probe.** If a probe needs more than ~30 lines or several
  setup steps, the mechanism is not isolated enough — split it.
- **Mutate in the coordinate space the API expects.** Qt cursor positions take
  UTF-16 offsets from the widget's own scan text (`_scan_text()`), not Python
  code-point indices from `toPlainText()`: a single emoji is 1 Python char but 2
  UTF-16 units, so mixing them silently edits the wrong character. The same
  applies to clean space (`_clean_to_qt`) versus raw XML.
- **Assert the mutation landed before asserting the feature.** Check that the
  fixture really contains the change you intended (e.g. the edited id, and still
  valid XML); otherwise a false failure sends you debugging working code.
- **Reproduce the reported scenario, not a nearby one.** For "the emoji should
  come back after saving", the fixture needs a see pointing at the NEW id. Say
  out loud when the real corpus does not match and you are adjusting the
  fixture.
- **One run per hypothesis**, then move on. A probe that stays valuable belongs
  in `tools/` instead of `%TEMP%`; delete one-off probes when done.

### 4.2 Checks

- After a change, run the project's lint / typecheck / tests **if they exist**.
  This repo has no test runner or lint config; do not invent one. Use
  `tools/check_cleanup.py` for the built-in checks (`compileall` and
  `find_unused_imports.py`) and `--clean` to drop artifacts.
- Link resolution (`<see>` classification, routing, headword/entry resolution) is
  verified with a targeted probe per §4.1, and visually with the markup app's
  broken-links filter (`missing_links` / `unresolved_links` / `ambiguous_g`).
- Edge cases already exercised for the DB/search layer: schema version, row
  counts, collation order vs. Python sort, incremental vs. full rebuild, and
  ё-sensitive lookups. Re-run the relevant checks when touching that layer.
- If you can't verify something, say so explicitly instead of assuming success.
- **Pure refactors:** bracket the work with `tools/snapshot_behavior.py --save`
  / `--check` (§9.14); it compares derived state (entries, searches, previews,
  sources, `<see>` outcomes), so a mismatch is a behavior change, not noise. The
  order of the change matters — see §8.16.
- **Qt lifetime/font changes:** run `tools/check_pyside_traps.py` (§9.15) after
  touching styles, documents, or text formats; it catches the ownership and
  font-family crashes documented in `dictionary_app/AGENTS.md`.

### 4.3 Diagnosing a failing check

- **Green baseline first.** Run the relevant check or probe *before* starting
  the change so any later failure is attributable to your change, not
  pre-existing.
- **Fix the first failure only, then re-run.** When N checks are red, the first
  one usually causes the rest; fixing later ones first chases cascades and
  blames the wrong layer.
- **The first run of a new probe is exploratory.** Print the actual state
  before trusting your expectations — a wrong expectation costs a full
  write→run→diagnose round-trip and blames the code for the probe's own bug.
- **Print `repr()` / `ord()`, never raw glyphs.** Emoji, PUA, and combining
  characters render invisible or substituted in this console; a failure detail
  can look like text is missing when it is present.
- **Three failed fixes on one check → stop patching, minimize.** Extract a
  ~10-line standalone repro of the mechanism (framework behavior: Qt signal
  semantics, index units) and prove where the behavior comes from before
  touching production code again.
- **Trace with stacks, not theories.** A spy connected to the signal or hook in
  question that prints `traceback.format_stack()[-6:-1]` names the caller in
  one run.
- **Qt positions are UTF-16 units; Python string indices are code points.**
  Every non-BMP character shifts all positions after it. When both spaces
  coexist, convert only at the boundary through a named helper and never mix
  the two in one expression.
- **Time to paint, not the call.** A Qt call can return before layout and paint;
  measure through `processEvents()` plus a repaint/grab or from the first
  `paintEvent`. Report cold vs warm separately: the first render of an emoji or
  a new font family includes one-time shaping (~28 ms here) and belongs in the
  real click cost. When a mixed glyph+text widget is slow on first show, pin
  only the glyph (rich text); pinning the whole widget to the emoji family
  moves the fallback onto the text and is usually worse.
- **A reproducible teardown crash is a finding.** If a fixed script crashes at
  interpreter shutdown every time, it is not probe noise; isolate the
  ownership/lifetime (§9.15) before dismissing it.
- **Wrapper liveness is not C++ validity.** A Python reference or `weakref` can
  outlive its `QObject`; use `shiboken6.isValid(obj)` before claiming the
  underlying object is still alive.

### 4.4 Testing budget (what the agent verifies, what the user checks)

Verification is expensive in requests; spending it on what the user can see in
one glance is waste. Split the work:

- **Probe only the invisible.** Mechanism, data, and side effects that cannot
  be seen on screen: index/derived state, coordinate conversions, signal order,
  persistence round-trips, cleanup after a view closes. These are the failures
  the user cannot spot by clicking.
- **Leave the visible to the user's manual pass.** Colours, spacing, hover and
  tooltip feel, focus rings, animation timing, and overall look. Do not write
  probes that assert appearance; state the change and ask for a visual check.
- **One probe script per task, three runs maximum.** First run exploratory
  (print state), second after the fix, third only if a new change touched the
  same layer. A fourth run means the hypothesis is wrong — rewrite the probe
  smaller instead of re-running it.
- **Run the standard checks once per task, at the end.** `tools/check_cleanup.py
  --clean` after code changes and `tools/check_doc_references.py` after doc
  changes. Not after every edit.
- **Report honestly what was and was not verified**, in one short paragraph:
  what the probe proved, and what is left to the user's eyes. "Not verified"
  is an acceptable outcome; a probe that pretends to cover appearance is not.
- **PySide6 details differ from Qt's C++ API.** In this build,
  `QTextEditExtraSelection.cursor` / `.format` are properties, while
  `cursorRect()` / `position()` are methods. Probe the accessor once rather
  than assuming; a wrong call looks like a feature bug.
- **A parity snapshot is not a visual pass.** `tools/snapshot_behavior.py`
  (§9.14) proves derived state; colours, spacing, hover, and first-paint feel
  still go to the user's manual pass.

## 5. Working with the user

### 5.1 Mid-task input (amend, don't restart)

The user often adds requirements while you are already working. Treat that as an
amendment to the current plan, never as a signal to re-plan from scratch.

- Read the new input once, state the delta in one line if it is not obvious, and
  apply it to the affected steps. Keep the rest of the plan and its state.
- Do not re-read files you already read or re-derive a plan you already hold;
  the todo list is the plan. "Have I already got this?" beats "let me look
  again."
- If the input does not change the immediate next action, say so in one line and
  continue working. Do not stop to negotiate.
- When the input contradicts an earlier instruction, follow the newest one and
  note the change; ask only if it is genuinely ambiguous.
- Prefer finishing the in-flight edit/probe before absorbing a new request; then
  fold the request in. Never leave both half-done.

### 5.2 Questions, not guesses

- **Ask targeted questions when unsure** rather than guessing or broadening the
  change. Surface the tradeoff and let the user decide.
- When the decision is the user's (product behavior, doc structure, whether to
  commit), present the options with a recommendation; never pick silently.

### 5.3 Fix root causes

- **Fix root causes, not symptoms.** No band-aid or special-case fixes that
  paper over a general bug.

## 6. Git

- Commit messages: **single, descriptive line**, matching existing style.
- **Commit, amend, push, or open a PR only when explicitly asked.** Never commit
  as a side effect of doing the work.
- Inspect `git status` / `git diff` before staging; stage only intended files.
- Build outputs and the database are gitignored — keep them out of commits.

## 7. Documentation

- `.md` docs are updated together with the code **when the user consents**
  (see §8.11). Do not silently rewrite docs.
- Keep docs de-duplicated: state each fact once, cross-reference the rest.

### 7.1 Stale vs. useful "negative" documentation

Docs often record what the code does *not* do. Keep the kind that constrains
code; delete the kind that only recounts history.

- **Keep (useful) — anything that governs current/future code:** invariants,
  `must` / `must not` / `do NOT` rules, subtle-behavior gotchas, rationale for
  why the code is the way it is, and short "do not reintroduce X" guards for
  removed tags, attributes, or schemes.
- **Remove (stale) — narrative about artifacts that no longer exist:** "the
  former `foo.py` is gone", "the old `#`-scheme was removed from …", and war
  stories such as "was once left after the `return` and became unreachable".
- **How to tell them apart:** wording alone is unreliable. Verify against the
  code — search (`rg`) for the symbol/tag/scheme the note names. If it still
  exists the note is useful; if not it is stale (but preserve any guard clause).
  If the code does not settle it, ask.
- When trimming a stale note, keep the invariant it was wrapped around (keep
  "`clear()` must stay BEFORE the `return`"; drop the incident story).

---

# Part II — Code standards

These are standards, not a one-time checklist. Apply them whenever you touch
code, and at the end of every cycle **walk this entire section top to bottom as
the cleanup checklist**. There is no separate checklist: any cleanup point must
live here, and every standard here is part of the cleanup pass. If a cleanup
concern is missing, add it here; if a rule here is obsolete, fix it here.

Run the cleanup pass only once the cycle's functionality is settled. Treat it as
a senior-developer quality pass: **do not change the design or the behavior** —
change only how the code is organized, named, and executed.

**Scale target:** the dictionary may grow to **200,000 headwords**. Treat runtime
and memory as first-class constraints throughout.

**Hard rules for every edit (not only at cleanup):**

- **Never touch real data**: dictionary XML (`dictionary_*.xml`, `sources.xml`,
  `data/dictionary/`) and the Belarusian text in localization JSON are
  off-limits. The DB rebuild reads XML only and must not rewrite it. Inspect it
  with the read-only `tools/inspect_data.py` (§9.9) instead of reading whole
  files into the conversation.
- **Localization JSON is manually maintained** — edit individual keys only,
  never re-serialize or reformat.
- **No comments in source code.** This codebase is comment-free by convention;
  rationale lives in the `.md` docs. (At cleanup: delete every comment.)
  `tools/strip_comments.py` (§9.6) deletes them; no confirmation needed.

### 8.1 Naming and terminology

- Names must be clear on the first read to a human developer who does not have
  this document open. If a name needs a doc sentence to be understood, it is the
  wrong name.
- When two names differ only by a qualifier, the qualifier must name the
  **actual difference** and nothing else. Example: `normalized_headword`
  excludes the text inside `<n>` (it is the sort form), while
  `normalized_plain_headword` keeps it — "plain" does not say that, so a
  first-time reader cannot tell the two apart. Names that carry the
  distinction itself (`normalized_without_n` vs. `normalized_full`) need no
  explanation.
- One concept, one name, everywhere (code, docs, UI strings, localization keys).
  Two different concepts must never share a name.
- **Entities that DO something** — functions, classes, and modules that act —
  get names that state the action: verb-first or a `..._doer` form
  (`build_database.py`, `create_search_engine.py`, `measure_scrollbars.py`,
  `link_marks_builder`). A module that only computes measurements is an actor,
  not a topic.
- **Reference data does not DO anything** — schemas, dictionary data, constants,
  style tokens, config tables — and keeps noun names (`xml_schema.py`,
  `layout_constants.py`). Do not invent an action for a file that only holds
  values.
- Test of the rule: read the name alone and ask "what does this file do?" If the
  name answers with a topic rather than an action for a module that acts,
  rename it. For example, a module that only computes scrollbar extents is
  better named `measure_scrollbars.py` than `scrollbar_geometry.py`; had it held
  only geometry constants, the noun name would be correct.
- Rename when behavior changed: an old name that no longer matches is a bug in
  the name. Also rename helpers whose scope expanded and now mislead.
- Correct inaccurate terminology (including terms carried over from prompts);
  adopt the correction consistently everywhere.
- Audit localization JSON **structure and key names** (never the Belarusian
  text) so keys match the entities they describe.
- When reviewing or editing localization JSON keys, keep the groupings and
  names logical and human-readable: group by the element's position in the
  UI, and make sure the name/grouping includes the function the string
  serves (title, button, tooltip, placeholder, message, …). Determine the
  function from code usage: search for the key and inspect only the relevant
  surrounding context. Group by where the element sits in the UI and name by
  what it is for — the editor save tooltip is editor.save.tooltip, not a
  bare save. Renaming or regrouping keys is fine; the Belarusian text
  values are not (see the hard rules above).

### 8.2 Structure and file layout

- Split files that have grown too large into smaller, single-purpose modules.
- During a refactor or cleanup pass, you may **provisionally merge** the
  files/modules being split and then **split them again along different logical
  boundaries** as you see fit — behavior and design stay unchanged, only the
  boundaries move.
- Make every module, class, and function cohesive: one clear responsibility
  each.
- When one functionality produces several pieces, **split it finely and put the
  pieces in an appropriately named subpackage** rather than a flat pile. The
  subpackage name states what the group does (`markup_app/panels/`,
  `services/`, `theme/`), and the same layout is mirrored in both apps (§8.8).
- **Rearranging the folder-and-file hierarchy is allowed** when it measurably
  improves human navigation, discoverability, or reading time. Do it as part of
  the cleanup pass, under the same constraints: keep the two apps mirrored,
  keep `markup_app/` deletable, and change no behavior or design.
- Prefer many small, action-named modules over one multi-purpose file, and a new
  focused module over growing an already broad one.
- **Split large files LAST**, after behavior is settled, dead code is gone, and
  shared primitives are consolidated: refactoring adds lines, so an early split
  is redone. The full order is in §8.16.
- Introduce **lazy evaluation** wherever work can be deferred until it is
  actually needed (parse on demand, build on access, compute on use).
- Check whether any code can be rewritten more directly / more neatly without
  changing behavior.

### 8.3 Dead weight

- Delete leftover test files, scratch scripts, and ad-hoc code snippets
  introduced during the cycle's fixes.
- `tools/` is the one sanctioned place for repo scripts, and it is **not
  gitignored** (documented in Part III). **The cleanup pass does not
  revise `tools/` content:** amend a tool ad hoc, at the moment it is called or
  used — stale expectations, new checks, and renamed helpers are fixed then, and
  only then. A tool must not be left red *because of* the pass: exit codes follow
  §10 (0 when clean, 1 on findings or failures), so a red scan is a real finding,
  not a broken script — if a rename or a moved file made a scan fail, fix it in
  that moment. The whole directory is
  deletable as a unit: nothing in `dictionary_app/` or `markup_app/` imports it
  (grep for `import tools` / `from tools` to confirm before deleting); keep only
  the scripts you actively rely on.
- Delete code that became redundant as a result of the fixes: obsolete helpers,
  flags, branches, imports, parameters, CSS rules, localization keys.
  `tools/find_unused_definitions.py` (§9.7) lists module-level functions and
  classes nothing references; `tools/find_unused_imports.py` covers imports.
  Resolve its hits by the flow in §9.7.
- Delete **all comments** in code (hard rule above).

### 8.4 Composition and modularity — compose reusable pieces, never stack named behaviors

This applies to **everything** (normalization, parsing, formatting, sorting,
validation, configuration, UI wiring — not just text handling).

Structure the code so each rule / concern / behavior is defined **once**, as a
self-contained primitive, and higher-level behavior is built by **explicitly
composing those primitives** — not by extending or aliasing a lower-level
*named* counterpart.

- **Preferred (additive composition):** define `rule_a`, `rule_b`, `rule_c`
  independently; then:

  ```
  context_x = rule_a + rule_b
  context_y = rule_a + rule_b + rule_c
  ```

  Each context lists exactly the primitives it needs. Editing `rule_b` affects
  only the contexts that name it.

- **Avoid (layered coupling):**

  ```
  context_x = base + rule_b
  context_y = context_x + rule_c   # silently inherits everything from context_x
  ```

  Here a change meant for one context leaks into every context built on top of
  it.

- Depend on **shared primitives and small interfaces**, not on a sibling module's
  higher-level convenience wrapper.
- If a function is only an alias for another, delete one and use the other.
- Avoid deep inheritance chains and pass-through wrappers that just forward to
  another named function; they hide coupling.
- Keep each primitive independently testable and observable.

### 8.5 Reuse and single source of truth

- Before writing new logic, search for an existing unit that already does the
  job; generalize and reuse it instead of duplicating.
- Merge duplicated logic into one shared unit; keep genuine app-specific
  variants only in the app that needs them (§8.8).
- Enforce a **single source of truth** for each concept: glyphs, URL schemes,
  tag attributes, style values, metric constants, user-facing strings.

### 8.6 Performance and memory (200,000 headwords)

- **Optimize current behavior, not only future scale.** The 200,000-headword
  target is a ceiling, not the only reason to optimize: reducing resource usage
  and execution time of existing functionality is a valid goal at the current
  corpus size. Measure the real entry point; if a change demonstrably improves
  it, it is justified even when the corpus is small.
- **Optimize from measurement, not intuition.** Measure the real entry point
  before changing it and re-measure after; a change that cannot be shown to
  move the number is churn.
- **Do not overengineer.** Add an abstraction, cache, option, or generalization
  only when a measured need or a second real caller justifies it; speculative
  flexibility is churn. Prefer the simplest code that meets the measured
  requirement and the rules here.
- **Balance speed against footprint.** Never buy faster startup or computation
  with an unbounded cache, a larger on-disk artifact, or permanently retained
  state; every cached byte must be cheaper than recomputing it.
- **Separate disposable caches from data.** Bytecode (`__pycache__`) and
  memoization tables may be discarded and rebuilt freely; databases
  (`dictionary.db`), user progress (`markup_checked.json`), and source XML are
  data and must never be deleted as an "optimization".
- Audit hot paths for algorithmic complexity; prefer `O(n)` / `O(log n)` over
  `O(n²)` as input grows.
- Eliminate repeated work: never re-parse, re-normalize, or re-materialize data
  that can be cached once.
- Use **bounded (LRU)** caches so caches can never grow without limit.
- Prefer streaming / lazy generation over building large intermediate
  collections.
- Use `dict`/`set` lookups for per-row access instead of linear scans inside
  loops.
- Watch memory retention: do not hold large XML strings or parsed roots longer
  than necessary.
- **Measured pain points (2026-11-03; 295 entries / 467 rows, Python 3.14,
  offscreen):** launch ~0.2 s (imports 0.11 s, `QApplication` 0.04 s, window
  0.02 s, first events 0.03 s); full DB rebuild 0.08 s warm / 0.5 s cold in a
  fresh process; incremental one-file rebuild 0.015 s; sources panel first open
  0.04 s and later opens 0.011 s (one rendered sources document 0.012 s); entry
  render with a target sub-headword 0.5 ms. These are baselines, not a verdict
  that current behavior needs no optimization: a measured change that reduces
  resource usage or execution time is still worth making at this size. The cheap
  wins (indexes, lazy loading, precomputed keys, per-file FTS, deferred initial
  load) are already in. Re-measure at the real corpus size; the next
  scale-specific candidates are search/lookup latency at 200,000 headwords,
  markup-app document load, and the first-run full build.
- **Reference catalog:** `tools/SOFTWARE_OPTIMIZATION_TECHNIQUES.md` is a
  menu of optimization techniques by level (architecture, algorithms, data
  structures, memory, I/O, databases, concurrency, deployment). Use it during
  refactors. It is guidance, not a mandate: measurement and the footprint rules
  above decide whether a technique is used.

### 8.7 Constants and styling

- No hardcoded / inline numeric or styling values outside dedicated constants or
  CSS/style files.
- Give every such value a **transparently named** global constant or style
  token, and import that single definition everywhere it is used.

### 8.8 dictionary_app vs markup_app

- **Merge what is shared** into the shared layer; **isolate what is
  app-specific**.
- Anything only the markup app needs must live inside `markup_app/`, under a
  subpackage that **mirrors the shared structure**.
- Keep the naming of files, folders, and entities consistent between the two
  apps.
- Keep `markup_app/` **deletable without a trace**: deleting `markup_app/` plus
  its launcher script must fully remove the markup app, leaving the dictionary
  app intact.

### 8.9 .gitignore

- Update it so build outputs, generated databases, caches, and scratch artifacts
  remain untracked. Generated data exports go with them: `tools/*.xlsx`
  (produced by the export scripts in §9.10) is ignored, while the scripts
  themselves stay tracked.

### 8.10 Auditing this document

At the end of every cycle, read this file end-to-end as an
audit target, not only as a reference:

- **Find contradictions.** Two rules that cannot both hold, or a rule that
  conflicts with a hard rule, must be resolved explicitly.
- **Find redundancy and drift.** The same rule stated in two places (Part I vs.
  Part II, or two subsections) tends to diverge; merge it into one place and
  cross-reference.
- **Find inefficiency.** A practice that costs more time than it saves (extra
  round-trips, probes nobody uses, stale tooling notes, paths or commands that no
  longer work) should be cut or tightened.
- **Verify the facts.** Check that named commands, paths, tools, and
  cross-references still exist and work (`rg` the symbols; run the command if it
  is cheap). `tools/check_doc_references.py` (§9.8) resolves every `§N` section
  and backticked repo path mechanically; it proves a reference *exists*, not that
  it points at the right place, so still read the passage it lands on.
- **Ask the user about the ultimate choices.** Do not silently pick a winner for
  a conflict or ambiguity. Present each finding as: the conflict/inefficiency,
  the realistic options, and a recommendation; wait for the user's decision.
- Apply the agreed changes with consent (§8.11), then re-read the affected
  sections once to confirm the doc is coherent after the edit.

### 8.11 After the audit (gated on explicit consent)

Report the proposed/actual changes, then **wait for explicit consent**. Only
after that:

- Bring every `.md` doc up to date with the code.
- Delete all redundant / stale passages from the docs.
- Record the answers to the audit questions from §8.10 in this file.


### 8.12 Cleanup scope: thorough or quick (ask explicitly)

Before starting any cleanup pass, **ask the user explicitly** which scope they
want:

- **Thorough (full codebase):** walk the entire repository against all of
  Part II. Use `tools/plan_cleanup.py --scenario thorough` to build the
  checklist from heuristics, then verify against reality. Treat the whole tree as
  in-scope.
- **Quick (delta only):** restrict to files changed in the current cycle
  (`git diff --name-only` / `--since REF`). Still apply every rule that touches
  those files (naming, dead code, imports, constants, layering), but do not block
  on unrelated long files. Use `tools/plan_cleanup.py --scenario quick`
  to scope.

State the choice and any constraints (behavior/design changes need consent per
§8.11) before making edits. If the answer is ambiguous, ask again — do not
guess.

### 8.13 Cleanup rules apply during routine implementation too

The standards in Part II are **not** cleanup-only. They must be followed on
every change:

- **Naming/layering:** apply §8.1/8.2 when creating or moving files/modules.
- **Dead code/imports:** do not leave unused imports, dead helpers, or
  pass-through aliases behind.
- **Composition/SSOT:** prefer §8.4/8.5 over duplicating or stacking named
  behaviors.
- **Constants/style:** no new inline magic values (see §8.7).
- **App boundaries:** respect §8.8 (`markup_app/` deletable, mirror shared
  structure, isolate app-specific code).
- **Tooling:** use `tools/read_codebase.py` to map unfamiliar areas,
  `tools/rewrite_imports.py` for safe renames/moves, and
  `tools/check_cleanup.py` to verify after structural changes. Run
  `tools/strip_comments.py` after adding code that may carry comments, and
  `tools/find_unused_definitions.py` before finishing a change that may have
  orphaned code. For
  `<see>` / link-resolution changes, use a targeted probe (§4.1) or the markup
  app's broken-links filter. For structural changes that must stay
  behavior-neutral, bracket the work with `tools/snapshot_behavior.py
  --save`/`--check` (§9.14, order in §8.16); after touching Qt styles,
  documents, or text formats, run `tools/check_pyside_traps.py` (§9.15).
- **Scope discipline:** for a small change, do not do a full-cycle cleanup —
  fix the touched code to comply with these rules (no behavior change). If
  compliance requires a broader refactor, ask the user per §8.11.

### 8.14 Lessons from the cleanup pass (kept as working guidance)

- **Import rewriting is the hazard:** bulk substring renames match suffixes
  (e.g. `.link_marks` inside longer names). Only rewrite import statements and
  move symbols through `tools/rewrite_imports.py`.
- **Boundaries are hard:** `dictionary_app` must not import `markup_app`; share
  via `dictionary_app/` (e.g. `utils/normalize_headword`, `theme/styles`).
- **One owner per rule:** duplicated logic drifts (quote sets, highlight
  exclusion) — extract to a shared primitive.
- **Naming follows role:** a module is an actor (verb) or data (noun); avoid
  buckets (`*_helpers`/`*_utils`) and one-file folders.
- **Verify before and after:** capture a baseline, run `compileall`, unused
  imports, and the relevant probes.
- **PowerShell + Unicode:** never rely on shell text rewrites on UTF-8
  sources; use the editor tools or `py -3` with UTF-8.
- **Orders and raw data:** preserve raw print order and never drop raw-only
  entries (see `markup_app/data/MARKUP_PATTERNS.md`); never touch dictionary
  XML/localization JSON/DB files.

### 8.15 Markdown naming convention
- **Project docs**: use SCREAMING_SNAKE_CASE.md (e.g., `AGENTS.md`,
  `DEVELOPMENT_PRACTICES.md`, `MARKUP_PATTERNS.md`); nested docs reuse the same
  name (`dictionary_app/AGENTS.md`, `markup_app/AGENTS.md`,
  `tools/DEVELOPMENT_PRACTICES.md`).
- **Exempt**: README.md follows universal convention and remains unchanged.
- All new project documentation must follow this rule. Do not use kebab-case, snake_case, or PascalCase for non-README markdown files.

### 8.16 Order of changes in a refactor or cleanup

Do the work in this order; each step makes the next one safer and cheaper:

1. **Settle behavior first.** Finish or explicitly freeze functional changes
   before restructuring, so any diff can be attributed to one kind of work.
2. **Capture derived behavior.** Run `tools/snapshot_behavior.py --save`
   (§9.14) on the current code. A snapshot is the only parity oracle for state
   derived from the DB and the formatters; comparing rendered output against
   `git HEAD` only works for pure moves.
3. **Delete dead code.** Remove unused imports, helpers, branches, flags, and
   localization keys (§8.3) before moving anything.
4. **Consolidate shared primitives.** Apply §8.4/§8.5 while the files are still
   recognizable; duplication is cheapest to remove before the split.
5. **Split files last.** Refactoring adds lines (signatures, imports, module
   scaffolding), so splitting earlier means splitting twice. Re-run the
   snapshot after each split; a pure move must keep it green.
6. **Docs last.** Update `AGENTS.md`/this file only after the code stops moving,
   then run `tools/check_doc_references.py` (§9.8).

Never treat "the refactor is neutral" as a reason to skip the snapshot: a green
snapshot proves neutrality, a red one means either the change was not neutral or
the baseline needs an intentional, reviewed re-save.

### 8.17 Crutches and accidental overengineering

A refactor is also the moment to recognize code that exists only because
something was hard at the time:

- **Crutches:** compatibility shims for data that no longer exists,
  retry/fallback branches that cannot fire, flags with one caller, helpers added
  only to make a probe pass, and duplicated values kept "just in case". Delete
  them unless a maintained doc names the case and calls the code a **trampoline
  for a specific planned feature**.
- **Accidental overengineering:** a new abstraction, cache, option, or
  generalization introduced by the refactor for one caller. §8.6's "do not
  overengineer" applies during cleanup as well as during optimization.
- **How to decide:** `rg` the symbol and its doc reference. If only probes,
  unreferenced helpers, or the refactor itself mention it, it is a crutch. If a
  doc says "keep"/"preserve"/"trampoline" and explains the future
  functionality, keep it and cross-reference that section instead of restating
  the rationale.
- **Report removals.** List deleted crutches in the change report so the user
  can veto one that was in fact planned.

# Part III — Repository tools

The scripts in this folder are reusable across projects: pass `--root`,
`--exclude`, JSON configs, or git ranges. Run them with `py -3` from the repo
root; set `$env:PYTHONUTF8="1"` when they touch Belarusian text or XML.
This folder is the only sanctioned location for scripts outside the two
applications and is not gitignored. Nothing in `dictionary_app/` or
`markup_app/` imports these scripts, so the folder is deletable as a unit.

## 9. Scripts

| script | purpose | example |
|---|---|---|
| `read_codebase.py` | build a symbol map of the repo (see below) | `py -3 tools/read_codebase.py --root .` |
| `plan_cleanup.py` | heuristic cleanup checklist (see below) | `py -3 tools/plan_cleanup.py --scenario thorough` |
| `rewrite_imports.py` | safe import renames/moves/splits | `py -3 tools/rewrite_imports.py plan.json` |
| `find_unused_imports.py` | AST scan for unused imports | `py -3 tools/find_unused_imports.py .` |
| `check_cleanup.py` | run the built-in checks, then clean artifacts | `py -3 tools/check_cleanup.py --clean --status` |
| `strip_comments.py` | delete source comments (see below) | `py -3 tools/strip_comments.py` |
| `find_unused_definitions.py` | module-level defs/classes nothing references (see below) | `py -3 tools/find_unused_definitions.py` |
| `check_doc_references.py` | unresolved `§` sections and repo paths in docs (see below) | `py -3 tools/check_doc_references.py` |
| `inspect_data.py` | read-only data queries: counts, lookup, duplicates, attribute census (see below) | `py -3 tools/inspect_data.py --count` |
| `digraph_export.py` | shared xlsx writer + digraph row builders; imported, no CLI (see below) | — |
| `export_hw_digraphs.py` | every `<hw>` containing `дз`/`дж` → xlsx | `py -3 tools/export_hw_digraphs.py` |
| `export_hw_separated_digraphs.py` | every `<hw>` whose digraph is split by `<sep />` → xlsx | `py -3 tools/export_hw_separated_digraphs.py` |
| `export_see_hw.py` | every `<see hw="…">` with its entry's main headword → xlsx | `py -3 tools/export_see_hw.py` |
| `search_xml.py` | grep-like recursive text search across the marked-up XML corpus (see below) | `py -3 tools/search_xml.py "слова"` |
| `search_xml_app.pyw` | double-clickable window around `search_xml.py`: type a query, press Enter, see headwords and snippets (see below) | double-click `tools/search_xml_app.pyw` |
| `fix_tag_punctuation.py` | move punctuation that follows a closing tag inside that tag, one reviewed candidate at a time (see below) | `py -3 tools/fix_tag_punctuation.py` (Enter = skip, `y` = accept, other text = replacement; `--apply` accepts all) |
| `compare_raw_markup.py` | raw-OCR vs marked-up XML: coverage per letter and convention census (see below) | `py -3 tools/compare_raw_markup.py --coverage` |
| `snapshot_behavior.py` | golden JSON of derived dictionary/search/sources/`<see>` behavior (see below) | `py -3 tools/snapshot_behavior.py --save` then `--check` |
| `check_pyside_traps.py` | AST scan for Qt style-ownership, font, and document traps (see below) | `py -3 tools/check_pyside_traps.py` |

### 9.1 `read_codebase.py` — map a repo quickly

Builds a symbol map without reading every file in chat. Outputs go to
`%TEMP%/cleanup/<root name>/` unless `--out` is given.

| flag | purpose |
|---|---|
| `--root DIR` | repo root |
| `--ext .py,.md` | extensions to index (default `.py`) |
| `--exclude parts` | extra path parts to skip |
| `--query REGEX` | grep the snapshot with `--context N` / `--limit N` |
| `--out DIR` | output directory |

Outputs: `code_map.txt` (imports/classes/functions/methods with line ranges),
`code_snapshot.txt` (numbered file contents), `symbols.txt`
(`name<TAB>path:line<TAB>kind`).

```powershell
$env:PYTHONUTF8="1"; py -3 tools/read_codebase.py --root .
py -3 tools/read_codebase.py --query "def on_link_clicked" --context 5
```

### 9.2 `plan_cleanup.py` — scope + heuristics

Produces a prioritized checklist written to `%TEMP%\cleanup\<repo>\plan.md`
(not into the repo). Supports `thorough` (default) and `quick`.

| flag | purpose |
|---|---|
| `--scenario thorough\|quick` | full codebase or delta only |
| `--since REF` | git range for quick mode (default `HEAD~1`) |
| `--config JSON` | override thresholds (`max_file_lines`, `max_func_lines`, `max_line_length`, `literal_min_length`, `literal_min_count`, `bucket_pattern`) |
| `--out FILE` | write plan elsewhere |

Findings: long files/functions/lines, bucket modules (`*_utils`/`*_helpers`),
private cross-module imports, one-module folders, folder/file name duplication,
repeated string literals.

```powershell
py -3 tools/plan_cleanup.py --scenario thorough
py -3 tools/plan_cleanup.py --scenario quick --since HEAD
```

### 9.3 `rewrite_imports.py` — safe renames/moves/splits

Updates **import statements only** (no symbol rewriting inside bodies). Dry-run
by default; refuses to write if any changed file would not parse.

Plan schema:

```json
{
  "files":   {"old/path.py": "new/path.py"},
  "modules": {"old.module": "new.module"},
  "splits":  {"old.module": {"Symbol": "new.module"}}
}
```

If `files` are given and `--no-move` is not set, files are moved with `git mv`
first, then module maps are derived. Relative imports are rewritten correctly,
parenthesized imports are re-wrapped to `<= 96` columns, and `__future__` imports
are untouched. Runs `compileall` after `--apply`.

```powershell
py -3 tools/rewrite_imports.py plan.json
py -3 tools/rewrite_imports.py plan.json --apply
```

### 9.4 `find_unused_imports.py` — unused import scan

AST scan for unused imports; skips `__init__`, build/test artifacts, and honors
`__all__` and `TYPE_CHECKING`. Exits `1` if any are found.

```powershell
py -3 tools/find_unused_imports.py .
```

### 9.5 `check_cleanup.py` — verify + clean

Runs built-ins when present: `compileall` on the selected packages and
`find_unused_imports.py`. Accepts PySide offscreen teardown codes if pass markers
appear in the output.

| flag | purpose |
|---|---|
| `--packages pkg1,pkg2` | override compileall targets |
| `--probes DIR` | run all `probe_*.py` (counts `0` or pass markers as success) |
| `--step "label::command"` | extra check (repeatable) |
| `--clean` | delete `*.pyc`/`*.pyo`/`*.orig`/`*.rej`/`*.bak` and `__pycache__` |
| `--scratch path` | extra temp to remove (repeatable) |
| `--dry-run` | show what `--clean` would delete |
| `--status` | print `git status` at the end |

```powershell
$env:PYTHONUTF8="1"; $env:QT_QPA_PLATFORM="offscreen"
py -3 tools/check_cleanup.py
py -3 tools/check_cleanup.py --probes "$env:TEMP\opencode" --clean --status
```

### 9.6 `strip_comments.py` — delete source comments

Deletes comments from source files, enforcing the "no comments in source code"
hard rule without asking. Tokenizes each file, so a `#` inside a string (CSS
colours, URL schemes) is not a comment and docstrings are untouched; shebangs,
coding cookies, and `--allow` matches are kept. Line endings and the source
encoding are preserved, and a write is refused if the `ast` tree would change.

| flag | purpose |
|---|---|
| `--root DIR` | repo root |
| `--ext .py` | extensions to scan |
| `--exclude parts` | extra path parts to skip |
| `--allow REGEX` | keep matching comments (repeatable) |
| `--dry-run` | list what would be deleted, change nothing |

Exits `0` after cleaning (also when there was nothing to delete) and `1` only
when a file cannot be read, parsed, or safely rewritten.

```powershell
py -3 tools/strip_comments.py
py -3 tools/strip_comments.py --dry-run
```

### 9.7 `find_unused_definitions.py` — dead definition scan

Complements `find_unused_imports.py` (imports only): reports module-level
functions and classes that nothing else in the tree references.

| flag | purpose |
|---|---|
| `--root DIR` | repo root |
| `--ext .py` | extensions to scan |
| `--kinds def,class[,constant]` | definition kinds to report |
| `--ignore REGEX` | names to exempt (repeatable), e.g. public API kept for callers |
| `--show-used` | also print candidates that are referenced |

The scan is name-based: `getattr`, string dispatch, and PEP 562 `__getattr__`
exports are invisible, so hits are candidates, not proof. Names listed in
`__all__`, dunders, and `__init__.py` are skipped. Exits `1` on findings; not
wired into `check_cleanup.py`, because a hit must be classified below before it
can be fixed.

Resolve every hit the same way:

1. **Obviously stale** — nothing can reach it and it has no documented purpose
   (an alias of another function, a helper superseded by its replacement):
   delete it without asking.
2. **Questionable** — public API, a documented helper, or possible dynamic use:
   ask the user before deleting.
3. In both cases update every doc that names the symbol (module tables, symbol
   lists, cross-references) in the same change. This flow is the standing
   consent for those doc edits (§8.11).

```powershell
py -3 tools/find_unused_definitions.py
py -3 tools/find_unused_definitions.py --kinds def,class,constant --ignore '^main$'
```

### 9.8 `check_doc_references.py` — doc cross-reference check

Mechanizes the "cross-references still exist" part of §8.10. Reports a `§N` /
`§N.M` that matches no numbered heading in its own document, and a backticked
repo path that does not exist relative to the root or to the file that names it.

| flag | purpose |
|---|---|
| `--root DIR` | repo root |
| `--ext .md` | extensions to scan |
| `--exclude parts` | extra path parts to skip |
| `--sections-from PATH` | also accept section numbers from this doc (repeatable) |
| `--ignore-glob PATTERN` | skip matching path references (repeatable) |
| `--path-ext LIST` | extensions that make a token count as a path |
| `--checks sections,paths` | run one class of check only |
| `--show-ignored` | list the references skipped via `.gitignore` |
| `--no-gitignore` | do not skip paths matched by `.gitignore` |

Sections resolve against the same document by default — the usual meaning of a
`§7` inside a doc that has its own §7 — so pass `--sections-from` for a doc that
cites another doc's numbering. A bare `§8` resolves when `8` or any `8.x` exists.
Only path-like tokens are checked (first segment exists at the root, or the
extension is in `--path-ext`), so prose slashes such as `back/forward` and module
mentions such as `theme/styles` are ignored. `.gitignore` is honoured, so
generated outputs (`build/`, `*.db`) never fail the check; `!` negation patterns
are not interpreted.

Exits `1` on any unresolved reference. It proves a reference resolves, never that
it points at the right content — read the target when the meaning matters.

```powershell
py -3 tools/check_doc_references.py
py -3 tools/check_doc_references.py --sections-from docs/index.md
py -3 tools/check_doc_references.py --checks sections
```

### 9.9 `inspect_data.py` — query data files read-only

Answers questions about data files (dictionary XML, raw OCR `.txt`) without
reading them into the conversation. **Never writes:** no query opens a file for
writing, creates a file, or touches the database. The tag scan is line-oriented,
so it reports `path:line` and survives malformed markup; records are discovered
at runtime as the most common child of the root element.

| flag | purpose |
|---|---|
| `--root DIR` | repo root |
| `--glob PATTERNS` | comma-separated file patterns (default `*.xml,*.txt`) |
| `--exclude parts` | extra path parts to skip |
| `--count` | per-file bytes, lines, tags, records, top tags |
| `--lookup TEXT` | substring search; `--ignore-case`, `--context N`, `--snippet N` |
| `--duplicates SPEC` | duplicate attribute values; `TAG/ATTR` or bare `ATTR` |
| `--attribute-audit` | tag/attr census with distinct counts, samples, single-use list |
| `--tag TAG` | restrict count/audit/duplicates to one element |
| `--record TAG` | record element for `--count` (default: auto-detect) |
| `--limit N` | max printed rows/groups (0 = all) |
| `--top N` | sample values per attribute pair (default 3) |

```powershell
$env:PYTHONUTF8="1"
py -3 tools/inspect_data.py --count
py -3 tools/inspect_data.py --lookup "ча́паць" --limit 5
py -3 tools/inspect_data.py --lookup "чохаўка" --context 1
py -3 tools/inspect_data.py --duplicates entry/id
py -3 tools/inspect_data.py --attribute-audit --tag hw
```

Use it before reading a data file: one count or lookup replaces a 6k–44k-token
file read with a few hundred tokens of ASCII-labelled lines. Cyrillic appears
only in the answer (a matched line, a duplicated value, a sample), never in the
labels. Exits `0` when the query ran and `1` when no file matched or a file could
not be read — the failure is reported and the remaining files are still queried,
so one bad file never hides the rest.

Limits: the scanner assumes XML-like markup and does not resolve entities or
CDATA; `--duplicates` compares raw attribute strings without normalization. It is
an inspector, not a validator.

### 9.10 Data exports (`digraph_export.py` + `export_*.py`)

Small, project-specific exporters that turn a corpus question into one xlsx the
user can scan in Excel. They read the source XML only — the database is not
opened, and nothing is written except the workbook.

- **`digraph_export.py` is a library, not a script.** It imports the repo
  (`get_source_names` / `get_source_path`, `hw_text_excluding_n`,
  `SEP_SORT_SENTINEL`, `ATTR_*`) and provides:
  - `digraph_rows()` — every `<hw>` whose text contains `дз`/`дж` (case-folded);
  - `separated_digraph_rows()` — every `<hw>` where `д`, the `SEP_SORT_SENTINEL`
    and `з`/`ж` are adjacent, i.e. a `<sep />` splits the digraph;
  - `write_workbook(rows, output_name, headers=HEADERS,
    column_widths=COLUMN_WIDTHS, sheet_title=SHEET_TITLE)` — writes the header
    (bold, wrapped), the rows (wrapped, top-aligned), the column widths, and
    freeze panes `A2`; a relative `output_name` resolves against `tools/`. The
    defaults are the digraph table (`Файл`, `Артыкул`, `Загаловак`,
    `XML загалоўка`, `XML артыкула`); `export_see_hw.py` overrides all three.
  Header text in these exporters is Belarusian, so the console output stays
  ASCII (`N row(s) written to <path>`).
- **Row shape:** digraph exports emit `(source_file, entry_id, headword_text,
  headword_xml, entry_xml)` with the sentinel rendered as `<sep />` in the display
  column; the see export emits `(main headword, <see …>…</see> span)` and skips
  sees without `hw`. `_main_headword` returns the first non-`excl` `<hw>`
  (falling back to the first non-empty one), so the label is the entry's real
  main headword, not the first `<hw excl="true">`.
- **Invocation:** each `export_*.py` takes an optional output name as `argv[1]`
  and otherwise writes its `DEFAULT_OUTPUT` (`hw_digraphs.xlsx`,
  `hw_separated_digraphs.xlsx`, `see_hw_links.xlsx`) into `tools/`. Output is
  gitignored (§8.9); add `openpyxl` to the environment before use.
- **Adding a new export:** put the row builder next to the existing ones (or a
  new `export_*.py` for a different corpus question), reuse `write_workbook`
  instead of duplicating styling, and keep the script read-only.

### 9.11 `fix_tag_punctuation.py` — trailing punctuation inside tags

A candidate is an opening tag, its content, its closing tag, and the run of
Unicode punctuation characters (category `P*`) that immediately follows the
closing tag. The run ends at the first non-punctuation character. These
candidates are skipped because moving the punctuation would change the rendered
form: any `</g>—` (an em dash after `</g>`), every `</hw>` whose run starts with
a character in the editable `SKIP_PUNCTUATION_BY_TAG['hw']` tuple (by default
`. , — ( ) : ; - [`), `</t>.`, every `</see>` and `</n>`, and any `<src>` whose
content contains `<b>` (e.g. `<src><b>С.</b></src>)`). Add new punctuation to
that tuple rather than to `_should_skip`.

When two or more adjacent `<src>` elements are separated by `;` or `,` and
optional spaces, the candidate covers the whole run (including optional
surrounding `(` / `)`), whether or not the last source is followed by
punctuation, and the prepared text merges them into one source span. The
separator may follow other punctuation, as in `</src>.; <src>`:

```text
  before: <src>Янк. І</src>; <src>Ар.</src>
  after:  <src>Янк. І; Ар.</src>
```

```text
  before: (<src>Ар.</src>; <src>Міх.</src>).
  after:  <src>(Ар.; Міх.).</src>
```

A single `<src>` wrapped in parentheses is treated as a one-member group, so
the parentheses move inside the source and any trailing punctuation follows
them:

```text
  before: (<src>Ар.</src>).
  after:  <src>(Ар.).</src>
```

For `<g>` and `<src>`, a trailing em dash stays outside the tag; only the
punctuation before it is absorbed. This turns `</g>,—` into `,</g>—` and
`</src>.—` into `.</src>—`:

```text
  before: <src>Нсл. 346</src>.—
  after:  <src>Нсл. 346.</src>—
```

Otherwise each candidate is shown as the pair before and after moving that run
inside the closing tag:

```text
  before: <g>муж.</g>,
  after:  <g>муж.,</g>
```

Each candidate also prints the headword(s) of its parent `<d>` span, or of the
entry span outside any `<d>`, so the reviewed context is identifiable.

The prompt offers three actions: Enter skips the candidate, `y` writes the
prepared `after` text, and any other input replaces the whole candidate span
(opening tag through trailing punctuation) with the typed text. Moving
punctuation inside `<hw>` changes the headword, so the `<hw>` cases above are
skipped; `<see>` and `<n>` are always skipped. An accepted change is written
immediately and the file's existing line endings are preserved. Before each
write the script re-reads the file and compares it with the text it last saw; if
another program (for example the markup app) saved the file in the meantime, the
script stops instead of overwriting that save. Rerun it to continue from the
current file. Later candidates are re-mapped after every write, so nested pairs
and following tags stay valid. `--apply` writes the prepared `after` text for
every candidate without asking (for scripts/automation); a non-interactive run
without `--apply` only previews. Arguments are XML files or directories; the
default target is `dictionary_app/data` (recursive `*.xml`). Examples:

```powershell
py -3 tools/fix_tag_punctuation.py
py -3 tools/fix_tag_punctuation.py --apply
py -3 tools/fix_tag_punctuation.py dictionary_app/data/dictionary/dictionary_D.xml --apply
```

### 9.12 `search_xml.py` — search every XML file at once

For non-developers, double-click `tools/search_xml_app.pyw`. A window opens
with a query field focused: type a query and press Enter (or click **Search**).
Results appear in a table with **Headword**, **File**, **Line** and **Snippet**
columns; **Regex** and **Ignore case** checkboxes are optional, and the status
line reports matches and files. The query is used exactly as typed: leading and
trailing spaces are significant (a single space searches for spaces), so no
whitespace is trimmed. The window calls the same functions as the CLI, so
headword rules and snippets are identical. Double-clicking the `.pyw` uses
`pythonw`, so no console window appears.

The CLI is the scriptable form. Windows Explorer cannot search inside several
files at once; this is the grep-like replacement for the marked-up corpus. It
walks the target directories recursively (default `dictionary_app/data`, glob
`*.xml`) and prints `path:line:column` for every matching line, with a clipped
snippet around its first match. Literal matching is the default; `--regex`
switches to Python regular expressions.

| flag | purpose |
|---|---|
| `--glob PATTERNS` | comma-separated file patterns (default `*.xml`) |
| `--exclude parts` | extra path parts to skip |
| `--ignore-case` | case-insensitive matching |
| `--regex` | treat the query as a regular expression |
| `--context N` | lines of context around each match (default `0`) |
| `--snippet N` | printed characters per line, `0` = full line (default `160`) |
| `--limit N` | matching lines to print per file, `0` = all (default `200`) |
| `--count` | per-file match counts and a total |
| `--files-with-matches` | print only paths that contain a match |

Match lines use `path:line:column: snippet`; context lines use
`path-line- snippet`, with `--` between non-adjacent groups. Each matching line
that belongs to a dictionary entry also prints
`path:line:column  headword(s): …` followed by an indented snippet. The
headwords come from the innermost enclosing `<d>` (its own `<hw>` children,
nested `<d>` spans excluded) or, outside any `<d>`, from the entry's own
`<hw>`s. Lines without a headword (e.g. `sources.xml`) keep the one-line form.
The summary reports matches and files. With no query the script prints its help
and exits `2` instead of raising an argparse error. Exit codes follow grep: `0`
match, `1` no match, `2` error.

```powershell
$env:PYTHONUTF8="1"
py -3 tools/search_xml.py "слова"
py -3 tools/search_xml.py "<src>" --context 1
py -3 tools/search_xml.py "\bча́паць\b" --regex --ignore-case
py -3 tools/search_xml.py "грыжа" --count
py -3 tools/search_xml.py "Ар." --glob "*.xml" --limit 0
```

### 9.13 `compare_raw_markup.py` — raw OCR vs marked-up XML

Answers "how much of this letter is marked up, and which conventions does its
XML use" without reading either file. Pairs
`dictionary_app/data/dictionary/dictionary_<X>.xml` with
`markup_app/data/dictionary_raw/dictionary_<X>_raw.txt` by the `<X>` suffix; a
missing partner is reported and skipped.

`--coverage` aligns XML entries to raw `•` blocks in print order (accent-free
fuzzy text match, order-preserving) and prints per letter: raw blocks, XML
entries, aligned pairs, consumed and skipped blocks, remaining blocks, and the
last covered raw preview. It then lists the XML entries that match no block (an
order deviation or a reworked entry) and the raw blocks skipped inside the
covered range (a `см. под` entry the user deleted, or a block printed out of
order).

`--conventions` prints per file: `<hw>`/`<g>` acute/grave counts, split-source
runs (`</src>; <src>`), the two `<br>` forms, `syn="true"` uses, `<see>`
attribute combinations, `<lang code>` values, `<p>` count, and ASCII vs curly
apostrophes.

| flag | purpose |
|---|---|
| `--root DIR` | repo root |
| `--letter X` | one letter only |
| `--limit N` | printed finding rows per letter, `0` = all (default 10) |

```powershell
$env:PYTHONUTF8="1"
py -3 tools/compare_raw_markup.py --coverage
py -3 tools/compare_raw_markup.py --coverage --letter Cz --limit 0
py -3 tools/compare_raw_markup.py --conventions --letter Cz
```

It is a locator, not a judge: a skipped block may be a deleted cross-reference
or a real gap, and an unmatched entry may be a deliberate move. Read only the
flagged blocks. The alignment assumes one bullet per printed headword and print
order; a transposed pair shows up as two findings. Exit `0` when the report ran,
`1` when a paired file is missing or unreadable.

### 9.14 `snapshot_behavior.py` — golden parity for derived behavior

Runs the real search engine, entry formatter, sources renderer, and `<see>`
classifier against the existing `dictionary.db` and writes a deterministic JSON
snapshot. It is read-only: it opens the DB directly (never
`create_search_engine()`), enables `PRAGMA query_only`, and fails cleanly when
the DB is missing. Default baseline:
`tools/build/behavior_snapshot.json` (under the ignored `build/`). Set
`$env:PYTHONUTF8="1"` when running it.

| flag | purpose |
|---|---|
| `--save [PATH]` | write the baseline (default path above) |
| `--check [PATH]` | compare the current code with the baseline |
| `--database PATH` | use another DB |
| `--entries N` | entry HTML samples, `0` = all (default 150) |
| `--rows N` | search rows kept verbatim per case; digests still cover all rows |

Captured state: DB invariants (schema version, table counts, content/index and
source-file distribution, index names); sampled `format_entry` hashes plus one
targeted-subheadword render; sixteen fixed search cases (headwords,
translations, examples; both alphabets; empty/whitespace query; wildcards;
accents; `ё`; `ґ`) with full row/preview digests and a verbatim sample; sources
rendering (expanded, collapsed, search, no match, marker anchors); and every
`<see>` outcome with its resolved row identity.

Exit codes: `0` identical, `1` mismatch (first 40 differences printed), `2`
missing DB/baseline or unreadable JSON. A mismatch is a finding: fix the code,
or, when the behavior change was intended, review and `--save` a new baseline.
Run it per §8.16 — before/after every behavior-neutral move and after each
split. It imports `markup_app`, so it lives only while both apps do.

### 9.15 `check_pyside_traps.py` — Qt ownership and font traps

AST scan (no imports, no Qt needed) for the PySide patterns that crash or leak
in this build. `--root` and `--ext` select the tree; `--exclude` adds path parts
on top of the built-in skip list. Findings print as
`path:line: severity [rule] message`.

| rule | severity | trigger | rule of thumb |
|---|---|---|---|
| `proxy-style-base` | fatal | `QProxyStyle(...)` or a `*Style(...)` subclass with a positional/keyword base | the proxy takes ownership of the base; construct it with no base and parent it (use `install_no_blue_focus_style`); never pass a live style (`self.style()`, `app.style()`) |
| `set-font-family` | fatal | `.setFontFamily(...)` / `.fontFamily(...)` | crash (0xC0000005) in this PySide build; use `setFonts` / `setFontFamilies` |
| `set-document` | advisory | `.setDocument(...)` | `QTextEdit.setDocument` does not own the document; keep a Python reference and `deleteLater()` the replaced one |

Advisory findings do not fail the run; `--strict` makes them fatal. Exit `0`
with no fatal finding, `1` fatal (or any advisory under `--strict`), `2` bad
root. The advisory is deliberate: `setDocument` is correct when ownership is
explicit (see `DictTextBrowser.setHtml` in `dictionary_app/AGENTS.md`).

## 10. Exit codes

Scripts exit `0` on success and `1` on findings/failures. `search_xml.py`
follows grep instead: `0` match, `1` no match, `2` error.
`snapshot_behavior.py` exits `2` for a missing database/baseline or unreadable
JSON.

## 11. Reuse

Copy the scripts in `tools/` into another repo; `read_codebase.py`,
`plan_cleanup.py`, `strip_comments.py`, `find_unused_definitions.py`,
`check_doc_references.py`, `inspect_data.py`, `search_xml.py`, and
`check_pyside_traps.py` are project-agnostic (the latter assumes PySide6). The data inspector learns the record tag at runtime and takes
`--glob`/`--tag`/`--record`, so it works on any XML-like dataset without edits;
the search script is a generic recursive grep with a data-folder default.
`rewrite_imports.py` only touches imports. `digraph_export.py` and the
`export_*.py` scripts (§9.10) are
the exception: they import `dictionary_app` and encode this corpus's `<hw>` /
`<sep />` / `<see hw>` shapes, so copy them only when the target repo has the
same schema (the `write_workbook` writer itself is generic).
`compare_raw_markup.py` (§9.13) hard-codes this repo's raw/XML folder layout and
`dictionary_<X>` naming; the alignment logic is reusable, the paths are not.
`snapshot_behavior.py` (§9.14) imports both apps plus this corpus's DB/format
layer, so copy it only with the same architecture. For per-repo policy,
write a local config and a plan JSON (populate from the repo's actual module
names).
