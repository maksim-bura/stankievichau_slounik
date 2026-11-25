# Dictionary Markup Patterns

Operational playbook for converting the authoritative OCR text in
`markup_app/data/dictionary_raw/dictionary_<letter>_raw.txt` into the
lexicographic XML in `dictionary_app/data/dictionary/dictionary_<letter>.xml`.
Written for an AI agent doing the transcription.

App behavior is documented in `dictionary_app/AGENTS.md` (shared substrate: rendering,
search, build, collation, DB schema) and `markup_app/AGENTS.md` (markup editor);
this file covers only raw → XML markup.

## 1. Input and output

| | |
|---|---|
| **Input** | `markup_app/data/dictionary_raw/dictionary_<letter>_raw.txt` — one proofread OCR block per printed page/region; the authoritative text for that letter |
| **Output** | `dictionary_app/data/dictionary/dictionary_<letter>.xml` — `<dictionary>` root; one `<entry>`…`</entry>` block per headword, at column 0, blank line between blocks |
| **Order** | Output keeps the raw **print order**. Never alphabetize an XML file. **Never move, reorder, re-indent, or re-insert an `<entry>` block that is already in the file** — existing blocks stay exactly where they are; new work is only appended at the end. On-screen sorting is done by the database at query time (see `dictionary_app/AGENTS.md` → Collation Rules), so file order and list order intentionally differ. |

Raw format facts that drive the splitting:

- **Every headword is wrapped in `<entry>`…`</entry>`.** The tags of one headword
  form the entry BODY; the body always sits inside the wrapper. In the XML file
  the wrapper is at column 0 with a blank line between blocks.
- Each printed headword starts with a `•` bullet: `•ся́драва, нареч.—холодновато.`
- A leading `^` is the same headword marker when it opens a raw block
  (`^чыты-тая-тае—трезвый.` → `<hw>чы́ты</hw>` — Cz); a caret before a
  parenthesized source (`^(Афанасьев, …)`) is source text, not a headword.
- A raw line/block may contain **several** bullet-led headwords joined by `,`
  (`•ґазалі́на-…, •ґазамэтра-…`) — each `•` becomes its own `<entry>`, in the
  order the bullets appear, left to right. A merged line is layout, not a sort:
  never re-order its bullets even when the pair looks alphabetically wrong (Cz
  `•чарот…, •чапы́жнік…` keeps чарот first). The printed order is the only
  authority.
- A raw block may also hide a related sub-word inside the same paragraph
  (`•ґарсэт, … •ґарсэтніца, …`); split those too. A bullet that follows a
  numbered continuation sense is a new entry, not part of that sense
  (`2. … •зырчэць` — Z).
- Blank lines separate printed blocks; they do **not** map 1:1 to entries.
- Multi-part content of one entry (senses, sub-headwords, phrasal headwords)
  becomes `<sense>`/`<d>` blocks separated by `<br />`.

## 2. Workflow (per chunk)

Work in small contiguous chunks (roughly one raw screen or one letter section),
never the whole file at once.

1. **Read the raw chunk** from the `_raw.txt`, plus the tail of the target XML
   to know the last entry written. Do not re-read the whole XML file.
2. **Split the chunk into entry units** at every `•`, including the merged and
   comma-joined ones, keeping their left-to-right order (§1). Missing a `•` is
   the most expensive error: that headword silently disappears from the
   dictionary.
3. **Transcribe one entry at a time** into the canonical shape (see §4), using
   the tag table in §3 and the conventions in §5–§8.
4. **Apply OCR fixes** from §9, including the `г`/`ґ` family rule. Fix only what
   the raw clearly proves; keep unknowable fragments verbatim.
5. **Resolve identity**: homonyms get nested `<n>` numerals (§8), colliding
   lexemes get an `<entry id="…">` (§8); cross-references use `<see>` (§7).
6. **Append** the `<entry>` blocks to the XML inside `<dictionary>`, column 0,
   blank line between blocks, keeping print order. Append only — never move, reorder, or
   re-insert existing `<entry>` blocks.
7. **Self-check the chunk** (§11) before moving on. Do not batch a whole file
   and check at the end.

## 3. Tag reference

