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

import random
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


# ── suggest_outfit helpers ────────────────────────────────────────────────────

def _style_signal(item: dict) -> set[str]:
    """Lowercase colors + style_tags as one signal set, for complement scoring."""
    colors = item.get("colors") or []
    tags = item.get("style_tags") or []
    return {s.lower() for s in (*colors, *tags)}


def _complement_score(new_item: dict, candidate: dict) -> int:
    """How much a candidate's colors/style_tags overlap with the new item's."""
    return len(_style_signal(new_item) & _style_signal(candidate))


def _pick_complementary_wardrobe_items(new_item: dict, wardrobe_items: list[dict]) -> dict:
    """
    One best-scoring wardrobe item per category other than new_item's own.

    This is the structural guard against "2 bottoms" style outfits: at most
    one candidate per category ever reaches the model, so there's never a
    second item of the same category in context for it to combine. Ties go to
    whichever item appears first in the wardrobe list.
    """
    new_category = new_item.get("category")
    by_category: dict[str, list[dict]] = {}
    for item in wardrobe_items:
        category = item.get("category")
        if not category or category == new_category:
            continue
        by_category.setdefault(category, []).append(item)

    return {
        category: max(candidates, key=lambda c: _complement_score(new_item, c))
        for category, candidates in by_category.items()
    }


def _random_complementary_thrift_items(new_item: dict) -> dict:
    """
    1-2 random thrift listings for when the wardrobe is empty, so the advice
    still names real pieces instead of staying purely abstract.

    Each pick is from a different category than the new item, and from each
    other — the same one-per-category guard as the wardrobe path, just with a
    random choice inside each category instead of a style-scored one.
    """
    pool = [
        listing
        for listing in load_listings()
        if listing["id"] != new_item.get("id")
        and listing["category"] != new_item.get("category")
    ]
    by_category: dict[str, list[dict]] = {}
    for listing in pool:
        by_category.setdefault(listing["category"], []).append(listing)

    categories = list(by_category.keys())
    if not categories:
        return {}

    chosen_categories = random.sample(categories, k=min(2, len(categories)))
    return {category: random.choice(by_category[category]) for category in chosen_categories}


def _describe_item(item: dict) -> str:
    name = item.get("title") or item.get("name") or "this piece"
    colors = ", ".join(item.get("colors") or []) or "unspecified"
    tags = ", ".join(item.get("style_tags") or []) or "unspecified"
    return f"{name} (colors: {colors}; style: {tags})"


_SUGGEST_SYSTEM = (
    "You are a thrift-shopping stylist. You will be given one item someone is "
    "considering, and a short list of specific complementary pieces, at most "
    "one per clothing category. Write 1-2 short outfit suggestions using ONLY "
    "the pieces listed by name — never invent a piece that wasn't given to "
    "you, and never pair two pieces from the same category together. Be "
    "specific and conversational, like a friend giving real styling advice, "
    "not a product description."
)


def _suggest_from_pieces(new_item: dict, picks: dict, closet_framing: bool) -> str:
    """Ask the model for 1-2 outfits combining new_item with the given picks."""
    new_desc = _describe_item(new_item)
    pieces_lines = "\n".join(
        f"- [{category}] {_describe_item(item)}" for category, item in picks.items()
    )
    if closet_framing:
        prompt = (
            f"New piece they're considering:\n{new_desc}\n\n"
            f"Pieces already in their closet that pair with it:\n{pieces_lines}\n\n"
            "Suggest 1-2 outfits that combine the new piece with one or more "
            "of these closet pieces. Name the specific pieces."
        )
    else:
        prompt = (
            f"New piece they're considering, for a closet that's currently "
            f"empty:\n{new_desc}\n\n"
            f"Other pieces from the same thrift listings that would pair well "
            f"with it:\n{pieces_lines}\n\n"
            "Suggest 1-2 starting outfits that combine the new piece with one "
            "or more of these pieces. Name the specific pieces."
        )
    return generate(prompt, system=_SUGGEST_SYSTEM)


def _general_styling_advice(new_item: dict) -> str:
    """Advice for the new item alone, when there's nothing to pair it with."""
    prompt = (
        f"They're considering this piece and have nothing specific to pair it "
        f"with right now:\n{_describe_item(new_item)}\n\n"
        "Give general styling advice for it on its own: what kind of pieces "
        "would complement it, what vibe it leans toward, how to wear it."
    )
    return generate(prompt, system=_SUGGEST_SYSTEM)


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

    Design (no mismatched outfits, e.g. never 2 bottoms or 2 hoodies):
        Rather than handing the model the whole wardrobe and trusting a
        prompt instruction to keep categories straight, the candidate pieces
        are curated in code first: at most one item per category other than
        new_item's own category ever reaches the model. That's a structural
        guarantee, not a hope — there's physically only one candidate per
        category in the prompt, so the model can't combine two of the same
        kind even if it tried.

        - Non-empty wardrobe: pick the best style/color-overlap match per
          category (_pick_complementary_wardrobe_items), ask the model to
          combine new_item with those specific closet pieces.
        - Empty wardrobe, or a wardrobe with nothing outside new_item's own
          category: grab 1-2 random listings from the thrift data itself,
          one per category, as a starting-closet idea
          (_random_complementary_thrift_items) — still real, specific pieces,
          not just abstract advice.
        - Wardrobe non-empty but truly nothing to pair with it (every item is
          the same category as new_item): fall back to general styling advice
          for the new item alone.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    items = wardrobe.get("items") or []

    if items:
        picks = _pick_complementary_wardrobe_items(new_item, items)
        if picks:
            return _suggest_from_pieces(new_item, picks, closet_framing=True)
        return _general_styling_advice(new_item)

    picks = _random_complementary_thrift_items(new_item)
    if picks:
        return _suggest_from_pieces(new_item, picks, closet_framing=False)
    return _general_styling_advice(new_item)


def _format_price(price) -> str:
    """$38 for a whole-dollar price, $38.50 if it's ever fractional."""
    if price is None:
        return "an unlisted price"
    price = float(price)
    return f"${int(price)}" if price.is_integer() else f"${price:.2f}"


_FIT_CARD_SYSTEM = (
    "You write short social-media captions for secondhand clothing finds — "
    "the kind someone would actually post next to a photo of the item. Write "
    "2 to 4 sentences. Mention the item once, its price once, and the "
    "platform it's from once — never repeat any of those three. Be specific "
    "about the vibe and how it fits into the outfit, not a product "
    "description. Sound like a real person posting, not an ad."
)


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

    Neither is touched here — config.TEMPERATURE is already 0.9 (chosen with
    this tool in mind), and generate() already falls back to it. Passing a
    temperature or cache override from inside this function would just fight
    the one-place-to-change-it design of config.py.

    TODO:
        1. Guard against an empty or whitespace-only `outfit`.
        2. Build a prompt with the item details and the outfit.
        3. Call generate() and return the response.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    if not outfit or not outfit.strip():
        title = new_item.get("title") or "this item"
        return f"No caption yet — there's no outfit to build one around for {title}."

    prompt = (
        f"The item: {_describe_item(new_item)}, priced at "
        f"{_format_price(new_item.get('price'))} on {new_item.get('platform')}.\n\n"
        f"The outfit idea for it:\n{outfit}\n\n"
        "Write the caption now."
    )
    return generate(prompt, system=_FIT_CARD_SYSTEM)
