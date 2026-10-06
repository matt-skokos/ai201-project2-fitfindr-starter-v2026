"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

All three are stubs right now. They run and they do nothing — that's the
starting position and it's deliberate.

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import re

import config  # noqa: F401 — you'll use this in search_listings
from generate import generate
from utils.data_loader import load_listings


# ── search_listings helpers ───────────────────────────────────────────────────

# Minimal stopword list — just filler words that shouldn't count as a "match"
# on their own. Style words like "vintage" or "oversized" stay in, since those
# are real search signal here.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in",
    "into", "is", "it", "of", "on", "or", "such", "that", "the", "their",
    "then", "there", "these", "they", "this", "to", "was", "will", "with",
    "looking", "want", "need",
})

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    """Lowercase, split into word/number tokens, drop stopwords."""
    return {t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS}


_PAREN_RE = re.compile(r"\([^)]*\)")
_US_SPACE_RE = re.compile(r"\bUS\s+(\d)")


def _size_tokens(raw: str) -> set[str]:
    """
    Normalize a size string into a set of comparable tokens.

    Handles the shapes seen in the data:
      "S/M"                    -> {"S", "M"}
      "W30 L30"                -> {"W30", "L30"}
      "US 8.5"                 -> {"US8.5"}          (keep unit glued to number)
      "One Size (adjustable)"  -> {"ONESIZE"}         (parenthetical dropped)
      "One Size / Oversized"   -> {"ONESIZE", "OVERSIZED"}
      "XL (oversized)"         -> {"XL"}

    Tokens are compared for exact equality, never substring — that's what
    keeps "S" from matching "US8" and "L" from matching "XL".
    """
    if not raw:
        return set()
    s = raw.upper()
    s = _PAREN_RE.sub("", s)
    s = s.replace("ONE SIZE", "ONESIZE")
    s = _US_SPACE_RE.sub(r"US\1", s)
    return {p for p in re.split(r"[\s/]+", s.strip()) if p}


def _sizes_match(query_size: str, listing_size: str) -> bool:
    """A match is any overlap between the two normalized token sets."""
    return bool(_size_tokens(query_size) & _size_tokens(listing_size))


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand. If something you write
    assumes a brand is always there, you will find out in unit 4.

    TODO:
        1. Load every listing with load_listings().
        2. Filter by max_price and by size, when each is provided.
        3. Score what's left by keyword overlap with `description`.
        4. Drop anything scoring zero.
        5. Sort by score, highest first, and return the listing dicts —
           at most config.SEARCH_RESULT_LIMIT of them.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"

    Scoring: a query token matched in `title` or `style_tags` is worth 2
    points, a token matched only in `description` is worth 1 — each query
    token counted once, toward whichever it matched. Title/tags are a more
    deliberate signal of what an item actually is than body text is.

    We don't load a trimmed-down projection of each listing here (just id /
    description / size / price) even though that would save some memory at a
    much larger scale — the title/tag weighting above needs `title` and
    `style_tags` in memory too, and at 40 listings the full dicts
    load_listings() already returns cost nothing to keep around.
    """
    candidates = load_listings()

    if max_price is not None:
        candidates = [c for c in candidates if c["price"] <= max_price]

    if size is not None:
        candidates = [c for c in candidates if _sizes_match(size, c["size"])]

    query_tokens = _tokenize(description)

    scored = []
    for item in candidates:
        title_tag_tokens = _tokenize(item["title"]) | _tokenize(" ".join(item["style_tags"]))
        desc_tokens = _tokenize(item["description"])

        matched_title_tags = query_tokens & title_tag_tokens
        matched_desc_only = (query_tokens & desc_tokens) - matched_title_tags

        score = 2 * len(matched_title_tags) + len(matched_desc_only)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _score, item in scored[: config.SEARCH_RESULT_LIMIT]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** Handle that.

    Returns:
        A non-empty string with outfit suggestions.
        With an empty wardrobe, return general styling advice rather than
        raising or returning "". Unit 4 has you trigger the empty wardrobe on
        purpose, so decide now what it should do.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If it is, ask the model for general styling ideas for this item.
        3. If it isn't, format the wardrobe items into the prompt and ask for
           specific combinations naming pieces the user already owns.
        4. Return the model's response.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    # TODO: replace this with your implementation
    return ""


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe.

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    TODO:
        1. Guard against an empty or whitespace-only `outfit`.
        2. Build a prompt with the item details and the outfit.
        3. Call generate() and return the response.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    # TODO: replace this with your implementation
    return ""