| tag | role | notes |
|---|---|---|
| `<hw>` | headword (bold, clickable anchor) | one per spelling variant; multi-word headwords like `ґазавая ґрана́та`; homonym numerals nested: `<hw>гале́ра <n>ІІ</n></hw>`; disambiguation links see §8; `excl="true"` marks a display-only variant that is kept out of the entry list and all logic except display + the pointing-finger (`👉`), e.g. `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>` (see `dictionary_app/AGENTS.md` → `<hw excl="true">`); an inflected/cognate variant shown alongside the main form may be italicized INSIDE `<hw>`: `<hw>Юр'е</hw>, <hw><i>Юр'я</i></hw>` (Ju); `keep-acc="true"` marks a headword whose combining accents are load-bearing and must be PRESERVED (never stripped) for display, list identity, search, and `<see>` resolution — used on the Cz `ча́паць`/`чапа́ць` family |
| `<g>` | grammar/declension, italic | declension starts with `-`: `-са, м.`; standalone markers: `нареч.`, `местоим.`, `союз`, `соверш.`, `несоверш.`, `безлич.`, `однкр.`, `средн.`, `прич.`, `отгл. имя сущ.`; may embed `<st>`, `<see>`, `<p>`, `<src>`, even `<hw>` (`один <hw>ґалёш</hw>`) |
| `<t>` | Russian translation; also appears nested INSIDE an `<ex>` as a Russian gloss of a proverb/idiom | transcription, multiple `<t>` per sense allowed; sources and `—` separators inside (H `гарох`: `<ex>Хадзі̀ма ў гарох <t>(знач. щипать горох)</t>. <src>Ст.</src></ex>`); a parenthetical Russian note inside a Belarusian `<ex>` is its own `<t>` (`надзявай<t>( зн. узкие)</t>` — Cz); an unreadable gloss stays a dot run `<t>.....</t>`, never empty |
| `<ex>` | Belarusian example, italic, srcless or `<src>`-tagged | may embed a Russian `<t>` gloss and/or `<st>Послов.</st>` (H `гарох`: `Ідзе гарох, там сем дарог. <st>Послов.</st>, <t>о частом щипании гороха</t>. <src>Дсл.</src>`); `lang="orv"` marks an Old Russian / Old Belarusian quoted passage (Cz `ча́ра`) |
| `<src>` | source, becomes link | `Ар.`, `Гсл.`, `Нсл. 119.`, `Стаішча Чаш. (Ксл.)`, long bibliographic refs stay whole (`Азбукін: Ґеоґрафія Эўропы, 1924`); single-letter `С.` bolded as `<src><b>С.</b></src>`; a source printed inside parens keeps them IN the tag (`<src>(Ксл.)</src>`, `<src>(Ар.)</src>`, `<src>(НК)</src>` — Cz); song/popular-lore attributions stay whole `<src>` (`Из песни, Войш.`, `Из нар. песни.`, `З купальскае песьні.` — Cz); a printed source RUN is one tag with its own separators inside (`<src>Ар.; Ксл.; Шсл.</src>`, `<src>Барсл., Пол., Лепл. (Юхн.).</src>`) — never one `<src>` per abbreviation (Cz review removed 97 split tags); `<st>`/`<i>` may nest inside it (`<src>Ст. Слабада, …, <st>област.</st> Люц. пав.</src>`, `<src>Ст.( <i>под <see>адбівацца</see></i>).</src>` — Cz) |
| `<st>` | register/style marker, italic, linkable | `хим.`, `биол.`, `рел.`, `муз.`, `ист. мор.`, `област.`, `перен.`, `Послов.`; may attach case (`послов.`). Before a sense dash: `<n>1.</n> <st>презр.</st>—<t>кровь. …` (Ju юшка 1); at an `<ex>` tail, with a trailing comma when followed by a source: `<ex>Які добры пан! … <st>Насм. пословица,</st> <src>Нсл.</src></ex>` (Ju юшка 2), also `<st>Поговор.</st>`; a parenthetical usage note inside `<g>` may also be a `<st>` (see §6). An embedded `<p>` inside `<st>` stays plain (non-italic): `<st><p>презр.</p></st>` renders `<span class="st"><span class="p">презр.</span></span>` (Ju `юха́`) |
| `<i>` | italic gloss container | `См. …`/`Ср. …` cross-reference tails, other gloss notes; `lang="vl"` marks a Belarusian-language quoted word/fragment inside a Russian `<t>` gloss (`<i lang="vl">"не"</i>` — N, Jo), `excl="true"` keeps a quoted fragment out of the translation/content index (`<i excl="true">"а (я)"</i>` — N); both render italic |
| `<lang code="…">` | quoted-language fragment, style-inheriting | same as `<i lang="…">` but without forcing italic: formatting (bold/italic/plain) inherits from the surrounding tag; exclusion rules identical to the `lang` attribute — `code="vl"` keeps a Belarusian fragment out of the `<t>` content index/highlight, `code="la"` keeps a Latin fragment out of the same, `code="ru"` out of the `<ex>` index/highlight, `excl="true"` (any value) out of the translation index (Ju `юха́`: `<t><i excl="true">ударение на <lang code="vl">ю</lang></i>—молодец. <src>Нсл. 725.</src></t>`); Latin taxonomic names use `code="la"` (`<lang code="la">Stellaria graminea L©</lang>` — Cz `чапняк`), not `<i>` |
| `<see>` | cross-reference, italic | inside `<i>`, `<g>`, or `<t>` glosses; `syn="true"` marks a synonym pointer, which is NOT a translation and is never wrapped in `<t>`: `—<see syn="true">чалесьнік</see>. <src>Растсл.</src>` (see §7) |
| `<sense n="…">` | numbered/lettered sense block | `<n>1.</n>` numeric or `<n>а)</n>` lettered; `<br />` between senses |
| `<n>` | sense number AND homonym numeral | `<n>1.</n>`, `<n>2.</n>`, `<n>а)</n>`, homonym `<hw>… <n>ІІ</n></hw>` |
| `<d>` | sub-dictionary block with own `<hw>` | phrasal sub-headwords and morphological family blocks; separated by `<br />`; may nest inside a `<sense>` OR contain its own lettered/numbered `<sense>` blocks (see §4, S `вы́смаргнуць`/`абсморганы`) |
| `<p>` | literal parens inside declension/headword strings, or a plain-text child inside `<st>`/`<src>` | keeps `(`/`)` out of italic side effects: `<g>-чу<p>(</p>чаю<p>)</p>…` — **optional/redundant**: the renderer auto-keeps parens non-italic inside `<g>`/`<i>`/`<ex>`/`<st>`/`<see>` even without `<p>` (see `dictionary_app/AGENTS.md` → Entry Formatting: Paren rule). Take-over from raw print stays verbatim: bare parens in italic tags render plain automatically. Also used to mark a variant spelling's `г` as plain inside a bold `<hw>` (`<hw><p>гірса</p></hw>` — G `ґірса`, where `гирса` is the г-spelled variant; treats the letter as non-bold like parens). Inside `<st>`/`<src>`/`<see>`, an embedded `<p>` child stays plain; a non-paren `<p>` pair keeps whatever it wraps non-italic too — a whole marker word inside `<i>` (`<i><p>Гл.</p> <see>зашчапіць</see>.</i>` — Cz) and a bold declension cluster inside `<g>` (`<g><p><b>-поў-пом,</b></p></g>` — Cz `чапы́`) |
| `<b>` | bold text | `<b>С.</b>` inside `<src>`; headword-zone separators like `<hw>акалотам</hw><b>:</b>`; punctuation separators between variant `<hw>`s with their sources: `(<src>Нсл.</src>; <src>Ар.</src>)<b>,</b> <hw>смарга́ць</hw>`, `<hw>ёмшы</hw> <b>?</b>`, `<b>?,</b>` (Jo/S) |
| `<br />` | block separator inside an entry | between senses, between `<d>` blocks |

