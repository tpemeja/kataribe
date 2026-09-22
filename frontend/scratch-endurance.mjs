import { readFileSync } from 'node:fs'

import { chromium } from '@playwright/test'

import { SAMPLE } from './e2e/generate-speech.ts'

const MINUTES = 6
const EVERY = 40 // seconds between utterances, leaving real silence between turns
const wav = readFileSync(SAMPLE).toString('base64')

const browser = await chromium.launch()
const context = await browser.newContext({ permissions: ['microphone'] })

await context.addInitScript(
  ([b64, every]) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
    navigator.mediaDevices.getUserMedia = async () => {
      const ctx = new AudioContext()
      const buffer = await ctx.decodeAudioData(bytes.buffer.slice(0))
      const destination = ctx.createMediaStreamDestination()
      // Speak, then go quiet, then speak again — so turns actually complete.
      for (let i = 0; i < 20; i++) {
        const source = ctx.createBufferSource()
        source.buffer = buffer
        source.connect(destination)
        source.start(ctx.currentTime + i * every)
      }
      return destination.stream
    }
  },
  [wav, EVERY],
)

const page = await context.newPage()
await page.goto('http://localhost:5173/')
await page.getByRole('button', { name: /start conversation/i }).click()

const started = Date.now()
let died = null
let entries = 0

for (let i = 0; i < MINUTES * 4; i++) {
  await page.waitForTimeout(15_000)
  const status = await page.locator('.status').innerText().catch(() => '')
  entries = await page.locator('.transcript article').count()
  const at = ((Date.now() - started) / 1000).toFixed(0)
  console.log(`   ${at}s  entries=${entries}  status=${status.replace(/\n/g, ' ')}`)
  if (/closed|error/i.test(status)) {
    died = { at, status }
    break
  }
}

console.log('\n--- browser endurance ---')
console.log(died ? `  DIED at ${died.at}s: ${died.status}` : `  survived ${MINUTES} minutes`)
console.log(`  transcript entries: ${entries}`)

await browser.close()
process.exit(died ? 1 : 0)
