# Dictionary Markup Patterns

Single source of truth for the **lexicographic XML markup** used in `data/dictionary/dictionary_*.xml`, distilled from `dictionary_G.xml` (130 entries) and reassessed against all letter files (`A` 32, `B` 3, `Ch` 3, `Cz` 7, `D` 3, `DZ` 1, `G` 130, `H` 4, `Jo` 35, `Ju` 23, `N` 1, `P` 2, `S` 3, `Y` 3, `Z` 1 — 251 entries total). `Cz` transcription is in progress: first chunk чооат…човен (7 entries) is user-checked.

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
| `<hw>` | headword (bold, clickable anchor) | one per spelling variant; multi-word headwords like `ґазавая ґрана́та`; homonym numerals nested: `<hw>гале́ра <n>ІІ</n></hw>`; disambiguation links see §7; `excl="true"` marks a display-only variant that is kept out of the entry list and all logic except display + the pointing-finger (`👉`), e.g. `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>` (see AGENTS.md → `<hw excl="true">`); an inflected/cognate variant shown alongside the main form may be italicized INSIDE `<hw>`: `<hw>Юр'е</hw>, <hw><i>Юр'я</i></hw>` (Ju) |
| `<g>` | grammar/declension, italic | declension starts with `-`: `-са, м.`; standalone markers: `нареч.`, `местоим.`, `союз`, `соверш.`, `несоверш.`, `безлич.`, `однкр.`, `средн.`, `прич.`, `отгл. имя сущ.`; may embed `<st>`, `<see>`, `<p>`, `<src>`, even `<hw>` (`один <hw>ґалёш</hw>`) |
| `<t>` | Russian translation (can also appear nested INSIDE an `<ex>` for a Russian gloss of a proverb/idiom — H `гарох`: `<ex>Хадзі̀ма ў гарох <t>(знач. щипать горох)</t>. <src>Ст.</src></ex>`) | transcription, multiple `<t>` per sense allowed; sources and `—` separators inside |
| `<ex>` | Belarusian example, italic, srcless or `<src>`-tagged | may embed a Russian `<t>` gloss and/or `<st>Послов.</st>` (H `гарох`: `Ідзе гарох, там сем дарог. <st>Послов.</st>, <t>о частом щипании гороха</t>. <src>Дсл.</src>`) |
| `<src>` | source, becomes link | `Ар.`, `Гсл.`, `Нсл. 119.`, `Стаішча Чаш. (Ксл.)`, long bibliographic refs stay whole (`Азбукін: Ґеоґрафія Эўропы, 1924`); single-letter `С.` bolded as `<src><b>С.</b></src>`; a source printed inside parens keeps them IN the tag (`<src>(Ксл.)</src>`, `<src>(Ар.)</src>`, `<src>(НК)</src>` — Cz); song/popular-lore attributions stay whole `<src>` (`Из песни, Войш.`, `Из нар. песни.`, `З купальскае песьні.` — Cz) |
| `<st>` | register/style marker, italic, linkable | `хим.`, `биол.`, `рел.`, `муз.`, `ист. мор.`, `област.`, `перен.`, `Послов.`; may attach case (`послов.`). Before a sense dash: `<n>1.</n> <st>презр.</st>—<t>кровь. …` (Ju юшка 1); at an `<ex>` tail, with a trailing comma when followed by a source: `<ex>Які добры пан! … <st>Насм. пословица,</st> <src>Нсл.</src></ex>` (Ju юшка 2), also `<st>Поговор.</st>`; a parenthetical usage note inside `<g>` may also be a `<st>` (see §5). An embedded `<p>` inside `<st>` stays plain (non-italic): `<st><p>презр.</p></st>` renders `<span class="st"><span class="p">презр.</span></span>` (Ju `юха́`) |
| `<i>` | italic gloss container | `См. …`/`Ср. …` cross-reference tails, other gloss notes; `lang="vl"` marks a Belarusian-language quoted word/fragment inside a Russian `<t>` gloss (`<i lang="vl">"не"</i>` — N, Jo), `excl="true"` keeps a quoted fragment out of the translation/content index (`<i excl="true">"а (я)"</i>` — N); both render italic |
| `<lang code="…">` | quoted-language fragment, style-inheriting | same as `<i lang="…">` but without forcing italic: formatting (bold/italic/plain) inherits from the surrounding tag; exclusion rules identical to the `lang` attribute — `code="vl"` keeps a Belarusian fragment out of the `<t>` content index/highlight, `code="la"` keeps a Latin fragment out of the same, `code="ru"` out of the `<ex>` index/highlight, `excl="true"` (any value) out of the translation index (Ju `юха́`: `<t><i excl="true">ударение на <lang code="vl">ю</lang></i>—молодец. <src>Нсл. 725.</src></t>`) |
| `<see>` | cross-reference, italic | inside `<i>`, `<g>`, or `<t>` glosses (see §6) |
| `<sense n="…">` | numbered/lettered sense block | `<n>1.</n>` numeric or `<n>а)</n>` lettered; `<br />` between senses |
| `<n>` | sense number AND homonym numeral | `<n>1.</n>`, `<n>2.</n>`, `<n>а)</n>`, homonym `<hw>… <n>ІІ</n></hw>` |
| `<d>` | sub-dictionary block with own `<hw>` | phrasal sub-headwords and morphological family blocks; separated by `<br />`; may nest inside a `<sense>` OR contain its own lettered/numbered `<sense>` blocks (see §5, S `вы́смаргнуць`/`абсморганы`) |
| `<p>` | literal parens inside declension/headword strings, or a plain-text child inside `<st>`/`<src>` | keeps `(`/`)` out of italic side effects: `<g>-чу<p>(</p>чаю<p>)</p>…` — **optional/redundant**: the renderer now auto-keeps parens non-italic inside `<g>`/`<i>`/`<ex>`/`<st>`/`<see>` even without `<p>` (see AGENTS.md → Entry Formatting: Paren rule). Take-over from raw print stays verbatim: bare parens in italic tags render plain automatically. Also used to mark a variant spelling's `г` as plain inside a bold `<hw>` (`<hw>-…</hw>`… `<hw><p>гірса</p></hw><p>,</p>` — G `ґірса`, where `гирса` is the г-spelled variant; treats the letter as non-bold like parens). Inside `<st>`/`<src>`/`<see>`, an embedded `<p>` child stays plain: `<st><p>презр.</p></st>` renders `<span class="st"><span class="p">презр.</span></span>` (Ju `юха́`) |
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
- `—` em-dash abuts the preceding tag: `</g>—<t>…</t>`, `</ex>—<t>…</t>` (no space before `—`). A translation may use `—` as an internal separator: `<t>…</t>—<t>…</t>`, `<ex>…</ex>—<t>…</t>`. A crowded proverb whose Russian gloss gets its own citation renders with the gloss OUTSIDE the `<ex>`, joined by `—` (user-checked Cz `чорт`): `<ex>Чорт на паганага папаў, <st>послов.</st></ex>—<t>нашла коса на камень. <src>Ар.</src>; <src>Іг.</src></t>`.
- `,`/`:`/`;` follows `</hw>` directly (no space before it), ordinary form: `•<hw>ґастрономны</hw>, <g>-ная-нае</g>—<t>…`; the symbol is auto-absorbed into the headword anchor at render time (stays bold) — e.g. `•<hw>акалотам</hw>: <ex>…`. Two duplicate commas `,,` directly after `</hw>` are BOTH absorbed (both stay bold) — e.g. `<hw>разьюрыцца</hw>,, <sense …`.
- Square brackets directly abut the preceding/following tag, **optional/redundant**: when `[`…`]` enclose only `<hw>` and/or `<src>`/`<st>` (at least one `<hw>`), the renderer auto-bolds the brackets even without `<b>` (see AGENTS.md  Entry Formatting: Square-bracket bold rule) — e.g. `</hw>[<hw>ёлупень</hw>, <src>Варсл.</src>; <src>Бяльсл.</src>]`. Bracket pairs around other content render literally.
- Parens directly abut content: `(<hw>галя́с</hw>)` no inner space; a raw `( ` keeps its space (` ( <hw>гвазьдзікі́</hw>, <src>Нсл.</src>)`).
- Literal `См.`, `Ср.` glosses inside `<i>`; the OCR forms `ем.`, `ер.`, `емь`, `ер` are to be read as `См.`/`Ср.`, not transcribed verbatim.
- Period placement follows the raw: `ж.` before the dash `—`.
- Trailing period: when a `<t>` contains no nested tags, the sentence-ending period goes AFTER `</t>` — `<t>Юрий, Георгий</t>.` — do not fold it into the tag. When `<t>` carries nested tags (`<src>`, `<st>`, …), the period follows the raw position. In the `Y` file the sentence-ending period after a closing page ref also moves outside: `—<t>… <see>"ых"</see>. <src>Нсл. 722</src></t>. …` (the page ref itself takes no inner period; the `;`-joined form is `<src>Нсл. 722</src>; <src>Ксл.</src>`). A source carrying its own trailing punctuation keeps it inside: `<src>Пск.(Иеропольский).</src>`, `<src>Нсл. 75.</src>`.
- `<br />` is the canonical block separator; the equivalent `<br></br>` form also occurs in the data (A, N) and ElementTree treats both identically — either is acceptable on input.