`<tp>` and `lvl` attributes must NOT be added (the data is stripped of them —
see `dictionary_app/AGENTS.md` → Source Data State).

**`keep-acc` attribute.** `<hw keep-acc="true">` marks a headword whose combining
accents (U+0300/U+0301) are semantically load-bearing: the accents are KEPT —
never `remove_accents`-stripped — for display, result-list identity, search
matching, and `<see>` target resolution. Use it when two spellings differ only by
accent (Cz `ча́паць` vs `чапа́ць`). It is a BOOL attribute of `<hw>` only (not
`<entry>`); see `dictionary_app/AGENTS.md` → Accent-Handling Chain.

**Accent-sensitive `<see>` resolution.** A `<see>` carrying `entry=`/`hw=` is
emitted as a `wordattr:` link and resolved ACCENT-PRESERVINGLY — an accented
target must match exactly (`абора` ≠ `абора́`) — while a text-only
`<see>word</see>` (and any see without attributes) keeps the accent-insensitive
default. Bare cross-references therefore still find any accent variant; only
attribute-pinned sees are strict.

## 4. Entry shapes (canonical)

Every shape below is the BODY of one `<entry>` block; wrap it in `<entry>` /
`</entry>`. The shapes omit the wrapper only to keep them readable. The first
shape shows the full block:

Simple:
```xml
<entry>
•<hw>ґорс</hw><g>-са, м.</g>—<t>выемка … груди, <src>Нсл. 119.</src> декольте. <src>БНсл.</src></t>
</entry>
```

All other shapes show only the body (insert it between `<entry>` and
`</entry>`):

Variant headwords (each its own `<hw>`, per-variant sources before the shared `<g>`):
```xml
•<hw>ґаза́</hw>, <src>Ар.</src> <hw>га́за</hw>, <src>Шсл.</src><g>-зы-зе, ж.</g>—<t>керосин. …
```

Multi-sense:
```xml
•<hw>ґазамэтра</hw><g>-ры-ры, ж.</g> <sense n="1"><n>1.</n> <t>газометр</t>.</sense>
<br />
<sense n="2"><n>2.</n> <t>газовый счётчик</t>.</sense>
```

A single unsensed translation stays at entry level; add `<sense n="1">` only
where the raw prints the numeral. Do not regularize a one-sense entry into a
numbered sense block.

Entry with sub-headwords — main headword in a `•<d>` block, phrasal/family blocks
after `<br />`; `<d>` may also carry its own variant `<hw>`s:
```xml
•<d><hw>ґаз</hw>, <g>ґазу, <st>хим.,</st> м.</g>—<t>газ</t>.</d>
<br />
<d><hw>сьвячэльны ґаз</hw>, <hw>ґаз сьвяціць</hw>—<t>светильный газ</t>.</d>
```

Homonym numeral:
```xml
•<hw>ґен <n>І</n></hw>, <g>ґену, м., <st>биол.</st></g>—<t>ген</t>.
```

Excluded headword variant (indexed only under the plain form; the `excl` variant
stays displayed and finger-pointable but never lists as its own row):
```xml
•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>,—<i>см. под <see>ё</see>.</i>
```

Variant headword plus its own `<g>` and sources, followed by the shared `<g>`
(S `сморгаць`):
```xml
•<hw>сморгаць</hw><g>-аю-аеш-ае</g> (<src>Нсл.</src>; <src>Ар.</src>)<b>,</b> <hw>смарга́ць</hw><g>-а̀ю-а̀еш-а̀е,</g> (<src>Нсл.</src>), <g>несоверш., перех.</g> …
```

Family/derived-form blocks: a `<d>` whose first word is a marker label
(`Уменьш.`, `Соверш.`, `Однкр.`, `Прич.`, `Собир.`, `Отгл. имя сущ.`) placed as
`<g>`, followed by a derived `<hw>` — may sit inside a `<sense>` or at entry level
(A `абагульня́ць`, S `абсморганы`):
```xml
•<hw>абагульня́ць</hw><g>-я̀ю-я̀еш-я̀е, несоверш., перех.</g>—<t>обобщать</t>. <d><g>Соверш.</g> <hw>абагу́льніць</hw><g>-ню-ніш-не</g>—<t>обобщить. <src>МГсл.</src></t></d> <d><g>Прич.</g> <hw>абагу́льнены</hw>.</d> <d><g>Отгл. имя сущ.</g> <hw>абагу́льненьне</hw>.</d>
```

Synonym pointer — the translation slot holds a `<see syn="true">`, never a `<t>`:
```xml
•<hw>чале́шык</hw><g>-ка, м.</g>—<see syn="true">чалесьнік</see>. <src>Растсл.</src>
```

## 5. Spacing and punctuation

- `•` no space before `<hw>` (or `•<d><hw>`).
- `—` em-dash abuts the preceding tag: `</g>—<t>…</t>`, `</ex>—<t>…</t>` (no
  space before `—`). A translation may use `—` as an internal separator:
  `<t>…</t>—<t>…</t>`, `<ex>…</ex>—<t>…</t>`. A crowded proverb whose Russian
  gloss gets its own citation renders with the gloss OUTSIDE the `<ex>`, joined
  by `—` (user-checked Cz `чорт`): `<ex>Чорт на паганага папаў, <st>послов.</st></ex>—<t>нашла коса на камень. <src>Ар.</src>; <src>Іг.</src></t>`.
