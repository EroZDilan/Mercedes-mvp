import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

function NoteCard({ note, onEdit, onDelete, canEdit }) {
  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
      <p className="text-sm text-gray-900 dark:text-gray-100 whitespace-pre-wrap">{note.content}</p>
      {note.related_to && (
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Ref: {note.related_to}</p>
      )}
      <div className="flex items-center justify-between mt-3">
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {new Date(note.created_at).toLocaleString('es', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
          {note.modified_at && ' (editada)'}
        </span>
        {canEdit && (
          <div className="flex gap-3">
            <button onClick={() => onEdit(note)} className="text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400">Editar</button>
            <button onClick={() => onDelete(note.id)} className="text-xs text-red-500 hover:text-red-700 dark:text-red-400">Eliminar</button>
          </div>
        )}
      </div>
    </div>
  )
}

function HistoryItem({ item }) {
  const [open, setOpen] = useState(false)
  const typeLabel = { chat: '💬', stock_change: '📦', crm_note: '📝' }
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
      >
        <span>{typeLabel[item.type] || '•'}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-900 dark:text-gray-100 truncate">{item.summary}</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
            {item.timestamp ? new Date(item.timestamp).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
          </p>
        </div>
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-4 pb-3 bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-600 dark:text-gray-400">
          <pre className="whitespace-pre-wrap font-sans">{JSON.stringify(item.detail, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

export default function CRM() {
  const { user, isAdmin } = useAuth()
  const [tab, setTab] = useState('notes')
  const [notes, setNotes] = useState([])
  const [history, setHistory] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [globalMetrics, setGlobalMetrics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [noteForm, setNoteForm] = useState({ content: '', related_to: '' })
  const [editingNote, setEditingNote] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const fetchNotes = useCallback(async () => {
    setLoading(true)
    try { const { data } = await api.get('/crm/notes'); setNotes(data) } catch {}
    setLoading(false)
  }, [])

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    try { const { data } = await api.get('/crm/history'); setHistory(data) } catch {}
    setLoading(false)
  }, [])

  const fetchMetrics = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/crm/metrics')
      setMetrics(data)
      if (isAdmin) {
        const { data: gm } = await api.get('/crm/metrics/global')
        setGlobalMetrics(gm)
      }
    } catch {}
    setLoading(false)
  }, [isAdmin])

  useEffect(() => {
    if (tab === 'notes') fetchNotes()
    else if (tab === 'history') fetchHistory()
    else if (tab === 'metrics') fetchMetrics()
  }, [tab, fetchNotes, fetchHistory, fetchMetrics])

  const handleCreateNote = async (e) => {
    e.preventDefault()
    setSaving(true); setError('')
    try {
      await api.post('/crm/notes', { content: noteForm.content, related_to: noteForm.related_to || null })
      setNoteForm({ content: '', related_to: '' })
      fetchNotes()
    } catch (e) {
      setError(e.response?.data?.detail || 'Error al guardar')
    } finally { setSaving(false) }
  }

  const handleEditNote = async (e) => {
    e.preventDefault()
    setSaving(true); setError('')
    try {
      await api.put(`/crm/notes/${editingNote.id}`, { content: editingNote.content })
      setEditingNote(null)
      fetchNotes()
    } catch (e) {
      setError(e.response?.data?.detail || 'Error al guardar')
    } finally { setSaving(false) }
  }

  const handleDeleteNote = async (id) => {
    if (!window.confirm('¿Eliminar esta nota?')) return
    try { await api.delete(`/crm/notes/${id}`); fetchNotes() } catch {}
  }

  const tabs = [
    { key: 'notes', label: 'Notas' },
    { key: 'history', label: 'Historial' },
    { key: 'metrics', label: 'Métricas' },
  ]

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-5">CRM Personal</h1>

      <div className="flex gap-1 mb-5 border-b border-gray-200 dark:border-gray-700">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === key
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ---- NOTES ---- */}
      {tab === 'notes' && (
        <div className="space-y-4">
          <form onSubmit={handleCreateNote} className="bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700 p-4 space-y-3">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Nueva nota</p>
            <textarea
              value={noteForm.content}
              onChange={(e) => setNoteForm({ ...noteForm, content: e.target.value })}
              placeholder="Escribe una nota…"
              rows={3}
              required
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Referencia (opcional)"
                value={noteForm.related_to}
                onChange={(e) => setNoteForm({ ...noteForm, related_to: e.target.value })}
                className="flex-1 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {saving ? '…' : 'Guardar'}
              </button>
            </div>
            {error && <p className="text-xs text-red-500">{error}</p>}
          </form>

          {loading ? (
            <p className="text-gray-400 text-sm text-center py-8">Cargando…</p>
          ) : notes.length === 0 ? (
            <p className="text-gray-400 dark:text-gray-500 text-sm text-center py-8">Sin notas aún</p>
          ) : (
            notes.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                canEdit={note.user_id === user?.id || isAdmin}
                onEdit={(n) => setEditingNote({ ...n })}
                onDelete={handleDeleteNote}
              />
            ))
          )}
        </div>
      )}

      {/* ---- HISTORY ---- */}
      {tab === 'history' && (
        <div className="space-y-2">
          {loading ? (
            <p className="text-gray-400 text-sm text-center py-8">Cargando…</p>
          ) : history.length === 0 ? (
            <p className="text-gray-400 dark:text-gray-500 text-sm text-center py-8">Sin actividad registrada</p>
          ) : (
            history.map((item, i) => <HistoryItem key={i} item={item} />)
          )}
        </div>
      )}

      {/* ---- METRICS ---- */}
      {tab === 'metrics' && (
        <div className="space-y-4">
          {loading ? (
            <p className="text-gray-400 text-sm text-center py-8">Cargando…</p>
          ) : metrics ? (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {[
                  { label: 'Consultas hoy', value: metrics.chatbot_queries_today },
                  { label: 'Consultas esta semana', value: metrics.chatbot_queries_week },
                  { label: 'Modificaciones de stock (30d)', value: metrics.stock_modifications_month },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{value ?? '—'}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{label}</p>
                  </div>
                ))}
              </div>

              {metrics.top_modified_products?.length > 0 && (
                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Productos más modificados</p>
                  <div className="space-y-2">
                    {metrics.top_modified_products.map((p, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <span className="text-gray-800 dark:text-gray-200">{p.product_name}</span>
                        <span className="text-indigo-600 dark:text-indigo-400 font-medium">{p.modification_count}×</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {metrics.last_activity && (
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  Última actividad: {new Date(metrics.last_activity).toLocaleString('es')}
                </p>
              )}

              {isAdmin && globalMetrics && (
                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Métricas globales (admin)</p>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="text-center">
                      <p className="text-xl font-bold text-indigo-600 dark:text-indigo-400">{globalMetrics.total_queries_today}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">Consultas hoy (total)</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xl font-bold text-indigo-600 dark:text-indigo-400">{globalMetrics.total_queries_week}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">Consultas semana (total)</p>
                    </div>
                  </div>
                  {globalMetrics.most_active_warehouse && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Almacén más activo: <strong className="text-gray-700 dark:text-gray-300">{globalMetrics.most_active_warehouse.warehouse_name}</strong>
                      {' '}({globalMetrics.most_active_warehouse.modification_count} modificaciones)
                    </p>
                  )}
                  {globalMetrics.top_users?.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">Usuarios más activos</p>
                      {globalMetrics.top_users.map((u, i) => (
                        <div key={i} className="flex justify-between text-xs text-gray-700 dark:text-gray-300 py-0.5">
                          <span>{u.username}</span>
                          <span className="text-indigo-600 dark:text-indigo-400">{u.activity_count} acciones</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          ) : null}
        </div>
      )}

      {/* Edit note modal */}
      {editingNote && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <form
            onSubmit={handleEditNote}
            className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md p-6 space-y-4"
          >
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Editar nota</h3>
            <textarea
              value={editingNote.content}
              onChange={(e) => setEditingNote({ ...editingNote, content: e.target.value })}
              rows={4}
              required
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
            {error && <p className="text-xs text-red-500">{error}</p>}
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setEditingNote(null)} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400">Cancelar</button>
              <button type="submit" disabled={saving} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium">
                {saving ? '…' : 'Guardar'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
