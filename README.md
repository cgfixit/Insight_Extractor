# Insight_Extractor

Turn a wall of threat-intel, OSINT, or security text into structured, typed insights in one
call:

1. **Regex entity extraction** — 15 pre-built IOC patterns (CVEs, hashes, IPs, wallets,
   `.onion` domains, ports, …). No model required.
2. **Dynamic keyword matching** — a 363-term seed bank with configurable stemming
   (exact, suffix-expansion, prefix, suffix, fuzzy, raw regex), compiled into chunked
   patterns that scale to thousands of keywords.
3. **BERT semantic scoring** — sentence-level relevance via `sentence-transformers`
   (`all-MiniLM-L6-v2` by default), plus TF-IDF-driven keyword expansion that grows the
   bank from what it reads.

Results are Pydantic v2 models. The CLI also writes a Markdown report and a JSON state file
that carries the learned keyword bank into the next run; API callers get the same files by
calling `save_results_to_markdown()` and `save_state()`.

## Why use it

- **Triage faster.** One `extract()` call surfaces IOCs, matched tradecraft terms, the
  most relevant sentences, and newly discovered vocabulary from a report, paste, or
  transcript.
- **Pay for ML only when you use it.** The BERT model and tokenizer load lazily on first
  semantic call. Regex and keyword pipelines run with no model, no network, and no GPU.
- **Learns your beat.** Keyword expansion plus persisted state means the bank adapts to
  the actors, tools, and jargon that recur in your feeds.
- **Typed end to end.** `mypy --strict` clean, PEP 561 `py.typed`, Pydantic schemas for
  every result.

### Use cases

| Scenario | What you get |
|----------|--------------|
| Ransomware leak-site / breach write-ups | CVEs, wallets, ransom amounts, data volumes, `.onion` links, actor handles |
| OSINT dossiers and investigation notes | Emails, domains, IPs, Telegram handles, recon-tool mentions |
| AI-safety / AI-security research corpora | Semantic hits on alignment, prompt-injection, RAG, and agentic-risk vocabulary |
| SOC / IR runbooks and incident timelines | Key sentences ranked by relevance to your seed terms, keyword frequency stats |
| Feeding a RAG or knowledge base | Deterministic JSON/Markdown output keyed by stable `PatternLabel` names |

---

## Quick start

Requires **Python 3.12 or newer** (CI tests 3.12 and 3.13). CPU-only inference works.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints.txt
python -m pip install -e .
```

On Windows, replace the activation line with `.venv\Scripts\activate` (cmd) or
`.venv\Scripts\Activate.ps1` (PowerShell).

Run the CLI on a file, or with no argument to use the built-in demo text (ransomware,
OSINT, CVE, and AI-pipeline content — a good end-to-end install check):

```bash
python -m insight_extractor my_report.txt     # also installed as `insight-extract`
python -m insight_extractor                   # demo text
```

Or from Python:

```python
from pathlib import Path

from insight_extractor import InsightExtractor

extractor = InsightExtractor(output_dir="results")
result = extractor.extract(Path("my_report.txt").read_text(encoding="utf-8"))

