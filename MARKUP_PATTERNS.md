# Dictionary Markup Patterns

Single source of truth for the **lexicographic XML markup** used in `data/dictionary/dictionary_*.xml`, distilled from `dictionary_G.xml` (130 entries) and reassessed against all 12 letter files (`A`, `B`, `Ch`, `D`, `DZ`, `G`, `H`, `Jo`, `N`, `P`, `S`, `Z` — 218 entries total).

Scope: how RAW OCR text (`raw_data/*_raw.txt`) is converted to marked-up XML. App behavior (rendering, search, build, collation, `tp`/`lvl` state) is in `AGENTS.md`; the markup editor is in `AGENTS_markup.md`. Do NOT restate those facts here — cross-reference instead.

## 1. File structure

- Root is `<dictionary>`; one `<entry>…</entry>` per printed dictionary headword, at column 0, blank line between entries.
- Files keep the **raw print order** (anchored to the `_raw.txt`), never alphabetized (see AGENTS.md → Source Data State).
- One `•` bullet per `<entry>`, directly before the main `<hw>` (no space): `•<hw>…`.
- Split merged raw rows into separate `<entry>` blocks: the raw frequently joins 2–3 headwords on one line with `,` (e.g. `•ґазалі́на-…, •ґазамэтра-…`), and also merges a related sub-word (`•ґарсэт, … •ґарсэтніца, …`). Each `•`-led headword becomes its own `<entry>`.
- Within an entry, multi-part content (senses, sub-headwords, phrasal headwords) is wrapped in `<sense>`/`<d>` blocks separated by `<br />`.

## 2. Tag reference

| tag | role | notes |
|---|---|---|
| `<hw>` | headword (bold, clickable anchor) | one per spelling variant; multi-word headwords like `ґазавая ґрана́та`; homonym numerals nested: `<hw>гале́ра <n>ІІ</n></hw>`; disambiguation links see §7; `excl="true"` marks a display-only variant that is kept out of the entry list and all logic except display + the pointing-finger (`👉`), e.g. `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>` (see AGENTS.md → `<hw excl="true">`) |
| `<g>` | grammar/declension, italic | declension starts with `-`: `-са, м.`; standalone markers: `нареч.`, `местоим.`, `союз`, `соверш.`, `несоверш.`, `безлич.`, `однкр.`, `средн.`, `прич.`, `отгл. имя сущ.`; may embed `<st>`, `<see>`, `<p>`, `<src>`, even `<hw>` (`один <hw>ґалёш</hw>`) |
| `<t>` | Russian translation (can also appear nested INSIDE an `<ex>` for a Russian gloss of a proverb/idiom — H `гарох`: `<ex>Хадзі̀ма ў гарох <t>(знач. щипать горох)</t>. <src>Ст.</src></ex>`) | transcription, multiple `<t>` per sense allowed; sources and `—` separators inside |
| `<ex>` | Belarusian example, italic, srcless or `<src>`-tagged | may embed a Russian `<t>` gloss and/or `<st>Послов.</st>` (H `гарох`: `Ідзе гарох, там сем дарог. <st>Послов.</st>, <t>о частом щипании гороха</t>. <src>Дсл.</src>`) |
| `<src>` | source, becomes link | `Ар.`, `Гсл.`, `Нсл. 119.`, `Стаішча Чаш. (Ксл.)`, long bibliographic refs stay whole (`Азбукін: Ґеоґрафія Эўропы, 1924`); single-letter `С.` bolded as `<src><b>С.</b></src>` |
| `<st>` | register/style marker, italic, linkable | `хим.`, `биол.`, `рел.`, `муз.`, `ист. мор.`, `област.`, `перен.`, `Послов.`; may attach case (`послов.`) |
| `<i>` | italic gloss container | `См. …`/`Ср. …` cross-reference tails, other gloss notes; `lang="vl"` marks a Belarusian-language quoted word/fragment inside a Russian `<t>` gloss (`<i lang="vl">"не"</i>` — N, Jo), `excl="true"` keeps a quoted fragment out of the translation/content index (`<i excl="true">"а (я)"</i>` — N); both render italic |
| `<see>` | cross-reference, italic | inside `<i>`, `<g>`, or `<t>` glosses (see §6) |
| `<sense n="…">` | numbered/lettered sense block | `<n>1.</n>` numeric or `<n>а)</n>` lettered; `<br />` between senses |
| `<n>` | sense number AND homonym numeral | `<n>1.</n>`, `<n>2.</n>`, `<n>а)</n>`, homonym `<hw>… <n>ІІ</n></hw>` |
| `<d>` | sub-dictionary block with own `<hw>` | phrasal sub-headwords and morphological family blocks; separated by `<br />`; may nest inside a `<sense>` OR contain its own lettered/numbered `<sense>` blocks (see §5, S `вы́смаргнуць`/`абсморганы`) |
| `<p>` | literal parens inside declension/headword strings | keeps `(`/`)` out of italic side effects: `<g>-чу<p>(</p>чаю<p>)</p>…` — **optional/redundant**: the renderer now auto-keeps parens non-italic inside `<g>`/`<i>`/`<ex>`/`<st>`/`<see>` even without `<p>` (see AGENTS.md → Entry Formatting: Paren rule). Take-over from raw print stays verbatim: bare parens in italic tags render plain automatically. Also used to mark a variant spelling's `г` as plain inside a bold `<hw>` (`<hw>-…</hw>`… `<hw><p>гірса</p></hw><p>,</p>` — G `ґірса`, where `гирса` is the г-spelled variant; treats the letter as non-bold like parens) |
| `<b>` | bold text | `<b>С.</b>` inside `<src>`; headword-zone separators like `<hw>акалотам</hw><b>:</b>`; punctuation separators between variant `<hw>`s with their sources: `(<src>Нсл.</src>; <src>Ар.</src>)<b>,</b> <hw>смарга́ць</hw>`, `<hw>ёмшы</hw> <b>?</b>`, `<b>?,</b>` (Jo/S) |
| `<br />` | block separator inside an entry | between senses, between `<d>` blocks |