## 5. Grammar and declension conventions

- Declension suffix chains are copied from the raw with OCR fixes (see §8), keeping the raw's punctuation: `-нку, на ґанку, м.,`, `-ара̀, предл.-ару̀, зват.-а̀ру; мн. ч.-ры̀-роў-ром, предл.-рох, м.`.
- A `<g>` that is only a category marker carries no dash: `<g>местоим.</g>`, `<g>нареч.</g>`, `<g>несоверш.</g>`, `<g>соверш.</g>`, `<g>прич.</g>`, `<g>отгл. имя сущ.</g>`, `<g>средн.</g>`, `<g>однкр.</g>`, `<g>междомет.</g>`.
- `прилаг. к <see>…</see>`, `однкр. к <see>…</see>`, `соверш. к <see>…</see>` in `<g>` use nested `<see>`.
- Declension containing parens: wrap the parens in `<p>` — optional (renderer auto-keeps parens plain inside italic tags; `<p>` is redundant but harmless and present in existing data): `<g>-чу<p>(</p>чаю<p>)</p>…`.
- **Per-variant declension with parenthetical sources** (Ch `хлѐў`): variant declension forms followed by their own source in parens stay plain via `<p>` around the whole cluster; a source-owning punctuation/continuation may be bolded: `<g>хлѐву, предл.-вѐ , <p>(<src>Ар.</src>)<b>, хлѐве.</b>(<src>Шсл.</src>),</p> зват. хлѐве; …</g>`.
- **Variant plural stems with their own sources** (Cz `човен`/`чаўны`): each stem variant is a nested `<hw>` inside its own declension `<g>`, joined with `<b>, </b>`: `•<g><hw>човен</hw>-вена, предл. и зват.-вене, мн. ч. човены, <src>(Ар.)</src></g><b>, </b><g><hw>чаўны</hw>-ноў-ном, <src>(НК)</src></g>—<t>…`.
- Declension case forms print lowercase even when raw OCR capitalized them: `чарта, предл.-ту̀, зват. чорце; мн. ч. …` (Cz `чорт`), `човены`.
- Grammar markers inside a declension `<g>` are wrapped in `<st>`: `<g>м., <st>област.</st></g>` (Cz `чобат`); the raw's `увел.`/`прилаг.`/`соверш.` relative labels stay literal words in `<g>`: `<g>-гі, увел. от <see>чорт</see></g>`.
- **Parenthetical usage note with an embedded proverb** (Ju `юры́ць`): the declension's `<g>` may carry a long parenthetical wrapped in `<st>`, and a proverb quoted inside is tagged `<ex>` even nested in the `<g>`/`<st>`: `<g>юру̀, юры̀ш<st>(ад Юр’я, што бывае 23-га красавіка, калі, з настаньням вясны, статак пачынае чуць сілу, бушаваць подле прыказкі: <ex>Бычкі бушуюць, вясну чуюць.</ex>)</st></g>`.

