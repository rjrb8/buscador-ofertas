# Buscador de Ofertas Laborales

Agente construido sobre Claude Code que recibe los datos de un candidato
(nombre, CV en `.docx`, perfil profesional declarado y correo), analiza su
CV, opcionalmente lo optimiza para ATS, busca ofertas laborales reales en
internet que coincidan con su perfil, y entrega los resultados: un top 10
en pantalla y el resto por correo.

## Arquitectura

El sistema tiene dos capas:

- **Capa de razonamiento (IA):** `CLAUDE.md` + 5 subagentes definidos en
  `.claude/agents/*.md`, interpretados directamente por Claude Code.
- **Capa de maquinaria auxiliar (código):** tres servidores MCP en Python
  que exponen a los subagentes capacidades que la IA no tiene de forma
  nativa (leer `.docx`, generar `.docx`, enviar correo por SMTP), más un
  script para la ejecución diaria automatizada.

### Subagentes (`.claude/agents/`)

| Subagente | Modelo | Responsabilidad |
|---|---|---|
| `planificador` | haiku | Decide, solo leyendo `memory/`, qué subagentes hace falta correr para un candidato y en qué orden (evita repetir trabajo ya hecho). |
| `analista-cv` | sonnet | Pide los 4 datos de entrada, valida formato, pregunta el consentimiento de optimización de CV, lee el CV con `read_cv_docx` y guarda el desglose (`cv_resumen_analizado`) comparado contra el perfil declarado. |
| `optimizador-cv` | sonnet | Se ejecuta solo si `cv_optimizacion_consentimiento=true` (registrado por `analista-cv`, nunca se vuelve a preguntar). Diagnostica brechas ATS, reescribe la experiencia (XYZ/STAR/CAR) y genera dos borradores para que el candidato elija la versión a usar. |
| `buscador-empleo` | sonnet | Lee `cv_version_elegida` para saber qué CV priorizar, incorpora las palabras clave faltantes de `cv_analisis_ats` a las búsquedas, y busca ofertas reales en fuentes verificables, en lotes de 10-15, deduplicando contra `ofertas_totales`. |
| `notificador` | haiku | Selecciona el top 10 para pantalla, evita reenviar ofertas ya presentes en `historial_envios`, y dispara el correo una sola vez por ejecución. |

### Orquestación

```
planificador → (según el plan que devuelva, en orden) →
  analista-cv → [optimizador-cv] → buscador-empleo → notificador
```

`optimizador-cv` es condicional: solo corre si el candidato no tiene aún
`cv_version_elegida` registrada (o el CV cambió). Reglas fijas (ver
`CLAUDE.md` y `planificador.md`):

1. Nunca se ejecuta `analista-cv`, `optimizador-cv`, `buscador-empleo` o
   `notificador` directamente sin pasar antes por `planificador`.
2. Nunca se paraleliza ni se salta el orden sobre el mismo candidato.
3. `optimizador-cv`, cuando corre, va siempre después de `analista-cv` y
   antes de `buscador-empleo`. Nunca se invierte ese orden.
4. No se avanza sin los 4 datos de entrada completos (nombre, CV `.docx`,
   perfil, correo).
5. Nunca se inventan ofertas: si no se llega a la meta buscada, se reporta
   lo que se encontró y se detiene.
6. El CV y los datos del candidato nunca se envían a servicios externos no
   autorizados explícitamente.

### El consentimiento de optimización vive en `analista-cv`, no en `optimizador-cv`

Decisión de diseño importante: la pregunta "¿quieres que optimice tu CV?"
se hace una sola vez, dentro de la fase de entrada de `analista-cv` (punto
5), junto con el resto de los datos que ya se le piden al candidato. El
resultado (`cv_optimizacion_consentimiento`) queda guardado en
`memory/candidatos/<correo>.json`, y `optimizador-cv` solo lo **lee** — no
vuelve a preguntarlo.

Esto evita un deadlock estructural: `optimizador-cv` corre como subagente
independiente y solo recibe mensajes reenviados por el orquestador, nunca
texto escrito directamente por el usuario. Si su propio consentimiento
dependiera de una pregunta que él mismo hace, ningún reenvío del
orquestador sería válido como respuesta del candidato, sin importar qué
tan literal fuera el reenvío. Al mover la pregunta a `analista-cv` —que sí
opera en la misma fase conversacional donde el orquestador recoge los 4
datos de entrada— el consentimiento se resuelve en un solo intercambio.

