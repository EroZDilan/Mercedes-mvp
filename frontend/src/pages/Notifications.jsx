import { useNotifications } from '../hooks/useNotifications'

const TYPE_ICONS = {
  stock_modification: '📦',
  stock_low: '⚠️',
  crm_note: '📝',
  chat_unresolved: '💬',
  account_locked: '🔒',
  sync_error: '🔄',
}

const TYPE_LABELS = {
  stock_modification: 'Stock',
  stock_low: 'Stock bajo',
  crm_note: 'Nota CRM',
  chat_unresolved: 'Chat sin resolver',
  account_locked: 'Cuenta bloqueada',
  sync_error: 'Error de sync',
}

export default function Notifications() {
  const { notifications, markRead, markAllRead, refresh } = useNotifications()

  const unread = notifications.filter((n) => !n.is_read)
  const read = notifications.filter((n) => n.is_read)

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
          Notificaciones
          {unread.length > 0 && (
            <span className="ml-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">{unread.length}</span>
          )}
        </h1>
        <div className="flex gap-2">
          {unread.length > 0 && (
            <button
              onClick={markAllRead}
              className="text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 font-medium"
            >
              Marcar todas como leídas
            </button>
          )}
          <button onClick={refresh} className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400">
            ↻ Actualizar
          </button>
        </div>
      </div>

      {notifications.length === 0 && (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">🔔</div>
          <p className="text-gray-500 dark:text-gray-400 text-sm">Sin notificaciones</p>
        </div>
      )}

      {unread.length > 0 && (
        <div className="mb-6">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
            Sin leer ({unread.length})
          </p>
          <div className="space-y-2">
            {unread.map((n) => (
              <NotifCard key={n.id} notif={n} onMarkRead={markRead} />
            ))}
          </div>
        </div>
      )}

      {read.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-2">
            Leídas
          </p>
          <div className="space-y-2 opacity-60">
            {read.map((n) => (
              <NotifCard key={n.id} notif={n} onMarkRead={null} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function NotifCard({ notif, onMarkRead }) {
  const icon = TYPE_ICONS[notif.type] || '🔔'
  const label = TYPE_LABELS[notif.type] || notif.type

  return (
    <div className={`flex gap-3 p-4 rounded-xl border transition-colors ${
      !notif.is_read
        ? 'bg-white dark:bg-gray-900 border-indigo-200 dark:border-indigo-800'
        : 'bg-gray-50 dark:bg-gray-900/50 border-gray-200 dark:border-gray-700'
    }`}>
      <span className="text-xl flex-shrink-0 mt-0.5">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm text-gray-900 dark:text-gray-100">{notif.message}</p>
          {onMarkRead && (
            <button
              onClick={() => onMarkRead(notif.id)}
              className="flex-shrink-0 text-xs text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 font-medium whitespace-nowrap"
            >
              Marcar leída
            </button>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1">
          <span className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 px-2 py-0.5 rounded-full">
            {label}
          </span>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {new Date(notif.created_at).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>
    </div>
  )
}
