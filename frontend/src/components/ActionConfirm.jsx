import { useState } from 'react'
import api from '../api/client'

export default function ActionConfirm({ summary, actionToken, onConfirmed, onCancelled }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleConfirm = async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await api.post('/actions/confirm', { action_token: actionToken })
      onConfirmed(data.detail)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al ejecutar la acción.'
      setError(msg)
      setLoading(false)
    }
  }

  return (
    <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700 rounded-2xl p-4 my-2 max-w-[85%]">
      <div className="flex items-start gap-2 mb-3">
        <span className="text-amber-500 text-base mt-0.5 flex-shrink-0">⚠</span>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wide mb-1.5">
            Confirmación requerida
          </p>
          <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-line leading-relaxed">
            {summary}
          </p>
        </div>
      </div>

      {error && (
        <p className="text-xs text-red-500 dark:text-red-400 mb-2 pl-6">{error}</p>
      )}

      <div className="flex gap-2 pl-6">
        <button
          onClick={handleConfirm}
          disabled={loading}
          className="px-4 py-1.5 bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white text-sm rounded-full font-medium transition-colors"
        >
          {loading ? 'Ejecutando…' : 'Confirmar'}
        </button>
        <button
          onClick={onCancelled}
          disabled={loading}
          className="px-4 py-1.5 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 text-sm rounded-full font-medium transition-colors"
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}
