import type { Frame } from "@playwright/test";

const resolveTargetFrame = async (cssSelector: string): Promise<Frame | null> => {
  const frames = page.frames();

  for (const frame of frames) {
    try {
      // Usa Locator (não frame.$) porque é mais consistente e suporta shadow open
      const count = await frame.locator(cssSelector).count();
      if (count > 0) return frame;
    } catch {
      // frame pode estar navegando/indisponível momentaneamente
    }
  }

  return null;
};

locator_click: {
  function: async (args: { cssSelector?: string; elementId?: string; selector?: string; rawCssSelector?: string }) => {
    const finalSelector = args.cssSelector || args.rawCssSelector || args.elementId || args.selector;
    if (!finalSelector) {
      throw new Error("cssSelector is required to locate the element.");
    }

    const targetFrame = await resolveTargetFrame(finalSelector);

    if (targetFrame) {
      // >>> AQUI é o equivalente ao seu: frameLocator(...).locator(...).click()
      const locator = targetFrame.locator(finalSelector).first();

      await locator.waitFor({ state: "attached", timeout: 15000 });
      await locator.waitFor({ state: "visible", timeout: 15000 });

      // garante viewport
      try { await locator.scrollIntoViewIfNeeded(); } catch {}

      await locator.click({ timeout: 10000 });
    } else {
      // fallback: fora de iframe
      const locator = page.locator(finalSelector).first();

      await locator.waitFor({ state: "attached", timeout: 15000 });
      await locator.waitFor({ state: "visible", timeout: 15000 });
      try { await locator.scrollIntoViewIfNeeded(); } catch {}

      await locator.click({ timeout: 10000 });
    }

    return buildReturn(args, { success: true });
  },

  name: "locator_click",
  description: "Click an element.",
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