`<tp>` and `lvl` attributes must NOT be added (data is stripped of them — AGENTS.md → Source Data State).

## 3. Entry shapes (canonical)

Simple:
```xml
•<hw>ґорс</hw><g>-са, м.</g>—<t>выемка … груди, <src>Нсл. 119.</src> декольте. <src>БНсл.</src></t>
```

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

Entry with sub-headwords — main headword in a `•<d>` block, phrasal/family blocks after `<br />`; `<d>` may also carry its own variant `<hw>`s:
```xml
•<d><hw>ґаз</hw>, <g>ґазу, <st>хим.,</st> м.</g>—<t>газ</t>.</d>
<br />
<d><hw>сьвячэльны ґаз</hw>, <hw>ґаз сьвяціць</hw>—<t>светильный газ</t>.</d>
```

Homonym numeral:
```xml
•<hw>ґен <n>І</n></hw>, <g>ґену, м., <st>биол.</st></g>—<t>ген</t>.
```

Excluded headword variant (indexed only under the plain form; the `excl` variant stays displayed and finger-pointable but never lists as its own row):
```xml
•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>,—<i>см. под <see>ё</see>.</i>
```

Variant headword plus its own `<g>` and sources, followed by the shared `<g>` (S `сморгаць`):
```xml
•<hw>сморгаць</hw><g>-аю-аеш-ае</g> (<src>Нсл.</src>; <src>Ар.</src>)<b>,</b> <hw>смарга́ць</hw><g>-а̀ю-а̀еш-а̀е,</g> (<src>Нсл.</src>), <g>несоверш., перех.</g> …
```

Family/derived-form blocks: a `<d>` whose first word is a marker label (`Уменьш.`, `Соверш.`, `Однкр.`, `Прич.`, `Собир.`, `Отгл. имя сущ.`) placed as `<g>`, followed by a derived `<hw>` — may sit inside a `<sense>` or at entry level (A `абагульня́ць`, S `абсморганы`):
```xml
•<hw>абагульня́ць</hw><g>-я̀ю-я̀еш-я̀е, несоверш., перех.</g>—<t>обобщать</t>. <d><g>Соверш.</g> <hw>абагу́льніць</hw><g>-ню-ніш-не</g>—<t>обобщить. <src>МГсл.</src></t></d> <d><g>Прич.</g> <hw>абагу́льнены</hw>.</d> <d><g>Отгл. имя сущ.</g> <hw>абагу́льненьне</hw>.</d>
```

## 4. Spacing and punctuation conventions

