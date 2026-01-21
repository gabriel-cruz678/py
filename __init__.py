========================
UNIQUENESS MUST INCLUDE VISIBILITY FILTER
========================
When a candidate selector matches multiple elements, you MUST attempt to disambiguate using ONLY DOM information.

You MUST prioritize refinements in this order:
1) Add a stable ancestor anchor that is UNIQUE (id / data-test / role / aria-label / title) and scope the selector under it.
2) If multiple elements exist because one is hidden/duplicate, refine using explicit DOM attributes available on the element or its container.
3) ONLY if absolutely necessary and after proving uniqueness, you MAY use :nth-of-type() under a stable parent anchor.

ABSOLUTE RULE:
- You MUST NOT rely on "visibility" as a disambiguation unless the DOM explicitly contains attributes that prove it (e.g., hidden, aria-hidden, style display:none).
- You MUST still verify uniqueness with locator_count after every refinement.
- If you cannot reach count == 1, you MUST return FAIL.
