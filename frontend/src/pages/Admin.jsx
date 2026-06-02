import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'

// ---- Users tab ----

function UserRow({ user, onAction, onRefresh }) {
  const [loading, setLoading] = useState(false)

  const doAction = async (action) => {
    setLoading(true)
    try {
      if (action === 'unlock') await api.post(`/users/${user.id}/unlock`)
      else if (action === 'deactivate') await api.post(`/users/${user.id}/deactivate`)
      else if (action === 'activate') await api.put(`/users/${user.id}`, { is_active: true })
      else if (action === 'force-logout') await api.post(`/users/${user.id}/force-logout`)
      onRefresh()
    } catch (e) {
      alert(e.response?.data?.detail || 'Error')
    } finally {
      setLoading(false)
    }
  }

  const roleColors = {
    admin: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
    gestor: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    supervisor: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400',
    operador: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
  }

  return (
    <tr className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50">
      <td className="px-3 py-2.5 font-medium text-gray-900 dark:text-gray-100 text-sm">{user.username}</td>
      <td className="px-3 py-2.5 text-sm text-gray-500 dark:text-gray-400">{user.full_name || '—'}</td>
      <td className="px-3 py-2.5">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${roleColors[user.role] || 'bg-gray-100'}`}>
          {user.role}
        </span>
      </td>
      <td className="px-3 py-2.5">
        {user.is_locked ? (
          <span className="text-xs text-red-600 dark:text-red-400 font-medium">🔒 Bloqueado</span>
        ) : user.is_active ? (
          <span className="text-xs text-green-600 dark:text-green-400 font-medium">● Activo</span>
        ) : (
          <span className="text-xs text-gray-400 font-medium">○ Inactivo</span>
        )}
      </td>
      <td className="px-3 py-2.5">
        <div className="flex gap-2 flex-wrap">
          {user.is_locked && (
            <button onClick={() => doAction('unlock')} disabled={loading}
              className="text-xs text-green-600 hover:text-green-800 dark:text-green-400 font-medium">
              Desbloquear
            </button>
          )}
          {user.is_active ? (
            <button onClick={() => doAction('deactivate')} disabled={loading}
              className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 font-medium">
              Desactivar
            </button>
          ) : (
            <button onClick={() => doAction('activate')} disabled={loading}
              className="text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 font-medium">
              Activar
            </button>
          )}
          <button onClick={() => doAction('force-logout')} disabled={loading}
            className="text-xs text-orange-500 hover:text-orange-700 dark:text-orange-400 font-medium">
            Logout forzado
          </button>
          <button onClick={() => onAction('resetpw', user)}
            className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 font-medium">
            Reset PW
          </button>
        </div>
      </td>
    </tr>
  )
}

function CreateUserModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ username: '', password: '', full_name: '', role_id: 4, warehouse_id: '' })
  const [roles, setRoles] = useState([{ id: 1, name: 'admin' }, { id: 2, name: 'gestor' }, { id: 3, name: 'supervisor' }, { id: 4, name: 'operador' }])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleCreate = async (e) => {
    e.preventDefault()
    setSaving(true); setError('')
    try {
      const body = { ...form, role_id: parseInt(form.role_id), warehouse_id: form.warehouse_id ? parseInt(form.warehouse_id) : null }
      await api.post('/users', body)
      onCreated()
    } catch (e) {
      const d = e.response?.data?.detail
      setError(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error'))
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <form onSubmit={handleCreate} className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md p-6 space-y-4">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Nuevo usuario</h3>
        {[['username', 'Usuario', 'text'], ['password', 'Contraseña', 'password'], ['full_name', 'Nombre completo', 'text']].map(([key, label, type]) => (
          <div key={key}>
            <label className="text-xs font-medium text-gray-600 dark:text-gray-400">{label}</label>
            <input type={type} required={key !== 'full_name'} value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              className="w-full mt-1 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        ))}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Rol</label>
            <select value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}
              className="w-full mt-1 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500">
              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 dark:text-gray-400">ID Almacén</label>
            <input type="number" placeholder="Dejar vacío = todos"
              value={form.warehouse_id}
              onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })}
              className="w-full mt-1 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
        {error && <p className="text-xs text-red-500">{error}</p>}
        <div className="flex gap-2 justify-end">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400">Cancelar</button>
          <button type="submit" disabled={saving}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium">
            {saving ? '…' : 'Crear'}
          </button>
        </div>
      </form>
    </div>
  )
}

function ResetPasswordModal({ user, onClose }) {
  const [pw, setPw] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const handleReset = async (e) => {
    e.preventDefault()
    setSaving(true); setError('')
    try {
      await api.post(`/users/${user.id}/reset-password`, { new_password: pw })
      setDone(true)
    } catch (e) {
      setError(e.response?.data?.detail || 'Error')
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-sm p-6">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Reset contraseña — {user.username}</h3>
        {done ? (
          <div className="text-center">
            <p className="text-green-600 dark:text-green-400 text-sm mb-4">Contraseña actualizada correctamente.</p>
            <button onClick={onClose} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm">Cerrar</button>
          </div>
        ) : (
          <form onSubmit={handleReset} className="space-y-3">
            <input type="password" placeholder="Nueva contraseña" required value={pw}
              onChange={(e) => setPw(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {error && <p className="text-xs text-red-500">{error}</p>}
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400">Cancelar</button>
              <button type="submit" disabled={saving}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm disabled:opacity-50">
                {saving ? '…' : 'Guardar'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

// ---- Main Admin page ----

export default function Admin() {
  const [tab, setTab] = useState('users')
  const [users, setUsers] = useState([])
  const [warehouses, setWarehouses] = useState([])
  const [syncLogs, setSyncLogs] = useState([])
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [actionModal, setActionModal] = useState(null)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try { const { data } = await api.get('/users'); setUsers(data) } catch {}
    setLoading(false)
  }, [])

  const fetchSync = useCallback(async () => {
    setLoading(true)
    try {
      const [{ data: wh }, { data: logs }] = await Promise.all([
        api.get('/sync/status'),
        api.get('/sync/logs'),
      ])
      setWarehouses(wh)
      setSyncLogs(logs)
    } catch {}
    setLoading(false)
  }, [])

  useEffect(() => {
    if (tab === 'users') fetchUsers()
    else if (tab === 'sync') fetchSync()
  }, [tab, fetchUsers, fetchSync])

  const triggerSync = async () => {
    setSyncing(true); setSyncMsg('')
    try {
      const { data } = await api.post('/sync/trigger')
      setSyncMsg(`Sync completada: ${data.total_updated || 0} registros actualizados`)
      fetchSync()
    } catch (e) {
      setSyncMsg(e.response?.data?.detail || 'Error en sync')
    } finally { setSyncing(false) }
  }

  const statusColor = {
    success: 'text-green-600 dark:text-green-400',
    error: 'text-red-600 dark:text-red-400',
    partial: 'text-yellow-600 dark:text-yellow-400',
  }

  const tabs = [{ key: 'users', label: 'Usuarios' }, { key: 'sync', label: 'Sync & Almacenes' }]

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-5">Panel Admin</h1>

      <div className="flex gap-1 mb-5 border-b border-gray-200 dark:border-gray-700">
        {tabs.map(({ key, label }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === key
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* ---- USERS ---- */}
      {tab === 'users' && (
        <>
          <div className="flex justify-end mb-3">
            <button onClick={() => setShowCreate(true)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors">
              + Nuevo usuario
            </button>
          </div>
          {loading ? (
            <p className="text-gray-400 text-sm text-center py-8">Cargando…</p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    {['Usuario', 'Nombre', 'Rol', 'Estado', 'Acciones'].map((h) => (
                      <th key={h} className="px-3 py-2.5 text-left font-medium text-gray-600 dark:text-gray-400">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {users.map((u) => (
                    <UserRow key={u.id} user={u} onRefresh={fetchUsers}
                      onAction={(type, user) => setActionModal({ type, user })} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ---- SYNC ---- */}
      {tab === 'sync' && (
        <div className="space-y-5">
          <div className="flex items-center gap-3">
            <button
              onClick={triggerSync}
              disabled={syncing}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
            >
              {syncing ? '⟳ Sincronizando…' : '⟳ Iniciar sync manual'}
            </button>
            {syncMsg && <p className="text-sm text-gray-600 dark:text-gray-400">{syncMsg}</p>}
          </div>

          <div>
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Estado de almacenes</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {warehouses.map((wh) => (
                <div key={wh.id} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-4 flex items-center gap-3">
                  <span className={`text-lg ${wh.is_online ? '🟢' : '🔴'}`}>{wh.is_online ? '🟢' : '🔴'}</span>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">{wh.name}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{wh.code}</p>
                    {wh.last_seen && (
                      <p className="text-xs text-gray-400 dark:text-gray-500">
                        Últ. contacto: {new Date(wh.last_seen).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Log de sincronizaciones</p>
            {loading ? (
              <p className="text-gray-400 text-sm">Cargando…</p>
            ) : syncLogs.length === 0 ? (
              <p className="text-gray-400 dark:text-gray-500 text-sm">Sin registros</p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      {['Almacén', 'Inicio', 'Fin', 'Estado', 'Registros', 'Error'].map((h) => (
                        <th key={h} className="px-3 py-2.5 text-left font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {syncLogs.map((log) => (
                      <tr key={log.id} className="bg-white dark:bg-gray-900">
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{log.warehouse_id}</td>
                        <td className="px-3 py-2 text-gray-500 dark:text-gray-400 text-xs whitespace-nowrap">
                          {log.started_at ? new Date(log.started_at).toLocaleString('es') : '—'}
                        </td>
                        <td className="px-3 py-2 text-gray-500 dark:text-gray-400 text-xs whitespace-nowrap">
                          {log.finished_at ? new Date(log.finished_at).toLocaleString('es') : '—'}
                        </td>
                        <td className={`px-3 py-2 text-xs font-medium capitalize ${statusColor[log.status] || 'text-gray-500'}`}>
                          {log.status}
                        </td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{log.records_updated}</td>
                        <td className="px-3 py-2 text-xs text-red-500 dark:text-red-400 max-w-xs truncate">
                          {log.error_message || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); fetchUsers() }}
        />
      )}
      {actionModal?.type === 'resetpw' && (
        <ResetPasswordModal user={actionModal.user} onClose={() => setActionModal(null)} />
      )}
    </div>
  )
}
