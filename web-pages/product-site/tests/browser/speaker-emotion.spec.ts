import { expect, test } from '@playwright/test';

for (const width of [390, 1440]) {
  for (const language of ['zh', 'en']) {
    test(`Speaker and emotion guide: ${language} ${width}px`, async ({ page, context }, testInfo) => {
      const prefix = language === 'en' ? '/en' : '';
      const title = language === 'en' ? 'Speakers and emotion tags' : '说话人与情感标签';
      const errors: string[] = [];
      page.on('pageerror', error => errors.push(error.message));
      await context.grantPermissions(['clipboard-read', 'clipboard-write']);
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`${prefix}/docs/`);
      await page.locator('[data-doc-search] input').fill(title);
      await page.locator(`.search-results a[href="${prefix}/docs/speaker-emotion.html"]`).click();
      await expect(page.locator('.docs-title h1')).toHaveText(title);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({ path: testInfo.outputPath('initial.png') });
      const checkpoints = page.locator('.docs-article ul').first();
      await expect(checkpoints.locator('li')).toHaveCount(3);
      await checkpoints.scrollIntoViewIfNeeded();
      await page.screenshot({ path: testInfo.outputPath('checkpoints.png') });
      const block = page.locator('.docs-article pre').filter({ hasText: 'def embedding_record' });
      await expect(block).toHaveCount(1);
      const expected = await block.locator('code').innerText();
      await block.locator('button').click();
      expect((await page.evaluate(() => navigator.clipboard.readText())).trim()).toBe(expected.trim());
      await page.screenshot({ path: testInfo.outputPath('code.png') });
      await page.goto(`${prefix}/docs/model-zoo.html`);
      await page.locator(`.docs-article a[href="${prefix}/docs/speaker-emotion.html"]`).click();
      await expect(page).toHaveURL(new RegExp(`${prefix}/docs/speaker-emotion.html$`));
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      expect(errors).toEqual([]);
    });
  }
}
