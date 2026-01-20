VISIBILITY & DUPLICATE RULE (MANDATORY)

If a candidate selector matches more than one element (count > 1), you MUST resolve duplicates in this priority order:

1) Prefer the VISIBLE element.
   - If the framework supports it (Playwright), append :visible to the selector and re-check uniqueness.
   - Example: input[type="password"][title="Senha"]:visible

2) If still not unique, exclude hidden containers by anchoring the selector to a visible parent.
   - Example: div:not([style*="display:none"]) input[...]

3) If still not unique, add additional REAL attributes from the SAME element (id, name, aria-label, placeholder, title, data-testid, etc.)

4) Only as a last resort, use a stable structural selector with a stable parent anchor + nth-of-type.

You MUST NOT return SUCCESS unless locator_count(cssSelector) == 1.
If you cannot reach uniqueness, return FAIL.


SELECTOR PRIORITY UPDATE

When multiple matches exist, always prioritize a selector that targets the VISIBLE element:
- Prefer ":visible" when available in the automation engine.
- Otherwise anchor to a visible parent (e.g., not([style*="display:none"])) before using nth
