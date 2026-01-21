const origin = new URL("").origin;

// geolocation prompt
await page.context().grantPermissions(["geolocation"], { origin });

// se o site usa localização real, opcional:
await page.context().setGeolocation({ latitude: -23.5505, longitude: -46.6333 });

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
    } catch {}
  }
  return targetFrame;
};

const dismissNativePromptsBestEffort = async () => {
  // Fecha bubble nativa do Chrome (geolocation etc.)
  try {
    await page.keyboard.press("Escape");
    await page.waitForTimeout(150);
    await page.keyboard.press("Escape");
  } catch {}

  // Tenta conceder permissão (se for o caso)
  try {
    const origin = new URL(page.url()).origin;
    await page.context().grantPermissions(["geolocation"], { origin });
  } catch {}
};

const waitAppOverlaysBestEffort = async () => {
  try {
    await page
      .locator("app-alert-loading-box, .loading, .spinner, .overlay, [aria-busy='true']")
      .first()
      .waitFor({ state: "detached", timeout: 8000 });
  } catch {}
};

const robustClickLikeYourTemplate = async (loc: any) => {
  await loc.waitFor({ state: "attached", timeout: 15000 });
  await waitAppOverlaysBestEffort();

  try { await loc.scrollIntoViewIfNeeded(); } catch {}
  await loc.waitFor({ state: "visible", timeout: 15000 });

  // tenta esperar habilitar (sem travar se flutuar)
  try {
    const start = Date.now();
    while (Date.now() - start < 15000) {
      if (await loc.isEnabled()) break;
      await page.waitForTimeout(200);
    }
  } catch {}

  // 1) normal
  try {
    await loc.click({ timeout: 10000 });
    return;
  } catch {}

  // 2) fecha prompt nativo + tenta de novo
  await dismissNativePromptsBestEffort();
  await waitAppOverlaysBestEffort();

  try {
    await loc.click({ timeout: 10000 });
    return;
  } catch {}

  // 3) trial -> click
  try {
    await loc.click({ trial: true, timeout: 3000 });
    await loc.click({ timeout: 10000 });
    return;
  } catch {}

  // 4) force
  try {
    await loc.click({ force: true, timeout: 10000 });
    return;
  } catch {}

  // 5) ÚLTIMO recurso: dispara evento click no DOM (quando há interceptação “impossível”)
  await loc.evaluate((el: any) => {
    el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
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
      const loc = targetFrame.locator(finalSelector).first();
      await robustClickLikeYourTemplate(loc);
    } else {
      const loc = page.locator(finalSelector).first();
      await robustClickLikeYourTemplate(loc);
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