### Servidores MCP (`mcp_*.py`)

- **`cv-reader`** (`mcp_cv_reader.py`): expone `read_cv_docx`, que extrae
  texto de párrafos y tablas de un `.docx`.
- **`cv-writer`** (`mcp_cv_writer.py`): expone `generar_cv_docx`, usado por
  `optimizador-cv` para producir el Borrador 2 en formato `.docx`.
- **`email-ofertas`** (`mcp_email_server.py`): expone `listar_pendientes` y
  `enviar_ofertas_candidato`, que envía por Gmail SMTP las ofertas
  pendientes de un candidato y registra el envío en su `historial_envios`
  para evitar duplicados.

Los tres se registran en Claude Code apuntando al intérprete de `venv/`
(no al `python` global), porque ahí están instaladas sus dependencias
(`python-docx`, `mcp`, etc.).

### Ejecución diaria (`ejecutar_busqueda_diaria.py`)

Pensado para correr por cron: recorre `memory/candidatos/*.json` y por
cada candidato invoca `claude -p` para que el agente revise si hay ofertas
nuevas y, si corresponde, las envíe — respetando siempre la orquestación
de arriba. En Windows, `claude` es un shim `claude.cmd` de npm, no un
ejecutable directo, así que la ruta se resuelve con `shutil.which("claude")`
antes de invocar `subprocess.run`; si no se encuentra en el `PATH`, se
loguea el error y se aborta esa ejecución sin lanzar excepción.

## Persistencia (`memory/`)

- `memory/candidatos/<correo_normalizado>.json`: estado de cada candidato
  (`cv_resumen_analizado`, `cv_optimizacion_consentimiento`,
  `cv_analisis_ats`, `cv_borrador_1_ruta`, `cv_borrador_2_ruta`,
  `cv_version_elegida`, `ofertas_totales`, `ofertas_enviadas_correo`,
  `historial_envios`, fechas de registro y última búsqueda). Ver
  `memory/schema.md` para el detalle campo por campo.
- `memory/conocimiento_ats.md`: criterios de referencia que usa
  `optimizador-cv` para evaluar un CV como lo haría un ATS.
- `memory/log_ejecuciones.md`: bitácora de cada corrida (candidato, ofertas
  encontradas/enviadas, estado, errores).
- `memory/schema.md`: esquema de referencia de los JSON de candidato.

**Nota:** `memory/candidatos/`, `cv-input/`, `logs/`, `output/` y
`memory/log_ejecuciones.md` contienen datos personales reales de
candidatos (CV, nombre, correo, historial laboral) y están excluidos del
repositorio vía `.gitignore`. Solo se versiona la estructura de carpetas
(`.gitkeep`).

## Permisos y seguridad (`.claude/settings.json`)

- Lectura/escritura sin confirmación dentro de `memory/`, `output/` y
  `logs/`.
- Cualquier comando `Bash`, o cualquier escritura fuera de esas tres
  carpetas, requiere confirmación manual.
- Se deniegan comandos y lecturas que expongan variables de entorno del
  sistema o archivos de perfil de shell.

Cada subagente además tiene sus propios "Carriles de seguridad" (límite de
reintentos de búsqueda, búsqueda por lotes, deduplicación de ofertas,
verificación de que los links sean reales, consentimiento obligatorio
antes de optimizar un CV, límite de un solo envío de correo por ejecución,
límite de alcance de archivos que puede tocar, etc.) documentados en su
propio archivo `.claude/agents/*.md`.

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
claude mcp add cv-writer -- venv/Scripts/python.exe mcp_cv_writer.py
claude mcp add email-ofertas -- venv/Scripts/python.exe mcp_email_server.py
```

## Uso

Simplemente pedirle a Claude Code "quiero buscar empleo para un candidato" y
proveer los 4 datos solicitados (nombre completo, ruta del CV `.docx`,
perfil profesional declarado, correo), más la respuesta de consentimiento
de optimización cuando `analista-cv` la pida. El resto del proceso lo
maneja la orquestación descripta arriba.