- `,`/`:`/`;`/`.`/`…` follows `</hw>` directly (no space before it), ordinary
  form: `•<hw>ґастрономны</hw>, <g>-ная-нае</g>—<t>…`; the symbol is auto-absorbed
  into the headword anchor at render time (stays bold) — e.g.
  `•<hw>акалотам</hw>: <ex>…`, the entry-final `.</d>` in
  `<d><g>Прич.</g> <hw>абагу́льнены</hw>.</d>`, and the ellipsis of
  `<d><hw>вычвара́ць</hw>…</d>` (Cz).
  Two duplicate commas `,,` directly after `</hw>` are BOTH absorbed (both stay
  bold) — e.g. `<hw>разьюрыцца</hw>,, <sense …`. A dot is absorbed singly (there
  is no `..` case in the corpus). A comma printed before a `см. под` dash stays
  after `</hw>` and before the dash:
  `<hw>чыніць ласку</hw>,—<i>см. под <see>ласка</see>.</i>` (Cz).
- Square brackets directly abut the preceding/following tag, **optional/redundant**:
  when `[`…`]` enclose only `<hw>` and/or `<src>`/`<st>` (at least one `<hw>`),
  the renderer auto-bolds the brackets even without `<b>` (see
  `dictionary_app/AGENTS.md` → Entry Formatting: Square-bracket bold rule) — e.g.
  `</hw>[<hw>ёлупень</hw>, <src>Варсл.</src>; <src>Бяльсл.</src>]`. Bracket pairs
  around other content render literally.
- Parens directly abut content: `(<hw>галя́с</hw>)` no inner space; a raw `( `
  keeps its space (` ( <hw>гвазьдзікі́</hw>, <src>Нсл.</src>)`).
- Literal `См.`, `Ср.` glosses inside `<i>`; the OCR forms `ем.`, `ер.`, `емь`,
  `ер` are to be read as `См.`/`Ср.`, not transcribed verbatim.
- Period placement follows the raw: `ж.` before the dash `—`.
- Trailing period: when a `<t>` contains no nested tags, the sentence-ending
  period goes AFTER `</t>` — `<t>Юрий, Георгий</t>.` — do not fold it into the
  tag. When `<t>` carries nested tags (`<src>`, `<st>`, …), the period follows
  the raw position. In the `Y` file the sentence-ending period after a closing
  page ref also moves outside: `—<t>… <see>"ых"</see>. <src>Нсл. 722</src></t>. …`
  (the page ref itself takes no inner period; the `;`-joined form is
  `<src>Нсл. 722</src>; <src>Ксл.</src>`). A source carrying its own trailing
  punctuation keeps it inside: `<src>Пск.(Иеропольский).</src>`,
  `<src>Нсл. 75.</src>`.
- `<br />` is the canonical block separator; the equivalent `<br></br>` form also
  occurs in the data (N) and ElementTree treats both identically — either is
  acceptable on input. The separator PRECEDES the block it opens (one `<br />`
  line between two blocks, none after the last block), and the first `<d>` may
  stay on the translation's line separated by one space
  (`…</t> <d><g>Уменьш.</g> …` — Cz `чорны`).

## 6. Grammar and declension

- Declension suffix chains are copied from the raw with OCR fixes (see §9),
  keeping the raw's punctuation: `-нку, на ґанку, м.,`,
  `-ара̀, предл.-ару̀, зват.-а̀ру; мн. ч.-ры̀-роў-ром, предл.-рох, м.`.
- A `<g>` that is only a category marker carries no dash: `<g>местоим.</g>`,
  `<g>нареч.</g>`, `<g>несоверш.</g>`, `<g>соверш.</g>`, `<g>прич.</g>`,
  `<g>отгл. имя сущ.</g>`, `<g>средн.</g>`, `<g>однкр.</g>`, `<g>междомет.</g>`.
- `прилаг. к <see>…</see>`, `однкр. к <see>…</see>`, `соверш. к <see>…</see>` in
  `<g>` use nested `<see>`.
- Declension containing parens: wrap the parens in `<p>` — optional (the renderer
  auto-keeps parens plain inside italic tags; `<p>` is redundant but harmless and
  present in existing data): `<g>-чу<p>(</p>чаю<p>)</p>…`.
- **Per-variant declension with parenthetical sources** (Ch `хлѐў`): variant
  declension forms followed by their own source in parens stay plain via `<p>`
  around the whole cluster; a source-owning punctuation/continuation may be
  bolded: `<g>хлѐву, предл.-вѐ , <p>(<src>Ар.</src>)<b>, хлѐве.</b>(<src>Шсл.</src>),</p> зват. хлѐве; …</g>`.
- **Variant plural stems with their own sources** (Cz `човен`/`чаўны`): each stem
  variant is a nested `<hw>` inside its own declension `<g>`, joined with
  `<b>, </b>`:
  `•<g><hw>човен</hw>-вена, предл. и зват.-вене, мн. ч. човены, <src>(Ар.)</src></g><b>, </b><g><hw>чаўны</hw>-ноў-ном, <src>(НК)</src></g>—<t>…`.
- Declension case forms print lowercase even when raw OCR capitalized them:
  `чарта, предл.-ту̀, зват. чорце; мн. ч. …` (Cz `чорт`), `човены`.
- Grammar markers inside a declension `<g>` are wrapped in `<st>`:
  `<g>м., <st>област.</st></g>` (Cz `чобат`); the raw's
  `увел.`/`прилаг.`/`соверш.` relative labels stay literal words in `<g>`:
  `<g>-гі, увел. от <see>чорт</see></g>`. A standalone family marker keeps the
  capitalized dictionary label (`Соверш.`, `Прич.`, `Отгл. имя сущ.`) even when
  the raw or a draft prints it lowercase.
