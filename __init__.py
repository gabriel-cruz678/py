import type { FrameLocator, Locator } from "@playwright/test";

const findFrameLocatorContaining = async (cssSelector: string): Promise<FrameLocator | null> => {
  // procura em iframes de 1º nível
  const topCount = await page.locator("iframe").count();

  for (let i = 0; i < topCount; i++) {
    const fl = page.frameLocator("iframe").nth(i);

    // o locator aqui está dentro do frameLocator (igual seu exemplo)
    try {
      const c = await fl.locator(cssSelector).count();
      if (c > 0) return fl;
    } catch {}

    // opcional: procura em iframes aninhados (nested)
    const nested = await fl.locator("iframe").count();
    for (let j = 0; j < nested; j++) {
      const nfl = fl.frameLocator("iframe").nth(j);
      try {
        const c2 = await nfl.locator(cssSelector).count();
        if (c2 > 0) return nfl;
      } catch {}
    }
  }

  return null;
};

const clickLikeFrameLocator = async (loc: Locator) => {
  await loc.waitFor({ state: "attached", timeout: 15000 });
  await loc.waitFor({ state: "visible", timeout: 15000 });

  try { await loc.scrollIntoViewIfNeeded(); } catch {}

  // exatamente como você faz no teste: locator(...).click()
  await loc.click({ timeout: 10000 });
};

locator_click: {
  function: async (args: { cssSelector?: string; elementId?: string; selector?: string; rawCssSelector?: string }) => {
    const finalSelector = args.cssSelector || args.rawCssSelector || args.elementId || args.selector;
    if (!finalSelector) {
      throw new Error("cssSelector is required to locate the element.");
    }

    // 1) tenta achar um frameLocator que contenha o elemento (SEM iframeSelector)
    const frameLocator = await findFrameLocatorContaining(finalSelector);

    if (frameLocator) {
      // 2) clique dentro do FrameLocator (replica seu comportamento)
      await clickLikeFrameLocator(frameLocator.locator(finalSelector).first());
    } else {
      // 3) fallback fora de iframe
      await clickLikeFrameLocator(page.locator(finalSelector).first());
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
