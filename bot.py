import os
import base64
import logging
import datetime
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)
from openai import OpenAI

# Cargar variables locales desde .env si existe
load_dotenv()

# Configurar Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("ObsidianAgent")

# Variables de Configuración
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID_STR = os.getenv("ALLOWED_USER_ID", "0")
ALLOWED_USER_ID = int(ALLOWED_USER_ID_STR) if ALLOWED_USER_ID_STR.isdigit() else 0
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # Formato: "usuario/repositorio"
NOTES_FOLDER = os.getenv("NOTES_FOLDER", "Obsesiones").strip("/")

# Inicializar cliente de DeepSeek (API compatible con OpenAI)
ai_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


def get_existing_notes():
    """Obtiene los nombres de notas existentes en GitHub para retroalimentar el grafo."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return []
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{NOTES_FOLDER}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            files = r.json()
            return [f["name"].replace(".md", "") for f in files if f.get("name", "").endswith(".md")]
        elif r.status_code == 404:
            # La carpeta aún no existe, se creará con el primer archivo
            return []
        else:
            logger.warning(f"Aviso al listar GitHub ({r.status_code}): {r.text}")
    except Exception as e:
        logger.error(f"Error consultando notas de GitHub: {e}")
    return []


def save_file_to_github(path, content, commit_message):
    """Crea o actualiza un archivo .md directamente en GitHub sin clonar repositorio."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    # Verificar si el archivo ya existe para obtener su SHA (requerido para actualizar)
    sha = None
    try:
        check_res = requests.get(url, headers=headers, timeout=10)
        if check_res.status_code == 200:
            sha = check_res.json().get("sha")
    except Exception as e:
        logger.warning(f"No se pudo consultar SHA previo: {e}")

    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": commit_message,
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, json=payload, headers=headers, timeout=15)
    if r.status_code in [200, 201]:
        return True, None
    else:
        return False, f"HTTP {r.status_code}: {r.text}"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start para comprobar que el agente está vivo."""
    user = update.effective_user
    if ALLOWED_USER_ID != 0 and user.id != ALLOWED_USER_ID:
        await update.message.reply_text(f"⛔ Acceso no autorizado. Tu Telegram ID es: `{user.id}`", parse_mode="Markdown")
        return

    await update.message.reply_text(
        f"🌌 **¡Hola {user.first_name}! Soy tu Cartógrafo de Obsesiones.**\n\n"
        f"Envíame cualquier pensamiento, idea fugaz o curiosidad por aquí.\n"
        f"• Los analizaré con **DeepSeek** para conectarlos con tu grafo de **Obsidian**.\n"
        f"• Cada semana te enviaré una **Micro-Tesis Inédita** cruzando conceptos.\n\n"
        f"Comandos útiles:\n"
        f"• `/sintesis` - Genera una síntesis interdisciplinaria de inmediato sin esperar la semana.\n"
        f"• `/status` - Verifica la conexión con GitHub y DeepSeek.",
        parse_mode="Markdown"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica estado de GitHub y número de notas en el grafo."""
    if ALLOWED_USER_ID != 0 and update.effective_user.id != ALLOWED_USER_ID:
        return

    notes = get_existing_notes()
    await update.message.reply_text(
        f"📊 **Estado de tu Bóveda:**\n"
        f"• Repositorio: `{GITHUB_REPO or 'No configurado'}`\n"
        f"• Carpeta: `{NOTES_FOLDER}`\n"
        f"• Nodos detectados: **{len(notes)} notas**\n"
        f"• Modelo IA: `deepseek-chat` / `deepseek-reasoner`",
        parse_mode="Markdown"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa cada mensaje de texto recibido."""
    user = update.effective_user
    if ALLOWED_USER_ID != 0 and user.id != ALLOWED_USER_ID:
        await update.message.reply_text(f"⛔ No autorizado. Tu ID: `{user.id}`", parse_mode="Markdown")
        return

    user_text = update.message.text
    status_msg = await update.message.reply_text("🧠 Conectando tu idea con el grafo en Obsidian...")

    # 1. Obtener notas actuales para el contexto
    existing_notes = get_existing_notes()
    existing_str = ", ".join([f"[[{n}]]" for n in existing_notes]) if existing_notes else "Bóveda vacía por ahora."

    today = datetime.date.today().isoformat()

    system_prompt = f"""
Eres un Cartógrafo de Conocimiento y Pensamiento Lateral. Tu labor es transformar las ideas espontáneas del usuario en notas de Obsidian profundamente interconectadas.

Notas que actualmente existen en su bóveda:
{existing_str}

Instrucciones:
1. Define un TÍTULO corto y sugerente (máximo 5 palabras, sin caracteres especiales como / \\ : * ? " < > |).
2. Estructura el archivo en Markdown:
   - Encabezado YAML con fecha ({today}) y 3-5 tags relevantes (#tema).
   - Resumen o desarrollo conciso de la idea.
   - Preguntas abiertas que despierta esta idea.
   - Sección obligatoria: '## Conexiones en el Grafo', donde relaciones esta idea con notas existentes usando enlaces [[Nombre de Nota]]. Si no existen notas relacionadas directas, sugiere 1 o 2 conceptos potenciales que valga la pena conectar a futuro en formato [[Nuevo Concepto]].
3. Devuelve estrictamente el siguiente formato:
TITULO: <Título aquí>
CONTENIDO:
<Markdown completo>
"""

    try:
        response = ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.7
        )
        ai_reply = response.choices[0].message.content

        # Parsear título y contenido
        lines = ai_reply.split("\n")
        title = "Nueva Obsesion"
        content_lines = []
        is_content = False

        for line in lines:
            if line.startswith("TITULO:"):
                title = line.replace("TITULO:", "").strip()
            elif line.startswith("CONTENIDO:"):
                is_content = True
            elif is_content:
                content_lines.append(line)

        final_markdown = "\n".join(content_lines).strip()
        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
        file_path = f"{NOTES_FOLDER}/{clean_title}.md"

        # Guardar en GitHub
        success, err = save_file_to_github(
            file_path,
            final_markdown,
            f"Obsidian Bot: {clean_title}"
        )

        if success:
            await status_msg.edit_text(
                f"✨ **¡Nodo incorporado a tu Grafo!**\n\n"
                f"📁 **Archivo:** `{file_path}`\n"
                f"🔗 Se crearon enlaces conceptuales y ya está disponible en tu repositorio.",
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text(f"❌ Error al guardar en GitHub:\n`{err}`", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error procesando nota: {e}")
        await status_msg.edit_text(f"❌ Error con DeepSeek o conexión: `{str(e)}`", parse_mode="Markdown")


async def generate_synthesis(context: ContextTypes.DEFAULT_TYPE, manual_trigger=False):
    """Genera una Micro-Tesis Inédita usando el modelo de razonamiento DeepSeek-R1."""
    notes = get_existing_notes()
    if len(notes) < 2:
        msg = "Aún tienes muy pocas notas en el grafo (mínimo 2). ¡Sigue compartiendo más ideas!"
        if manual_trigger and context.job and context.job.chat_id:
            await context.bot.send_message(chat_id=context.job.chat_id, text=msg)
        return

    prompt = f"""
Eres un sintetizador de conocimiento de clase mundial y pensador transdisciplinario.
El usuario tiene estas notas registradas en su bóveda de Obsidian:
{', '.join([f'[[{n}]]' for n in notes])}

Tu misión:
1. Elige dos o tres notas que a primera vista pertenezcan a campos o disciplinas totalmente diferentes.
2. Encuentra una conexión subterránea, puente analógico o principio compartido que nadie suele notar.
3. Escribe una 'Micro-Tesis Inédita' estructurada en 3 párrafos claros y estimulantes.
4. Concluye con una pregunta provocadora para abrir una nueva rama de investigación.
"""

    try:
        response = ai_client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "user", "content": prompt}]
        )
        synthesis = response.choices[0].message.content

        # Guardar también la síntesis en Obsidian en la carpeta de Síntesis
        today = datetime.date.today().isoformat()
        synthesis_title = f"Sintesis-{today}"
        synthesis_md = f"---\nfecha: {today}\ntags: [sintesis-cruzada, micro-tesis]\n---\n# Micro-Tesis: {today}\n\n{synthesis}"
        
        save_file_to_github(
            f"{NOTES_FOLDER}/Sintesis/{synthesis_title}.md",
            synthesis_md,
            f"Obsidian Bot: Síntesis semanal {today}"
        )

        target_chat = ALLOWED_USER_ID if not manual_trigger else (context.job.chat_id if context.job else ALLOWED_USER_ID)
        await context.bot.send_message(
            chat_id=target_chat,
            text=f"🔮 **MICRO-TESIS INÉDITA (Síntesis de Grafo)**\n\n{synthesis}\n\n_Guardada también en tu Obsidian en `/Sintesis/{synthesis_title}.md`_",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error en síntesis: {e}")
        if manual_trigger and context.job and context.job.chat_id:
            await context.bot.send_message(chat_id=context.job.chat_id, text=f"Error generando síntesis: {e}")


async def manual_synthesis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando manual /sintesis para forzar la generación de una tesis."""
    if ALLOWED_USER_ID != 0 and update.effective_user.id != ALLOWED_USER_ID:
        return

    status = await update.message.reply_text("🧐 DeepSeek Reasoner está analizando el grafo en busca de conexiones ocultas...")
    context.job_queue.run_once(
        lambda ctx: generate_synthesis(ctx, manual_trigger=True),
        when=1,
        chat_id=update.effective_chat.id
    )


def main():
    if not TELEGRAM_TOKEN:
        print("❌ ERROR: Falta TELEGRAM_TOKEN en las variables de entorno.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("sintesis", manual_synthesis_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    # Tarea recurrente: Síntesis semanal proactiva (cada 7 días = 604800 seg)
    if app.job_queue:
        app.job_queue.run_repeating(
            generate_synthesis,
            interval=604800,
            first=86400  # Primer disparo tras 24h de estar encendido
        )

    logger.info("Bot persistente iniciado con éxito.")
    app.run_polling()


if __name__ == "__main__":
    main()