## 6. Cross-references (`<see>`)

- `См.`/`Ср.` tails: `<i>См. <see>газоўка</see>, <see>газулька</see>.</i>`; sense-targeted: `<i>См. <see>зык 3</see>.</i>`, `<see>смаргаць 4</see>`, also with a comma before the number: `<i>Ср. <see>юшка, 3</see>.</i>` (Ju юха 2).
- **`см. под` (preserve):** when the raw entry reads `см. под X`, KEEP the phrase verbatim in the resulting markup — `<i>см. под <see>X</see>.</i>` — do NOT rewrite it to `См.` or fold it into a plain `<see>`. Transcription must not drop such entries; the user deletes them manually if they prove unnecessary (see the `ёлупень`→`см. под ёлапень` example, which was removed by hand). Kept example: `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>,—<i>см. под <see>ё</see>.</i>`.
- Two `См.` sets same entry: `<i>См. <see>грункач</see>, <see>ґруґан</see>, <see>крумкач</see>.</i>`.
- In `<g>`: `прилаг. к <see>ґімназя</see>`, `увел. от <see>чорт</see>` (Cz), `соверш. к <see>чахці</see>, 1` (Cz) — sense targets use Arabic numerals even when the raw prints Roman `І`; in `<t>` glosses with explicit target: `<t>… <see hw="ґіль">"ґілёў"</see> —овадов, …`; `<see hw="плаксу́ха">-уха</see>`. A quoted word may be a plain quoted `<see>` without `hw`: `—<t>… говоря: <see>"ых"</see> …` (Y `ы́хаць`).
- Homonym cross-refs carry the numeral inside `<see>`: `<i>См. <see>грыжа <n>ІІ</n>, 1, 2</see>.</i>` (H), `собир. к <see>брус 1, 2, 3, 4</see>` (B).
- `<see>` headword spelling must match the linked entry's headword (accents allowed; normalization is accent-stripped). When the raw's cross-ref is OCR-mangled, normalize it back to the dictionary's headword spelling (e.g. `Кажа-мЯКа` → `кажамяка`).

