import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const CACHE = join(dirname(fileURLToPath(import.meta.url)), '.audio-cache')
export const SAMPLE = join(CACHE, 'ja.wav')

export const UTTERANCE =
  'こんにちは。私は昭和二十二年に、長野の小さな村で生まれました。' +
  '父は、村で小さな織物の工場をやっておりました。'

export default function generateSpeech() {
  if (existsSync(SAMPLE)) return

  mkdirSync(CACHE, { recursive: true })
  const aiff = join(CACHE, 'ja.aiff')
  const text = join(CACHE, 'ja.txt')

  try {
    execFileSync('/bin/sh', ['-c', `printf %s ${JSON.stringify(UTTERANCE)} > ${text}`])
    execFileSync('say', ['-v', 'Kyoko', '-f', text, '-o', aiff])
    execFileSync('afconvert', ['-f', 'WAVE', '-d', 'LEI16@16000', '-c', '1', aiff, SAMPLE])
  } finally {
    rmSync(aiff, { force: true })
    rmSync(text, { force: true })
  }
}
