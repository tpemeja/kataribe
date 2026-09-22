export const PLAYBACK_RATE = 24000;

export interface PlayedChunk {
  offsetSec: number;
  pcm: Int16Array;
}

export class Playback {
  private context = new AudioContext({ sampleRate: PLAYBACK_RATE });
  private startedAt = this.context.currentTime;
  private nextStart = this.context.currentTime;
  private sources = new Set<AudioBufferSourceNode>();
  private played: PlayedChunk[] = [];

  enqueue(pcm: Int16Array): void {
    const buffer = this.context.createBuffer(1, pcm.length, PLAYBACK_RATE);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 0x8000;

    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);

    const startAt = Math.max(this.nextStart, this.context.currentTime);
    source.start(startAt);
    this.sources.add(source);
    source.onended = () => this.sources.delete(source);

    this.played.push({ offsetSec: startAt - this.startedAt, pcm });
    this.nextStart = startAt + buffer.duration;
  }

  /** Drop everything still queued — the senior started speaking over the AI. */
  flush(): void {
    for (const source of this.sources) {
      try {
        source.stop();
      } catch {
        // Already finished; nothing to stop.
      }
    }
    this.sources.clear();
    this.nextStart = this.context.currentTime;
  }

  recorded(): PlayedChunk[] {
    return this.played;
  }

  async close(): Promise<void> {
    this.flush();
    await this.context.close();
  }
}
