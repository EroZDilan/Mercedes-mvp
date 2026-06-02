import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const STATUS_LABELS = {
  disponible: 'Disponible',
  reservado: 'Reservado',
  en_reparacion: 'En reparación',
  dado_de_baja: 'Baja',
}
const STATUS_COLORS = {
  disponible: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  reservado: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  en_reparacion: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
  dado_de_baja: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
}

function StatusBadge({ status }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[status] || 'bg-gray-100 text-gray-600'}`}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

function EditModal({ item, type, onClose, onSave }) {
  const isSerial = type === 'serial'
  const [form, setForm] = useState(
    isSerial
      ? { status: item.status, location_in_warehouse: item.location_in_warehouse || '' }
      : { quantity: item.quantity, status: item.status, location_in_warehouse: item.location_in_warehouse || '', min_quantity: item.min_quantity }
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const endpoint = isSerial ? `/stock/serial/${item.id}` : `/stock/${item.id}`
      await api.put(endpoint, form)
      onSave()
    } catch (e) {
      setError(e.response?.data?.detail || 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md p-6">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Editar: {item.product_name}
        </h3>
        <div className="space-y-3">
          {!isSerial && (
            <>
              <div>
                <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Cantidad</label>
                <input
                  type="number" min={0}
                  value={form.quantity}
                  onChange={(e) => setForm({ ...form, quantity: parseInt(e.target.value) || 0 })}
                  className="w-full mt-1 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Cantidad mínima</label>
                <input
                  type="number" min={0}
                  value={form.min_quantity}
                  onChange={(e) => setForm({ ...form, min_quantity: parseInt(e.target.value) || 0 })}
                  className="w-full mt-1 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </>
          )}
          <div>
            <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Estado</label>
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
              className="w-full mt-1 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {Object.entries(STATUS_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Ubicación</label>
            <input
              type="text"
              value={form.location_in_warehouse}
              onChange={(e) => setForm({ ...form, location_in_warehouse: e.target.value })}
              className="w-full mt-1 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
        {error && <p className="text-red-500 text-xs mt-3">{error}</p>}
        <div className="flex gap-2 mt-5 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100">
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Stock() {
  const { isAdmin, isGestor } = useAuth()
  const [tab, setTab] = useState('cantidad')
  const [items, setItems] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)

  const fetchStock = useCallback(async () => {
    setLoading(true)
    try {
      const endpoint = tab === 'cantidad' ? '/stock' : '/stock/serial'
      const { data } = await api.get(endpoint)
      setItems(data)
    } catch {}
    setLoading(false)
  }, [tab])

  useEffect(() => { fetchStock() }, [fetchStock])

  const filtered = items.filter((i) =>
    i.product_name?.toLowerCase().includes(search.toLowerCase()) ||
    i.product_code?.toLowerCase().includes(search.toLowerCase())
  )

  const handleSaved = () => { setEditing(null); fetchStock() }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-5">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Stock</h1>
        <div className="flex gap-1">
          {['cantidad', 'serie'].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                tab === t
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {t === 'cantidad' ? 'Por cantidad' : 'Nº de serie'}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Buscar producto…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="sm:ml-auto px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 w-full sm:w-64"
        />
      </div>

      {loading ? (
        <p className="text-gray-400 dark:text-gray-500 text-sm text-center py-12">Cargando…</p>
      ) : filtered.length === 0 ? (
        <p className="text-gray-400 dark:text-gray-500 text-sm text-center py-12">Sin resultados</p>
      ) : tab === 'cantidad' ? (
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {['Código', 'Nombre', 'Categoría', 'Cantidad', 'Mín.', 'Ubicación', 'Estado', ''].map((h) => (
                  <th key={h} className="px-3 py-2.5 text-left font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {filtered.map((item) => (
                <tr key={item.id} className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <td className="px-3 py-2.5 font-mono text-xs text-gray-500 dark:text-gray-400">{item.product_code}</td>
                  <td className="px-3 py-2.5 font-medium text-gray-900 dark:text-gray-100">{item.product_name}</td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{item.category || '—'}</td>
                  <td className="px-3 py-2.5">
                    <span className={`font-semibold ${item.quantity <= item.min_quantity ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'}`}>
                      {item.quantity} {item.unit}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{item.min_quantity}</td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{item.location_in_warehouse || '—'}</td>
                  <td className="px-3 py-2.5"><StatusBadge status={item.status} /></td>
                  <td className="px-3 py-2.5">
                    <button
                      onClick={() => setEditing({ item, type: 'cantidad' })}
                      className="text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 text-xs font-medium"
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {['Código', 'Nombre', 'Nº Serie', 'Categoría', 'Ubicación', 'Estado', ''].map((h) => (
                  <th key={h} className="px-3 py-2.5 text-left font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {filtered.map((item) => (
                <tr key={item.id} className="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <td className="px-3 py-2.5 font-mono text-xs text-gray-500 dark:text-gray-400">{item.product_code}</td>
                  <td className="px-3 py-2.5 font-medium text-gray-900 dark:text-gray-100">{item.product_name}</td>
                  <td className="px-3 py-2.5 font-mono text-xs text-gray-500 dark:text-gray-400">{item.serial_number}</td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{item.category || '—'}</td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{item.location_in_warehouse || '—'}</td>
                  <td className="px-3 py-2.5"><StatusBadge status={item.status} /></td>
                  <td className="px-3 py-2.5">
                    <button
                      onClick={() => setEditing({ item, type: 'serial' })}
                      className="text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 text-xs font-medium"
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">{filtered.length} item{filtered.length !== 1 ? 's' : ''}</p>

      {editing && (
        <EditModal
          item={editing.item}
          type={editing.type}
          onClose={() => setEditing(null)}
          onSave={handleSaved}
        />
      )}
    </div>
  )
}
