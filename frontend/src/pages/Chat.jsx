import { useState, useEffect, useRef } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import ActionConfirm from '../components/ActionConfirm'
import AudioRecorder from '../components/AudioRecorder'
import SlashCommandMenu from '../components/SlashCommandMenu'
import SlashCommandWizard from '../components/SlashCommandWizard'

const SESSION_KEY = 'chat_session_id'

function genSessionId() {
  return 'sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

function MessageBubble({ msg, onConfirmed, onCancelled }) {
  const isUser = msg.role === 'user'

  if (msg.role === 'action_pending') {
    return (
      <div className="flex justify-start mb-3">
        <ActionConfirm
          summary={msg.summary}
          actionToken={msg.actionToken}
          onConfirmed={onConfirmed}
          onCancelled={onCancelled}
        />
      </div>
    )
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-indigo-600 text-white rounded-br-sm'
            : msg.isSuccess
            ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 rounded-bl-sm border border-green-200 dark:border-green-800'
            : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-sm'
        }`}
      >
        {msg.content}
        {msg.response_time_ms && (
          <span className="block text-xs opacity-50 mt-1">{msg.response_time_ms}ms</span>
        )}
      </div>
    </div>
  )
}

export default function Chat() {
  const { user } = useAuth()
  const [sessionId] = useState(() => {
    const saved = sessionStorage.getItem(SESSION_KEY)
    if (saved) return saved
    const id = genSessionId()
    sessionStorage.setItem(SESSION_KEY, id)
    return id
  })
  const [messages, setMessages] = useState([])
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [showHistory, setShowHistory] = useState(false)
  const [slashData, setSlashData] = useState(null)
  const [showSlashMenu, setShowSlashMenu] = useState(false)
  const [activeWizard, setActiveWizard] = useState(null)
  const bottomRef = useRef(null)
  const timerRef = useRef(null)

  // Cargar historial del sidebar y restaurar mensajes de la sesión actual
  useEffect(() => {
    api.get('/chatbot/history').then(({ data }) => {
      setHistory(data)
      // Restaurar mensajes de la sesión activa si hay entradas en el historial
      const sessionMsgs = data.filter((h) => h.session_id === sessionId)
      if (sessionMsgs.length > 0) {
        const restored = sessionMsgs
          .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
          .flatMap((h) => [
            { role: 'user', content: h.question },
            { role: 'assistant', content: h.response, response_time_ms: h.response_time_ms },
          ])
        setMessages(restored)
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleInputChange = (e) => {
    const val = e.target.value
    setInput(val)
    if (val.startsWith('/')) {
      setShowSlashMenu(true)
      if (!slashData) {
        api.get('/chatbot/slash-data').then(({ data }) => setSlashData(data)).catch(() => {})
      }
    } else {
      setShowSlashMenu(false)
    }
  }

  const openWizard = (cmd) => {
    setShowSlashMenu(false)
    setInput('')
    setActiveWizard(cmd)
  }

  const handleWizardClose = (subcommand) => {
    if (subcommand) {
      setActiveWizard(subcommand)
    } else {
      setActiveWizard(null)
    }
  }

  const handleWizardSend = (message) => {
    setActiveWizard(null)
    sendMessage(null, message)
  }

  const sendMessage = async (e, overrideText) => {
    if (e) e.preventDefault()
    const text = overrideText || input.trim()
    if (!text || loading) return
    setInput('')
    setShowSlashMenu(false)
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)
    setElapsed(0)
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)

    // Placeholder para el mensaje que se va a ir completando con streaming
    const placeholderId = Date.now()
    setMessages((prev) => [...prev, { role: 'assistant', content: '', _id: placeholderId, streaming: true }])

    try {
      const token = localStorage.getItem('access_token')
      const resp = await fetch('/api/chatbot/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      })

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let sessionReceived = sessionId
      let responseTimeMs = null

      const replacePlaceholder = (fields) =>
        setMessages((prev) => prev.map((m) => (m._id === placeholderId ? { ...m, ...fields } : m)))

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })

        // SSE lines end with \n\n — process complete events
        const parts = buf.split('\n\n')
        buf = parts.pop() // keep incomplete tail

        for (const part of parts) {
          const line = part.startsWith('data: ') ? part.slice(6) : part.trim()
          if (!line) continue
          let evt
          try { evt = JSON.parse(line) } catch { continue }

          if (evt.session_id) sessionReceived = evt.session_id
          if (evt.response_time_ms) responseTimeMs = evt.response_time_ms

          if (evt.type === 'delta') {
            setMessages((prev) =>
              prev.map((m) =>
                m._id === placeholderId
                  ? { ...m, content: (m.content || '') + evt.delta }
                  : m
              )
            )
          } else if (evt.type === 'query' || evt.type === 'error') {
            replacePlaceholder({ content: evt.response, streaming: false, response_time_ms: responseTimeMs })
          } else if (evt.type === 'action_pending') {
            setMessages((prev) => prev
              .filter((m) => m._id !== placeholderId)
              .concat({
                role: 'action_pending',
                id: placeholderId,
                summary: evt.summary,
                actionToken: evt.action_token,
                response_time_ms: responseTimeMs,
              })
            )
          } else if (evt.type === 'done') {
            replacePlaceholder({ streaming: false, response_time_ms: responseTimeMs })
          }
        }
      }

      api.get('/chatbot/history').then(({ data }) => setHistory(data)).catch(() => {})
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m._id === placeholderId
            ? { ...m, content: 'Error al conectar con el servidor.', streaming: false }
            : m
        )
      )
    } finally {
      clearInterval(timerRef.current)
      setLoading(false)
      setElapsed(0)
    }
  }

  const handleActionConfirmed = (msgId, resultMsg) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId
          ? { role: 'assistant', content: `✓ ${resultMsg}`, isSuccess: true }
          : m
      )
    )
    api.get('/chatbot/history').then(({ data }) => setHistory(data)).catch(() => {})
  }

  const handleActionCancelled = (msgId) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId
          ? { role: 'assistant', content: 'Acción cancelada. ¿En qué más puedo ayudarte?' }
          : m
      )
    )
  }

  const loadSession = async (sid) => {
    setShowHistory(false)
    try {
      const { data } = await api.get(`/chatbot/history?session_id=${sid}`)
      const msgs = data.flatMap((h) => [
        { role: 'user', content: h.question },
        { role: 'assistant', content: h.response, response_time_ms: h.response_time_ms },
      ])
      setMessages(msgs)
    } catch {}
  }

  const uniqueSessions = [...new Map(history.map((h) => [h.session_id, h])).values()]

  return (
    <div className="flex h-[calc(100vh-57px)]">
      {/* Sidebar historial */}
      <div className={`${showHistory ? 'w-64' : 'w-0'} transition-all overflow-hidden border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 flex-shrink-0`}>
        <div className="p-3">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
            Conversaciones anteriores
          </p>
          {uniqueSessions.length === 0 && (
            <p className="text-xs text-gray-400 dark:text-gray-500">Sin historial</p>
          )}
          {uniqueSessions.map((h) => (
            <button
              key={h.session_id}
              onClick={() => loadSession(h.session_id)}
              className="w-full text-left px-2 py-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors mb-1"
            >
              <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">{h.question}</p>
              <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                {new Date(h.timestamp).toLocaleDateString('es', {
                  day: '2-digit',
                  month: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Main chat */}
      <div className="flex flex-col flex-1 min-w-0">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 text-sm"
            title="Ver historial"
          >
            ☰
          </button>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Asistente de inventario · <span className="capitalize">{user?.role}</span>
          </span>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-4xl mb-3">🤖</div>
              <p className="text-gray-500 dark:text-gray-400 text-sm max-w-xs">
                Hola {user?.username}, pregúntame sobre el stock o escribe <span className="font-mono bg-gray-100 dark:bg-gray-700 px-1 rounded">/</span> para ver acciones disponibles.
              </p>
            </div>
          )}
          {messages.map((msg, i) => (
            <MessageBubble
              key={i}
              msg={msg}
              onConfirmed={(resultMsg) => handleActionConfirmed(msg.id, resultMsg)}
              onCancelled={() => handleActionCancelled(msg.id)}
            />
          ))}
          {loading && (
            <div className="flex justify-start mb-3">
              <div className="bg-gray-100 dark:bg-gray-800 px-4 py-2.5 rounded-2xl rounded-bl-sm">
                <span className="text-gray-400 dark:text-gray-500 text-sm animate-pulse">
                  Pensando… {elapsed > 0 && `(${elapsed}s)`}
                </span>
                {elapsed >= 10 && (
                  <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-1">
                    El modelo local puede tardar hasta 90s. Por favor espera.
                  </p>
                )}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="relative px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          {activeWizard && (
            <SlashCommandWizard
              command={activeWizard}
              slashData={slashData}
              onSend={handleWizardSend}
              onClose={handleWizardClose}
            />
          )}
          {showSlashMenu && !activeWizard && (
            <SlashCommandMenu
              available={slashData?.commands || []}
              inputValue={input}
              onSelect={openWizard}
            />
          )}
          <form onSubmit={sendMessage} className="flex gap-2 items-center">
            <AudioRecorder
              onTranscribed={(text) => setInput((prev) => (prev ? prev + ' ' + text : text))}
              disabled={loading}
            />
            <input
              value={input}
              onChange={handleInputChange}
              onFocus={() => input.startsWith('/') && setShowSlashMenu(true)}
              onBlur={() => setTimeout(() => setShowSlashMenu(false), 150)}
              placeholder="Escribe, dicta, o usa / para acciones…"
              className="flex-1 px-4 py-2 rounded-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white rounded-full text-sm font-medium transition-colors"
            >
              Enviar
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
