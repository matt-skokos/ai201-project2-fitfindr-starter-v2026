# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"The agent handles errors"* is an opinion.
*"When search returns nothing, the agent stops before calling the second tool,
in 5 of 5 tries"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter one. A reason that says something about your tools, your loop, or the
data earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

**Two are written for you. You write three.**

---

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:**
The loop requires that two inputs: a wardrobe and a target outfit are present to complete the process. If one or both of these are missing the tool may fail to return a non-empty result. In most cases it should fall back tot he branch that is built in but in other tests where both inputs are empty it may not.

---

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what to change — 5 of 5 tries.

**Why this target:**
This is important because the user is after all searching for items to buy through the thrift. This should return nothing because there's nothing to purchase. 


---

## 3. Something about state
Check that the item id that exists in each tool is the same spanning from search_results() -> selected_item() -> outfit_suggestion() 5/5 times.

**Why this target:**

The model should never swap this item that's returned at first out and it should succeed 5/5 times as it could dilute and skew results.

---

## 4. Something about the fit card
The fit_card that is sent into the model is accurately described and matched with complementing items from the wardrobe. This means that a queried thrift item that is in 'bottoms' does not get paired with another item in category 'bottoms'. This should succeed 4/5 times.

**Why this target:**

This is important because the recommendation would be completely unusable and 'goofy' if the model returns two pairs of pants the user can wear. 4/5 is the target becasuse sometimes there may be a mix up of items that don't "make sense" and that's also a fail.

---

## 5. Your choice

The user cannot query completely irrelevant results from the thrift store. This should fail/return a suitable message that the query is not accepted 5/5 times.

**Why this target:**

This is important because it shows that the tool is focused on returning results that are focused and relevant to the task. It also serves as a way to make sure the model is not prompt hijacked. 5/5 is important for this.


---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
