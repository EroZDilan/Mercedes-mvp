import { useState, useEffect, useRef } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const SESSION_KEY = 'chat_session_id'

function genSessionId() {
  return 'sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-indigo-600 text-white rounded-br-sm'
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
  const [showHistory, setShowHistory] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    api.get('/chatbot/history').then(({ data }) => setHistory(data)).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const text = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const { data } = await api.post('/chatbot/message', {
        message: text,
        session_id: sessionId,
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: data.response, response_time_ms: data.response_time_ms }])
      // refresh history sidebar
      api.get('/chatbot/history').then(({ data }) => setHistory(data)).catch(() => {})
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Error al conectar con el servidor.' }])
    } finally {
      setLoading(false)
    }
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
                {new Date(h.timestamp).toLocaleDateString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
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
                Hola {user?.username}, pregúntame sobre el stock del almacén.
              </p>
            </div>
          )}
          {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
          {loading && (
            <div className="flex justify-start mb-3">
              <div className="bg-gray-100 dark:bg-gray-800 px-4 py-2.5 rounded-2xl rounded-bl-sm">
                <span className="text-gray-400 dark:text-gray-500 text-sm animate-pulse">Pensando…</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={sendMessage} className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escribe tu pregunta…"
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
  )
}