## 7. Homonyms and `link` attributes

- **Homonym numerals** (`гале́ра І`, `ґале́ра ІІ`, `ґен І`, `ґен ІІ`): the numeral is marked-up as `<n>І</n>` INSIDE `<hw>`: `<hw>гале́ра <n>І</n></hw>`. No `link` attribute is needed — indexing strips the `<n>` content (AGENTS.md → Collation Rules), and distinct entries keep stable file order.
- **Distinct lexemes that share the same plain headword** (homographs) get a `link` on the `<entry>` and/or `<hw>`/`<see>`: `абора` → `<entry link="абора_бечевка">` and `<entry link="абора_хлев">`, sub-forms `<hw link="абора_бечевка#аборына">`, cross-refs `<see link="абора_бечевка#аборка">` (see dictionary_A.xml).
- Same-file homograph pairs are the ONLY plain-headword collision found in the corpus (`абора` ×2 in dictionary_A.xml, resolved with `link`). Distinct lexemes that share a spelling AND a file but are NOT linked would collide on lookup — that is why every such pair gets `link` (see previous bullet).

## 8. OCR transcription rules (raw → XML)

- **High-confidence letter fixes** where the raw is unambiguously a known word: `светйль-ный`→`светильный`, `р)’-рыш`→`ру-рыш`, `повел,`→`повел.`, `ж„`→`ж.,`, `мш ч.`→`мн. ч.`, `ХоЧуць`→`хочуць`, `Ґа-Ґа-Ґа`→`ґа-ґа-ґа`, `2З-га`→`23-га` (OCR reads the digit 3 as Cyrillic З — Ju `юры́ць`), `прыказг.`→`прыказкі:`, `чуюцы`→`чуюць`, `проказы-вать`→`проказывать`, `КрОВЬ`→`кровь`, `гЛедЗяЧЫ`→`гледзячы`, `а Мне`→`мне`, `Наем,`→`Насм.,` (`Наем, пословица`→`Насм. пословица`), `лри`→`при` (Cz `ча`: `лри вопросе`→`при вопросе`). **`Пе`/`Пя`→`Ня`** in Cz examples where the negation `ня` was misprinted with `п` (`Пе чакай`→`Ня чакай`, `Пя відна`→`Ня відна`, `Пя чадзь`→`Ня чадзь`) — unmistakable by meaning; flagged in §9 should the user disagree. Digit OCR: `Но. 20, б.`→`Но. 20, 6.` (the letter `б` standing for the digit `6` in issue refs — Cz `чарцю́га` example). Do NOT "fix" words that could be deliberate (e.g. `Ґімназы̀сцкая хорма.` keeps `хорма`).
- **Declension tail OCR fixes** (raw base+suffix tails mangled): `«-ншы-нце»`→`-нты-нце`, `ґазаме́р-ера`→`-ѐра, предл.-ѐру`, `ґенара́ліха-іхі-ісв`→`-іхі-ісе`, `ґраната-алны-ацв`→`-ты-це`, `ґеохіма-йы-.йе`→`-мы-ме`, `ґу́лта-лна`→`-та`, `ґімназы́сты-лнага`→`-тага`, `ґеоґра́фка-$кі-$цы`→`-фкі-фцы`, `-н/, ж.`→`-ні, ж.` (Ju `юра́нь`). Cz: `ча́хнуць-нг-нсш-не`→`-ну-неш-не`, `чака́ць-аю-аеін-ав`→`-аю-аеш-ае`, `чаборавы-вая-вав`→`-вая-вае`, `адча́хацца-аюся-авшся`→`-аюся-аешся`, `чаўны-ноў-нолі`→`-ноў-ном`.
- **Headword fixes**: `ґейззр`→`ґейзэр`, `ґа́мл`→`ґа́ма` (ґама has declension `-мы-ме`), `ґе́мзазы`→`ґе́мза`; OCR headword corruptions proven by the dictionary's own example sentences: `кітрань`→`ю́трань`, `кішна`→`ю́шна` (Ju — the examples `на ютрань` и `будзе табе і рыбна і юшна` fix the spelling); `чооат`→`чобат` (Cz — user-confirmed against the gloss `сапог`).
- **г/ґ restoration**: OCR frequently drops the ґ's descender, printing `ґ` as `г` (`го́нта`→`ґонта`, `гілёс`→`ґілёс`). Restore `ґ` when the surrounding print order or the word family confirms it (this file sorts `ґ` between `г` and `д`, and family members in the same entry are printed `ґ`). Otherwise keep the raw's printed letter: `ге́мзавы` kept `г` while its phrase `ґе́мзавыя чаравікі` kept `ґ` — do not mass-normalize.
- **Keep raw fragments verbatim when unknowable**: `супраціпаўзьнява́я`, `раськяпі`, `состоянме`, `-нв` declensions past `-не`, etc. Never invent content; if a fragment is genuinely unreadable, transcribe it and flag for the user.
- **Unreadable translation printed as dots** stays as printed inside `<t>`: Ju `разью́шавацца` `<g>-шуюся-шуешся. <src>Нсл.</src></g>—<t>.....</t>` — the illegible Russian gloss keeps its dot run (`—.. ...` in the raw).
- **Case-mangling fixes** are allowed in `<hw>`/`<ex>` where OCR produced random capitals (`Ґа-Ґа-Ґа`, `ХоЧуць`, `аўЧЫньнік`→`аўчыньнік`, `Рох`→`рох`, `мЯКа`→`мяка`); but never change legitimate sentence-initial capitals.
- **Implicit source refs** like `Нсл. 119.` (page numbers) stay INSIDE `<src>`: `<src>Нсл. 119.</src>`; the trailing `.` follows the raw. When a page ref closes a `<t>`, the sentence-final period may instead be placed after `</t>` (Y `ы́хаць`/`ыт` — see §4).
- **Source abbreviations**: never "correct" `Гсл.`, `Ксл.` etc. into `Гел.`, `Кел.` etc.; the reverse normalization IS expected instead (`Гел.` → `Гсл.`, `Кел.` → `Ксл.`). Same for `Шел.`→`Шсл.` (Y `ых`) and `Бясл.`→`Бяльсл.`.
- **`С.` as a source**: in most cases `С.` is NOT marked `<src>С.</src>` but `<src><b>С.</b></src>` (the single-letter source is bolded, as in the `<src>` row of §2).
- **Reference markers `ем.`/`ер.` → `См.`/`Ср.`** and drop the raw's mangled cross-ref casing.
- **Accent marks**: combining accents U+0300 (grave) / U+0301 (acute) are preserved as in the raw (`ґа́ґаць`, `да̀ўна`, `ґе́мза`, `ґіля̀`). Restore the word's known-stress accent on a headword or split declension base even when the raw collation print omitted it (Ju `ю́хта`, `ю́шка <n>ІІ</n>`, `ю́шна`, `ю́трань`, `ю́траня`; `ґазаме́р-ера`→`-ѐра`; Cz `чарцю́га`). Do not guess accents the raw gives no evidence for — in Cz example text a stray grave was dropped (`дзя̀ўчына`→`дзяўчына`).

