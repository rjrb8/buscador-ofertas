# Buscador de Ofertas Laborales

Agente construido sobre Claude Code que recibe los datos de un candidato
(nombre, CV en `.docx`, perfil profesional declarado y correo), analiza su
CV, busca ofertas laborales reales en internet que coincidan con su perfil,
y entrega los resultados: un top 10 en pantalla y el resto por correo.

## Arquitectura

El sistema tiene dos capas:

- **Capa de razonamiento (IA):** `CLAUDE.md` + 4 subagentes definidos en
  `.claude/agents/*.md`, interpretados directamente por Claude Code.
- **Capa de maquinaria auxiliar (código):** dos servidores MCP en Python que
  exponen a los subagentes capacidades que la IA no tiene de forma nativa
  (leer `.docx`, enviar correo por SMTP), más un script para la ejecución
  diaria automatizada.

### Subagentes (`.claude/agents/`)

| Subagente | Modelo | Responsabilidad |
|---|---|---|
| `planificador` | haiku | Decide, solo leyendo `memory/`, qué subagentes hace falta correr para un candidato (evita repetir trabajo ya hecho). |
| `analista-cv` | sonnet | Pide los 4 datos de entrada, valida formato, lee el CV con `read_cv_docx` y guarda el desglose (`cv_resumen_analizado`) comparado contra el perfil declarado. |
| `buscador-empleo` | sonnet | Lee el resumen de CV ya generado y busca ofertas reales en fuentes verificables, en lotes de 10-15, hasta completar `ofertas_totales`. |
| `notificador` | haiku | Selecciona el top 10 para pantalla, evita reenviar ofertas ya presentes en `historial_envios`, y dispara el correo una sola vez por ejecución. |

### Orquestación

```
planificador → (según el plan que devuelva) → analista-cv → buscador-empleo → notificador
```

Reglas fijas (ver `CLAUDE.md`):

1. Nunca se ejecuta `analista-cv`, `buscador-empleo` o `notificador`
   directamente sin pasar antes por `planificador`.
2. Nunca se paraleliza ni se salta el orden sobre el mismo candidato.
3. No se avanza sin los 4 datos de entrada completos.
4. Nunca se inventan ofertas: si no se llega a la meta buscada, se reporta
   lo que se encontró y se detiene.
5. El CV y los datos del candidato nunca se envían a servicios externos no
   autorizados explícitamente.

### Servidores MCP (`mcp_*.py`)

- **`cv-reader`** (`mcp_cv_reader.py`): expone `read_cv_docx`, que extrae
  texto de párrafos y tablas de un `.docx`.
- **`email-ofertas`** (`mcp_email_server.py`): expone `listar_pendientes` y
  `enviar_ofertas_candidato`, que envía por Gmail SMTP las ofertas
  pendientes de un candidato y registra el envío en su `historial_envios`
  para evitar duplicados.

Ambos se registran en Claude Code apuntando al intérprete de `venv/` (no al
`python` global), porque ahí están instaladas sus dependencias
(`python-docx`, `mcp`, etc.).

### Ejecución diaria (`ejecutar_busqueda_diaria.py`)

Pensado para correr por cron: recorre `memory/candidatos/*.json` y por cada
candidato invoca `claude -p` para que el agente revise si hay ofertas
nuevas y, si corresponde, las envíe — respetando siempre la orquestación de
arriba.

## Persistencia (`memory/`)

- `memory/candidatos/<correo_normalizado>.json`: estado de cada candidato
  (`cv_resumen_analizado`, `ofertas_totales`, `ofertas_enviadas_correo`,
  `historial_envios`, fechas de registro y última búsqueda).
- `memory/log_ejecuciones.md`: bitácora de cada corrida (candidato, ofertas
  encontradas/enviadas, estado, errores).
- `memory/schema.md`: esquema de referencia de los JSON de candidato.

**Nota:** `memory/candidatos/`, `cv-input/`, `logs/` y `output/` contienen
datos personales reales de candidatos (CV, nombre, correo, historial
laboral) y están excluidos del repositorio vía `.gitignore`. Solo se versiona
la estructura de carpetas.

## Permisos y seguridad (`.claude/settings.json`)

- Lectura/escritura sin confirmación dentro de `memory/`, `output/` y `logs/`.
- Cualquier comando `Bash`, o cualquier escritura fuera de esas tres
  carpetas, requiere confirmación manual.
- Se deniegan comandos y lecturas que expongan variables de entorno del
  sistema o archivos de perfil de shell.

Cada subagente además tiene sus propios "Carriles de seguridad" (límite de
reintentos de búsqueda, búsqueda por lotes, verificación de que los links
sean reales, límite de un solo envío de correo por ejecución, límite de
alcance de archivos que puede tocar, etc.) documentados en su propio archivo
`.claude/agents/*.md`.

## Setup

```bash
python -m venv venv
venv/Scripts/pip install -r requirements.txt   # o: pip install python-docx mcp python-dotenv
```

Crear un `.env` en la raíz con:

```
GMAIL_USER=tu_cuenta@gmail.com
GMAIL_APP_PASSWORD=tu_app_password
```

Registrar los servidores MCP (una sola vez):

```bash
claude mcp add cv-reader -- venv/Scripts/python.exe mcp_cv_reader.py
claude mcp add email-ofertas -- venv/Scripts/python.exe mcp_email_server.py
```

## Uso

Simplemente pedirle a Claude Code "quiero buscar empleo para un candidato" y
proveer los 4 datos solicitados (nombre completo, ruta del CV `.docx`,
perfil profesional declarado, correo). El resto del proceso lo maneja la
orquestación descripta arriba.
