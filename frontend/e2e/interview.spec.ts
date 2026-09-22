import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { SAMPLE } from './generate-speech'

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

  const levels: string[] = []
  page.on('console', (message) => {
    if (message.text().includes('[kataribe]')) levels.push(message.text())
  })

  await page.goto('/')
  await page.getByRole('button', { name: /start conversation/i }).click()

  const senior = page.locator('.transcript article.senior')
  await expect(senior).toContainText('長野', { timeout: 60_000 })

  const interviewer = page.locator('.transcript article.ai')
  await expect(interviewer).toBeVisible({ timeout: 90_000 })
  await expect(interviewer).toContainText(/[぀-ヿ一-鿿]/)

  // A dropped session shows up here rather than as an empty transcript.
  await expect(page.locator('.status')).not.toContainText('Closed')

  expect(levels.some((l) => /peak (?!0%)\d+%/.test(l)), levels.join(' | ')).toBe(true)
})
