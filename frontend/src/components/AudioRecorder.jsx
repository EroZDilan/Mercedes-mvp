import { useState, useRef } from 'react'
import api from '../api/client'

const MIME_TYPES = ['audio/webm', 'audio/ogg', 'audio/mp4']
function getSupportedMime() {
  return MIME_TYPES.find((m) => MediaRecorder.isTypeSupported(m)) || ''
}

export default function AudioRecorder({ onTranscribed, disabled }) {
  const [recording, setRecording] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const mediaRef = useRef(null)
  const chunksRef = useRef([])

  const start = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mime = getSupportedMime()
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        sendAudio(mime)
      }
      recorder.start()
      mediaRef.current = recorder
      setRecording(true)
    } catch {
      setError('No se pudo acceder al micrófono.')
    }
  }

  const stop = () => {
    if (mediaRef.current?.state === 'recording') {
      mediaRef.current.stop()
    }
    setRecording(false)
  }

  const sendAudio = async (mime) => {
    setLoading(true)
    try {
      const ext = mime.includes('ogg') ? 'ogg' : mime.includes('mp4') ? 'mp4' : 'webm'
      const blob = new Blob(chunksRef.current, { type: mime || 'audio/webm' })
      const form = new FormData()
      form.append('file', blob, `audio.${ext}`)
      const { data } = await api.post('/audio/transcribe', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      onTranscribed(data.text)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al transcribir el audio.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleClick = () => {
    if (recording) stop()
    else start()
  }

  return (
    <div className="relative flex items-center">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || loading}
        title={recording ? 'Detener grabación' : 'Grabar mensaje de voz'}
        className={`w-9 h-9 flex items-center justify-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
          recording
            ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse'
            : 'bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300'
        } disabled:opacity-40`}
      >
        {loading ? (
          <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
        ) : (
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 1a4 4 0 014 4v7a4 4 0 01-8 0V5a4 4 0 014-4zm-1 18.93V22h2v-2.07A8.001 8.001 0 0020 12h-2a6 6 0 01-12 0H4a8.001 8.001 0 007 7.93z" />
          </svg>
        )}
      </button>
      {error && (
        <span className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-red-500 text-white text-[10px] rounded px-2 py-0.5 whitespace-nowrap z-10">
          {error}
        </span>
      )}
    </div>
  )
}
