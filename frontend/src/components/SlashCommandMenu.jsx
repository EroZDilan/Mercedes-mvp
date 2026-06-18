const COMMANDS = {
  mover:    { icon: '↔️', label: 'Transferir producto',   desc: 'Mover entre almacenes' },
  estado:   { icon: '🔄', label: 'Cambiar estado',        desc: 'disponible, reservado, reparación…' },
  crear:    { icon: '➕', label: 'Crear producto',         desc: 'Nuevo producto en inventario' },
  editar:   { icon: '✏️', label: 'Editar producto',       desc: 'Modificar datos de un producto' },
  eliminar: { icon: '🗑️', label: 'Dar de baja',          desc: 'Eliminar producto del sistema' },
  usuario:  { icon: '👤', label: 'Gestionar usuario',     desc: 'Crear, desactivar o cambiar contraseña' },
}

export default function SlashCommandMenu({ available, inputValue, onSelect }) {
  if (!inputValue.startsWith('/')) return null

  const search = inputValue.slice(1).toLowerCase()
  const filtered = available.filter((c) => !search || c.startsWith(search))
  if (!filtered.length) return null

  return (
    <div className="absolute bottom-full left-0 right-0 mb-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg overflow-hidden z-20">
      <p className="px-3 py-1.5 text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide border-b border-gray-100 dark:border-gray-700">
        Comandos disponibles
      </p>
      {filtered.map((cmd) => (
        <button
          key={cmd}
          onMouseDown={(e) => { e.preventDefault(); onSelect(cmd) }}
          className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 text-left transition-colors"
        >
          <span className="text-lg">{COMMANDS[cmd]?.icon}</span>
          <div>
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
              /{cmd} <span className="font-normal text-gray-500 dark:text-gray-400">— {COMMANDS[cmd]?.label}</span>
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">{COMMANDS[cmd]?.desc}</p>
          </div>
        </button>
      ))}
    </div>
  )
}