print(result.regex_entities.get("CVE_ID", []))   # keys appear only when matched
print([hit.keyword for hit in result.semantic_keywords[:5]])
extractor.save_results_to_markdown(result)                       # results/insights_extracted.md
extractor.save_state(extractor.output_dir / "insight_extractor_state.json")
```

The first semantic call downloads `all-MiniLM-L6-v2` (~90 MB) from Hugging Face. For a
model-free path, see [Regex-only example](#example--regex-only-no-bert-fast).

---

## Installation details

Install with `-c constraints.txt` — the pins encode a tested
`transformers` / `sentence-transformers` / `accelerate` combination. Development extras
(ruff, mypy, pytest):

```bash
python -m pip install -e ".[dev]" -c constraints.txt
```

CI's lint/type/unit jobs install `.[dev]` **without** the constraints file; keep it for a
fully pinned local setup.

### Known issues

Both errors trace to the `accelerate` package and both have the same fix:

```bash
python -m pip install "accelerate>=1.15.0" --upgrade
```

| Error | Cause |
|-------|-------|
| `ModelLoadError: name 'init_empty_weights' is not defined` | `accelerate` not installed; `sentence-transformers` needs it at model-load time |
| `ImportError: cannot import name 'TorchTensorParallelPlugin' from 'accelerate.utils'` | `accelerate < 1.3.0` alongside `transformers >= 4.53.0`; fires on `import sentence_transformers`, not just on model load |

`requirements.txt` requires `accelerate>=1.15.0` and `constraints.txt` pins
`1.15.0`, so fresh installs are unaffected. The error only appears with an older
`accelerate` left over from a previous environment.

---

## CLI and output

`python -m insight_extractor [file.txt]` writes two files to the **current working
directory** (or `output_dir` via the API), and reloads an existing state file from that
directory on the next run:

| File | Contents |
|------|----------|
| `insights_extracted.md` | Markdown report: regex entities, dynamic matches, semantic hits, key sentences, keyword stats |
| `insight_extractor_state.json` | Keyword bank, frequencies, categories, stem mode, threshold, model name |

Because state persists, run the CLI from a scratch directory. Console sections:

```
=== REGEX ENTITIES ===
=== DYNAMIC KEYWORD MATCHES ===
=== SEMANTIC KEYWORD HITS (top 10) ===
=== KEY SENTENCES ===
=== DYNAMIC EXPANSION: +N new keywords ===
Total tracked keywords: N
Results saved to: insights_extracted.md
=== KEYWORD STATS ===
```

Windows drag-and-drop launcher — save as `run.bat`, then drop any `.txt` onto it:

```bat
@echo off
python -m insight_extractor %1
pause
```

---

## Regex patterns — what gets extracted

These run on every input with no BERT model required. Labels are `PatternLabel` members
(a `StrEnum`), so `"CVE_ID" in result.regex_entities` works with plain strings.
Static patterns are case-insensitive in both `extract_regex_entities()` and
`KeywordPatternRegistry.extract_all()`; matches preserve their original spelling
and order. For example, both `CVE-2026-1234` and `cve-2026-5678` are extracted.

| Pattern Label | Matches | Example |
|---------------|---------|---------|
| `CVE_ID` | CVE identifiers | `CVE-2026-48710` |
| `IP_ADDRESS` | IPv4 addresses | `192.168.1.254` |
| `HASH_SHA256` | 64-char hex strings | `3b4c5d6e...` |
| `HASH_MD5` | 32-char hex strings | `d41d8cd9...` |
| `UUID` | 8-4-4-4-12 hex UUIDs/GUIDs | `9a2f15b7-2c91-4cbb-b8a7-52def899cfce` |
| `URL` | `http(s)://` and `ftp://` URLs, including defanged `hxxp(s)`, `[:]`, and `[.]`; trailing `.,;:!?)` is dropped | `hxxps[:]//bad[.]ru/x` |
| `DOMAIN` | Hostnames ending in `.com .net .org .io .ai .gov .edu .onion .xyz .co`; never a prefix of a longer host (`paypal.com.evil.ru` yields nothing) | `ransom.onion` |
| `EMAIL` | Email addresses | `threat@dark.io` |
| `BTC_WALLET` | Legacy (`1…`/`3…`) Bitcoin addresses; base58 stays case-sensitive and pure-hex strings are excluded | `1A1zP1eP5Q...` |
| `RANSOM_AMOUNT` | Dollar amounts with optional decimals and a `k`/`M`/`B`/`bn`/`mn`/million/billion scale | `$1.5 million`, `$186` |
| `FILE_EXTENSION` | `.exe .dll .ps1 .bat .sh .py .bin .enc .locked` | `.locked` |
| `DARK_WEB` | `.onion` hostnames | `abc123.onion` |
| `TELEGRAM_HANDLE` | `@handle`, 5+ word characters | `@threatactor` |
| `PORT_NUMBER` | `port NNNN`, `Port: NNNN`, `port=NNNN`, `ports NN` — returns the number only | `4444` |
| `TB_GB_DATA` | Data volumes in MB/GB/TB or (giga\|tera)byte(s) | `8 TB`, `8 terabytes` |
| `YEAR` | Four-digit years 2010–2029 | `2026` |
| `PERCENTAGE` | Percentage values | `94.3%` |

---

## Python API

### `InsightExtractor` constructor

