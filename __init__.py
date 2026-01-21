import type { Frame, Locator } from "@playwright/test";

// 1) acha frame que contém o selector (sem iframeSelector)
const resolveTargetFrame = async (cssSelector: string): Promise<Frame | null> => {
  for (const frame of page.frames()) {
    try {
      const count = await frame.locator(cssSelector).first().count();
      if (count > 0) return frame;
    } catch {}
  }
  return null;
};

// 2) click com fallbacks (selenium-like)
const clickSeleniumLike = async (locFactory: () => Locator) => {
  let loc = locFactory().first();

  await loc.waitFor({ state: "attached", timeout: 15000 });
  await loc.waitFor({ state: "visible", timeout: 15000 });

  // tentativa A: click normal (Playwright)
  try {
    await loc.click({ timeout: 8000 });
    return;
  } catch {}

  // re-resolve (evita stale após re-render)
  loc = locFactory().first();

  // tentativa B: click por coordenada (mais parecido com Selenium)
  try {
    await loc.scrollIntoViewIfNeeded();
  } catch {}

  const box = await loc.boundingBox();
  if (box) {
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    try {
      await page.mouse.click(x, y);
      return;
    } catch {}
  }

  // tentativa C: DOM click (último recurso)
  loc = locFactory().first();
  await loc.evaluate((el: any) => {
    el.click?.();
  });
};

locator_click: {
  function: async (args: { cssSelector?: string; elementId?: string; selector?: string; rawCssSelector?: string }) => {
    const finalSelector = args.cssSelector || args.rawCssSelector || args.elementId || args.selector;
    if (!finalSelector) throw new Error("cssSelector is required to locate the element.");

    const targetFrame = await resolveTargetFrame(finalSelector);

    if (targetFrame) {
      await clickSeleniumLike(() => targetFrame.locator(finalSelector));
    } else {
      await clickSeleniumLike(() => page.locator(finalSelector));
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
