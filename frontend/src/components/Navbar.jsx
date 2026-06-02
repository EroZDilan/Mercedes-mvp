import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useNotifications } from '../hooks/useNotifications'

const roleLabel = { admin: 'Admin', gestor: 'Gestor', supervisor: 'Supervisor', operador: 'Operador' }

export default function Navbar() {
  const { user, logout, darkMode, setDarkMode, isAdmin, isGestor } = useAuth()
  const { unreadCount } = useNotifications()
  const location = useLocation()
  const navigate = useNavigate()

  const links = [
    { to: '/chat', label: 'Chat' },
    { to: '/stock', label: 'Stock' },
    { to: '/crm', label: 'CRM' },
    { to: '/notifications', label: 'Notificaciones' },
    ...(isAdmin ? [{ to: '/admin', label: 'Admin' }] : []),
  ]

  const handleLogout = () => { logout(); navigate('/login') }
  const active = (to) => location.pathname.startsWith(to)

  return (
    <nav className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center justify-between gap-4 sticky top-0 z-50">
      <div className="flex items-center gap-1 flex-wrap">
        <span className="text-indigo-600 dark:text-indigo-400 font-bold text-lg mr-3">StockBot</span>
        {links.map(({ to, label }) => (
          <Link
            key={to}
            to={to}
            className={`relative px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              active(to)
                ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300'
                : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800'
            }`}
          >
            {label}
            {to === '/notifications' && unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </Link>
        ))}
      </div>
      <div className="flex items-center gap-3 ml-auto">
        <span className="text-xs text-gray-500 dark:text-gray-400 hidden sm:block">
          {user?.username} · <span className="capitalize">{roleLabel[user?.role] || user?.role}</span>
        </span>
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="p-1.5 rounded-md text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          title="Cambiar tema"
        >
          {darkMode ? '☀️' : '🌙'}
        </button>
        <button
          onClick={handleLogout}
          className="text-sm text-red-500 hover:text-red-700 dark:hover:text-red-400 transition-colors"
        >
          Salir
        </button>
      </div>
    </nav>
  )
}