```python
from insight_extractor import InsightExtractor, StemMode

extractor = InsightExtractor(
    model_name="sentence-transformers/all-MiniLM-L6-v2",  # HF model ID or local path
    config_path=None,              # optional .toml / .yaml / .yml / .json (see below)
    seed_keywords=None,            # None *or* [] both load THREAD_SEEDS (363 terms)
    top_k=10,                      # max results from extract_key_sentences()
    similarity_threshold=0.38,     # cosine threshold for semantic hits (0.0–1.0)
    dynamic_expansion_top_n=15,    # TF-IDF candidates considered per expansion
    # keyword-only from here:
    stem_mode=StemMode.STEM,       # EXACT | STEM | PREFIX | SUFFIX | FUZZY | REGEX
    enable_dynamic_regex=True,     # compile the keyword bank into regex patterns
    custom_stem_suffixes=None,     # e.g. ("ed", "ing", "er"); None uses the default tuple
    output_dir=".",                # where reports and state are written
)
```

A config file may set `seed_keywords`, `similarity_threshold`, and `stem_mode`; these
override the constructor arguments. A missing file is ignored and an unparseable one logs
a warning and falls back to defaults:

```toml
# extractor.toml
seed_keywords = ["lockbit", "clop", "akira"]
similarity_threshold = 0.30
stem_mode = "prefix"
```

### Stem modes

| Mode | Behavior |
|------|----------|
| `EXACT` | Keyword exactly as given, case-insensitive, at word boundaries |
| `STEM` | Keyword plus an optional known suffix (`s es ed ing er est ly tion ness ment`) at word boundaries — default |
| `PREFIX` | Any word starting with the keyword |
| `SUFFIX` | Any word ending with the keyword |
| `FUZZY` | Any word containing the keyword |
| `REGEX` | Keyword is a raw regex, passed through unescaped — the caller owns validity |

Keywords that start or end with a non-word character (`C++`, `.NET`) compile but never match
in `EXACT`/`STEM` because `\b` needs a word/non-word transition; use `REGEX` for those.
Interior punctuation is fine (`zero-day` matches normally).

### Extraction methods

`extract_dynamic_entities()` and `ExtractResult.dynamic_keyword_matches` contain
only the `DYNAMIC_KEYWORD` label, or an empty dict when no keyword matches.
Static labels appear in `regex_entities`. Disabling dynamic regex returns empty
dynamic results while leaving static extraction available.
`KeywordPatternRegistry.extract_all()` retains its combined static + dynamic contract.

```python
# Full pipeline: regex + dynamic + semantic + key sentences + keyword expansion
result = extractor.extract(text, update_keywords=True)   # -> ExtractResult

# Model-free, fast
regex_hits = extractor.extract_regex_entities(text)      # -> dict[str, list[str]]
dynamic_hits = extractor.extract_dynamic_entities(text)  # -> dict[str, list[str]]
positions = extractor.extract_keywords_with_positions(text)
# -> list[dict] with keys: keyword, match, start, end, category

# Loads the BERT model on first call
semantic_hits = extractor.extract_semantic_keywords(text, chunk_size=512)
# -> list[SemanticHit]  (.keyword, .score, .context)
sentences = extractor.extract_key_sentences(text, top_n=5)
# -> list[SentenceScore] (.sentence, .score)
new_keywords = extractor.update_thread_keywords(text, auto_expand=True)  # -> list[str]

# Stats, reports, persistence
stats = extractor.get_keyword_stats()                    # -> KeywordStats
top = extractor.top_keywords(n=20)                       # -> list[tuple[str, int]]
md_path = extractor.save_results_to_markdown(result, filename="insights_extracted.md")
# A relative Path resolves from the CWD, not output_dir, so build it from output_dir:
state_path = extractor.output_dir / "insight_extractor_state.json"
extractor.save_state(state_path)            # -> None
loaded = extractor.load_state(state_path)   # -> bool
```

`load_state()` returns `False` for a missing file. It validates the full JSON
object and prepares keyword patterns before applying any state. Malformed JSON,
invalid UTF-8, invalid field types/settings, and pattern-compilation failures raise
`StateLoadError`; the existing keywords, counts, categories, model/tokenizer caches,
embeddings, and compiled runtime remain unchanged.

