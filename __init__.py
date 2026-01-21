locator_fill: {
  function: async (args: {
    value: string;
    cssSelector?: string;
    iframeSelector?: string;
    elementId?: string;
    selector?: string;
    rawCssSelector?: string;
  }) => {
    const { value } = args;

    const cssSelector =
      args.cssSelector || args.rawCssSelector || args.selector || args.elementId;

    if (!cssSelector) {
      throw new Error("cssSelector is required to locate the element.");
    }

    // 1) Se veio iframeSelector, usa FrameLocator
    if (args.iframeSelector) {
      const iframeLocator = page.frameLocator(args.iframeSelector);
      const locator = iframeLocator.locator(cssSelector).first();

      await locator.waitFor({ state: "attached", timeout: 15000 });
      await locator.waitFor({ state: "visible", timeout: 15000 });
      try { await locator.scrollIntoViewIfNeeded(); } catch {}

      await locator.fill(value, { timeout: 10000 });

      return buildReturn(args, { success: true });
    }

    // 2) Sem iframe: comportamento padrão
    const locator = page.locator(cssSelector).first();

    await locator.waitFor({ state: "attached", timeout: 15000 });
    await locator.waitFor({ state: "visible", timeout: 15000 });
    try { await locator.scrollIntoViewIfNeeded(); } catch {}

    await locator.fill(value, { timeout: 10000 });

    return buildReturn(args, { success: true });
  },

  name: "locator_fill",
  description: "Set a value to the input field (supports iframe via iframeSelector).",
  parse: (args: string) => {
    return z
      .object({
        value: z.string(),
        cssSelector: z.string().optional(),
        iframeSelector: z.string().optional(),
        elementId: z.string().optional(),
        selector: z.string().optional(),
        rawCssSelector: z.string().optional(),
      })
      .refine(
        (d) =>
          !!(d.cssSelector || d.rawCssSelector || d.elementId || d.selector),
        { message: "cssSelector is required." },
      )
      .parse(JSON.parse(args));
  },
  parameters: {
    type: "object",
    properties: {
      value: { type: "string" },
      cssSelector: { type: "string" },
      iframeSelector: { type: "string" },
      elementId: { type: "string" },
      selector: { type: "string" },
      rawCssSelector: { type: "string" },
    },
    required: ["value"],
  },
},
