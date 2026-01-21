import { z } from "zod";
import type { Locator, Page } from "playwright";

function normalizeCssSelector(selector: string) {
  return selector.trim().replace(/^css[=:]\s*/i, "");
}

async function getLocatorAcrossFrames(page: Page, cssSelector: string): Promise<Locator> {
  const sel = normalizeCssSelector(cssSelector);

  // main document
  const main = page.locator(sel).first();
  if ((await main.count()) > 0) return main;

  // all iframes (includes nested frames)
  for (const frame of page.frames()) {
    if (frame === page.mainFrame()) continue;
    const loc = frame.locator(sel).first();
    if ((await loc.count()) > 0) return loc;
  }

  throw new Error(`Nenhum elemento encontrado (main/iframes) para o selector: ${cssSelector}`);
}

async function waitEnabledVisible(locator: Locator, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      if ((await locator.isVisible()) && (await locator.isEnabled())) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error("Elemento encontrado, mas permaneceu invisível ou desabilitado dentro do tempo limite.");
}

async function robustClick(page: Page, locator: Locator) {
  await locator.waitFor({ state: "attached", timeout: 15000 });

  // tenta esperar overlays comuns (não falha se não existir)
  try {
    await page
      .locator("app-alert-loading-box, .loading, .spinner, .overlay, [aria-busy='true']")
      .first()
      .waitFor({ state: "detached", timeout: 8000 });
  } catch {}

  try {
    await locator.scrollIntoViewIfNeeded();
  } catch {}

  await waitEnabledVisible(locator, 15000);

  // 1) normal
  try {
    await locator.click({ timeout: 10000 });
    return;
  } catch {}

  // 2) trial + normal
  try {
    await locator.click({ trial: true, timeout: 3000 });
    await locator.click({ timeout: 10000 });
    return;
  } catch {}

  // 3) force
  await locator.click({ force: true, timeout: 10000 });
}

locator_click: {
  function: async (args: { elementId: string }) => {
    // elementId = CSS selector (sempre)
    const locator = await getLocatorAcrossFrames(page, args.elementId);
    await robustClick(page, locator);

    return { success: true };
  },
  name: "locator_click",
  description: "Click an element.",
  parse: (args: string) => {
    return z
      .object({
        elementId: z.string(),
      })
      .parse(JSON.parse(args));
  },
  parameters: {
    type: "object",
    properties: {
      elementId: {
        type: "string",
      },
    },
  },
},
