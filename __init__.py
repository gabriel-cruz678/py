const resolveTargetFrame = async (cssSelector: string) => {
  const frames = page.frames();
  let targetFrame: any = null;

  for (const frame of frames) {
    try {
      const count = await frame.locator(cssSelector).first().count();
      if (count > 0) {
        targetFrame = frame;
        break;
      }
    } catch {
      // ignora frame não pronto/navegando
    }
  }

  return targetFrame;
};


locator_click: {
  function: async (args: { cssSelector?: string; elementId?: string; selector?: string; rawCssSelector?: string }) => {
    const { cssSelector, elementId, selector, rawCssSelector } = args;

    const finalSelector = cssSelector || rawCssSelector || elementId || selector;
    if (!finalSelector) {
      throw new Error("cssSelector is required to locate the element.");
    }

    const targetFrame = await resolveTargetFrame(finalSelector);

    // mesma estrutura do seu template:
    if (targetFrame) {
      const locator = targetFrame.locator(finalSelector).first();

      // robustez p/ click (overlay, interceptação, efeitos)
      await locator.waitFor({ state: "attached", timeout: 15000 });
      try { await locator.scrollIntoViewIfNeeded(); } catch {}

      // espera ficar visível e habilitado (evita clicar em disabled)
      await locator.waitFor({ state: "visible", timeout: 15000 });
      // isEnabled pode falhar se elemento troca rápido, então é try
      try {
        const start = Date.now();
        while (Date.now() - start < 15000) {
          if (await locator.isEnabled()) break;
          await page.waitForTimeout(200);
        }
      } catch {}

      try {
        await locator.click({ timeout: 10000 });
      } catch {
        // tentativa 2: trial -> click
        try {
          await locator.click({ trial: true, timeout: 3000 });
          await locator.click({ timeout: 10000 });
        } catch {
          // tentativa 3: force (último recurso)
          await locator.click({ force: true, timeout: 10000 });
        }
      }

    } else {
      const locator = page.locator(finalSelector).first();

      await locator.waitFor({ state: "attached", timeout: 15000 });
      try { await locator.scrollIntoViewIfNeeded(); } catch {}
      await locator.waitFor({ state: "visible", timeout: 15000 });

      try {
        const start = Date.now();
        while (Date.now() - start < 15000) {
          if (await locator.isEnabled()) break;
          await page.waitForTimeout(200);
        }
      } catch {}

      try {
        await locator.click({ timeout: 10000 });
      } catch {
        try {
          await locator.click({ trial: true, timeout: 3000 });
          await locator.click({ timeout: 10000 });
        } catch {
          await locator.click({ force: true, timeout: 10000 });
        }
      }
    }

    return buildReturn(args, { success: true });
  },

  name: "locator_click",
  description: "Click an element (CSS selector; supports iframes + open shadow DOM).",
  parse: (args: string) => {
    return z
      .object({
        cssSelector: z.string().optional(),
        rawCssSelector: z.string().optional(),
        elementId: z.string().optional(),
        selector: z.string().optional(),
      })
      .refine(d => !!(d.cssSelector || d.rawCssSelector || d.elementId || d.selector))
      .parse(JSON.parse(args));
  },
  parameters: {
    type: "object",
    properties: {
      cssSelector: { type: "string" },
      rawCssSelector: { type: "string" },
      elementId: { type: "string" },
      selector: { type: "string" },
    },
  },
},

locator_fill: {
  function: async (args: { value: string; cssSelector?: string; elementId?: string; selector?: string; rawCssSelector?: string }) => {
    const finalSelector = args.cssSelector || args.rawCssSelector || args.elementId || args.selector;
    if (!finalSelector) throw new Error("cssSelector is required to locate the element.");

    const targetFrame = await resolveTargetFrame(finalSelector);

    if (targetFrame) {
      const locator = targetFrame.locator(finalSelector).first();
      await locator.fill(args.value);
    } else {
      const locator = page.locator(finalSelector).first();
      await locator.fill(args.value);
    }

    return buildReturn(args, { success: true });
  },
  name: "locator_fill",
  description: "Set a value to the input field.",
  parse: (args: string) => {
    return z.object({
      value: z.string(),
      cssSelector: z.string().optional(),
      rawCssSelector: z.string().optional(),
      elementId: z.string().optional(),
      selector: z.string().optional(),
    })
    .refine(d => !!(d.cssSelector || d.rawCssSelector || d.elementId || d.selector))
    .parse(JSON.parse(args));
  },
  parameters: {
    type: "object",
    properties: {
      value: { type: "string" },
      cssSelector: { type: "string" },
      rawCssSelector: { type: "string" },
      elementId: { type: "string" },
      selector: { type: "string" },
    },
    required: ["value"],
  },
},


