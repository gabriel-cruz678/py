import { z } from "zod";
import type { Locator, Page } from "playwright";

function looksLikeCssSelector(s: string) {
  const v = s.trim();
  return (
    v.startsWith("#") ||
    v.startsWith(".") ||
    v.startsWith("[") ||
    v.startsWith("button") ||
    v.startsWith("input") ||
    v.startsWith("div") ||
    v.includes(":has-text(") ||
    v.includes(">>") ||
    v.includes(" ")
  );
}

async function findInAllFrames(page: Page, selector: string): Promise<Locator> {
  const sel = selector.trim().replace(/^css[=:]\s*/i, "");

  // main
  const main = page.locator(sel).first();
  if ((await main.count()) > 0) return main;

  // iframes (inclui nested)
  for (const frame of page.frames()) {
    if (frame === page.mainFrame()) continue;
    const loc = frame.locator(sel).first();
    if ((await loc.count()) > 0) return loc;
  }

  throw new Error(`Nenhum elemento encontrado (main/iframes) para: ${selector}`);
}

async function robustClick(locator: Locator, page: Page) {
  // espera existir no DOM
  await locator.waitFor({ state: "attached", timeout: 15000 });

  // se existir overlay/loading comum no seu app, espere sumir (não quebra se não existir)
  try {
    await page
      .locator("app-alert-loading-box, .loading, .spinner, .overlay, [aria-busy='true']")
      .first()
      .waitFor({ state: "detached", timeout: 8000 });
  } catch {}

  // rola pra área
  try {
    await locator.scrollIntoViewIfNeeded();
  } catch {}

  // tentativa 1: click normal
  try {
    await locator.click({ timeout: 10000 });
    return;
  } catch {}

  // tentativa 2: trial (verifica se está “clicável”) e tenta de novo
  try {
    await locator.click({ trial: true, timeout: 3000 });
    await locator.click({ timeout: 10000 });
    return;
  } catch {}

  // tentativa 3: força o click (overlay/efeitos interceptando)
  await locator.click({ force: true, timeout: 10000 });
}

locator_click: {
  function: async (args: { elementId: string }) => {
    // 1) tenta do seu jeito (mantém padrão)
    try {
      const loc = getLocator(args.elementId);
      await robustClick(loc, page);
      return { success: true };
    } catch (e) {
      // 2) fallback: se elementId for CSS selector, tenta em iframes
      if (!looksLikeCssSelector(args.elementId)) {
        throw e;
      }

      const loc = await findInAllFrames(page, args.elementId);
      await robustClick(loc, page);

      return { success: true };
    }
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
