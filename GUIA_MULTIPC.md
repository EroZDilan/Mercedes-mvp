# Guía: Probar el proyecto en 2 PCs conectadas

**Versión:** 1.0 | **Fecha:** Julio 2026

---

## Qué vas a montar

```
PC-A (Servidor central)            PC-B (Nodo cliente)
┌─────────────────────────┐        ┌─────────────────────────┐
│  Backend FastAPI :8000  │◄──────►│  Backend FastAPI :8000  │
│  Frontend Vite   :3000  │  WiFi  │  Frontend Vite   :3000  │
│  InvenTree       :8080  │        │  Ollama (LLM + audio)   │
│  Ollama                 │        │  (sin InvenTree)        │
└─────────────────────────┘        └─────────────────────────┘
         Fuente de verdad                Nodo de trabajo
```

Ambas PCs necesitan estar en la **misma red WiFi o LAN**.

---

## Requisitos en ambas PCs

- Git instalado
- Python 3.11+
- Node.js 18+
- Ollama instalado y con el modelo descargado (`ollama pull qwen2.5:7b`)
- ffmpeg instalado (`sudo pacman -S ffmpeg` en Arch/Garuda)
- **Solo PC-A:** Docker instalado

---

## Paso 1 — Saber las IPs de cada PC

En cada PC, abre una terminal y ejecuta:

```bash
ip route get 1 | awk '{print $7; exit}'
# Ejemplo de salida: 192.168.1.10
```

Anota las dos IPs. Ejemplo para esta guía:
- **PC-A (servidor):** `192.168.1.10`
- **PC-B (cliente):**  `192.168.1.50`

---

## Paso 2 — Clonar el proyecto en ambas PCs

```bash
git clone https://github.com/EroZDilan/Mercedes-mvp.git
cd Mercedes-mvp
```

Si ya tienes el proyecto, actualiza:

```bash
cd Mercedes-mvp
git pull origin main
```

---

## Paso 3 — Configurar y levantar PC-A (Servidor)

### 3.1 Ejecutar el setup (solo la primera vez)

```bash
bash scripts/setup.sh
```

### 3.2 Abrir el firewall para PC-B

```bash
# Permitir que PC-B acceda al backend y al frontend
sudo ufw allow 8000   # backend
sudo ufw allow 3000   # frontend
sudo ufw allow 8080   # InvenTree (opcional, para que PC-B pueda verlo)
```

Si no tienes `ufw`:

```bash
# Con firewalld (Garuda/Fedora)
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --add-port=3000/tcp --permanent
sudo firewall-cmd --reload
```

### 3.3 Añadir la IP de PC-B en el .env de PC-A

Edita el archivo `.env` en PC-A y actualiza `ALLOWED_ORIGINS`:

```env
ALLOWED_ORIGINS=https://localhost:3000,https://192.168.1.50:3000
```

> Sustituye `192.168.1.50` por la IP real de PC-B.

### 3.4 Arrancar el servidor

```bash
bash scripts/start_server.sh
```

Al terminar verás algo como:

```
  ✓ Backend listo en https://localhost:8000
  ✓ Frontend listo en https://localhost:3000
  ✓ InvenTree disponible en http://localhost:8080
```

### 3.5 Verificar que PC-A es accesible desde la red

```bash
curl http://192.168.1.10:8000/health
# Debe devolver: {"status":"ok","node_id":"server-principal","node_role":"server",...}
```

---

## Paso 4 — Configurar y levantar PC-B (Cliente)

### 4.1 Ejecutar el setup (solo la primera vez)

```bash
bash scripts/setup.sh
```

### 4.2 Arrancar el cliente

```bash
# Pasas la IP del servidor como argumento
bash scripts/start_client.sh 192.168.1.10
```

El script hace automáticamente:
- Verifica que puede conectar con PC-A
- Actualiza el `.env` con `NODE_ROLE=client` y `CENTRAL_SERVER_URL`
- Arranca backend local, Ollama y frontend (sin InvenTree)

Al terminar verás:

```
  ✓ Servidor encontrado: server-principal en http://192.168.1.10:8000
  ✓ .env configurado (NODE_ROLE=client, CENTRAL_SERVER_URL=http://192.168.1.10:8000)
  ✓ Backend listo en https://localhost:8000
  ✓ Frontend listo en https://localhost:3000
```

