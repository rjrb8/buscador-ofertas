import subprocess
import json
import os
import shutil
from datetime import datetime

CANDIDATOS_DIR = "memory/candidatos"
LOG_FILE = "logs/cron_log.txt"


def log(mensaje):
    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {mensaje}\n")


def ejecutar_para_candidato(correo):
    prompt = (
        f"Ejecuta el subagente buscador-empleo en modo actualización para el "
        f"candidato registrado con correo {correo}. Lee su perfil desde "
        f"memory/candidatos/{correo}.json, busca nuevas ofertas que aún no "
        f"estén en ofertas_totales ni en historial_envios, y si encuentras "
        f"nuevas, envíalas por correo siguiendo las reglas de Carriles de seguridad."
    )
    claude_path = shutil.which("claude")
    if claude_path is None:
        log("ERROR: no se encontró el comando 'claude' en el PATH")
        return

    resultado = subprocess.run(
        [claude_path, "-p", prompt],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    log(f"Candidato {correo}: {resultado.returncode} - {resultado.stdout[:200]}")


def main():
    if not os.path.exists(CANDIDATOS_DIR):
        log("No existe carpeta de candidatos aún")
        return

    archivos = [f for f in os.listdir(CANDIDATOS_DIR) if f.endswith(".json")]
    log(f"Iniciando ejecución diaria. Candidatos encontrados: {len(archivos)}")

    for archivo in archivos:
        correo = archivo.replace(".json", "")
        ejecutar_para_candidato(correo)

    log("Ejecución diaria finalizada.")


if __name__ == "__main__":
    main()