## 9. Remaining-uncertain spots (kept verbatim / flagged)

- `супраціпа́нцырная ґраната`, `супраціпаўзьнява́я ґраната` kept as raw (`супраці-` prefixes are OCR-dubious).
- `ґенера́тар` translation `генерптор` kept (Russian `генератор` was OCR-mangled; left as-is; user-verified).
- `ґу́лта` (постель свиньи …) kept as headword, `<g>-та, ср.</g>`.
- `гімна…` family: `ґімназы́сты|-тага, сущ., м.`; `ґімназы́стая|-ае, сущ., ж.`.
- `состоянме` in `ґілёс` sense 2 kept verbatim (Russian typo in source).
- Ju `юр` sense 1 keeps `при издышке энергии` verbatim (Russian `избытке` implied but printed so).
- Ju `юрлі́вы` sense 1 keeps `гаривый` verbatim.
- Ju `заюшы́цца`: `Палуж Краснап.(Бясл.)` still holds `Бясл.` — normalize to `Бяльсл.` per §8.
- Ju headwords `Юр'е`/`Юр'я` use ASCII `'` while body text uses typographic `’` (`Мар’я`, `Юр’я`, `ад’юшыць`) — unify to `’` when editing.
- Cz (checked chunk чооат…човен): `чорт` declension `мн. ч. ты̀-тоў-том-тоў-тамі-тох` kept verbatim (user kept); `чарцянё` decl `-няці; мн. ч. -няты-нят(нятаў), м.` (the unclosed paren was closed by user); `палцы`, `из далека`, `рэнэґатаў` kept verbatim; `чохаўка` example dropped the stray `(')` print.
- Cz chunk 2 (ча…чалом, *in transcription*) flags: `чабор` decl `-дора, предл.-бару̀, зват.-бору` (first link `-дора` OCR-dubious); `чакмень-енкэ`; `чаку́ха-ухі-усе`; example-gloss `ад кашлю ПЩЪ`; roman-digit OCR `Но. І-І1`, `Рам. УШ`, `кн. ХУП`; example OCR `лідойк`, `залётавае…адводзе`; negation `Пе`/`Пя`→`Ня` applied per §8.

## 10. Verification

- Output must parse with `xml.etree.ElementTree` (the markup editor and `db.build_database` rely on it).
- Every `<src>` abbreviation should resolve against `data/source_mappings.json` / `sources.xml` (see AGENTS.md → Source Mapping).
- Do NOT check against the source mappings when marking up raw content — transcribe `<src>` verbatim as printed (normalizing only per §8); resolving every abbreviation against the mappings costs too much time and resources.