- **Register markers stay outside the source.** A `<st>` is never moved inside
  the `<src>` that follows it, `перен.`/`ирон.` stand as their own `<st>` beside
  the `<t>`, and a marker qualifying one noun stays inside `<g>`
  (`<g>м., <st>област.</st></g>` — Cz `чобат`). Sense-dash and `<ex>`-tail
  placement are in §3 (`<st>` row).
- **The two combining accents are not interchangeable:** `<hw>` takes the acute
  U+0301, `<g>` (and its declension tails) takes the grave U+0300. One corpus
  exception exists: an italicized derived variant inside `<hw>` keeps the raw's
  grave (`<hw><i>ачулѐць</i></hw>` — Cz). Mixing both marks inside one tag is an
  error even when they render alike.
- **Parenthetical usage note with an embedded proverb** (Ju `юры́ць`): the
  declension's `<g>` may carry a long parenthetical wrapped in `<st>`, and a
  proverb quoted inside is tagged `<ex>` even nested in the `<g>`/`<st>`:
  `<g>юру̀, юры̀ш<st>(ад Юр’я, што бывае 23-га красавіка, калі, з настаньням вясны, статак пачынае чуць сілу, бушаваць подле прыказкі: <ex>Бычкі бушуюць, вясну чуюць.</ex>)</st></g>`.

## 7. Cross-references (`<see>`)

- `См.`/`Ср.` tails: `<i>См. <see>газоўка</see>, <see>газулька</see>.</i>`;
  sense-targeted: `<i>См. <see>зык 3</see>.</i>`, `<see>смаргаць 4</see>`, also
  with a comma before the number: `<i>Ср. <see>юшка, 3</see>.</i>` (Ju юха 2).
- **`Гл.` marker (Cz):** `Гл.` ("look") is a cross-reference marker kept PLAIN
  inside `<i>` via `<p>`: `<i><p>Гл.</p> <see>зашчапіць</see>.</i>` (Cz
  `зашчапіць`); unlike `См.` it is not italicized in the checked data.
- **Synonym pointer — `syn="true"`:** a `<see syn="true">` standing in the
  translation slot is a synonym, not a translation, so it is NEVER wrapped in
  `<t>`: `—<see syn="true">чалесьнік</see>. <src>Растсл.</src>` (Cz `чале́шык`).
  It may follow a real `<t>` gloss after the dash (Cz `чарэн`:
  `…</t> — <see syn="true">чарэнь</see>.`). When the target must stay
  accent-distinct, pin it with `hw=`: `<see hw="часіна́" syn="true">часіна̀</see>`
  (Cz `часіна`).
- **`см. под` (preserve):** when the raw entry reads `см. под X`, KEEP the phrase
  verbatim in the resulting markup — `<i>см. под <see>X</see>.</i>` — do NOT
  rewrite it to `См.` or fold it into a plain `<see>`. Transcription must not drop
  such entries; the user deletes them manually if they prove unnecessary. Kept
  example:
  `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>,—<i>см. под <see>ё</see>.</i>`.
  A redundant stub is never folded or dropped by the transcriber: the user may
  delete it, leaving the word as a `<hw>` variant or `<d>` sub-headword of the
  target (`ёлупень` in `ёлапень`, `чува́ць` in `чуць`).
- Two `См.` sets same entry:
  `<i>См. <see>грункач</see>, <see>ґруґан</see>, <see>крумкач</see>.</i>`.
- In `<g>`: `прилаг. к <see>ґімназя</see>`, `увел. от <see>чорт</see>` (Cz),
  `соверш. к <see>чахці</see>, 1` (Cz) — sense targets use Arabic numerals even
  when the raw prints Roman `І`; in `<t>` glosses with explicit target:
  `<t>… <see hw="ґіль">"ґілёў"</see> —овадов, …`; `<see hw="плаксу́ха">-уха</see>`.
  A quoted word may be a plain quoted `<see>` without `hw`:
  `—<t>… говоря: <see>"ых"</see> …` (Y `ы́хаць`).
- Homonym cross-refs carry the numeral inside `<see>`:
  `<i>См. <see>грыжа <n>ІІ</n>, 1, 2</see>.</i>` (H),
  `собир. к <see>брус 1, 2, 3, 4</see>` (B).
- `<see>` headword spelling must match the linked entry's headword (accents
  allowed; normalization is accent-stripped). When the raw's cross-ref is
  OCR-mangled, normalize it back to the dictionary's headword spelling
  (e.g. `Кажа-мЯКа` → `кажамяка`). When the printed label is an archaic or
  line-broken form, keep it as the visible `<see>` text and pin the real target
  with `hw=`: `<i>см. под <see hw="прырачэньне">прырачэнье</see>.</i>` (Cz).

## 8. Homonyms and disambiguating IDs

- **Homonym numerals** (`гале́ра І`, `ґале́ра ІІ`, `ґен І`, `ґен ІІ`): the numeral
  is marked up as `<n>І</n>` INSIDE `<hw>`: `<hw>гале́ра <n>І</n></hw>`. Indexing
  strips the `<n>` content (see `dictionary_app/AGENTS.md` → Collation Rules), and
  distinct entries keep stable file order.
- **Distinct lexemes that share the same plain headword** (homographs) get a
  unique `id` on the `<entry>`, named after the printed page and the element's
  order on it: `<entry id="абора_p5_1">`, `<entry id="абора_p5_2">` (page 5,
  first and second colliding entry; see `dictionary_A.xml`). Sub-headword
  anchors carry `<hw id="…">`; cross-references use
  `<see entry="ID">TEXT</see>` or, to pin a sub-headword,
  `<see entry="ID" hw="H">TEXT</see>`. There is NO `link` attribute and NO
  `#`-fragment scheme — both are removed; do not reintroduce them (see
  `dictionary_app/AGENTS.md` → Word-URL forms). The older
  `абора_бечевка` / `абора_хлев` names were an early experiment, not the
  convention: they appear nowhere in the corpus and must not be used.