- `•` no space before `<hw>` (or `•<d><hw>`).
- `—` em-dash abuts the preceding tag: `</g>—<t>…</t>`, `</ex>—<t>…</t>` (no space before `—`). A translation may use `—` as an internal separator: `<t>…</t>—<t>…</t>`, `<ex>…</ex>—<t>…</t>`.
- `,`/`:`/`;` follows `</hw>` directly (no space before it), ordinary form: `•<hw>ґастрономны</hw>, <g>-ная-нае</g>—<t>…`; the symbol is auto-absorbed into the headword anchor at render time (stays bold) — e.g. `•<hw>акалотам</hw>: <ex>…`.
- Square brackets directly abut the preceding/following tag, **optional/redundant**: when `[`…`]` enclose only `<hw>` and/or `<src>`/`<st>` (at least one `<hw>`), the renderer auto-bolds the brackets even without `<b>` (see AGENTS.md  Entry Formatting: Square-bracket bold rule) — e.g. `</hw>[<hw>ёлупень</hw>, <src>Варсл.</src>; <src>Бяльсл.</src>]`. Bracket pairs around other content render literally.
- Parens directly abut content: `(<hw>галя́с</hw>)` no inner space; a raw `( ` keeps its space (` ( <hw>гвазьдзікі́</hw>, <src>Нсл.</src>)`).
- Literal `См.`, `Ср.` glosses inside `<i>`; the OCR forms `ем.`, `ер.`, `емь`, `ер` are to be read as `См.`/`Ср.`, not transcribed verbatim.
- Period placement follows the raw: `ж.` before the dash `—`.
- `<br />` is the canonical block separator; the equivalent `<br></br>` form also occurs in the data (A, N) and ElementTree treats both identically — either is acceptable on input.

## 5. Grammar and declension conventions

- Declension suffix chains are copied from the raw with OCR fixes (see §8), keeping the raw's punctuation: `-нку, на ґанку, м.,`, `-ара̀, предл.-ару̀, зват.-а̀ру; мн. ч.-ры̀-роў-ром, предл.-рох, м.`.
- A `<g>` that is only a category marker carries no dash: `<g>местоим.</g>`, `<g>нареч.</g>`, `<g>несоверш.</g>`, `<g>соверш.</g>`, `<g>прич.</g>`, `<g>отгл. имя сущ.</g>`, `<g>средн.</g>`, `<g>однкр.</g>`.
- `прилаг. к <see>…</see>`, `однкр. к <see>…</see>`, `соверш. к <see>…</see>` in `<g>` use nested `<see>`.
- Declension containing parens: wrap the parens in `<p>` — optional (renderer auto-keeps parens plain inside italic tags; `<p>` is redundant but harmless and present in existing data): `<g>-чу<p>(</p>чаю<p>)</p>…`.
- **Per-variant declension with parenthetical sources** (Ch `хлѐў`): variant declension forms followed by their own source in parens stay plain via `<p>` around the whole cluster; a source-owning punctuation/continuation may be bolded: `<g>хлѐву, предл.-вѐ , <p>(<src>Ар.</src>)<b>, хлѐве.</b>(<src>Шсл.</src>),</p> зват. хлѐве; …</g>`.

## 6. Cross-references (`<see>`)

- `См.`/`Ср.` tails: `<i>См. <see>газоўка</see>, <see>газулька</see>.</i>`; sense-targeted: `<i>См. <see>зык 3</see>.</i>`, `<see>смаргаць 4</see>`.
- **`см. под` (preserve):** when the raw entry reads `см. под X`, KEEP the phrase verbatim in the resulting markup — `<i>см. под <see>X</see>.</i>` — do NOT rewrite it to `См.` or fold it into a plain `<see>`. Transcription must not drop such entries; the user deletes them manually if they prove unnecessary (see the `ёлупень`→`см. под ёлапень` example, which was removed by hand). Kept example: `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>,—<i>см. под <see>ё</see>.</i>`.
- Two `См.` sets same entry: `<i>См. <see>грункач</see>, <see>ґруґан</see>, <see>крумкач</see>.</i>`.
- In `<g>`: `прилаг. к <see>ґімназя</see>`; in `<t>` glosses with explicit target: `<t>… <see hw="ґіль">"ґілёў"</see> —овадов, …`; `<see hw="плаксу́ха">-уха</see>`.
- Homonym cross-refs carry the numeral inside `<see>`: `<i>См. <see>грыжа <n>ІІ</n>, 1, 2</see>.</i>` (H), `собир. к <see>брус 1, 2, 3, 4</see>` (B).
- `<see>` headword spelling must match the linked entry's headword (accents allowed; normalization is accent-stripped). When the raw's cross-ref is OCR-mangled, normalize it back to the dictionary's headword spelling (e.g. `Кажа-мЯКа` → `кажамяка`).

## 7. Homonyms and `link` attributes

