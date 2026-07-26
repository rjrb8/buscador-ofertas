import json
import re
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("email-ofertas")

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

BASE_DIR = Path(__file__).parent
CANDIDATOS_DIR = BASE_DIR / "memory" / "candidatos"


def normalizar_correo(correo: str) -> str:
    correo = correo.strip().lower()
    return re.sub(r"[^a-z0-9.\-_@]", "", correo)


def ruta_candidato(correo_normalizado: str) -> Path:
    return CANDIDATOS_DIR / f"{correo_normalizado}.json"


def cargar_candidato(correo_normalizado: str) -> dict:
    ruta = ruta_candidato(correo_normalizado)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe memory/candidatos/{correo_normalizado}.json")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_candidato(correo_normalizado: str, datos: dict) -> None:
    with open(ruta_candidato(correo_normalizado), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def construir_cuerpo_html(nombre_candidato: str, ofertas: list) -> str:
    cuerpo_html = f"<h2>Hola {nombre_candidato},</h2>"
    cuerpo_html += "<p>Aquí tienes el resto de ofertas encontradas para tu perfil:</p><ul>"
    for oferta in ofertas:
        cuerpo_html += (
            f"<li><b>{oferta.get('titulo', 'Sin título')}</b> - "
            f"{oferta.get('empresa', 'N/A')} - "
            f"<a href='{oferta.get('url', oferta.get('link', '#'))}'>Ver oferta</a></li>"
        )
    cuerpo_html += "</ul>"
    return cuerpo_html


@mcp.tool()
def listar_pendientes() -> list[dict]:
    """Lista los candidatos que tienen ofertas pendientes de envío por correo."""
    pendientes = []
    if not CANDIDATOS_DIR.exists():
        return pendientes
    for archivo in CANDIDATOS_DIR.glob("*.json"):
        with open(archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)
        ofertas = datos.get("ofertas_enviadas_correo", [])
        if ofertas:
            pendientes.append(
                {
                    "correo_normalizado": archivo.stem,
                    "nombre": datos.get("nombre", ""),
                    "cantidad_pendiente": len(ofertas),
                }
            )
    return pendientes


@mcp.tool()
def enviar_ofertas_candidato(correo: str) -> dict:
    """
    Envía por correo las ofertas pendientes de un candidato (el contenido de
    "ofertas_enviadas_correo" en memory/candidatos/<correo_normalizado>.json)
    y registra el resultado en "historial_envios" de ese mismo archivo.
    """
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        return {"estado": "error", "errores": "Credenciales no configuradas en .env (GMAIL_USER / GMAIL_APP_PASSWORD)"}

    correo_normalizado = normalizar_correo(correo)

    try:
        datos = cargar_candidato(correo_normalizado)
    except FileNotFoundError as e:
        return {"estado": "error", "errores": str(e)}

    ofertas = datos.get("ofertas_enviadas_correo", [])
    if not ofertas:
        return {"estado": "sin_pendientes", "correo_normalizado": correo_normalizado, "errores": ""}

    entrada_historial = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "cantidad_ofertas": len(ofertas),
        "estado": "",
    }

    destinatario = datos.get("correo", correo)
    nombre_candidato = datos.get("nombre", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Ofertas laborales para {nombre_candidato}"
    msg["From"] = GMAIL_USER
    msg["To"] = destinatario
    msg.attach(MIMEText(construir_cuerpo_html(nombre_candidato, ofertas), "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        entrada_historial["estado"] = "éxito"
        datos.setdefault("historial_envios", []).append(entrada_historial)
        datos["ofertas_enviadas_correo"] = []
        guardar_candidato(correo_normalizado, datos)
        return {
            "estado": "éxito",
            "correo_normalizado": correo_normalizado,
            "cantidad_enviada": entrada_historial["cantidad_ofertas"],
            "errores": "",
        }
    except Exception as e:
        entrada_historial["estado"] = "error"
        entrada_historial["error_detalle"] = str(e)
        datos.setdefault("historial_envios", []).append(entrada_historial)
        guardar_candidato(correo_normalizado, datos)
        return {"estado": "error", "correo_normalizado": correo_normalizado, "errores": str(e)}


if __name__ == "__main__":
    mcp.run()
