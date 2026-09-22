import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { SAMPLE } from './generate-speech'

const MINUTES = 6
const EVERY = 40 // seconds between utterances, leaving real silence for turns to complete

/**
 * The plan calls for five to ten minute sessions, and every other test here
 * finishes inside a minute. That gap hid a real fault once already: sessions
 * were dying at around two minutes and nothing ran long enough to see it.
 */
test(
  'keeps a session alive for a full interview',
  { tag: '@endurance' },
  async ({ page, context }) => {
    test.setTimeout((MINUTES + 3) * 60_000)

    const wav = readFileSync(SAMPLE).toString('base64')
    await context.addInitScript(
      ([b64, every]: [string, number]) => {
        const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
        navigator.mediaDevices.getUserMedia = async () => {
          const ctx = new AudioContext()
          const buffer = await ctx.decodeAudioData(bytes.buffer.slice(0) as ArrayBuffer)
          const destination = ctx.createMediaStreamDestination()
          // Speak, fall silent, speak again. Continuous audio would be someone
          // who never stops talking, and the interviewer would rightly never reply.
          for (let i = 0; i < 20; i++) {
            const source = ctx.createBufferSource()
            source.buffer = buffer
            source.connect(destination)
            source.start(ctx.currentTime + i * every)
          }
          return destination.stream
        }
      },
      [wav, EVERY] as [string, number],
    )

    await page.goto('/')
    await page.getByRole('button', { name: /start conversation/i }).click()

    let entries = 0
    for (let i = 0; i < MINUTES * 4; i++) {
      await page.waitForTimeout(15_000)
      const status = await page.locator('.status').innerText()
      expect(status, `session dropped after ${i * 15}s`).not.toMatch(/closed|error/i)
      entries = await page.locator('.transcript article').count()
    }

    // Roughly one exchange per utterance; well under that means turns stopped
    // completing even though the socket stayed open.
    expect(entries).toBeGreaterThan(MINUTES * 2)
  },
)
