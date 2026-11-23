from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from insight_extractor.config import PatternLabel, StemMode
from insight_extractor.exceptions import PatternCompileError
from insight_extractor.models import MatchInfo

if TYPE_CHECKING:
    pass

logger: logging.Logger = logging.getLogger(__name__)

# re.escape renders each whitespace char as a backslash plus that char; a run of them
# becomes one \s+ so "data breach" also matches hard-wrapped "data\nbreach".
_ESCAPED_WHITESPACE_RUN: re.Pattern[str] = re.compile(r"(?:\\\s)+")


def _normalize_whitespace(text: str) -> str:
    """Collapse every whitespace run in *text* to a single space."""
    return " ".join(text.split())


# Type aliases
class ChunkedKeywordPattern:
    """Small adapter that searches multiple regex chunks as one logical pattern."""

    def __init__(self, patterns: list[re.Pattern[str]]) -> None:
        self.patterns = patterns
        self.pattern = "|".join(pattern.pattern for pattern in patterns)

    def search(self, text: str) -> re.Match[str] | None:
        matches = [match for pattern in self.patterns if (match := pattern.search(text))]
        if not matches:
            return None
        return min(matches, key=lambda match: match.start())

    def finditer(self, text: str) -> Iterator[re.Match[str]]:
        matches: list[re.Match[str]] = []
        for pattern in self.patterns:
            matches.extend(pattern.finditer(text))
        matches.sort(key=lambda match: (match.start(), match.end()))
        yield from matches


type KeywordPattern = re.Pattern[str] | ChunkedKeywordPattern
type RegexPatternDict = dict[str, str]
type TypedPatternDict = dict[str, KeywordPattern]
type EntityResults = dict[str, list[str]]
type MatchResultList = list[MatchInfo]
type KeywordList = list[str]


