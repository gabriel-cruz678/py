export const getSnapshot = async (page: Page): Promise<{ dom: string }> => {
  const html = await page.content();
  const sanitizedHtml = sanitizeHtml(html);

  const sanitizedIframeHtml = await sanitizeIframeHtml(page); // vai retornar WRAPPERS

  return {
    dom: sanitizedHtml + "\n" + sanitizedIframeHtml,
  };
};


import type { Page, Frame } from "@playwright/test";
import { sanitizeHtml } from "./sanitizeHtml";

const escapeAttr = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const buildIframeSelector = async (frame: Frame): Promise<string | null> => {
  const el = await frame.frameElement().catch(() => null);
  if (!el) return null;

  const id = await el.getAttribute("id");
  if (id) return `iframe#${CSS.escape(id)}`;

  const name = await el.getAttribute("name");
  if (name) return `iframe[name="${escapeAttr(name)}"]`;

  const title = await el.getAttribute("title");
  if (title) return `iframe[title="${escapeAttr(title)}"]`;

  const src = await el.getAttribute("src");
  if (src) {
    // substring curta pra ficar estável
    const part = src.length > 40 ? src.slice(0, 40) : src;
    return `iframe[src*="${escapeAttr(part)}"]`;
  }

  return null;
};

export const sanitizeIframeHtml = async (page: Page): Promise<string> => {
  const frames = page.frames().filter(f => f !== page.mainFrame());
  let out = "";

  for (const frame of frames) {
    // tenta obter seletor do iframe pai
    const iframeSelector = await buildIframeSelector(frame);

    // se não conseguir, ainda assim gera snapshot, mas marca como unknown
    const selectorValue = iframeSelector ?? "UNKNOWN_IFRAME";

    let frameHtml = "";
    try {
      frameHtml = await frame.content();
    } catch {
      continue;
    }

    const sanitized = sanitizeHtml(frameHtml);

    out += `\n<iframe-snapshot data-iframe-selector="${escapeAttr(selectorValue)}">\n`;
    out += sanitized;
    out += `\n</iframe-snapshot>\n`;
  }

  return out;
};
