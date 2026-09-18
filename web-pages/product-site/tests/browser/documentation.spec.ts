import { expect, test } from '@playwright/test';

for (const prefix of ['', '/en']) {
  for (const width of [320, 390, 1440]) {
    for (const slug of ['gradio', 'kubernetes']) {
      test(`Service guide ${slug} ${prefix || '/zh'} ${width}`, async ({ page, context }) => {
        await context.grantPermissions(['clipboard-read', 'clipboard-write']);
        await page.setViewportSize({ width, height: 900 });
        const errors: string[] = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${prefix}/docs/`);
        await page.locator('[data-doc-search] input').fill(slug === 'gradio' ? 'Gradio' : 'Kubernetes');
        const route = `${prefix}/docs/${slug}.html`;
        await page.locator(`.search-results a[href="${route}"]`).click();
        await expect(page).toHaveURL(new RegExp(`${route}$`));
        await expect(page.locator('.docs-article')).toBeVisible();
        expect((await page.locator('.docs-title h1').boundingBox())!.y).toBeLessThan(450);
        await page.screenshot({ path: `/tmp/funasr-kubernetes-docs-evidence-20260908/${slug}-${prefix ? 'en' : 'zh'}-${width}-top.png` });
        const block = page.locator('.docs-article pre').first();
        const expected = await block.locator('code').innerText();
        await block.locator('button').click();
        expect((await page.evaluate(() => navigator.clipboard.readText())).trim()).toBe(expected.trim());
        for (const heading of await page.locator('.docs-article h2, .docs-article h3').all()) {
          await heading.scrollIntoViewIfNeeded();
          expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
        }
        if (slug === 'gradio') {
          await expect(page.locator('.docs-article h2')).toHaveCount(5);
          await page.goto(`${prefix}/docs/http-server.html`);
          await page.locator(`.docs-article a[href="${route}"]`).first().click();
          await expect(page).toHaveURL(new RegExp(`${route}$`));
        } else {
          const moss = page.locator('.docs-article h3').filter({ hasText: 'MOSS GPU' });
          await moss.scrollIntoViewIfNeeded();
          await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
          await page.screenshot({ path: `/tmp/funasr-kubernetes-docs-evidence-20260908/kubernetes-${prefix ? 'en' : 'zh'}-${width}-moss.png` });
        }
        await page.locator(`.docs-article a[href="${prefix}/docs/security.html"]`).click();
        await expect(page).toHaveURL(new RegExp(`${prefix}/docs/security.html$`));
        await page.goto(route);
        const peer = `${prefix ? '' : '/en'}/docs/${slug}.html`;
        await page.locator(`a[href="${peer}"]`).first().click();
        await expect(page).toHaveURL(new RegExp(`${peer}$`));
        expect(errors).toEqual([]);
      });
    }
  }
}

for (const language of ['ja', 'ko']) {
  for (const filename of ['agent', 'benchmark']) {
    for (const width of [390, 1440]) {
      test(`Localized Pages ${language}/${filename} ${width}`, async ({ page, context }) => {
        await context.grantPermissions(['clipboard-read', 'clipboard-write']);
        await page.setViewportSize({ width, height: 900 });
        const errors: string[] = [];
        page.on('pageerror', error => errors.push(error.message));
        const response = await page.goto(`/__pages/${language}/${filename}.html`);
        expect(response!.status()).toBe(200);
        await expect(page.locator('html')).toHaveAttribute('lang', language);
        await expect(page.locator('link[rel=canonical]')).toHaveAttribute('href',
          `https://modelscope.github.io/FunASR/${language}/${filename}.html`);
        expect((await page.locator('.docs-title h1').boundingBox())!.y).toBeLessThan(450);
        await page.screenshot({ path: `/tmp/funasr-ja-ko-docs-evidence-20260907/${language}-${filename}-${width}-top.png` });
        const ids = filename === 'benchmark' ? ['summary', 'table', 'method', 'choose'] :
          (language === 'ja' ? ['server', 'sdk', 'mcp', 'voice', 'subtitle'] : ['server', 'sdk', 'workflows', 'mcp', 'voice', 'subtitle']);
        for (const id of ids) {
          await expect(page.locator(`[id="${id}"]`)).toHaveCount(1);
          await page.evaluate(fragment => { location.hash = fragment; }, id);
          expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
        }
        const block = page.locator('.docs-article pre').first();
        const expected = await block.locator('code').innerText();
        await block.locator('button').click();
        expect((await page.evaluate(() => navigator.clipboard.readText())).trim()).toBe(expected.trim());
        if (filename === 'benchmark') {
          await expect(page.locator('.docs-article table')).toHaveCount(3);
          const notes = page.locator('.docs-article table').nth(1).locator('td:nth-child(6)');
          expect(await notes.evaluateAll(nodes => nodes.every(node =>
            node.getBoundingClientRect().width >= 260 && node.parentElement!.getBoundingClientRect().height < 240))).toBeTruthy();
          for (const table of await page.locator('.docs-article table').all()) {
            await table.locator('tr').last().locator('td').last().scrollIntoViewIfNeeded();
            expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
          }
        }
        await page.screenshot({ path: `/tmp/funasr-ja-ko-docs-evidence-20260907/${language}-${filename}-${width}.png`, fullPage: true });
        await page.locator('[data-peer-link]').click();
        await expect(page).toHaveURL(new RegExp(`/__pages/${language === 'ja' ? 'ko' : 'ja'}/${filename}.html$`));
        expect(errors).toEqual([]);
      });
    }
  }
}

