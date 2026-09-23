import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const CACHE = join(dirname(fileURLToPath(import.meta.url)), '.audio-cache');
export const SAMPLE = join(CACHE, 'ja.wav');
export const SAMPLE_FR = join(CACHE, 'fr.wav');

/** A stereo file shaped like a downloaded session: senior left, interviewer
 *  right, with deliberately different words on each side so a replay that
 *  leaks the right channel is visible in the transcript. */
export const SESSION = join(CACHE, 'session-stereo.wav');

export const UTTERANCE =
  'こんにちは。私は昭和二十二年に、長野の小さな村で生まれました。' +
  '父は、村で小さな織物の工場をやっておりました。';

/** Only ever on the right channel. If this word reaches the model, the replay
 *  is feeding the interviewer its own voice. */
export const UTTERANCE_FR =
  'Bonjour. Je suis né en 1947 dans un petit village en Bretagne. ' +
  'Mon père tenait une petite fabrique de textile.';

export const INTERVIEWER_ONLY = '沖縄';
const INTERVIEWER_LINE = `そうでしたか。${INTERVIEWER_ONLY}のお話も聞かせてください。`;

export default function generateSpeech() {
  if (existsSync(SAMPLE) && existsSync(SESSION) && existsSync(SAMPLE_FR)) return;
  mkdirSync(CACHE, { recursive: true });

  synthesize(UTTERANCE, SAMPLE);
  synthesize(UTTERANCE_FR, SAMPLE_FR, 'Thomas');
  const right = join(CACHE, 'right.wav');
  synthesize(INTERVIEWER_LINE, right);
  writeFileSync(SESSION, interleave(readPcm(SAMPLE), readPcm(right)));
  rmSync(right, { force: true });
}

function synthesize(text: string, out: string, voice = 'Kyoko') {
  const aiff = `${out}.aiff`;
  const source = `${out}.txt`;
  try {
    writeFileSync(source, text, 'utf8');
    execFileSync('say', ['-v', voice, '-f', source, '-o', aiff]);
    execFileSync('afconvert', ['-f', 'WAVE', '-d', 'LEI16@16000', '-c', '1', aiff, out]);
  } finally {
    rmSync(aiff, { force: true });
    rmSync(source, { force: true });
  }
}

function readPcm(path: string): Int16Array {
  const buffer = readFileSync(path);
  const start = buffer.indexOf('data', 12, 'ascii') + 8;
  return new Int16Array(buffer.buffer, buffer.byteOffset + start, (buffer.length - start) >> 1);
}

function interleave(left: Int16Array, right: Int16Array): Buffer {
  const frames = Math.max(left.length, right.length);
  const view = new DataView(new ArrayBuffer(44 + frames * 4));
  const ascii = (at: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(at + i, text.charCodeAt(i));
  };

  ascii(0, 'RIFF');
  view.setUint32(4, 36 + frames * 4, true);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 2, true);
  view.setUint32(24, 16000, true);
  view.setUint32(28, 16000 * 4, true);
  view.setUint16(32, 4, true);
  view.setUint16(34, 16, true);
  ascii(36, 'data');
  view.setUint32(40, frames * 4, true);

  for (let i = 0; i < frames; i++) {
    view.setInt16(44 + i * 4, left[i] ?? 0, true);
    view.setInt16(46 + i * 4, right[i] ?? 0, true);
  }
  return Buffer.from(view.buffer);
}
