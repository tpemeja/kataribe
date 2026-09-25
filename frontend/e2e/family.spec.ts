import { execFileSync } from 'node:child_process';

import { expect, test, type APIRequestContext } from '@playwright/test';

/**
 * The family page shows only what the person agreed to share.
 *
 * Tested from the page rather than from the API. Whatever the filtering does
 * upstream, what matters is that nothing private appears on the screen a
 * relative actually opens.
 */
async function seed(request: APIRequestContext, visibility: 'family' | 'private', title: string) {
  const senior = await (
    await request.post('/api/seniors', {
      data: {
        name: '田中ハル',
        name_reading: 'たなかはる',
        birth_year: 1947,
        birthplace: '長野',
        family: [],
        language: 'ja',
      },
    })
  ).json();

  execFileSync(
    'uv',
    [
      'run',
      'python',
      'seed_story.py',
      '--senior-id',
      senior.id,
      '--title',
      title,
      '--summary',
      '父が村で小さな織物の工場をやっていた。',
      '--quote',
      '父は村で小さな織物の工場をやっておりました。',
      '--visibility',
      visibility,
    ],
    { cwd: '../backend' },
  );
  return senior.id as string;
}

test('a shared story reaches the family, with her voice behind it', async ({ page, request }) => {
  const seniorId = await seed(request, 'family', '織物工場のこと');

  await page.goto(`/family/${seniorId}`);

  await expect(page.locator('h1')).toContainText('田中ハル');
  await expect(page.locator('.chapter h2')).toContainText('子供時代');
  await expect(page.locator('.told h3')).toContainText('織物工場のこと');
  await expect(page.locator('.told blockquote')).toContainText('織物の工場');
  // Her own voice one tap away is the whole claim.
  await expect(page.locator('.listen')).toBeVisible();
  await expect(page.locator('.withheld')).toHaveCount(0);
});

test('a story she did not agree to share never appears', async ({ page, request }) => {
  const seniorId = await seed(request, 'private', '話したくないこと');

  await page.goto(`/family/${seniorId}`);

  await expect(page.locator('.withheld')).toContainText('kept private');
  await expect(page.locator('.told')).toHaveCount(0);
  // Not the title, not the summary, not a word of it.
  await expect(page.locator('body')).not.toContainText('話したくないこと');
  await expect(page.locator('body')).not.toContainText('織物');
});
