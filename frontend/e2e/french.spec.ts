import { readFileSync } from 'node:fs';

import { expect, test } from '@playwright/test';

import { addPerson } from './people';
import { SAMPLE_FR } from './generate-speech';

/**
 * French exists so the loop can be exercised without a Japanese speaker. It
 * proves the mechanics — turn-taking, extraction, storage — and deliberately
 * proves nothing about honorific register or name spelling, which are the parts
 * that actually decide whether the product works.
 */
test('holds a French conversation and extracts a story from it', async ({ page, context }) => {
  test.setTimeout(180_000);

  const wav = readFileSync(SAMPLE_FR).toString('base64');
  await context.addInitScript((b64: string) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    navigator.mediaDevices.getUserMedia = async () => {
      const ctx = new AudioContext();
      const buffer = await ctx.decodeAudioData(bytes.buffer.slice(0) as ArrayBuffer);
      const destination = ctx.createMediaStreamDestination();
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(destination);
      source.start();
      return destination.stream;
    };
  }, wav);

  await page.goto('/');

  await addPerson(page, { name: 'Jean Dupont', birthplace: 'Bretagne', language: 'fr' });

  await page.getByRole('button', { name: /start conversation/i }).click();
  await expect(page.locator('.transcript article.senior')).toContainText('Bretagne', {
    timeout: 60_000,
  });
  await expect(page.locator('.transcript article.ai')).toBeVisible({ timeout: 90_000 });

  await page.getByRole('button', { name: /^stop$/i }).click();
  await expect(page.locator('.status')).toContainText(/saved|finished/i, { timeout: 30_000 });

  await page.getByRole('button', { name: /past sessions/i }).click();
  const first = page.locator('.session').first();
  await first.locator('.summary').click();
  await expect(first.locator('.story')).toBeVisible({ timeout: 90_000 });
  await expect(first.locator('.story blockquote').first()).toContainText('Bretagne');
});