test('mobile topic navigation leaves the article in the first viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/docs/training.html');
  const menu = page.locator('.docs-navigation');
  await expect(menu).not.toHaveAttribute('open', '');
  expect((await page.locator('.docs-title h1').boundingBox())!.y).toBeLessThan(300);
  await menu.locator(':scope > summary').press('Enter');
  await expect(menu).toHaveAttribute('open', '');
  await menu.locator('details').filter({ hasText: '训练与扩展' }).locator('summary').click();
  await page.locator('.docs-sidebar a[href="/docs/model-registration.html"]').click();
  await expect(page).toHaveURL(/model-registration.html$/);
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.locator('.docs-navigation')).toHaveAttribute('open', '');
  await expect(page.locator('.docs-sidebar summary').filter({ hasText: '训练与扩展' })).toBeVisible();
});

for (const width of [320, 768, 1440]) {
  test(`expanded documentation journey fits ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const slug of ['installation', 'quickstart', 'python-api', 'model-zoo', 'training', 'model-registration', 'runtime-guide', 'service-api', 'security', 'kubernetes']) {
      await page.goto(`/docs/${slug}.html`, { waitUntil: 'domcontentloaded' });
      await expect(page.locator('.docs-article')).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), slug).toBeLessThanOrEqual(1);
      await expect(page.locator('.docs-toc a').first()).toHaveAttribute('href', /^#/);
    }
    expect(errors).toEqual([]);
  });
}

test('SDK, training and Model Zoo are discoverable through search', async ({ page }) => {
  for (const [query, slug] of [['AutoModel', 'python-api'], ['Model Zoo', 'model-zoo'], ['fine-tuning', 'training']]) {
    await page.goto('/en/docs/');
    await page.locator('[data-doc-search] input').fill(query);
    await expect(page.locator(`.search-results a[href="/en/docs/${slug}.html"]`)).toBeVisible();
  }
});

for (const width of [320, 390, 768, 1440, 1920]) {
  test(`documentation and legacy layouts fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const route of ['/docs/', '/en/docs/', '/docs/moss-transcribe-diarize.html', '/models.html', '/blog/', '/donors.html']) {
      await page.goto(route);
      await expect(page.locator('[data-primary-nav]')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    }
    expect(errors).toEqual([]);
  });
}

test('search is bilingual, keyboard accessible, and handles missing results', async ({ page }) => {
  for (const prefix of ['', '/en']) {
    await page.goto(`${prefix}/docs/`);
    const query = page.locator('[data-doc-search] input');
    await query.fill('MOSS');
    const first = page.locator('.search-results a').first();
    await expect(first).toBeVisible();
    await query.press('ArrowDown');
    await expect(first).toBeFocused();
    await expect(first).toHaveAttribute('href', new RegExp(`^${prefix}/`));
    await query.fill('zzzz-no-document-match-48291');
    await expect(page.locator('.search-results')).toContainText(prefix ? 'No matching documents' : '没有找到');
  }
});

test('source-derived code copies cleanly and legacy menu closes with Escape', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/docs/moss-transcribe-diarize.html');
  const block = page.locator('.docs-article pre').first();
  const expected = await block.locator('code').innerText();
  await block.locator('button').click();
  expect((await page.evaluate(() => navigator.clipboard.readText())).trim()).toBe(expected.trim());
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/models.html');
  const menu = page.locator('[data-menu-toggle]');
  await menu.press('Enter');
  await expect(menu).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
});

