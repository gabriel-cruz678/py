import { FrameLocator, Locator, Page } from "@playwright/test";

async function findFrameLocatorForSelector(
  page: Page,
  cssSelector: string,
  timeout = 15000
): Promise<FrameLocator | null> {

  const iframeCount = await page.locator("iframe").count();
  const start = Date.now();

  while (Date.now() - start < timeout) {
    for (let i = 0; i < iframeCount; i++) {
      const frameLocator = page.frameLocator("iframe").nth(i);

      try {
        const count = await frameLocator.locator(cssSelector).count();
        if (count > 0) {
          return frameLocator;
        }
      } catch {
        // iframe ainda carregando, ignora
      }
    }

    // aguarda re-render Angular / SPA
    await page.waitForTimeout(200);
  }

  return null;
}

async function clickUsingAutoFrameLocator(
  page: Page,
  cssSelector: string
) {
  // 1) tenta achar o FrameLocator certo
  const frameLocator = await findFrameLocatorForSelector(page, cssSelector);

  if (frameLocator) {
    const locator = frameLocator.locator(cssSelector).first();

    await locator.waitFor({ state: "visible", timeout: 15000 });
    await locator.scrollIntoViewIfNeeded();
    await locator.click({ timeout: 10000 });

    return;
  }

  // 2) fallback: fora de iframe
  const locator = page.locator(cssSelector).first();
  await locator.waitFor({ state: "visible", timeout: 15000 });
  await locator.scrollIntoViewIfNeeded();
  await locator.click({ timeout: 10000 });
}

