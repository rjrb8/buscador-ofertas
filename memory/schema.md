# Esquema de memoria — Buscador de Ofertas Laborales

Este documento describe el contenido y formato de cada archivo dentro de
`memory/`, para que cualquier modelo de IA que opere este agente sepa cómo
leerlos y escribirlos de forma consistente.

## Estructura general

```
memory/
├── schema.md                  # Este archivo
├── candidatos/                # Un archivo JSON por candidato
│   └── <email_normalizado>.json
└── log_ejecuciones.md         # Tabla histórica de ejecuciones del agente
```

## candidatos/<email_normalizado>.json

Un archivo por candidato. El nombre de archivo es el correo del candidato
normalizado: minúsculas, sin espacios, y con caracteres no alfanuméricos
(excepto `.`, `-`, `_`) reemplazados o eliminados. Ejemplo de normalización:
`Juan.Perez+jobs@Gmail.com` → `juan.perezjobs@gmail.com`.

Este archivo es la fuente de verdad del estado de un candidato entre
ejecuciones. Debe leerse antes de procesar a un candidato (para no repetir
trabajo innecesario) y actualizarse al finalizar cada ejecución relacionada
a él.

### Campos

| Campo | Tipo | Descripción |
|---|---|---|
| `nombre` | string | Nombre completo del candidato, tal como lo proporcionó. |
| `correo` | string | Correo del candidato sin normalizar (formato original). |
| `perfil_declarado` | string | Perfil profesional indicado manualmente por el candidato. Tiene prioridad sobre lo inferido del CV en caso de conflicto. |
| `cv_ruta` | string | Ruta local o referencia al archivo .docx del CV original. |
| `cv_resumen_analizado` | object | Resultado estructurado del análisis del CV: experiencia laboral, habilidades técnicas, años de experiencia, idiomas, nivel educativo, logros cuantificables. Estructura interna libre pero debe ser un objeto JSON válido, no texto plano. |
| `cv_optimizacion_consentimiento` | boolean | Si el candidato aceptó optimizar su CV. |
| `cv_analisis_ats` | object | Diagnóstico ATS generado por optimizador-cv: `{brechas_palabras_clave, señales_alerta, puntos_debiles}`. |
| `cv_borrador_1_ruta` | string | Ruta al borrador de CV optimizado, en texto plano. |
| `cv_borrador_2_ruta` | string | Ruta al borrador de CV optimizado, en formato .docx. |
| `cv_version_elegida` | string | Versión de CV elegida por el candidato para la búsqueda: `"original"` \| `"borrador_1"` \| `"borrador_2"`. |
| `fecha_registro` | string (ISO 8601) | Fecha en que el candidato fue registrado por primera vez. No se modifica en ejecuciones posteriores. |
| `ultima_busqueda` | string (ISO 8601) | Fecha de la búsqueda de ofertas más reciente para este candidato. Se actualiza en cada ejecución. |
| `ofertas_totales` | array | Todas las ofertas reales encontradas en la búsqueda más reciente, sin filtrar. Cada elemento debe incluir al menos: título, empresa, fuente (sitio), URL y fecha de publicación si está disponible. |
| `ofertas_top10_mostradas` | array | Subconjunto de `ofertas_totales`: las 10 ofertas mejor alineadas al perfil, que fueron mostradas en pantalla al candidato. |
| `ofertas_enviadas_correo` | array | Ofertas (fuera del top 10 mostrado en pantalla) que se guardaron para envío por correo. |
| `historial_envios` | array | Registro de cada envío de correo realizado a este candidato: fecha, cantidad de ofertas enviadas, estado del envío (éxito/error). |

### Reglas de integridad

- Nunca incluir ofertas laborales ficticias o generadas — todo elemento de
  `ofertas_totales` debe corresponder a una oferta real verificable.
- Si no hay suficientes ofertas reales para completar el top 10, el arreglo
  `ofertas_top10_mostradas` debe contener solo las ofertas reales disponibles
  (puede tener menos de 10 elementos). No rellenar con datos falsos.
- El archivo debe ser JSON válido en todo momento; no dejarlo en un estado
  parcial o corrupto tras una escritura.

## log_ejecuciones.md

Tabla Markdown con el historial de todas las ejecuciones del agente,
independientemente del candidato procesado. Sirve como bitácora auditable
del comportamiento del sistema en el tiempo.

### Columnas

| Columna | Descripción |
|---|---|
| `Fecha` | Fecha y hora de la ejecución (formato ISO 8601 recomendado). |
| `Candidato` | Nombre o correo del candidato procesado en esa ejecución. |
| `Ofertas encontradas` | Cantidad total de ofertas reales encontradas en la búsqueda. |
| `Ofertas enviadas` | Cantidad de ofertas enviadas por correo (fuera del top 10 mostrado). |
| `Estado` | Resultado general de la ejecución (por ejemplo: completado, completado con errores, fallido). |
| `Errores` | Descripción breve de errores o fallos ocurridos (por ejemplo, fuentes de búsqueda que no respondieron). Vacío o "-" si no hubo errores. |

Cada ejecución del agente debe agregar una nueva fila a esta tabla antes de
finalizar, sin modificar ni eliminar filas anteriores.