class DynamicKeywordStemmer:
    """Generates regex patterns from a keyword bank with configurable stemming.

    Patterns auto-update when keywords change. Supports multiple matching modes
    from exact word-boundary matching to fuzzy substring search.

    Parameters
    ----------
    stem_mode:
        Default stemming mode for pattern generation.
    case_sensitive:
        Whether matches are case-sensitive.
    custom_suffixes:
        Suffix tuple for STEM-mode expansion.
    max_pattern_length:
        Maximum length of a compiled regex pattern (safety limit).
    """

    def __init__(
        self,
        *,
        stem_mode: StemMode = StemMode.STEM,
        case_sensitive: bool = False,
        custom_suffixes: tuple[str, ...] = (
            "s",
            "es",
            "ed",
            "ing",
            "er",
            "est",
            "ly",
            "tion",
            "ness",
            "ment",
        ),
        max_pattern_length: int = 50000,
    ) -> None:
        self.stem_mode: StemMode = stem_mode
        self.case_sensitive: bool = case_sensitive
        self.custom_suffixes: tuple[str, ...] = custom_suffixes
        self.max_pattern_length: int = max_pattern_length

        # Precomputed once -- custom_suffixes is immutable after construction
        self._suffix_group: str = "|".join(re.escape(s) for s in self.custom_suffixes)
        # Shortest suffix first = longest root first, mirroring longest-keyword-first matching.
        self._suffixes_shortest_first: tuple[str, ...] = tuple(
            sorted(self.custom_suffixes, key=len)
        )

        # Internal caches -- invalidated on keyword changes
        self._keywords: KeywordList = []
        self._compiled_master: KeywordPattern | None = None
        self._compiled_typed: TypedPatternDict | None = None
        self._keyword_lookup: dict[str, str] | None = None
        self._last_updated: datetime | None = None

    # -- Representation -------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"stem_mode={self.stem_mode!r}, "
            f"case_sensitive={self.case_sensitive}, "
            f"keywords={len(self._keywords)}, "
            f"suffixes={len(self.custom_suffixes)}"
            f")"
        )

    def __str__(self) -> str:
        flags = "case-sensitive" if self.case_sensitive else "case-insensitive"
        return (
            f"DynamicKeywordStemmer[{self.stem_mode.value}] "
            f"({len(self._keywords)} keywords, {flags})"
        )

    # -- Pattern generation ---------------------------------------------------

    def generate_pattern(self, keyword: str, mode: StemMode | None = None) -> str:
        """Generate a regex pattern for a single keyword.

        Parameters
        ----------
        keyword:
            The keyword to build a pattern for.
        mode:
            Override stemming mode. Uses ``self.stem_mode`` when *None*.

        Returns
        -------
        str
            Regex pattern string (not yet compiled).
        """
        effective_mode = mode or self.stem_mode
        escaped = _ESCAPED_WHITESPACE_RUN.sub(r"\\s+", re.escape(keyword))

        match effective_mode:
            case StemMode.EXACT:
                return rf"\b{escaped}\b"
            case StemMode.STEM:
                return rf"\b{escaped}(?:{self._suffix_group})?\b"
            case StemMode.PREFIX:
                return rf"\b{escaped}\w*\b"
            case StemMode.SUFFIX:
                return rf"\b\w*{escaped}\b"
            case StemMode.FUZZY:
                return rf"\b\w*{escaped}\w*\b"
            case StemMode.REGEX:
                # Caller is responsible for regex validity
                return keyword
            case _:
                # Fallback for unexpected mode values
                return rf"\b{escaped}\b"

    def generate_stem_variations(self, keyword: str) -> KeywordList:
        """Generate stemmed variations of a keyword for broader matching.

        Detects the root by stripping known suffixes, then expands with all
        configured suffixes.

        Parameters
        ----------
        keyword:
            Source keyword.

        Returns
        -------
        list[str]
            List of variations (always includes the original keyword).

        Examples
        --------
        >>> stemmer = DynamicKeywordStemmer()
        >>> stemmer.generate_stem_variations("ransomware")
        ['ransomware', 'ransomwares']
        """
        variations = [keyword]
        keyword_lower = keyword.lower()

        # Strip trailing suffixes to find the root
        root = keyword_lower
        stripped = False
        for suffix in sorted(self.custom_suffixes, key=len, reverse=True):
            if root.endswith(suffix) and len(root) > len(suffix) + 2:
                root = root[: -len(suffix)]
                stripped = True
                break

        if stripped:
            variations.append(keyword_lower)
        else:
            # Add suffixed variations
            for suffix in self.custom_suffixes:
                candidate = keyword_lower + suffix
                if candidate not in variations:
                    variations.append(candidate)

        return variations

    # -- Compilation ----------------------------------------------------------

    def compile_keywords(self, keywords: list[str]) -> KeywordPattern:
        """Compile all keywords into one logical regex pattern.

        Parameters
        ----------
        keywords:
            Keywords to compile.

        Returns
        -------
        KeywordPattern
            Compiled regex or chunked adapter matching any keyword variation.

        Raises
        ------
        PatternCompileError
            If the final regex fails to compile (should not normally happen).
        """
        if not keywords:
            # Never-match pattern
            return re.compile(r"(?!)")

        # Non-capturing on purpose: with one capturing group per keyword, re's per-branch
        # mark bookkeeping grows with the group count, so matching ~370 keywords was
        # quadratic in the bank (48.6 s of a 62.7 s run on a 19k-word input). Only
        # group(0) is ever read.
        patterns: list[str] = []
        # At one position the first fitting alternative wins, so a keyword listed after its
        # own prefix never matched ("music industry" came back as "music"). REGEX-mode
        # keywords are raw alternatives whose order the caller owns.
        if self.stem_mode is not StemMode.REGEX:
            keywords = sorted(keywords, key=len, reverse=True)
        for kw in keywords:
            pat = self.generate_pattern(kw)
            patterns.append(f"(?:{pat})")

        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            chunks: list[list[str]] = [[]]
            current_len = 0
            for pat in patterns:
                separator_len = 1 if chunks[-1] else 0
                candidate_len = current_len + separator_len + len(pat)
                if chunks[-1] and candidate_len > self.max_pattern_length:
                    chunks.append([pat])
                    current_len = len(pat)
                else:
                    chunks[-1].append(pat)
                    current_len = candidate_len

            compiled = [re.compile("|".join(chunk), flags) for chunk in chunks if chunk]
            if len(compiled) == 1:
                return compiled[0]
            return ChunkedKeywordPattern(compiled)
        except re.error as exc:
            raise PatternCompileError(f"Failed to compile combined pattern: {exc}") from exc

    def compile_keywords_incremental(self, keywords: list[str]) -> KeywordPattern:
        """Compile *keywords*; kept for compatibility, identical to :meth:`compile_keywords`.

        It used to compile only an appended tail as an extra chunk. Overlapping
        chunks then reported matches a fresh compile did not, and every update
        added a chunk that rescanned the text. A full compile of ~500 keywords
        takes ~30 ms, so the bank is always compiled in one go.

        Parameters
        ----------
        keywords:
            Full current keyword list to compile.

        Returns
        -------
        KeywordPattern
            Same result as :meth:`compile_keywords`.
        """
        return self.compile_keywords(keywords)

    def compile_typed_patterns(self, keywords: list[str]) -> TypedPatternDict:
        """Compile keywords into categorized patterns by type heuristic.

        Uses simple heuristics to categorize keywords into
        *technical_terms*, *proper_nouns*, or *general_terms*.

        Parameters
        ----------
        keywords:
            Keywords to categorize and compile.

        Returns
        -------
        dict[str, re.Pattern[str]]
            Mapping from category name to compiled regex.
        """
        technical_terms: KeywordList = []
        proper_nouns: KeywordList = []
        general_terms: KeywordList = []

        for kw in keywords:
            kw_stripped = kw.strip()
            if not kw_stripped:
                continue

            # Heuristic: uppercase / mixed-case short tokens are likely proper nouns
            if kw_stripped.isupper() and len(kw_stripped) <= 6 and " " not in kw_stripped:
                proper_nouns.append(kw_stripped)
            # Heuristic: contains digits, special chars, or is camelCase/PascalCase
            elif (
                any(c.isdigit() for c in kw_stripped)
                or "-" in kw_stripped
                or any(c.isupper() for c in kw_stripped[1:])
            ):
                technical_terms.append(kw_stripped)
            else:
                general_terms.append(kw_stripped)

        result: TypedPatternDict = {}
        if technical_terms:
            result["technical_terms"] = self.compile_keywords(technical_terms)
        if proper_nouns:
            result["proper_nouns"] = self.compile_keywords(proper_nouns)
        if general_terms:
            result["general_terms"] = self.compile_keywords(general_terms)

        return result

    # -- Keyword management ---------------------------------------------------

    def add_keyword(self, keyword: str) -> None:
        """Add a keyword and invalidate caches.

        Parameters
        ----------
        keyword:
            Keyword to add. Duplicates are ignored.
        """
        if keyword not in self._keywords:
            self._keywords.append(keyword)
            self._invalidate_caches()

    def remove_keyword(self, keyword: str) -> None:
        """Remove a keyword and invalidate caches.

        Parameters
        ----------
        keyword:
            Keyword to remove. No-op if not present.
        """
        if keyword in self._keywords:
            self._keywords.remove(keyword)
            self._invalidate_caches()

    def set_keywords(self, keywords: list[str]) -> None:
        """Replace the entire keyword bank and invalidate caches.

        Parameters
        ----------
        keywords:
            New keyword list (replaces existing).
        """
        self._keywords = list(keywords)
        self._invalidate_caches()

    def _invalidate_caches(self) -> None:
        """Clear compiled pattern caches after keyword mutations."""
        self._compiled_master = None
        self._compiled_typed = None
        self._keyword_lookup = None
        self._last_updated = datetime.now(UTC)

    # -- Lazy compiled pattern ------------------------------------------------

    @property
    def compiled_pattern(self) -> KeywordPattern | None:
        """Lazily compiled master pattern -- rebuilt on cache miss."""
        if self._compiled_master is None and self._keywords:
            self._compiled_master = self.compile_keywords(self._keywords)
        return self._compiled_master

    # -- Matching -------------------------------------------------------------

    def find_matches(self, text: str) -> MatchResultList:
        """Find all keyword matches in text with position info.

        Parameters
        ----------
        text:
            Input text to search.

        Returns
        -------
        list[MatchInfo]
            Pydantic *MatchInfo* objects with match, keyword, start, end,
            and stemmed fields.
        """
        if not self._keywords:
            return []

        pattern = self.compiled_pattern
        if pattern is None:
            return []

        results: MatchResultList = []
        seen: set[tuple[int, int]] = set()

        for match in pattern.finditer(text):
            span = match.span()
            if span in seen:
                continue
            seen.add(span)

            matched_text = match.group(0)
            source_keyword = self._resolve_source_keyword(matched_text)
            is_stemmed = (
                source_keyword is not None
                and _normalize_whitespace(matched_text).lower()
                != _normalize_whitespace(source_keyword).lower()
            )

            results.append(
                MatchInfo(
                    match=matched_text,
                    keyword=source_keyword or matched_text,
                    start=span[0],
                    end=span[1],
                    stemmed=is_stemmed,
                )
            )

        return results

    def _get_keyword_lookup(self) -> dict[str, str]:
        """Lazily build a lowercase-keyword -> original-keyword exact-match map.

        First occurrence wins, matching the priority order of the linear scan
        it replaces. Rebuilt on cache miss after any keyword mutation.
        """
        if self._keyword_lookup is None:
            lookup: dict[str, str] = {}
            for kw in self._keywords:
                lookup.setdefault(_normalize_whitespace(kw).lower(), kw)
            self._keyword_lookup = lookup
        return self._keyword_lookup

    def _resolve_source_keyword(self, matched_text: str) -> str | None:
        """Map matched text back to its originating keyword.

        Tries an exact case-insensitive match, then the match minus one
        configured suffix (shortest suffix first), then substring containment
        in either direction. Whitespace runs in *matched_text* are collapsed to
        one space first, since multi-word keywords match across newlines, tabs
        and repeated spaces.

        Parameters
        ----------
        matched_text:
            The text that was matched by the regex.

        Returns
        -------
        str | None
            The originating keyword, or *None* if no mapping found.
        """
        matched_lower = _normalize_whitespace(matched_text).lower()

        # Exact match -- O(1) via lazily-built lookup instead of a linear scan
        lookup = self._get_keyword_lookup()
        exact = lookup.get(matched_lower)
        if exact is not None:
            return exact

        # A STEM match is root + suffix. Substring search alone credited "awards" to an
        # earlier "war" and "video games" to "game".
        for suffix in self._suffixes_shortest_first:
            if suffix and matched_lower.endswith(suffix):
                stemmed = lookup.get(matched_lower[: -len(suffix)])
                if stemmed is not None:
                    return stemmed

        # Fuzzy fallback: reuse the ordered lowercase lookup to avoid re-lowering each keyword.
        for kw_lower, kw in lookup.items():
            if kw_lower in matched_lower or matched_lower in kw_lower:
                return kw

        return None