- Plain headwords that collide within one file get a unique `id` on each
  colliding `<entry>` (`абора` ×2 in `dictionary_A.xml`). Distinct lexemes that
  share a spelling and a file but lack a unique id would collide on lookup —
  that is why every such pair gets an `id`.

## 9. OCR transcription rules (raw → XML)

- **High-confidence letter fixes** where the raw is unambiguously a known word:
  `светйль-ный`→`светильный`, `р)’-рыш`→`ру-рыш`, `повел,`→`повел.`, `ж„`→`ж.,`,
  `мш ч.`→`мн. ч.`, `ХоЧуць`→`хочуць`, `Ґа-Ґа-Ґа`→`ґа-ґа-ґа`, `2З-га`→`23-га`
  (OCR reads the digit 3 as Cyrillic З — Ju `юры́ць`), `прыказг.`→`прыказкі:`,
  `чуюцы`→`чуюць`, `проказы-вать`→`проказывать`, `КрОВЬ`→`кровь`,
  `гЛедЗяЧЫ`→`гледзячы`, `а Мне`→`мне`, `Наем,`→`Насм.,`
  (`Наем, пословица`→`Насм. пословица`), `лри`→`при` (Cz `ча`:
  `лри вопросе`→`при вопросе`). **`Пе`/`Пя`→`Ня`** in Cz examples where the
  negation `ня` was misprinted with `п` (`Пе чакай`→`Ня чакай`, `Пя відна`→`Ня відна`,
  `Пя чадзь`→`Ня чадзь`) — unmistakable by meaning; flag it if the user might
  disagree. The reverse misprint also occurs — a printed `Н` standing for `П`:
  `Навесь`→`Павесь`, `Надружкі`→`Падружкі`, `Наеду`→`Паеду` (Cz example text).
  Fix the letter only where the printed word is not a real form: never "improve"
  a plainly printed word (`нчараваў` stays). Digit OCR: `Но. 20, б.`→`Но. 20, 6.`
  (the letter `б` standing for the digit `6` in issue refs — Cz `чарцю́га`
  example). Do NOT "fix" words that could be deliberate
  (e.g. `Ґімназы̀сцкая хорма.` keeps `хорма`).
- **Declension tail OCR fixes** (raw base+suffix tails mangled):
  `«-ншы-нце»`→`-нты-нце`, `ґазаме́р-ера`→`-ѐра, предл.-ѐру`,
  `ґенара́ліха-іхі-ісв`→`-іхі-ісе`, `ґраната-алны-ацв`→`-ты-це`,
  `ґеохіма-йы-.йе`→`-мы-ме`, `ґу́лта-лна`→`-та`, `ґімназы́сты-лнага`→`-тага`,
  `ґеоґра́фка-$кі-$цы`→`-фкі-фцы`, `-н/, ж.`→`-ні, ж.` (Ju `юра́нь`).
  Cz: `ча́хнуць-нг-нсш-не`→`-ну-неш-не`, `чака́ць-аю-аеін-ав`→`-аю-аеш-ае`,
  `чаборавы-вая-вав`→`-вая-вае`, `адча́хацца-аюся-авшся`→`-аюся-аешся`,
  `чаўны-ноў-нолі`→`-ноў-ном`, `чарапе́нь-йня`→`-пня̀`, `чапуру́ха-ўхі`→`-у̀хі`,
  `частава́ць-сую`→`-тую`, `чацьве́рты-днага`→`-тага`,
  `чацьвярта́к-ака`→`-така̀`, `часаме́р-ду`→`-ру`,
  `чаркава́цца-куюся`→`-ку̀ся`.
- **Headword fixes**: `ґейззр`→`ґейзэр`, `ґа́мл`→`ґа́ма` (ґама has declension
  `-мы-ме`), `ґе́мзазы`→`ґе́мза`; OCR headword corruptions proven by the
  dictionary's own example sentences: `кітрань`→`ю́трань`, `кішна`→`ю́шна`
  (Ju — the examples `на ютрань` и `будзе табе і рыбна і юшна` fix the spelling);
  `чооат`→`чобат` (Cz — user-confirmed against the gloss `сапог`).
- **г/ґ restoration**: OCR frequently drops the ґ's descender, printing `ґ` as
  `г` (`го́нта`→`ґонта`, `гілёс`→`ґілёс`). Restore `ґ` when the surrounding print
  order or the word family confirms it (this file sorts `ґ` between `г` and `д`,
  and family members in the same entry are printed `ґ`). Otherwise keep the raw's
  printed letter: `ге́мзавы` kept `г` while its phrase `ґе́мзавыя чаравікі` kept
  `ґ` — do not mass-normalize.
- **Keep raw fragments verbatim when unknowable**: `супраціпаўзьнява́я`,
  `раськяпі`, `состоянме`, `-нв` declensions past `-не`, etc. Never invent
  content; if a fragment is genuinely unreadable, transcribe it and flag it for
  the user.
- **Unreadable translation printed as dots** stays as printed inside `<t>`:
  Ju `разью́шавацца`
  `<g>-шуюся-шуешся. <src>Нсл.</src></g>—<t>.....</t>` — the illegible Russian
  gloss keeps its dot run (`—.. ...` in the raw).
- **Case-mangling fixes** are allowed in `<hw>`/`<ex>` where OCR produced random
  capitals (`Ґа-Ґа-Ґа`, `ХоЧуць`, `аўЧЫньнік`→`аўчыньнік`, `Рох`→`рох`,
  `мЯКа`→`мяка`); but never change legitimate sentence-initial capitals.
