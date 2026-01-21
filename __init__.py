locator_click: {
  function: async (args: {
    cssSelector?: string;
    iframeSelector?: string;
    elementId?: string;
    selector?: string;
    rawCssSelector?: string;
  }) => {
    const cssSelector =
      args.cssSelector || args.rawCssSelector || args.selector || args.elementId;

    if (!cssSelector) {
      throw new Error("cssSelector is required to locate the element.");
    }

    // 1) Se veio iframeSelector, usa FrameLocator (mesma ideia do seu exemplo funcional)
    if (args.iframeSelector) {
      const iframeLocator = page.frameLocator(args.iframeSelector);
      const locator = iframeLocator.locator(cssSelector).first();

      await locator.waitFor({ state: "attached", timeout: 15000 });
      await locator.waitFor({ state: "visible", timeout: 15000 });
      try { await locator.scrollIntoViewIfNeeded(); } catch {}

      await locator.click({ timeout: 10000 });

      return buildReturn(args, { success: true });
    }

    // 2) Sem iframe: comportamento padrão
    const locator = page.locator(cssSelector).first();

    await locator.waitFor({ state: "attached", timeout: 15000 });
    await locator.waitFor({ state: "visible", timeout: 15000 });
    try { await locator.scrollIntoViewIfNeeded(); } catch {}

    await locator.click({ timeout: 10000 });

    return buildReturn(args, { success: true });
  },

  name: "locator_click",
  description: "Click an element (supports iframe via iframeSelector).",
  parse: (args: string) => {
    return z
      .object({
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
      cssSelector: { type: "string" },
      iframeSelector: { type: "string" },
      elementId: { type: "string" },
      selector: { type: "string" },
      rawCssSelector: { type: "string" },
    },
  },
},
