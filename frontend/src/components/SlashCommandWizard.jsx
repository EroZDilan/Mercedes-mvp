import { useState } from 'react'

const STATUS_OPTS = [
  { value: 'disponible',    label: 'Disponible' },
  { value: 'reservado',     label: 'Reservado' },
  { value: 'en_reparacion', label: 'En reparación' },
  { value: 'dado_de_baja',  label: 'Dado de baja' },
]

const ROLE_OPTS = [
  { value: 'operador',   label: 'Operador' },
  { value: 'supervisor', label: 'Supervisor' },
  { value: 'gestor',     label: 'Gestor' },
  { value: 'admin',      label: 'Admin' },
]

const FIELD_OPTS = [
  { value: 'product_name',          label: 'Nombre del producto' },
  { value: 'category',              label: 'Categoría' },
  { value: 'min_quantity',          label: 'Stock mínimo' },
  { value: 'unit',                  label: 'Unidad de medida' },
  { value: 'location_in_warehouse', label: 'Ubicación' },
]

const TITLES = {
  mover:               '↔️  Transferir producto',
  estado:              '🔄  Cambiar estado',
  crear:               '➕  Crear producto',
  editar:              '✏️  Editar producto',
  eliminar:            '🗑️  Dar de baja producto',
  usuario:             '👤  Gestionar usuario',
  usuario_crear:       '👤  Crear usuario',
  usuario_desactivar:  '⛔  Desactivar usuario',
  usuario_contraseña:  '🔑  Resetear contraseña',
}

// ── tiny subcomponents ──────────────────────────────────────────────────────

function Shell({ title, onClose, children }) {
  return (
    <div className="absolute bottom-full left-0 right-0 mb-2 mx-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-xl z-20 flex flex-col max-h-[72vh]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex-shrink-0">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
        <button
          onClick={() => onClose()}
          className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-base leading-none"
        >✕</button>
      </div>
      <div className="p-4 overflow-y-auto">{children}</div>
    </div>
  )
}

function Field({ label, value = '', onChange, type = 'text', placeholder = '', min, max, disabled }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        min={min}
        max={max}
        disabled={disabled}
        className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
      />
    </div>
  )
}

function Sel({ label, options, value = '', onChange, disabled }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || !options.length}
        className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
      >
        <option value="">— Selecciona —</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

