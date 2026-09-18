import { test, expect } from '@playwright/test';

for (const width of [390, 1440]) {
  for (const prefix of ['', '/en']) {
    test(`vLLM benchmark cells stay readable at ${width} ${prefix || '/zh'}`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`${prefix}/docs/vllm.html`);
      const table = page.locator('.docs-article table').first();
      await expect(table).toBeVisible();
      const cells = table.locator('th').filter({ hasText: /^(RTFx|CER)$/ });
      await expect(cells).toHaveCount(2);
      for (const cell of await cells.all()) {
        const metrics = await cell.evaluate(node => {
          const range = document.createRange();
          range.selectNodeContents(node);
          return {
            textHeight: range.getBoundingClientRect().height,
            fontSize: parseFloat(getComputedStyle(node).fontSize),
          };
        });
        expect(metrics.textHeight).toBeLessThan(metrics.fontSize * 1.8);
      }
      if (width === 390) {
        const scroll = await table.evaluate(node => {
          node.scrollLeft = node.scrollWidth;
          return { left: node.scrollLeft, width: node.clientWidth, content: node.scrollWidth };
        });
        expect(scroll.content).toBeGreaterThan(scroll.width);
        expect(scroll.left).toBeGreaterThan(0);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({ path: testInfo.outputPath('readable-table.png') });
    });
  }
}
