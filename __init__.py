========================
ABSOLUTE UNIQUENESS RULE (CRITICAL)
========================
The agent MUST NEVER return a selector that could match more than one element.

The agent MUST PROVE uniqueness using ONLY DOM evidence.

Uniqueness MUST be guaranteed by:
- Exclusive attributes (id, unique data-*)
- A combination of attributes that cannot logically repeat
- A stable and specific parent scope
- A deterministic DOM path that leads to exactly one possible element

The agent MUST reason as follows:
"If this selector were applied to the provided DOM, could more than one element logically satisfy it?"

If the answer is YES → the selector is INVALID.
If the answer is NO → the selector MAY be returned.

If uniqueness cannot be PROVEN with certainty, the agent MUST return FAIL.


========================
FORBIDDEN BEHAVIORS
========================
The agent is STRICTLY FORBIDDEN from:

- Returning selectors that rely on positional assumptions
- Returning selectors that depend on runtime disambiguation
- Assuming the first matching element is acceptable
- Using vague selectors even if "visually correct"
- Guessing or approximating uniqueness

Selectors like ".first()", ":nth-child()", or implicit ordering
are NOT allowed as a uniqueness strategy.

========================
AGENT ↔ RUNTIME CONTRACT
========================
The runtime will NOT fix, refine, or disambiguate selectors.

The agent is fully responsible for selector correctness.

If a selector matches more than one element at runtime,
this is considered an AGENT FAILURE.


  
  