Saved keywords must be strings, frequencies nonnegative integers, categories and
stem mode supported enum values, the threshold a finite JSON number, and the model
name a nonempty string. Missing keyword collections default to empty; omitted
settings retain their current values. Legacy `child_safety` categories map to
`ai_safety`, and extra metadata is ignored. Valid loads remain lazy: embeddings are
invalidated, and a changed model name also clears cached model/tokenizer objects.
The CLI reports invalid state as `error: Failed to load state ...` and exits 1.

`ExtractResult` fields: `timestamp`, `input_hash`, `word_count`, `regex_entities`,
`dynamic_keyword_matches`, `semantic_keywords`, `key_sentences`,
`newly_expanded_keywords`, `total_tracked_keywords`, `keyword_stats`.

### Keyword categories

Every keyword is auto-categorised into one `KeywordCategory`:

| Category | Covers |
|----------|--------|
| `threat_intel` | Ransomware, malware, TTPs, CVEs, threat actors |
| `osint` | OSINT tools, data brokers, recon techniques, PII |
| `ai_safety` | Alignment, jailbreaks, prompt injection, bias |
| `ai_infra` | LLMs, RAG, embeddings, vector DBs, AI frameworks |
| `infosec` | Red teaming, incident response, SIEM/EDR, threat hunting |
| `general` | Everything else |

### Example — regex-only (no BERT, fast)

```python
from pathlib import Path

from insight_extractor import InsightExtractor

extractor = InsightExtractor(enable_dynamic_regex=False)
hits = extractor.extract_regex_entities(Path("report.txt").read_text(encoding="utf-8"))
for label, matches in hits.items():
    print(f"{label}: {matches}")
```

### Example — custom keywords, lower threshold

```python
from pathlib import Path

from insight_extractor import InsightExtractor, StemMode

extractor = InsightExtractor(
    seed_keywords=["lockbit", "clop", "medusa", "akira"],
    similarity_threshold=0.30,   # more hits, lower precision
    stem_mode=StemMode.PREFIX,
    output_dir="results",
)
result = extractor.extract(Path("intel_report.txt").read_text(encoding="utf-8"))
extractor.save_results_to_markdown(result, filename="lockbit_report.md")
```

### Example — `DynamicKeywordStemmer` standalone

```python
from insight_extractor import THREAD_SEEDS, DynamicKeywordStemmer, StemMode

stemmer = DynamicKeywordStemmer(stem_mode=StemMode.STEM, case_sensitive=False)
stemmer.set_keywords(THREAD_SEEDS)

for m in stemmer.find_matches("ALPHV ransomware exploited CVE-2024-1234 via lateral movement."):
    print(f"  {m.keyword!r} -> span={m.start}-{m.end}, stemmed={m.stemmed}")
```

---

## Core API reference

### `DynamicKeywordStemmer`

| Method | Signature | Description |
|--------|-----------|-------------|
| Constructor | `DynamicKeywordStemmer(*, stem_mode, case_sensitive, custom_suffixes, max_pattern_length)` | Keyword-only constructor |
| `generate_pattern` | `(keyword, mode=None) -> str` | Regex pattern for one keyword |
| `generate_stem_variations` | `(keyword) -> list[str]` | All stemmed forms |
| `compile_keywords` | `(keywords) -> KeywordPattern` | One logical pattern, chunked internally for large banks |
| `compile_keywords_incremental` | `(keywords) -> KeywordPattern` | Recompile only the appended tail when the bank grows |
| `compile_typed_patterns` | `(keywords) -> dict[str, re.Pattern]` | Per-keyword typed patterns |
| `find_matches` | `(text) -> list[MatchInfo]` | All keyword matches with positions (`.match .keyword .start .end .stemmed`) |
| `add_keyword` / `remove_keyword` | `(keyword)` | Mutate the bank and invalidate caches |
| `set_keywords` | `(keywords)` | Replace the full keyword set |
| `compiled_pattern` | property `-> KeywordPattern \| None` | Lazily compiled master pattern |

### `KeywordPatternRegistry`

| Method | Signature | Description |
|--------|-----------|-------------|
| Constructor | `KeywordPatternRegistry(*, static_patterns=None, stemmer=None)` | Combine static regexes with a stemmer |
| `all_patterns` | property `-> dict[str, str]` | Static + dynamic patterns |
| `regenerate_dynamic_patterns` | `(keywords)` | Rebuild dynamic patterns — call after any keyword change |
| `extract_all` | `(text) -> dict[str, list[str]]` | All pattern matches from text |

