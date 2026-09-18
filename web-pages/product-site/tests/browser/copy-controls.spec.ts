import { expect, test } from '@playwright/test';

for (const prefix of ['', '/en']) {
  for (const width of [320, 390, 1440]) {
    for (const route of ['/', '/docs/deployment-matrix.html']) {
      test(`copy icon contrast ${prefix || '/zh'} ${route} ${width}`, async ({ page, context }) => {
        await context.grantPermissions(['clipboard-read', 'clipboard-write']);
        await page.setViewportSize({ width, height: 900 });
        await page.goto(prefix + route);
        const button = page.locator('.copy-button, .command-copy').first();
        await button.scrollIntoViewIfNeeded();
        const check = async (state: string) => {
          const style = await button.evaluate(node => ({
            background: getComputedStyle(node).backgroundColor,
            filter: getComputedStyle(node.querySelector('img')!).filter,
          }));
          expect(style.filter).toBe('brightness(0) invert(1)');
          const rgb = style.background.match(/[\d.]+/g)!.map(Number);
          expect(rgb.length === 3 || rgb[3] === 1).toBeTruthy();
          const linear = rgb.slice(0, 3).map(channel => {
            const value = channel / 255;
            return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
          });
          const luminance = linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
          expect(1.05 / (luminance + 0.05), `${state}: ${style.background}`).toBeGreaterThanOrEqual(3);
        };
        await page.mouse.move(0, 0);
        await check('normal');
        await button.focus();
        await expect(button).toBeFocused();
        await check('focus');
        await button.hover();
        await check('hover');
        await button.click();
        await check('copied');
        expect((await page.evaluate(() => navigator.clipboard.readText())).length).toBeGreaterThan(0);
      });
    }
  }
}
