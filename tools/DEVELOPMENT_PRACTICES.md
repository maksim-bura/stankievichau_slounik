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
  off-limits. The DB rebuild reads XML only and must not rewrite it.
- **Localization JSON is manually maintained** — edit individual keys only,
  never re-serialize or reformat.
- **No comments in source code.** This codebase is comment-free by convention;
  rationale lives in the `.md` docs. (At cleanup: delete every comment.)

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
- Keep file, folder, and entity naming consistent across both apps (§8.8).

### 8.2 Structure and file layout

- Split files that have grown too large into smaller, single-purpose modules.
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
  only then. A tool must exit 0 whenever it is run: if the pass made it fail, fix
  it in that moment, so no red tool is left behind. The whole directory is
  deletable as a unit: nothing in `dictionary_app/` or `markup_app/` imports it
  (grep for `import tools` / `from tools` to confirm before deleting); keep only
  the scripts you actively rely on.
- Delete code that became redundant as a result of the fixes: obsolete helpers,
  flags, branches, imports, parameters, CSS rules, localization keys.
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

- **Optimize from measurement, not intuition.** Measure the real entry point
  before changing it and re-measure after; a change that cannot be shown to
  move the number is churn.
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
- **Reference catalog:** `tools/SOFTWARE_OPTIMIZATION_TECHNIQUES.md` is a
  menu of optimization techniques by level (architecture, algorithms, data
  structures, memory, I/O, databases, concurrency, deployment). Consult it when
  choosing an approach, but it is guidance, not a mandate: measurement and the
  footprint rules above decide whether a technique is used.

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
  remain untracked.

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
  is cheap).
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
  `tools/check_cleanup.py` to verify after structural changes. For
  `<see>` / link-resolution changes, use a targeted probe (§4.1) or the markup
  app's broken-links filter.
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

## 10. Exit codes

Scripts exit `0` on success and `1` on findings/failures.

## 11. Reuse

Copy the scripts in `tools/` into another repo; `read_codebase.py`/`plan_cleanup.py` are
project-agnostic. `rewrite_imports.py` only touches imports. For per-repo policy,
write a local config and a plan JSON (populate from the repo's actual module
names).