---

## Paso 5 — Abrir el chatbot en el navegador

**En PC-A:**
```
https://localhost:3000
```

**En PC-B:**
```
https://localhost:3000
```

**Desde cualquier PC de la red (o móvil):**
```
https://192.168.1.10:3000   ← abre el frontend de PC-A
https://192.168.1.50:3000   ← abre el frontend de PC-B
```

> La primera vez el navegador mostrará un aviso de certificado autofirmado.
> Haz clic en **Avanzado → Continuar de todos modos**.

---

## Paso 6 — Lista de pruebas

### Pruebas básicas (hacer en ambas PCs)

- [ ] Login con `admin` / `admin1234`
- [ ] El chatbot responde a: *"¿Cuánto stock hay de filtros de aceite?"*
- [ ] El chatbot responde a: *"¿Qué hay en el Almacén Norte?"*
- [ ] La grabación de audio transcribe correctamente

### Pruebas multi-PC específicas

- [ ] Desde PC-B, hacer una consulta de stock → los datos son los mismos que en PC-A
- [ ] Crear un producto desde PC-B: *"Crea un producto llamado Filtro premium con 50 unidades"*
- [ ] Verificar en PC-A que el producto aparece en stock
- [ ] En PC-A, consultar el mismo producto → aparece el creado desde PC-B
- [ ] Verificar en InvenTree (`http://192.168.1.10:8080`) que el producto se sincronizó

### Prueba de acceso cruzado

- [ ] Desde el **navegador de PC-B**, abrir `https://192.168.1.10:3000` (frontend de PC-A)
- [ ] Hacer login y probar el chatbot → funciona en PC-B usando el backend de PC-A

---

## Solución de problemas frecuentes

### "No se pudo conectar con el servidor"

```bash
# Verificar que el backend de PC-A escucha en 0.0.0.0 (no solo localhost)
curl http://<IP-PC-A>:8000/health

# Si falla, verificar firewall en PC-A:
sudo ufw status
sudo ufw allow 8000
```

### "CORS error" en el navegador de PC-B

El `.env` de PC-A no tiene la IP de PC-B en `ALLOWED_ORIGINS`.

```env
# .env de PC-A
ALLOWED_ORIGINS=https://localhost:3000,https://192.168.1.50:3000
```

Después de editar el `.env`, reinicia el backend de PC-A:

```bash
bash scripts/stop.sh
bash scripts/start_server.sh
```

### El chatbot de PC-B no responde (timeout)

PC-B usa su propio Ollama local. Verificar que está corriendo:

```bash
curl http://localhost:11434
# Debe responder: "Ollama is running"

ollama list
# Debe mostrar: qwen2.5:7b (u otro modelo configurado)
```

Si el modelo no está:

```bash
ollama pull qwen2.5:7b
```

### Audio no funciona en PC-B

```bash
# Verificar ffmpeg
which ffmpeg   # debe mostrar /usr/bin/ffmpeg

# Si no está:
sudo pacman -S ffmpeg    # Garuda/Arch
# o
sudo apt install ffmpeg   # Ubuntu/Debian
```

### InvenTree no sincroniza desde PC-B

InvenTree solo corre en PC-A. Las acciones de PC-B se sincronizan con InvenTree
a través del backend de PC-B, que llama a InvenTree de PC-A.

Verificar que `INVENTREE_URL` en PC-B apunta a PC-A:

```env
# .env de PC-B
INVENTREE_URL=http://192.168.1.10:8080/api/
INVENTREE_TOKEN=<token del servidor>
```

> El token de InvenTree se obtiene una sola vez en PC-A:
> ```bash
> curl http://localhost:8080/api/user/token/ -u "admin:admin1234"
> ```

---

## Para parar todo

```bash
bash scripts/stop.sh
```

---

## Próximo paso: Cola offline

Una vez probado el setup multi-PC básico, el siguiente paso es la **cola offline**:
PC-B podrá hacer ventas y movimientos sin red, y al reconectarse sincronizará
todo con PC-A en orden cronológico.

Ver `PROGRESO.md` para el estado actual del desarrollo.
