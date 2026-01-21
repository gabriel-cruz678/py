locator_fill: {
  function: async (args: {
    value: string;
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
    if (args.value === undefined) {
      throw new Error("value is required.");
    }

    const timeout = 15000;

    const doFill = async (locator: import("@playwright/test").Locator) => {
      // tenta o caminho ideal
      try {
        await locator.waitFor({ state: "attached", timeout });
        await locator.scrollIntoViewIfNeeded().catch(() => {});
        await locator.fill(args.value, { timeout });
        return;
      } catch {
        // fallback estilo Selenium: focar + digitar via teclado
        await locator.waitFor({ state: "attached", timeout });
        await locator.scrollIntoViewIfNeeded().catch(() => {});
        await locator.click({ timeout, force: true });

        // limpa e digita
        await page.keyboard.press(process.platform === "darwin" ? "Meta+A" : "Control+A");
        await page.keyboard.type(args.value);
      }
    };

    // 1) Com iframeSelector: usa FrameLocator (igual ao seu exemplo que funciona)
    if (args.iframeSelector) {
      // garante que o iframe existe/está anexado
      await page.locator(args.iframeSelector).first().waitFor({ state: "attached", timeout });

      const locator = page
        .frameLocator(args.iframeSelector)
        .locator(cssSelector)
        .first();

      await doFill(locator);
      return buildReturn(args, { success: true });
    }

    // 2) Sem iframe: padrão
    const locator = page.locator(cssSelector).first();
    await doFill(locator);

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
        (d) => !!(d.cssSelector || d.rawCssSelector || d.elementId || d.selector),
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
