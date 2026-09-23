import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { INTERVIEWER_ONLY, SAMPLE, SESSION } from './generate-speech'

test('holds a Japanese conversation through the real page', async ({ page, context }) => {
  const wav = readFileSync(SAMPLE).toString('base64')

  // Everything downstream of getUserMedia is the production path: the worklet,
  // the resampler, the SDK and the playback queue.
  await context.addInitScript((b64: string) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
    navigator.mediaDevices.getUserMedia = async () => {
      const ctx = new AudioContext()
      const buffer = await ctx.decodeAudioData(bytes.buffer.slice(0) as ArrayBuffer)
      const destination = ctx.createMediaStreamDestination()
      const source = ctx.createBufferSource()
      source.buffer = buffer
      source.connect(destination)
      source.start()
      return destination.stream
    }
  }, wav)

  const diagnostics: string[] = []
  page.on('console', (message) => {
    if (message.text().includes('[kataribe]')) diagnostics.push(message.text())
  })

  await page.goto('/')
  await page.getByRole('button', { name: /start conversation/i }).click()

  // The microphone is being heard, which is all the screen can show while
  // someone is still talking.
  await expect(page.locator('.monitor .meter span')).toBeVisible()

  const senior = page.locator('.transcript article.senior')
  await expect(senior).toContainText('長野', { timeout: 60_000 })

  const interviewer = page.locator('.transcript article.ai')
  await expect(interviewer).toBeVisible({ timeout: 90_000 })
  await expect(interviewer).toContainText(/[぀-ヿ一-鿿]/)

  // A dropped session shows up here rather than as an empty transcript.
  await expect(page.locator('.status')).not.toContainText('Closed')

  const report = diagnostics.join(' | ')
  expect(diagnostics.some((l) => /peak (?!0%)\d+%/.test(l)), report).toBe(true)
  // A transcript without audio is the "it never spoke" failure.
  expect(diagnostics.some((l) => l.includes('started speaking')), report).toBe(true)

  // Stopping must leave the session on the server, not only in the browser.
  await page.getByRole('button', { name: /^stop$/i }).click()
  await expect(page.locator('.status')).toContainText(/saved|finished/i, { timeout: 30_000 })

  await page.getByRole('button', { name: /past sessions/i }).click()
  const first = page.locator('.session').first()
  await expect(first).toBeVisible()
  await expect(first.locator('.facts')).toContainText(/[1-9]\d* turns/)

  await first.locator('.summary').click()
  await expect(first.locator('.detail audio')).toBeVisible()
  await expect(first.locator('.line.senior')).toContainText('長野')
})

test('replays a downloaded session in place of the microphone', async ({ page }) => {
  await page.goto('/')
  await page.locator('.replay input[type="file"]').setInputFiles(SESSION)

  await page.getByRole('button', { name: /replay recording/i }).click()

  const senior = page.locator('.transcript article.senior')
  await expect(senior).toContainText('長野', { timeout: 60_000 })

  // The right channel carries the interviewer's own voice. If it reaches the
  // model, a replay is worthless — it would be answering itself.
  await expect(senior).not.toContainText(INTERVIEWER_ONLY)

  await expect(page.locator('.transcript article.ai')).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.status')).not.toContainText('Closed')
})
