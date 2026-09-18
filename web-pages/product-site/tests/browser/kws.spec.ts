import { expect, test } from '@playwright/test';

for (const width of [390, 1440]) {
  for (const language of ['zh', 'en']) {
    test(`KWS guide search and runnable code: ${language} ${width}px`, async ({ page, context }, testInfo) => {
      const prefix = language === 'en' ? '/en' : '';
      const query = language === 'en' ? 'Keyword spotting' : '关键词检测';
      const errors: string[] = [];
      page.on('pageerror', error => errors.push(error.message));
      await context.grantPermissions(['clipboard-read', 'clipboard-write']);
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`${prefix}/docs/`);
      await page.locator('[data-doc-search] input').fill(query);
      await page.locator(`.search-results a[href="${prefix}/docs/keyword-spotting.html"]`).click();
      await expect(page.locator('.docs-title h1')).toHaveText(query);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({ path: testInfo.outputPath('initial.png') });
      const block = page.locator('.docs-article pre').filter({ hasText: 'def detect_stream' });
      await expect(block).toHaveCount(1);
      const expected = await block.locator('code').innerText();
      await block.locator('button').click();
      expect((await page.evaluate(() => navigator.clipboard.readText())).trim()).toBe(expected.trim());
      await page.screenshot({ path: testInfo.outputPath('code.png') });
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      expect(errors).toEqual([]);
    });
  }
}
