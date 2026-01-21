if (args.iframeSelector) {
  const frame = page.frameLocator(args.iframeSelector);

  const count = await frame.locator(args.cssSelector).count();
  if (count !== 1) {
    throw new Error(
      `Selector inside iframe is not unique (count=${count}): ${args.cssSelector}`
    );
  }

  await frame.locator(args.cssSelector).click(); // ou fill
  return buildReturn(args, { success: true });
}


const count = await page.locator(args.cssSelector).count();
if (count !== 1) {
  throw new Error(
    `Selector is not unique (count=${count}): ${args.cssSelector}`
  );
}

await page.locator(args.cssSelector).fill(args.value);