- **Implicit source refs** like `Нсл. 119.` (page numbers) stay INSIDE `<src>`:
  `<src>Нсл. 119.</src>`; the trailing `.` follows the raw. When a page ref closes
  a `<t>`, the sentence-final period may instead be placed after `</t>`
  (Y `ы́хаць`/`ыт` — see §9).
- **Keep the printed punctuation before an embedded `<src>`.** A `.` in
  `<t>черноглазый. <src>ЗСД 213</src></t>` stays a period — never rewrite it as
  a `,` and never move it into/out of the source. `tools/fix_tag_punctuation.py`
  lists every tag pair whose closing tag is immediately followed by punctuation,
  shows the pair before and after moving that punctuation inside the closing tag,
  and lets you skip, accept, or type a replacement. The list is exhaustive, so
  skip an `<hw>`/`<see>` candidate whose punctuation must stay outside the
  headword or link target. `tools/search_xml.py` searches every dictionary `*.xml`
  recursively, since Explorer cannot search several files at once.
- **Source abbreviations**: never "correct" `Гсл.`, `Ксл.` etc. into `Гел.`,
  `Кел.` etc.; the reverse normalization IS expected instead (`Гел.` → `Гсл.`,
  `Кел.` → `Ксл.`). Same for `Шел.`→`Шсл.` (Y `ых`) and `Бясл.`→`Бяльсл.`.
- **`С.` as a source**: in most cases `С.` is NOT marked `<src>С.</src>` but
  `<src><b>С.</b></src>` (the single-letter source is bolded, as in the `<src>`
  row of §3).
- **Reference markers `ем.`/`ер.` → `См.`/`Ср.`** and drop the raw's mangled
  cross-ref casing.
- **Accent marks**: combining accents U+0300 (grave) / U+0301 (acute) are
  preserved as in the raw (`ґа́ґаць`, `да̀ўна`, `ґе́мза`, `ґіля̀`); which tag takes
  which mark is fixed in §6 (`<hw>` acute, `<g>` grave). Restore the
  word's known-stress accent on a headword or split declension base even when the
  raw collation print omitted it (Ju `ю́хта`, `ю́шка <n>ІІ</n>`, `ю́шна`,
  `ю́трань`, `ю́траня`; `ґазаме́р-ера`→`-ѐра`; Cz `чарцю́га`). Do not guess accents
  the raw gives no evidence for — in Cz example text a stray grave was dropped
  (`дзя̀ўчына`→`дзяўчына`).

## 10. Practices that speed markup up

- **One chunk at a time, one entry at a time.** Read a screen of raw, mark it up
  fully, append it, self-check, continue. Do not hold a whole letter in context.
- **Read only the raw chunk + the XML tail.** `rg` in the raw file for the last
  marked-up headword, then read forward. Re-reading finished XML is wasted work.
  A block missed earlier is only recoverable by appending it at the END, never
  by inserting it where it seems to belong.
- **Locate with the comparison tool, read only what it flags.**
  `py -3 tools/compare_raw_markup.py --coverage` gives the untranscribed raw
  blocks, the blocks skipped inside the covered range, and any entry that broke
  print order; `--conventions` gives the per-file tag/accent/attribute census.
  Read the flagged entries, not the whole letter. Coverage aligns `•`-led blocks
  only: a `^`-led headword surfaces as an unmatched XML entry (`best 0.00`), and
  a user-deleted `см. под` stub surfaces as `skipped raw` (§1, §7). A positive
  `remaining` count is a missing entry (Z `зырчэць`), not a formatting quirk.
  Treat all three as findings to read.
- **Reuse the shapes.** Most entries are one of the §4 shapes; copy the closest
  shape and substitute the text instead of composing tags from scratch.
- **Use the existing entries as the template library.** When a construction is
  unfamiliar (a family block, a per-variant declension), search the corpus for a
  similar printed pattern (`rg` the marker word, e.g. `Соверш.`) and mirror its
  markup.
- **Fix OCR with the rule list, not by feel.** Scan the §9 list for the patterns
  first; only then judge letter-by-letter. Same for `г`/`ґ` (§9 family rule).
- **Batch the write, not the thinking.** Prepare several entries, then append
  them in one `write`/`edit` call; do not round-trip per entry.
- **Never run the dictionary app or rebuild the database mid-markup.** Validation
  is a parse check (§11); the DB rebuilds itself when the app starts.
- **Do not resolve `<src>` abbreviations** while marking up — transcribe as
  printed (normalizing only per §9). Resolving every abbreviation costs too much
  time and is not part of transcription.
- **Stop and ask on genuine ambiguity** (illegible fragments, `Пе`/`Пя`, a
  possible new tag/attribute). Transcription must not guess silently.

## 11. Self-checks (per chunk, before moving on)

1. **Parses.** The chunk must parse with `xml.etree.ElementTree` (the markup
   editor and `dictionary_app.db.build_database` rely on it). A quick probe:
   `py -3 -c "import xml.etree.ElementTree as ET; ET.parse(r'dictionary_app/data/dictionary/dictionary_X.xml')"`.
2. **Every headword marker accounted for.** Count `•` and leading `^` (§1) in the
   raw chunk and the new `<entry>` blocks; none missing, none duplicated.
3. **Print order preserved.** Existing `<entry>` blocks are untouched — never
   moved, re-sorted, or re-inserted; new entries are appended at the end in raw
   order; no alphabetical sorting, including within one merged raw line (§1).
   `py -3 tools/compare_raw_markup.py --coverage` flags a re-ordered pair as one
   unmatched XML entry (with an `order-hint`) plus the skipped raw block.
4. **No content dropped.** Every raw sentence appears somewhere in the entry —
   including `см. под` entries, unreadable dot runs, and uncertain fragments.
5. **Tags balanced and nested correctly.** `<hw>` inside `<hw>` only when the raw
   really nests it; no crossed pairs; `<br />` self-closed.
