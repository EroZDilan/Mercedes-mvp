import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const STATUS_COLORS = {
  completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  conflict:  'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  cancelled: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
}
const STATUS_LABELS = { completed: 'Completada', conflict: 'Conflicto', cancelled: 'Cancelada' }

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Sales() {
  const { isAdmin, isGestor } = useAuth()
  const canSeeStats = isAdmin || isGestor

  const [sales, setSales] = useState([])
  const [stats, setStats] = useState(null)
  const [queueStatus, setQueueStatus] = useState(null)
  const [search, setSearch] = useState('')
  const [warehouse, setWarehouse] = useState('')
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')

  const fetchAll = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (warehouse) params.warehouse = warehouse
      if (search) params.customer = search
      const [salesRes, queueRes] = await Promise.all([
        api.get('/sales/', { params }),
        api.get('/sales/queue/status'),
      ])
      setSales(salesRes.data)
      setQueueStatus(queueRes.data)
    } catch {}
    setLoading(false)
  }, [warehouse, search])

  const fetchStats = useCallback(async () => {
    if (!canSeeStats) return
    try {
      const { data } = await api.get('/sales/stats')
      setStats(data)
    } catch {}
  }, [canSeeStats])

  useEffect(() => { fetchAll(); fetchStats() }, [fetchAll, fetchStats])

  const handleSync = async () => {
    setSyncing(true)
    setSyncMsg('')
    try {
      const { data } = await api.post('/sales/queue/push')
      setSyncMsg(`Sincronizado: ${data.synced} operaciones · ${data.conflicts} conflictos`)
      fetchAll()
    } catch {
      setSyncMsg('Error al sincronizar con el servidor central')
    }
    setSyncing(false)
  }

  const filtered = sales.filter(s =>
    !search || s.customer_name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      {/* Cabecera */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-5">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Ventas</h1>
        <div className="sm:ml-auto flex items-center gap-2 flex-wrap">
          {queueStatus && queueStatus.pending > 0 && (
            <button
              onClick={handleSync}
              disabled={syncing || queueStatus.node_role !== 'client'}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <span className="inline-block w-2 h-2 rounded-full bg-white animate-pulse" />
              {syncing ? 'Sincronizando…' : `${queueStatus.pending} pendientes de sync`}
            </button>
          )}
          {queueStatus && queueStatus.pending === 0 && queueStatus.node_role === 'client' && (
            <span className="text-xs text-green-600 dark:text-green-400 font-medium">✓ Sincronizado</span>
          )}
          <select
            value={warehouse}
            onChange={e => setWarehouse(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Todos los almacenes</option>
            <option value="ALM-A">Almacén Norte</option>
            <option value="ALM-B">Almacén Sur</option>
          </select>
          <input
            type="text"
            placeholder="Buscar cliente…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 w-44"
          />
        </div>
      </div>

      {syncMsg && (
        <p className="text-sm text-indigo-600 dark:text-indigo-400 mb-4">{syncMsg}</p>
      )}

      {/* Stats (solo admin/gestor) */}
      {canSeeStats && stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5">
          <StatCard label="Total ventas" value={stats.total_sales} />
          <StatCard
            label="Ingresos totales"
            value={`${stats.total_revenue.toFixed(2)}€`}
            sub="solo ventas con precio registrado"
          />
          {Object.entries(stats.by_warehouse).map(([wh, cnt]) => (
            <StatCard key={wh} label={`Ventas ${wh}`} value={cnt} />
          ))}
        </div>
      )}

      {/* Tabla */}
      {loading ? (
        <p className="text-gray-400 dark:text-gray-500 text-sm text-center py-12">Cargando…</p>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-400 dark:text-gray-500 text-sm">Sin ventas registradas</p>
          <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">
            Di al chatbot: <em>"Vende 2 filtros de aceite al cliente García"</em>
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {['Fecha', 'Producto', 'Nº Serie', 'Cliente', 'Cant.', 'Precio unit.', 'Total', 'Almacén', 'Vendedor', 'Estado'].map(h => (
                  <th key={h} className="px-3 py-2.5 text-left font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {filtered.map(sale => (
                <tr key={sale.id} className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <td className="px-3 py-2.5 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                    {new Date(sale.created_at).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' })}
                  </td>
                  <td className="px-3 py-2.5 font-medium text-gray-900 dark:text-gray-100">{sale.product_name}</td>
                  <td className="px-3 py-2.5 font-mono text-xs text-gray-500 dark:text-gray-400">{sale.serial_number || '—'}</td>
                  <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300">{sale.customer_name || '—'}</td>
                  <td className="px-3 py-2.5 text-center font-semibold text-gray-900 dark:text-gray-100">{sale.quantity}</td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">
                    {sale.unit_price != null ? `${sale.unit_price.toFixed(2)}€` : '—'}
                  </td>
                  <td className="px-3 py-2.5 font-semibold text-gray-900 dark:text-gray-100">
                    {sale.total_price != null ? `${sale.total_price.toFixed(2)}€` : '—'}
                  </td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{sale.warehouse_code}</td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{sale.seller_username || '—'}</td>
                  <td className="px-3 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[sale.status] || ''}`}>
                      {STATUS_LABELS[sale.status] || sale.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">{filtered.length} venta{filtered.length !== 1 ? 's' : ''}</p>
    </div>
  )
}
