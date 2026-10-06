"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import json
import re

import config
import trace
from tools import search_listings, suggest_outfit, create_fit_card
from generate import generate, ModelUnavailable


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    ─────────────────────────────────────────────────────────────────────────
    TODO — build this, following the branch rule you wrote in Milestone 2.

      1. Start a session with new_session().

      2. Count the times round the loop, and call trace.check_iterations(count)
         on each one before you go again. It raises when the count passes
         MAX_ITERATIONS in config.py — see trace.py.

      3. Parse the query into a description, a size, and a max_price. Regex,
         string splitting, or asking the model are all fine — say which you
         chose in your README. Put the result in session["parsed"].

      4. Call search_listings() with what you parsed.
         Put the results in session["search_results"].

         ⚠️ THIS IS THE BRANCH. If nothing came back:
              - put a message in session["error"] saying what the user could
                change — "No results" is not that message
              - return the session
              - do NOT call suggest_outfit with nothing

      5. Choose an item — the first result is fine. Put it in
         session["selected_item"].

      6. Call suggest_outfit() with the selected item and the wardrobe.
         Put the result in session["outfit_suggestion"].

      7. Call create_fit_card() with the outfit and the item.
         Put the result in session["fit_card"].

      8. Return the session.

    ─────────────────────────────────────────────────────────────────────────
    IN UNIT 4 you come back and add two things:

      • Trace calls. One per step. `trace.step("search_listings", inputs=...,
        returned=...)` — see trace.py. Your README needs the output.

      • A handler for ModelUnavailable, so a bad key produces a message rather
        than a stack trace. The import is already at the top of this file.
    """
    session = new_session(query, wardrobe)
    count = 0

    # Each time round, look at what the session holds and pick the next step
    # from that. Nothing here is called on a fixed schedule — every step is
    # chosen by reading the result of the one before it.
    while True:
        count += 1
        trace.check_iterations(count)

        # Step 3 — nothing parsed yet: parse the query.
        if not session["parsed"]:
            session["parsed"] = parse_query(query)
            continue

        # Step 4 — parsed but not searched yet: search.
        if session["selected_item"] is None and not session["search_results"]:
            parsed = session["parsed"]
            session["search_results"] = search_listings(
                description=parsed["description"],
                size=parsed["size"],
                max_price=parsed["max_price"],
            )

            # ⚠️ THE BRANCH. Empty list → tell the user what to change and stop.
            if not session["search_results"]:
                session["error"] = _no_results_message(parsed)
                return session
            continue

        # Step 5 — results but no pick yet: take the best match.
        if session["selected_item"] is None:
            session["selected_item"] = session["search_results"][0]
            continue

        # Step 6 — item picked but no outfit yet: ask for one.
        if session["outfit_suggestion"] is None:
            session["outfit_suggestion"] = suggest_outfit(
                session["selected_item"], session["wardrobe"]
            )
            continue

        # Step 7 — outfit but no fit card yet: write the caption.
        if session["fit_card"] is None:
            session["fit_card"] = create_fit_card(
                session["outfit_suggestion"], session["selected_item"]
            )
            continue

        # Step 8 — everything is filled in. Done.
        return session


# ── helpers ───────────────────────────────────────────────────────────────────

_PARSE_SYSTEM = (
    "You extract search filters from a shopper's request for second-hand "
    "clothing. Reply with ONLY a JSON object, no prose and no code fences, "
    "with exactly these keys:\n"
    '  "description": the item being looked for, as a few search keywords '
    "(string, never empty)\n"
    '  "size": the size if one is stated, e.g. "M", "S/M", "W30", "US 9" '
    "(string or null)\n"
    '  "max_price": the price ceiling as a number if one is stated '
    "(number or null)\n"
    "Do not invent a size or a price that the request does not mention."
)


def parse_query(query: str) -> dict:
    """
    Turn free text into {"description": str, "size": str | None, "max_price": float | None}.

    Asks the model for a JSON object at temperature 0.0, so the same query
    parses the same way every run. If the model's reply isn't usable JSON,
    fall back to searching the whole query with no filters rather than
    crashing — the search step still gets something sensible to work with.
    """
    raw = generate(f"Request: {query}", system=_PARSE_SYSTEM, temperature=0.0)

    # Strip ```json ... ``` fences if the model added them despite being asked not to.
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)

    try:
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except (json.JSONDecodeError, ValueError):
        return {"description": query.strip(), "size": None, "max_price": None}

    description = str(data.get("description") or "").strip() or query.strip()

    size = data.get("size")
    size = str(size).strip() if size not in (None, "", "null") else None

    max_price = data.get("max_price")
    try:
        max_price = float(max_price) if max_price not in (None, "", "null") else None
    except (TypeError, ValueError):
        max_price = None

    return {"description": description, "size": size, "max_price": max_price}


def _no_results_message(parsed: dict) -> str:
    """Say what the user could change, based on which filters they used."""
    desc = parsed.get("description") or "that"
    filters = []
    if parsed.get("size"):
        filters.append(f"size {parsed['size']}")
    if parsed.get("max_price") is not None:
        filters.append(f"under ${parsed['max_price']:.0f}")

    if filters:
        return (
            f"No listings matched '{desc}' {' '.join(filters)}. "
            f"Try raising the price limit, dropping the size, or using broader "
            f"words for the item (for example 'tee' instead of a specific style)."
        )
    return (
        f"No listings matched '{desc}'. Try different or broader words for the "
        f"item — the listings cover tops, bottoms, outerwear, shoes, and accessories."
    )


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