function ProductSel({ stock, value, onChange }) {
  const byWarehouse = stock.reduce((acc, s) => {
    const key = s.warehouse_name
    if (!acc[key]) acc[key] = []
    acc[key].push(s)
    return acc
  }, {})

  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Producto</label>
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      >
        <option value="">— Selecciona producto —</option>
        {Object.entries(byWarehouse).map(([wh, items]) => (
          <optgroup key={wh} label={wh}>
            {items.map((s) => (
              <option key={s.id} value={s.id}>
                {s.product_name} ({s.product_code})
                {s.type === 'serial' ? ` · SN: ${s.serial_number}` : ` · cant: ${s.quantity}`}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  )
}

// ── main component ──────────────────────────────────────────────────────────

export default function SlashCommandWizard({ command, slashData, onSend, onClose }) {
  const [form, setForm] = useState({})
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const { stock = [], warehouses = [], users = [] } = slashData || {}
  const selectedProduct = stock.find((s) => s.id === Number(form.product_id))
  const destWarehouses = warehouses.filter((w) => w.id !== selectedProduct?.warehouse_id)

  // ── usuario subcommand picker ─────────────────────────────────────────────
  if (command === 'usuario') {
    return (
      <Shell title={TITLES.usuario} onClose={onClose}>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">Selecciona una acción:</p>
        <div className="space-y-2">
          {[
            { cmd: 'usuario_crear',      label: '➕  Crear usuario' },
            { cmd: 'usuario_desactivar', label: '⛔  Desactivar usuario' },
            { cmd: 'usuario_contraseña', label: '🔑  Resetear contraseña' },
          ].map(({ cmd, label }) => (
            <button
              key={cmd}
              onClick={() => onClose(cmd)}
              className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 rounded-xl text-sm font-medium text-gray-800 dark:text-gray-200 text-left border border-gray-200 dark:border-gray-600 transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      </Shell>
    )
  }

  // ── build natural-language message from form ──────────────────────────────
  const buildMessage = () => {
    if (command === 'mover') {
      const p = selectedProduct
      const dest = warehouses.find((w) => w.id === Number(form.dest_warehouse_id))
      if (!p || !dest) return null
      const qty = p.type === 'serial' ? 1 : Math.max(1, Number(form.quantity) || 1)
      return `Transfiere ${qty} unidad${qty !== 1 ? 'es' : ''} de ${p.product_name} (${p.product_code}) del ${p.warehouse_name} (${p.warehouse_code}) al ${dest.name} (${dest.code})`
    }
    if (command === 'estado') {
      const p = selectedProduct
      if (!p || !form.new_status) return null
      return `Cambia el estado de ${p.product_name} (${p.product_code}) en ${p.warehouse_name} (${p.warehouse_code}) a ${form.new_status}`
    }
    if (command === 'crear') {
      const wh = warehouses.find((w) => w.id === Number(form.warehouse_id))
      if (!wh || !form.product_code || !form.product_name || !form.category) return null
      const qty = Number(form.quantity) || 0
      const min = Number(form.min_quantity) || 0
      const unit = form.unit || 'unidad'
      const loc = form.location ? `, ubicación ${form.location}` : ''
      return `Crea un nuevo producto en ${wh.name} (${wh.code}): código ${form.product_code}, nombre ${form.product_name}, categoría ${form.category}, cantidad ${qty}, mínimo ${min}, unidad ${unit}${loc}`
    }
    if (command === 'editar') {
      const p = selectedProduct
      if (!p || !form.field || !form.new_value) return null
      const fieldLabel = FIELD_OPTS.find((f) => f.value === form.field)?.label || form.field
      return `Edita el producto ${p.product_name} (${p.product_code}) en ${p.warehouse_name} (${p.warehouse_code}): cambia ${fieldLabel} a "${form.new_value}"`
    }
    if (command === 'eliminar') {
      const p = selectedProduct
      if (!p) return null
      return `Da de baja el producto ${p.product_name} (${p.product_code}) en ${p.warehouse_name} (${p.warehouse_code})`
    }
    if (command === 'usuario_crear') {
      if (!form.username || !form.full_name || !form.role) return null
      const wh = warehouses.find((w) => w.id === Number(form.warehouse_id))
      const whPart = wh ? `, almacén ${wh.name} (${wh.code})` : ''
      return `Crea un usuario: username ${form.username}, nombre ${form.full_name}, rol ${form.role}${whPart}`
    }
    if (command === 'usuario_desactivar') {
      const u = users.find((u) => u.id === Number(form.user_id))
      if (!u) return null
      return `Desactiva al usuario ${u.username}`
    }
    if (command === 'usuario_contraseña') {
      const u = users.find((u) => u.id === Number(form.user_id))
      if (!u || !form.new_password) return null
      return `Resetea la contraseña del usuario ${u.username} a ${form.new_password}`
    }
    return null
  }

  const message = buildMessage()

  return (
    <Shell title={TITLES[command] || command} onClose={onClose}>
      <div className="space-y-3">

        {command === 'mover' && (
          <>
            <ProductSel stock={stock} value={form.product_id} onChange={(v) => { set('product_id', v); set('dest_warehouse_id', '') }} />
            {selectedProduct?.type === 'bulk' && (
              <Field
                label={`Cantidad (máx. ${selectedProduct.quantity})`}
                type="number" min={1} max={selectedProduct.quantity}
                value={form.quantity} onChange={(v) => set('quantity', v)}
              />
            )}
            <Sel
              label="Almacén destino"
              options={destWarehouses.map((w) => ({ value: w.id, label: `${w.name} (${w.code})` }))}
              value={form.dest_warehouse_id} onChange={(v) => set('dest_warehouse_id', v)}
              disabled={!selectedProduct}
            />
          </>
        )}

        {command === 'estado' && (
          <>
            <ProductSel stock={stock} value={form.product_id} onChange={(v) => set('product_id', v)} />
            <Sel label="Nuevo estado" options={STATUS_OPTS.map((s) => ({ value: s.value, label: s.label }))}
              value={form.new_status} onChange={(v) => set('new_status', v)} />
          </>
        )}

        {command === 'crear' && (
          <>
            <Sel label="Almacén" options={warehouses.map((w) => ({ value: w.id, label: `${w.name} (${w.code})` }))}
              value={form.warehouse_id} onChange={(v) => set('warehouse_id', v)} />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Código" value={form.product_code} onChange={(v) => set('product_code', v)} placeholder="Ej: P007" />
              <Field label="Categoría" value={form.category} onChange={(v) => set('category', v)} placeholder="Ej: Lubricantes" />
            </div>
            <Field label="Nombre del producto" value={form.product_name} onChange={(v) => set('product_name', v)} placeholder="Ej: Aceite motor 10W40" />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Cantidad inicial" type="number" min={0} value={form.quantity} onChange={(v) => set('quantity', v)} />
              <Field label="Stock mínimo" type="number" min={0} value={form.min_quantity} onChange={(v) => set('min_quantity', v)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Unidad" value={form.unit} onChange={(v) => set('unit', v)} placeholder="unidad" />
              <Field label="Ubicación (opcional)" value={form.location} onChange={(v) => set('location', v)} placeholder="Ej: Estante A3" />
            </div>
          </>
        )}

        {command === 'editar' && (
          <>
            <ProductSel stock={stock} value={form.product_id} onChange={(v) => { set('product_id', v); set('new_value', '') }} />
            <Sel label="Campo a editar" options={FIELD_OPTS.map((f) => ({ value: f.value, label: f.label }))}
              value={form.field} onChange={(v) => { set('field', v); set('new_value', '') }} />
            <Field
              label="Nuevo valor"
              type={form.field === 'min_quantity' ? 'number' : 'text'}
              value={form.new_value} onChange={(v) => set('new_value', v)}
              disabled={!form.field}
            />
          </>
        )}

        {command === 'eliminar' && (
          <>
            <ProductSel stock={stock} value={form.product_id} onChange={(v) => set('product_id', v)} />
            {selectedProduct && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
                ⚠️ Se dará de baja <strong>{selectedProduct.product_name}</strong> de {selectedProduct.warehouse_name}. Requiere confirmación.
              </div>
            )}
          </>
        )}

        {command === 'usuario_crear' && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Nombre de usuario" value={form.username} onChange={(v) => set('username', v)} placeholder="sin espacios" />
              <Sel label="Rol" options={ROLE_OPTS.map((r) => ({ value: r.value, label: r.label }))}
                value={form.role} onChange={(v) => { set('role', v); set('warehouse_id', '') }} />
            </div>
            <Field label="Nombre completo" value={form.full_name} onChange={(v) => set('full_name', v)} />
            {['supervisor', 'operador'].includes(form.role) && (
              <Sel label="Almacén asignado" options={warehouses.map((w) => ({ value: w.id, label: `${w.name} (${w.code})` }))}
                value={form.warehouse_id} onChange={(v) => set('warehouse_id', v)} />
            )}
          </>
        )}

        {command === 'usuario_desactivar' && (
          <Sel
            label="Usuario a desactivar"
            options={users.filter((u) => u.is_active).map((u) => ({ value: u.id, label: `${u.username} (${u.role})` }))}
            value={form.user_id} onChange={(v) => set('user_id', v)}
          />
        )}

        {command === 'usuario_contraseña' && (
          <>
            <Sel label="Usuario" options={users.map((u) => ({ value: u.id, label: `${u.username} (${u.role})` }))}
              value={form.user_id} onChange={(v) => set('user_id', v)} />
            <Field label="Nueva contraseña" type="password" value={form.new_password} onChange={(v) => set('new_password', v)} />
          </>
        )}

      </div>

      {message && (
        <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl border border-gray-100 dark:border-gray-600">
          <p className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-1">Mensaje al asistente:</p>
          <p className="text-sm text-gray-700 dark:text-gray-300 italic">"{message}"</p>
        </div>
      )}

      <div className="mt-4 flex gap-2 justify-end">
        <button
          onClick={() => onClose()}
          className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
        >
          Cancelar
        </button>
        <button
          onClick={() => message && onSend(message)}
          disabled={!message}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white rounded-xl text-sm font-medium transition-colors"
        >
          Enviar al asistente →
        </button>
      </div>
    </Shell>
  )
}