- **Homonym numerals** (`гале́ра І`, `ґале́ра ІІ`, `ґен І`, `ґен ІІ`): the numeral is marked-up as `<n>І</n>` INSIDE `<hw>`: `<hw>гале́ра <n>І</n></hw>`. No `link` attribute is needed — indexing strips the `<n>` content (AGENTS.md → Collation Rules), and distinct entries keep stable file order.
- **Distinct lexemes that share the same plain headword** (homographs) get a `link` on the `<entry>` and/or `<hw>`/`<see>`: `абора` → `<entry link="абора_бечевка">` and `<entry link="абора_хлев">`, sub-forms `<hw link="абора_бечевка#аборына">`, cross-refs `<see link="абора_бечевка#аборка">` (see dictionary_A.xml).
- Same-file homograph pairs are the ONLY plain-headword collision found in the corpus (`абора` ×2 in dictionary_A.xml, resolved with `link`). Distinct lexemes that share a spelling AND a file but are NOT linked would collide on lookup — that is why every such pair gets `link` (see previous bullet).

## 8. OCR transcription rules (raw → XML)

- **High-confidence letter fixes** where the raw is unambiguously a known word: `светйль-ный`→`светильный`, `р)’-рыш`→`ру-рыш`, `повел,`→`повел.`, `ж„`→`ж.,`, `мш ч.`→`мн. ч.`, `ХоЧуць`→`хочуць`, `Ґа-Ґа-Ґа`→`ґа-ґа-ґа`. Do NOT "fix" words that could be deliberate (e.g. `Ґімназы̀сцкая хорма.` keeps `хорма`).
- **Declension tail OCR fixes** (raw base+suffix tails mangled): `«-ншы-нце»`→`-нты-нце`, `ґазаме́р-ера`→`-ѐра, предл.-ѐру`, `ґенара́ліха-іхі-ісв`→`-іхі-ісе`, `ґраната-алны-ацв`→`-ты-це`, `ґеохіма-йы-.йе`→`-мы-ме`, `ґу́лта-лна`→`-та`, `ґімназы́сты-лнага`→`-тага`, `ґеоґра́фка-$кі-$цы`→`-фкі-фцы`.
- **Headword fixes**: `ґейззр`→`ґейзэр`, `ґа́мл`→`ґа́ма` (ґама has declension `-мы-ме`), `ґе́мзазы`→`ґе́мза`.
- **г/ґ restoration**: OCR frequently drops the ґ's descender, printing `ґ` as `г` (`го́нта`→`ґонта`, `гілёс`→`ґілёс`). Restore `ґ` when the surrounding print order or the word family confirms it (this file sorts `ґ` between `г` and `д`, and family members in the same entry are printed `ґ`). Otherwise keep the raw's printed letter: `ге́мзавы` kept `г` while its phrase `ґе́мзавыя чаравікі` kept `ґ` — do not mass-normalize.
- **Keep raw fragments verbatim when unknowable**: `супраціпаўзьнява́я`, `раськяпі`, `состоянме`, `-нв` declensions past `-не`, etc. Never invent content; if a fragment is genuinely unreadable, transcribe it and flag for the user.
- **Case-mangling fixes** are allowed in `<hw>`/`<ex>` where OCR produced random capitals (`Ґа-Ґа-Ґа`, `ХоЧуць`, `аўЧЫньнік`→`аўчыньнік`, `Рох`→`рох`, `мЯКа`→`мяка`); but never change legitimate sentence-initial capitals.
- **Implicit source refs** like `Нсл. 119.` (page numbers) stay INSIDE `<src>`: `<src>Нсл. 119.</src>`; the trailing `.` follows the raw.
- **Reference markers `ем.`/`ер.` → `См.`/`Ср.`** and drop the raw's mangled cross-ref casing.
- **Accent marks**: combining accents U+0300 (grave) / U+0301 (acute) are preserved as in the raw (`ґа́ґаць`, `да̀ўна`, `ґе́мза`, `ґіля̀`). Do not add accents unless the raw has them — exception: aligning an accent onto a split declension base (`ґазаме́р-ера`→`-ѐра`).

## 9. Remaining-uncertain G spots (kept verbatim / flagged)

- `супраціпа́нцырная ґраната`, `супраціпаўзьнява́я ґраната` kept as raw (`супраці-` prefixes are OCR-dubious).
- `ґенера́тар` translation `генерптор` kept (Russian `генератор` was OCR-mangled; left as-is; user-verified).
- `ґу́лта` (постель свиньи …) kept as headword, `<g>-та, ср.</g>`.
- `гімна…` family: `ґімназы́сты|-тага, сущ., м.`; `ґімназы́стая|-ае, сущ., ж.`.
- `состоянме` in `ґілёс` sense 2 kept verbatim (Russian typo in source).

## 10. Verification

- Output must parse with `xml.etree.ElementTree` (the markup editor and `db.build_database` rely on it).
- Every `<src>` abbreviation should resolve against `data/source_mappings.json` / `sources.xml` (see AGENTS.md → Source Mapping).