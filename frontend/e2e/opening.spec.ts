import { expect, test } from '@playwright/test';

import { addPerson } from './people';

/** Nobody should have to work out that they are meant to speak first — least of
 *  all someone sitting in front of a device they did not ask for. */
test('the interviewer speaks first, before anyone has said anything', async ({ page, context }) => {
  test.setTimeout(120_000);

  // A microphone that hears nothing at all. If the interviewer only ever
  // replies, this session stays silent forever.
  await context.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      const ctx = new AudioContext();
      const destination = ctx.createMediaStreamDestination();
      const silence = ctx.createBufferSource();
      silence.buffer = ctx.createBuffer(1, ctx.sampleRate * 60, ctx.sampleRate);
      silence.connect(destination);
      silence.start();
      return destination.stream;
    };
  });

  await page.goto('/');
  await addPerson(page, { name: 'Jean Dupont', birthplace: 'Bretagne', language: 'fr' });
  await page.getByRole('button', { name: /start conversation/i }).click();

  const interviewer = page.locator('.transcript article.ai');
  await expect(interviewer).toBeVisible({ timeout: 60_000 });
  await expect(interviewer).toContainText(/\p{L}{10,}/u);

  // And nothing was attributed to a person who has not spoken.
  await expect(page.locator('.transcript article.senior')).toHaveCount(0);
});