class KeywordPatternRegistry:
    """Manages keyword-to-pattern mappings with auto-regeneration.

    Bridges static ``REGEX_PATTERNS`` with dynamic keyword stemmer patterns.

    Parameters
    ----------
    static_patterns:
        Pre-built label-to-regex mappings (e.g. CVE patterns).
    stemmer:
        Optional :class:`DynamicKeywordStemmer` for keyword matching.
    """

    def __init__(
        self,
        *,
        static_patterns: dict[str, str] | None = None,
        stemmer: DynamicKeywordStemmer | None = None,
    ) -> None:
        self.static_patterns: RegexPatternDict = dict(static_patterns or {})
        self.stemmer: DynamicKeywordStemmer | None = stemmer
        self._dynamic_patterns: RegexPatternDict = {}
        self._compiled_dynamic: KeywordPattern | None = None
        self._compiled_static_patterns: dict[str, re.Pattern[str]] = {}

    # -- Representation -------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"static={len(self.static_patterns)}, "
            f"dynamic={len(self._dynamic_patterns)}, "
            f"has_stemmer={self.stemmer is not None}"
            f")"
        )

    def __str__(self) -> str:
        return (
            f"KeywordPatternRegistry["
            f"{len(self.static_patterns)} static, "
            f"{len(self._dynamic_patterns)} dynamic]"
        )

    # -- Pattern merging ------------------------------------------------------

    @property
    def all_patterns(self) -> RegexPatternDict:
        """Merge static + dynamic patterns.

        Dynamic patterns take precedence on key collision.
        """
        merged = dict(self.static_patterns)
        merged.update(self._dynamic_patterns)
        return merged

    # -- Dynamic pattern regeneration -----------------------------------------

    def regenerate_dynamic_patterns(self, keywords: list[str]) -> None:
        """Rebuild all dynamic patterns from current keyword list.

        Parameters
        ----------
        keywords:
            Keywords to regenerate patterns for.
        """
        if self.stemmer is None:
            return

        self.stemmer.set_keywords(keywords)

        if keywords:
            compiled_dynamic = self.stemmer.compile_keywords(keywords)
            master_pattern = compiled_dynamic.pattern
            self._dynamic_patterns = {
                PatternLabel.DYNAMIC_KEYWORD: master_pattern,
            }
            self._compiled_dynamic = compiled_dynamic
        else:
            self._dynamic_patterns = {}
            self._compiled_dynamic = None

    # -- Extraction -----------------------------------------------------------

    def extract_all(self, text: str) -> EntityResults:
        """Run all patterns (static + dynamic) and return merged results.

        Static patterns are run individually per label.
        Dynamic matches are grouped under *DYNAMIC_KEYWORD*, with whitespace
        runs collapsed to one space before deduplication so a keyword wrapped
        across lines is reported once, as it would read in prose.

        Parameters
        ----------
        text:
            Input text to extract entities from.

        Returns
        -------
        dict[str, list[str]]
            Mapping from label to deduplicated match strings.
        """
        results: EntityResults = defaultdict(list)

        # Static patterns
        for label, pattern in self.static_patterns.items():
            try:
                compiled = self._compiled_static_patterns.get(pattern)
                if compiled is None:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    self._compiled_static_patterns[pattern] = compiled
                matches = compiled.findall(text)
            except re.error as exc:
                logger.warning("Invalid regex pattern '%s': %s", label, exc)
                continue

            if matches:
                seen: set[str] = set()
                for m in matches:
                    m_str = m if isinstance(m, str) else m[0]
                    if m_str not in seen:
                        results[label].append(m_str)
                        seen.add(m_str)

        # Dynamic keyword patterns
        if self._compiled_dynamic is not None:
            seen_dynamic: set[str] = set()
            for match in self._compiled_dynamic.finditer(text):
                m_str = _normalize_whitespace(match.group(0))
                if m_str not in seen_dynamic:
                    results[PatternLabel.DYNAMIC_KEYWORD].append(m_str)
                    seen_dynamic.add(m_str)

        return dict(results)