### `SentenceTokenizer`

`chunk_text(text, max_tokens=512, overlap=50)` returns sliding token windows.
`max_tokens` must be a positive integer; `overlap` must be an integer in
`[0, max_tokens)`. Invalid arguments raise `ValueError` before loading a tokenizer,
including for empty or short text. When using a budget of 50 or less, pass an
explicit overlap below that budget. Zero overlap covers every token exactly once,
including the final partial chunk.

Each chunk is the verbatim slice of the input that its token window covers
(`text[start_char:end_char]` from the fast tokenizer's `offset_mapping`), so case,
punctuation spacing, URLs, and characters the tokenizer maps to `[UNK]` (emoji,
box-drawing glyphs) are preserved inside the span, and no `##` continuation markers
are introduced. Windows are not snapped to word boundaries, so a chunk can still begin
or end inside a word. Whitespace between two windows is not part of either chunk.
Because WordPiece re-tokenizes a cut word differently, re-encoding a chunk can
occasionally yield one or two tokens more than `max_tokens`. Slow (non-fast)
tokenizers, which have no offsets, fall back to `tokenizer.decode(window)`, which for
uncased models lowercases and re-spaces the text.

`tokenize_sentences(text, max_tokens=512)` uses the same budget validation and
splits oversized sentences with `min(50, max_tokens - 1)` overlapping tokens.
Budgets as small as one token are supported. Tokenizer loading remains lazy.

Sentence units come from `insight_extractor.utils.split_sentences`, shared with
`extract_key_sentences()` (which keeps units longer than 30 characters). Hard-wrapped
prose lines are joined and split on `.`, `!`, or `?`; blank lines end a paragraph;
list items and `>` quotes start one; headings and table rows (a leading `|` or
box-drawing bar, or rows attached to a `|---|` delimiter row) are single units with
their outer frame removed;
lines with no word characters, such as `|---|` rules and box borders, are dropped.
Whitespace inside each unit is collapsed to single spaces.

`extract_semantic_keywords(text, chunk_size=512)` caps `chunk_size` at the loaded
model's `max_seq_length` minus its two special tokens (254 for all-MiniLM-L6-v2), so
oversized units are split into windows the model actually embeds instead of being
silently truncated.

All of the above, plus `SentenceTokenizer`, the Pydantic models, the exceptions
(`InsightExtractorError` → `ConfigLoadError`, `ModelLoadError`, `StateLoadError`,
`PatternCompileError`), `THREAD_SEEDS`, and `REGEX_PATTERNS`, import from the top-level
package. Heavy classes are lazy-imported, so `import insight_extractor` never pulls in torch.

---

## Project structure

```
Insight_Extractor/
├── .github/workflows/
│   ├── ci.yml                  # Required: ruff, mypy, unit (3.12/3.13), CLI smoke; optional integration
│   └── gitleaks.yml            # Secret scanning on push/PR
├── .claude/skills/             # Claude Code skills: preflight, add-entity-pattern, deps, verification
├── .agents/skills/             # Cross-agent skills (insight-* names)
├── .codex/                     # Codex workflow map and custom instructions
├── AGENTS.md                   # Short cross-agent operating summary
├── CLAUDE.md                   # Full agent operating manual (conventions, footguns, gates)
├── LICENSE                     # MIT
├── pyproject.toml              # PEP 621 metadata + ruff/mypy/pytest config
├── requirements.txt            # Runtime bounds
├── constraints.txt             # Exact known-good pins
├── docs/
│   ├── SPEC.md                 # Design reference; source code is the behavioural authority
│   ├── SECURITY_AUDIT.md       # Dependency CVE triage with reachability verdicts
│   └── CODEX_SETUP_REVIEW.md   # Verified Codex setup scope
├── src/
│   ├── sample_input.txt        # 19k-word AI-safety reference corpus
│   ├── sample_extracted_insights.md
│   └── insight_extractor/
│       ├── __init__.py         # Public exports; lazy imports for heavy classes
│       ├── __main__.py         # CLI: python -m insight_extractor [file.txt]
│       ├── config.py           # StemMode, KeywordCategory, PatternLabel
│       ├── constants.py        # THREAD_SEEDS (363), REGEX_PATTERNS (15)
│       ├── exceptions.py       # InsightExtractorError hierarchy
│       ├── models.py           # Pydantic v2 result models
│       ├── stemmer.py          # DynamicKeywordStemmer, KeywordPatternRegistry
│       ├── extractor.py        # InsightExtractor orchestrator
│       ├── tokenizer.py        # SentenceTokenizer (lazy AutoTokenizer)
│       ├── utils.py            # Logging, hashing, timestamps
│       └── py.typed
└── tests/
    ├── unit/                   # Required CI, model-free (fakes injected via _model/_tokenizer)
    └── integration/            # Optional: full orchestration with offline ML doubles
```

---

## Testing and CI

Required CI (`ci-pass` in `.github/workflows/ci.yml`) on every push and PR:

1. `ruff check` + `ruff format --check`
2. `mypy src/insight_extractor` (strict)
3. `pytest tests/unit/` on Python **3.12 and 3.13** — no network, no model download
4. CLI smoke — the production `python -m insight_extractor` path with fake BERT
   boundaries (`HF_HUB_OFFLINE=1`); also asserts the `insight-extract` script exists

Integration tests (`tests/integration/`) run the full orchestration with fake model/tokenizer
doubles, only on `workflow_dispatch` or when a **push head commit** message contains
`[run-integration]`. Neither suite certifies real BERT weight compatibility.

Local gates, same order as CI:

```bash
python -m ruff check src/ tests/
python -m ruff format --check src/ tests/
python -m mypy src/insight_extractor
python -m pytest tests/unit/ -v --tb=short
```

Agents working in this repo should start at [AGENTS.md](AGENTS.md) (cross-agent summary),
[CLAUDE.md](CLAUDE.md) (full manual), or [the Codex workflow map](.codex/README.md).

---

## Example output

Captured from `python -m insight_extractor src/sample_input.txt` — a ~19k-word AI-safety
corpus sourced from the cgfixit.com RAG database. The full report is checked in as
`src/sample_extracted_insights.md`.

> This transcript used the original 69-keyword seed bank. The current default bank has
> 363 keywords, so your counts will be higher.

```
=== REGEX ENTITIES ===
  DOMAIN: ['medium.com', 'fortune.com', 'techcrunch.com', 'hiddenlayer.com', ...]
  RANSOM_AMOUNT: ['$9M', '$186', '$950M']
  FILE_EXTENSION: ['.py']
  TELEGRAM_HANDLE: ['@sobyx']
  YEAR: ['2025', '2026', '2024', '2023', '2020', '2019', '2015']
  PERCENTAGE: ['4.1%', '9.6%', '13%', '68%', '800%', ...]

=== DYNAMIC KEYWORD MATCHES ===
  loader: ['loader', 'Loader', ...]  (31 total)
  veeam: ['veeam', 'Veeam', ...]  (16 total)
  RAG: ['RAG', 'rag', ...]  (9 total)
  exploit: ['exploit', 'exploiting', ...]  (8 total)
  supply chain: ['supply chain']  (1 total)

=== SEMANTIC KEYWORD HITS (top 10) ===
  [0.821] offline
           ...MCP-Specific Offline Patterns — validates thread emphasis on offline MCP ...
  [0.794] RAG
           ...PsyClaw uses BERT embeddings with ChromaDB and BM25 hybrid retrieval via R...
  [0.718] APT
           ...advanced persistent threat actors leverage AI-generated phishing at scale...
  [0.702] conti
           ...leaked Conti 2 builder code repurposed for ESXi locker generation...

=== KEY SENTENCES ===
  [0.821] MCP-Specific Offline Patterns - Score: 1 - Stem hits: pattern
  [0.794] This mirrors Claude's blackmail simulations: the model's chain-of-thought ...
  [0.743] Validates thread emphasis on offline MCP with mandatory approval gates.

=== DYNAMIC EXPANSION: +10 new keywords ===
  ['alignment', 'deception', 'agentic', 'oversight', 'autonomy',
   'chain-of-thought', 'adversarial', 'capability', 'approval', 'governance']

Total tracked keywords: 79

=== KEYWORD STATS ===
  Categories: {'threat_intel': 28, 'osint': 12, 'ai_safety': 9, 'ai_infra': 12, 'infosec': 8, 'general': 10}
  Stem mode: stem
```

---

## License

MIT. See [LICENSE](LICENSE).

Initial inspiration: https://cgfixit.com/ai