6. **Structural separators.** `<sense>`/`<d>` blocks separated by `<br />` (the
   separator precedes each block, none trails the last one, no block packed onto
   one line); `<sense>` appears only where the raw prints its numeral (§4); every
   headword is one `<entry>`…`</entry>` block; entry blocks separated by a blank
   line.
7. **Identity.** Homonym numerals inside `<hw>`; every colliding plain headword
   has a unique `<entry id>`; `<see>` targets spell the real headword.
8. **Spacing.** `•` abuts `<hw>`; `—` abuts the preceding tag; `,`/`:`/`;`/`.`
   follow `</hw>` directly; no stray space inside tags.
9. **Attributes.** Only schema attributes (`entry:id`, `hw:id,excl,keep-acc`,
   `g:hw`, `see:entry,hw,syn`, `sense:n`, `ex:lang`, `i:lang,excl`, `p:lang`,
   `lang:code`) — no `tp`, no `lvl`, no `link`, no `#` fragments.
10. **Source runs merged.** A run printed together is ONE `<src>`
    (`<src>Ар.; Ксл.; Шсл.</src>`), never one tag per abbreviation; a
    parenthesized run keeps its parens inside the tag.
11. **Accent mark matches the tag.** `<hw>` carries U+0301, `<g>` carries U+0300
    (§6); an italicized derived `<hw>` may keep the raw grave (§6); no tag mixes
    both, no accent was silently dropped.
12. **Encoding.** UTF-8, Cyrillic intact, combining accents preserved.
13. **Printed `<hw>`/`<g>` order.** When `<hw>` and `<g>` are adjacent, keep
    the raw order — normally `<hw>word</hw><g>morphology</g>`; a grammar label
    before a derived headword (`<g>Соверш.</g> <hw>…</hw>`) stays only where the
    raw prints it. Never flip the pair.
14. **Do not hallucinate.** Never add a `<src>`, `<g>`, `<t>`, `<ex>`, or `<hw>`
    the raw does not contain; a source belongs only to the example it follows,
    never copied from the previous one. When unsure, transcribe only what is
    printed.

## 12. Failure modes (what goes wrong and how to avoid it)

| failure | cause | avoidance |
|---|---|---|
| A headword silently vanishes | a `•` inside a merged raw line was treated as punctuation | split at every `•`; check the bullet count (§11, item 2) |
| An entry exists twice | the same raw block was appended twice after a context reset | track the last written headword; read the XML tail before appending |
| File ends up alphabetized or reordered | "tidying" the file, or inserting a new entry in the middle | never sort or move blocks; print order is the invariant; append at the end |
| An entry sits next to the wrong neighbour | a two-bullet raw line was split alphabetically, or a missed block was inserted where it "belongs" | split left to right (§1); append missed blocks at the end; run the coverage check (§11, item 3) |
| Cross-refs point nowhere | `<see>` uses the raw's OCR spelling | normalize to the real headword; check with the broken-links filter in the markup app |
| Homonyms collapse into one row | numeral printed outside `<hw>`, or no `<entry id>` on a colliding pair | numeral inside `<hw>`; unique `id` per colliding lexeme |
| Italic leaks into parens/markers | relying on `<p>` only, or adding bold by hand | let the renderer handle parens/brackets; do not hand-add `<span>`/styles |
| Data lost behind "cleanup" | "fixing" a word that was deliberately printed that way | §9: fix only proven OCR; keep unknowable fragments verbatim |
| XML fails to parse | unclosed/misnested tag, unescaped `&`/`<` in text | parse check after each chunk; escape literal `&`/`<` |
| Extra history noise in git | rewriting already-checked entries | append new work only; do not reformat finished blocks |
| A source run explodes into many `<src>` tags | each abbreviation was copied as its own tag | keep the printed run inside ONE `<src>`; check §11, item 10 |
| A synonym renders as a translation | `<see syn="true">` was wrapped in `<t>` | a synonym pointer stands bare in the translation slot (§7) |
| Two blocks render as one paragraph | `</t> <d>` or `</sense> <sense>` without the separator | `<br />` before each block, none after the last (§5) |
| A Latin name renders italic | taxonomic name put in `<i>` | `<lang code="la">…</lang>` inherits the surrounding style (§3) |
| A tag is invented or its order flipped | the source/label was inferred from a neighbour instead of read from the raw | keep the printed order; add no `<src>`/`<g>`/`<t>`/`<ex>`/`<hw>` the raw lacks (§11, items 13–14) |
| A caret-led headword is skipped | only `•` was counted as a bullet | treat leading `^` as a bullet; coverage reports its XML entry as unmatched with `best 0.00` (§1, §10) |
| A bullet after a continuation sense is absorbed | the block was read as one sense | split at every `•` even after `2. …`; coverage `remaining` flags the missing entry (§1, §10) |
| A redundant `см. под` stub is mishandled | the draft re-created it as its own `<entry>` or dropped it | transcribe it verbatim as its own entry; let the user delete it (§7) |
| An unsensed entry gets `<sense n="1">` | the draft regularized the structure | add `<sense>` only where the raw prints the numeral (§4, §11, item 6) |
| A cross-ref label is rewritten or left unpinned | the draft copied the raw spelling into `<see>` without `hw=` | keep the printed label and pin the real headword with `hw=` (§7) |

## 13. Verification and commit

- Parse check per chunk (§11, item 1); the full-file parse happens when the app starts.
- Output must stay loadable by both apps: the markup editor and
  `dictionary_app.db.build_database` parse the same `<entry>` blocks.
- **Do not** validate every `<src>` against `dictionary_app/data/source_mappings.json`
  / `sources.xml` while marking up — transcribe sources verbatim as printed
  (normalizing only per §9).
- **Commit rule:** before every commit, ask the user which files/portions of the
  dictionary XMLs have been checked, and report only the checked range.
