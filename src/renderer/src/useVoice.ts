import { useCallback, useRef, useState } from 'react'
import { api } from './api'

type VoiceState = 'idle' | 'recording' | 'transcribing'

/** Records from the mic and transcribes on-device via the sidecar (faster-whisper). */
export function useVoice(onText: (text: string) => void, onError: (msg: string) => void) {
  const [state, setState] = useState<VoiceState>('idle')
  const rec = useRef<MediaRecorder | null>(null)

  const stop = useCallback(() => rec.current?.state === 'recording' && rec.current.stop(), [])

  const start = useCallback(async () => {
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      onError('Microphone access was blocked.')
      return
    }
    const chunks: Blob[] = []
    const r = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
    r.ondataavailable = (e) => e.data.size && chunks.push(e.data)
    r.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      setState('transcribing')
      try {
        const { text } = await api.transcribe(new Blob(chunks, { type: 'audio/webm' }))
        if (text) onText(text)
        else onError("Didn't catch that. Try again a little closer to the mic.")
      } catch (e) {
        onError((e as Error).message)
      } finally {
        setState('idle')
      }
    }
    rec.current = r
    r.start()
    setState('recording')
    // Search phrases are short; stop automatically so nobody records forever by accident.
    setTimeout(() => r.state === 'recording' && r.stop(), 12_000)
  }, [onText, onError])

  const toggle = useCallback(() => (state === 'recording' ? stop() : state === 'idle' ? void start() : undefined), [
    state,
    start,
    stop
  ])

  return { state, toggle }
}
