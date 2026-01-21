const resolveTargetFrame = async (cssSelector: string) => {
  const frames = page.frames();
  let targetFrame: Frame | null = null;

  for (const frame of frames) {
    try {
      const count = await frame.locator(cssSelector).first().count();
      if (count > 0) {
        targetFrame = frame;
        break;
      }
    } catch {}
  }

  return targetFrame;
};

const clickWithFallbacks = async (getFreshLocator: () => Locator) => {
  // Sempre pega locator "novo" (evita stale após re-render)
  let locator = getFreshLocator().first();

  await locator.waitFor({ state: "attached", timeout: 15000 });
  await locator.waitFor({ state: "visible", timeout: 15000 });

  // (1) click padrão
  try {
    await locator.click({ timeout: 8000 });
    return;
  } catch {}

  // Re-resolve (evita stale)
  locator = getFreshLocator().first();

  // (2) click por coordenada (ignora hit-target do locator)
  try {
    await locator.scrollIntoViewIfNeeded();
  } catch {}

  const box = await locator.boundingBox();
  if (box) {
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;

    try {
      await page.mouse.move(x, y);
      await page.mouse.down();
      await page.mouse.up();
      return;
    } catch {}
  }

  // Re-resolve de novo
  locator = getFreshLocator().first();

  // (3) click DOM (último recurso) - ignora interceptação de pointer
  await locator.evaluate((el: any) => {
    try {
      el.click();
      return;
    } catch {}

    el.dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true, view: window }),
    );
  });
};

locator_click: {
  function: async (args: { cssSelector?: string; elementId?: string; selector?: string; rawCssSelector?: string }) => {
    const { cssSelector, rawCssSelector, elementId, selector } = args;

    const finalSelector = cssSelector || rawCssSelector || elementId || selector;
    if (!finalSelector) {
      throw new Error("cssSelector is required to locate the element.");
    }

    const targetFrame = await resolveTargetFrame(finalSelector);

    if (targetFrame) {
      await clickWithFallbacks(() => targetFrame.locator(finalSelector));
    } else {
      await clickWithFallbacks(() => page.locator(finalSelector));
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