test('public speech sample is playable and waveform has actual pixels', async ({ page }) => {
  await page.goto('/');
  await expect.poll(() => page.locator('audio').evaluate((audio: HTMLAudioElement) => audio.duration)).toBeGreaterThan(5);
  await page.locator('audio').evaluate((audio: HTMLAudioElement) => audio.play());
  await expect.poll(() => page.locator('audio').evaluate((audio: HTMLAudioElement) => audio.currentTime)).toBeGreaterThan(0);
  await page.locator('audio').evaluate((audio: HTMLAudioElement) => audio.pause());
  expect(await page.locator('.hero-image').evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(1000);
});

for (const prefix of ['', '/en']) {
  for (const width of [390, 1440]) {
    test(`Historical ASR benchmark is discoverable and readable ${prefix || '/zh'} ${width}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      const errors: string[] = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(`${prefix}/docs/`);
      await page.locator('[data-doc-search] input').fill(prefix ? 'Historical ASR' : '历史 ASR');
      const route = `${prefix}/docs/historical-asr-benchmark.html`;
      await page.locator(`.search-results a[href="${route}"]`).click();
      await expect(page).toHaveURL(new RegExp(`${route}$`));
      await expect(page.locator('.docs-article h2')).toHaveCount(4);
      await expect(page.locator('.docs-article table')).toHaveCount(3);
      const results = page.locator('.docs-article table').nth(1);
      await expect(results.locator('tr')).toHaveCount(10);
      const notes = await results.locator('td:nth-child(6)').evaluateAll(nodes => nodes.map(node => ({
        width: node.getBoundingClientRect().width,
        rowHeight: node.parentElement!.getBoundingClientRect().height,
      })));
      expect(notes.every(note => note.width >= 260 && note.rowHeight < 240)).toBeTruthy();
      const cell = results.locator('td').filter({ hasText: /^0\.005896$/ });
      await cell.scrollIntoViewIfNeeded();
      const numberHeight = await cell.evaluate(node => {
        const range = document.createRange();
        range.selectNodeContents(node);
        return range.getBoundingClientRect().height;
      });
      expect(numberHeight).toBeLessThan(32);
      for (const table of await page.locator('.docs-article table').all()) {
        await table.scrollIntoViewIfNeeded();
        expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      }
      const peer = `${prefix ? '' : '/en'}/docs/historical-asr-benchmark.html`;
      await page.locator(`.docs-article a[href="${peer}"]`).click();
      await expect(page).toHaveURL(new RegExp(`${peer}$`));
      expect(errors).toEqual([]);
    });
  }
}

for (const prefix of ['', '/en']) {
  for (const width of [390, 1440]) {
    test(`Agent integration is discoverable and readable ${prefix || '/zh'} ${width}`, async ({ page, context }) => {
      await context.grantPermissions(['clipboard-read', 'clipboard-write']);
      await page.setViewportSize({ width, height: 900 });
      const errors: string[] = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(`${prefix}/docs/`);
      await page.locator('[data-doc-search] input').fill('Agent');
      const route = `${prefix}/docs/agent-integration.html`;
      await page.locator(`.search-results a[href="${route}"]`).click();
      await expect(page).toHaveURL(new RegExp(`${route}$`));
      await expect(page.locator('[data-source-link]')).toHaveAttribute('href',
        new RegExp(`/docs/agent_integration${prefix ? '' : '_zh'}.md$`));
      await expect(page.locator('.docs-article h2')).toHaveCount(6);
      const block = page.locator('.docs-article pre').first();
      const expected = await block.locator('code').innerText();
      await block.locator('button').click();
      expect((await page.evaluate(() => navigator.clipboard.readText())).trim()).toBe(expected.trim());
      for (const heading of await page.locator('.docs-article h2').all()) {
        await heading.scrollIntoViewIfNeeded();
        expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      }
      const token = page.locator('.docs-article p code').filter({ hasText: 'verbose_json' }).first();
      await expect(token).toBeVisible();
      expect((await token.boundingBox())!.height).toBeLessThan(40);
      const peer = `${prefix ? '' : '/en'}/docs/agent-integration.html`;
      await page.locator(`.docs-article a[href="${peer}"]`).click();
      await expect(page).toHaveURL(new RegExp(`${peer}$`));
      expect(errors).toEqual([]);
    });
  }
}
