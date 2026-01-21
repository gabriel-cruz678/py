import { FrameLocator, Locator } from "@playwright/test";

const findFrameLocatorForSelector = async (
  page: Page,
  cssSelector: string,
  timeout = 15000
): Promise<FrameLocator | null> => {
  const start = Date.now();

  while (Date.now() - start < timeout) {
    const iframeCount = await page.locator("iframe").count();

    for (let i = 0; i < iframeCount; i++) {
      const frameLocator = page.frameLocator("iframe").nth(i);

      try {
        const count = await frameLocator.locator(cssSelector).count();
        if (count > 0) {
          return frameLocator;
        }
      } catch {
        // iframe ainda carregando / navegando
      }
    }

    await page.waitForTimeout(200);
  }

  return null;
};

const clickWithFrameLocator = async (
  page: Page,
  cssSelector: string
) => {
  const frameLocator = await findFrameLocatorForSelector(page, cssSelector);

  if (frameLocator) {
    const locator = frameLocator.locator(cssSelector).first();

    await locator.waitFor({ state: "visible", timeout: 15000 });
    await locator.scrollIntoViewIfNeeded();
    await locator.click({ timeout: 10000 });

    return;
  }

  // fallback: fora de iframe
  const locator = page.locator(cssSelector).first();
  await locator.waitFor({ state: "visible", timeout: 15000 });
  await locator.scrollIntoViewIfNeeded();
  await locator.click({ timeout: 10000 });
};



locator_click: {
  function: async (args: {
    cssSelector?: string;
    rawCssSelector?: string;
    elementId?: string;
    selector?: string;
  }) => {
    const cssSelector =
      args.cssSelector ||
      args.rawCssSelector ||
      args.selector ||
      args.elementId;

    if (!cssSelector) {
      throw new Error("cssSelector is required to locate the element.");
    }

    // >>> AQUI está a ligação com FrameLocator automático
    await clickWithFrameLocator(page, cssSelector);

    return { success: true };
  },

  name: "locator_click",
  description: "Click an element using FrameLocator auto-discovery.",
  parse: (args: string) => {
    return z
      .object({
        cssSelector: z.string().optional(),
        rawCssSelector: z.string().optional(),
        elementId: z.string().optional(),
        selector: z.string().optional(),
      })
      .refine(
        (d) =>
          d.cssSelector ||
          d.rawCssSelector ||
          d.elementId ||
          d.selector,
      )
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
