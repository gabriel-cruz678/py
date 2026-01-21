========================
MANDATORY DISAMBIGUATION ALGORITHM (NO EXCEPTIONS)
========================
If locator_count returns count > 1, you MUST refine the selector using ONLY DOM facts.

You MUST follow this exact refinement order until count == 1:

Step 1) Add a UNIQUE parent anchor (preferred)
- Find the closest ancestor that has one of:
  id, data-testid/data-test/data-qa/data-cy, name, aria-label, role, title
- Build: "<parentAnchorSelector> <targetSelector>"
- Re-run locator_count.

Step 2) Add stable attributes from the SAME element
- Add additional attributes that exist on the target element (e.g. type + title + name + placeholder).
- Re-run locator_count.

Step 3) Use component/tag scoping (Angular/Web Components)
- If the element is inside a custom component (e.g. brad-input-text, app-*, brad-*),
  scope under that component using any stable class/attribute on the component.
- Example pattern: "brad-input-text.password input[title='Senha']"
- Re-run locator_count.

Step 4) Only if still ambiguous: structural disambiguation under a stable anchor
- Choose a UNIQUE parent anchor (from Step 1). If you cannot find a UNIQUE anchor, FAIL.
- Use :nth-of-type() ONLY as a last resort and ONLY under that UNIQUE parent anchor.
- Re-run locator_count.

ABSOLUTE STOP RULE:
- If after these steps you cannot reach count == 1, you MUST return FAIL.
- You MUST NEVER return SUCCESS with count != 1.
