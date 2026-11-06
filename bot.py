import os
import json
import time
import queue
import base64
import logging
import datetime
import threading
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
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
WHITELIST_FILE = "config/whitelist.json"
LOGS_FOLDER = "logs"

# Estado de usuarios autorizados en memoria
AUTHORIZED_USERS = {}  # { "user_id_str": {"name": "...", "date": "..."} }
PUBLIC_MODE = False

# ================= SISTEMA DE LOGS Y AUDITORÍA INMUTABLE =================
LOG_QUEUE = queue.Queue()
RECENT_LOGS = deque(maxlen=30)  # Últimos 30 eventos para consulta inmediata en Telegram
LOG_SEQ = 0
LOG_LOCK = threading.Lock()


def record_audit_event(event_type, details=None, user=None, level="INFO"):
    """
    Registra un evento cronológico y secuencial en memoria y en la cola de persistencia.
    """
    global LOG_SEQ
    with LOG_LOCK:
        LOG_SEQ += 1
        current_seq = LOG_SEQ

    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    user_payload = None
    if user:
        user_payload = {
            "id": getattr(user, "id", None),
            "username": getattr(user, "username", None),
            "first_name": getattr(user, "first_name", None)
        }

    entry = {
        "seq": current_seq,
        "timestamp": now_utc,
        "level": level,
        "event": event_type,
        "user": user_payload,
        "details": details or {}
    }

    # Guardar en memoria para acceso rápido
    RECENT_LOGS.append(entry)
    # Encolar para escritura asíncrona en GitHub
    LOG_QUEUE.put(entry)

    logger.info(f"[AUDIT #{current_seq}] [{event_type}] {details}")


def append_log_to_github(entry):
    """Escribe de forma acumulativa (append-only) en el archivo diario de logs en GitHub."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return

    today_str = datetime.date.today().isoformat()
    log_path = f"{LOGS_FOLDER}/audit_{today_str}.jsonl"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{log_path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    sha = None
    existing_content = ""
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            sha = data.get("sha")
            raw_b64 = data.get("content", "")
            existing_content = base64.b64decode(raw_b64).decode("utf-8")
    except Exception as e:
        logger.warning(f"Error consultando log previo en GitHub: {e}")

    # Formatear la línea JSONL
    new_line = json.dumps(entry, ensure_ascii=False) + "\n"
    updated_content = existing_content + new_line
    encoded_content = base64.b64encode(updated_content.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"audit: #{entry['seq']} {entry['event']}",
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha

    try:
        put_res = requests.put(url, json=payload, headers=headers, timeout=15)
        if put_res.status_code not in [200, 201]:
            logger.warning(f"No se pudo persistir log #{entry['seq']} en GitHub: {put_res.text}")
    except Exception as e:
        logger.error(f"Fallo al enviar log a GitHub: {e}")


def log_worker():
    """Hilo trabajador en segundo plano que procesa la cola de auditoría de manera secuencial."""
    while True:
        try:
            entry = LOG_QUEUE.get()
            if entry is None:
                break
            append_log_to_github(entry)
            LOG_QUEUE.task_done()
            time.sleep(0.5)  # Evitar saturar el rate-limit de GitHub
        except Exception as e:
            logger.error(f"Error en log_worker: {e}")

# Inicializar cliente de DeepSeek (API compatible con OpenAI)
ai_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive and healthy!")

    def log_message(self, format, *args):
        pass


def run_health_check_server():
    """Servidor HTTP mínimo para pasar health checks si Koyeb/Render lo corre como Web Service."""
    port = int(os.getenv("PORT", "8000"))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health check HTTP iniciado en puerto {port}")
        server.serve_forever()
    except Exception as e:
        logger.warning(f"No se pudo iniciar el servidor health check: {e}")


def get_relevant_notes(user_text, all_notes, top_k=12):
    """Filtra solo las notas más pertinentes para ahorrar tokens en el prompt."""
    if len(all_notes) <= top_k:
        return all_notes

    user_words = set(w.lower() for w in user_text.split() if len(w) > 3)
    scored = []
    for note in all_notes:
        note_words = set(w.lower() for w in note.replace("_", " ").replace("-", " ").split())
        overlap = len(user_words.intersection(note_words))
        scored.append((overlap, note))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [note for _, note in scored[:top_k]]


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
            return []
        else:
            logger.warning(f"Aviso al listar GitHub ({r.status_code}): {r.text}")
    except Exception as e:
        logger.error(f"Error consultando notas de GitHub: {e}")
    return []


def save_file_to_github(path, content, commit_message):
    """Crea o actualiza un archivo en GitHub sin clonar repositorio."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    sha = None
    try:
        check_res = requests.get(url, headers=headers, timeout=10)
        if check_res.status_code == 200:
            sha = check_res.json().get("sha")
    except Exception as e:
        logger.warning(f"No se pudo consultar SHA previo de {path}: {e}")

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


# ================= GESTIÓN DE WHITELIST (USUARIOS AUTORIZADOS) =================

def load_whitelist():
    """Carga los usuarios invitados autorizados desde GitHub."""
    global AUTHORIZED_USERS, PUBLIC_MODE
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{WHITELIST_FILE}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            content_b64 = r.json().get("content", "")
            data = json.loads(base64.b64decode(content_b64).decode("utf-8"))
            AUTHORIZED_USERS = data.get("users", {})
            PUBLIC_MODE = data.get("public_mode", False)
            logger.info(f"Whitelist cargada: {len(AUTHORIZED_USERS)} invitados. Modo público: {PUBLIC_MODE}")
    except Exception as e:
        logger.warning(f"Whitelist no encontrada o vacía ({e}), iniciando nueva.")


def sync_whitelist_to_github():
    """Guarda permanentemente la lista de usuarios autorizados en GitHub."""
    data = {
        "public_mode": PUBLIC_MODE,
        "users": AUTHORIZED_USERS
    }
    content = json.dumps(data, indent=2, ensure_ascii=False)
    save_file_to_github(WHITELIST_FILE, content, "Config: actualizar lista de usuarios autorizados")


def is_user_authorized(user_id):
    """Verifica si un usuario puede hablar con el bot."""
    if PUBLIC_MODE or ALLOWED_USER_ID == 0:
        return True
    if user_id == ALLOWED_USER_ID:
        return True
    return str(user_id) in AUTHORIZED_USERS


async def notify_unauthorized_attempt(user, context: ContextTypes.DEFAULT_TYPE):
    """Notifica al creador cuando alguien intenta usar el bot y le envía botones de aprobación."""
    record_audit_event("AUTH_UNAUTHORIZED_ATTEMPT", {"name": user.full_name, "username": user.username}, user=user, level="WARNING")
    if ALLOWED_USER_ID == 0:
        return

    first_name = user.first_name or "Usuario"
    keyboard = [
        [
            InlineKeyboardButton("✅ Autorizar", callback_data=f"appr_{user.id}_{first_name}"),
            InlineKeyboardButton("❌ Denegar", callback_data=f"deny_{user.id}_{first_name}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    username_display = f"@{user.username}" if user.username else "Sin alias"
    try:
        await context.bot.send_message(
            chat_id=ALLOWED_USER_ID,
            text=(
                f"🔔 **Solicitud de Acceso para Pruebas**\n\n"
                f"👤 **Nombre:** {user.full_name}\n"
                f"📱 **Usuario:** {username_display}\n"
                f"🆔 **ID:** `{user.id}`\n\n"
                f"¿Deseas permitirle usar el bot para que pruebe el grafo?"
            ),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error notificando al administrador: {e}")


def build_admin_keyboard():
    """Construye los botones del panel de control de usuarios."""
    keyboard = []
    mode_text = "🔓 Modo Libre: ACTIVADO (Cualquiera entra)" if PUBLIC_MODE else "🔒 Modo Privado: ACTIVADO (Solo lista)"
    keyboard.append([InlineKeyboardButton(mode_text, callback_data="toggle_mode")])

    for uid, data in AUTHORIZED_USERS.items():
        name = data.get("name", uid)
        keyboard.append([InlineKeyboardButton(f"❌ Quitar acceso a: {name}", callback_data=f"del_{uid}")])

    keyboard.append([
        InlineKeyboardButton("📜 Ver Logs de Auditoría", callback_data="view_logs"),
        InlineKeyboardButton("🔄 Actualizar", callback_data="refresh_admin")
    ])
    return InlineKeyboardMarkup(keyboard)


# ================= COMANDOS DE ADMINISTRADOR =================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panel visual para que el dueño agregue o quite usuarios con 1 clic."""
    user = update.effective_user
    if ALLOWED_USER_ID != 0 and user.id != ALLOWED_USER_ID:
        return

    text = (
        f"👑 **Panel de Gestión de Usuarios (Pruebas)**\n\n"
        f"• **Admin:** `{ALLOWED_USER_ID}`\n"
        f"• **Modo actual:** {'🔓 Libre (Público)' if PUBLIC_MODE else '🔒 Privado (Protegido)'}\n"
        f"• **Invitados con acceso:** {len(AUTHORIZED_USERS)}\n\n"
        f"Toca los botones para activar/desactivar o quitar a alguien.\n\n"
        f"Comandos manuales rápidos:\n"
        f"• `/add <ID> <Nombre>` - Agregar invitado directamente\n"
        f"• `/remove <ID>` - Quitar invitado"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=build_admin_keyboard())


async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /add <ID> <Nombre> para añadir manualmente."""
    if ALLOWED_USER_ID != 0 and update.effective_user.id != ALLOWED_USER_ID:
        return
    if not context.args:
        await update.message.reply_text("Uso: `/add <ID_NUMERICO> [Nombre]`", parse_mode="Markdown")
        return
    target_id = context.args[0].strip()
    target_name = " ".join(context.args[1:]) if len(context.args) > 1 else f"Invitado_{target_id}"

    AUTHORIZED_USERS[str(target_id)] = {
        "name": target_name,
        "date": datetime.date.today().isoformat()
    }
    sync_whitelist_to_github()
    record_audit_event("AUTH_MANUAL_ADD", {"target_id": target_id, "name": target_name}, user=user)
    await update.message.reply_text(f"✅ Usuario **{target_name}** (`{target_id}`) autorizado.", parse_mode="Markdown")


async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /remove <ID> para revocar manualmente."""
    user = update.effective_user
    if ALLOWED_USER_ID != 0 and user.id != ALLOWED_USER_ID:
        return
    if not context.args:
        await update.message.reply_text("Uso: `/remove <ID_NUMERICO>`", parse_mode="Markdown")
        return
    target_id = context.args[0].strip()
    if str(target_id) in AUTHORIZED_USERS:
        name = AUTHORIZED_USERS[str(target_id)].get("name", target_id)
        del AUTHORIZED_USERS[str(target_id)]
        sync_whitelist_to_github()
        record_audit_event("AUTH_MANUAL_REMOVE", {"target_id": target_id, "name": name}, user=user)
        await update.message.reply_text(f"🗑️ Acceso revocado a **{name}** (`{target_id}`).", parse_mode="Markdown")
    else:
        await update.message.reply_text("Ese ID no está en la lista de autorizados.")


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestiona los clics en los botones interactivos."""
    query = update.callback_query
    await query.answer()
    clicker_id = query.from_user.id

    if ALLOWED_USER_ID != 0 and clicker_id != ALLOWED_USER_ID:
        await query.edit_message_text("⛔ Solo el administrador puede usar estos controles.")
        return

    data = query.data

    if data.startswith("appr_"):
        parts = data.split("_", 2)
        target_id = parts[1]
        target_name = parts[2] if len(parts) > 2 else f"Usuario_{target_id}"
        AUTHORIZED_USERS[str(target_id)] = {
            "name": target_name,
            "date": datetime.date.today().isoformat()
        }
        sync_whitelist_to_github()
        record_audit_event("AUTH_ACCESS_APPROVED", {"approved_id": target_id, "name": target_name}, user=query.from_user)
        await query.edit_message_text(f"✅ **¡Acceso autorizado!**\n**{target_name}** (`{target_id}`) ya puede usar el bot.", parse_mode="Markdown")
        try:
            await context.bot.send_message(
                chat_id=int(target_id),
                text="🎉 **¡Acceso concedido!**\nLeonardo te ha autorizado a probar el bot. Ya puedes enviarme tus ideas, dudas o pensamientos.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"No se pudo notificar al usuario aprobado: {e}")

    elif data.startswith("deny_"):
        parts = data.split("_", 2)
        target_id = parts[1]
        target_name = parts[2] if len(parts) > 2 else target_id
        record_audit_event("AUTH_ACCESS_DENIED", {"denied_id": target_id, "name": target_name}, user=query.from_user)
        await query.edit_message_text(f"❌ Acceso **DENEGADO** a {target_name} (`{target_id}`).", parse_mode="Markdown")
        try:
            await context.bot.send_message(
                chat_id=int(target_id),
                text="⛔ Tu solicitud de acceso para pruebas fue rechazada por el administrador.",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    elif data.startswith("del_"):
        target_id = data.replace("del_", "")
        if str(target_id) in AUTHORIZED_USERS:
            name = AUTHORIZED_USERS[str(target_id)].get("name", target_id)
            del AUTHORIZED_USERS[str(target_id)]
            sync_whitelist_to_github()
            record_audit_event("AUTH_ACCESS_REVOKED", {"revoked_id": target_id, "name": name}, user=query.from_user)
            await query.edit_message_reply_markup(reply_markup=build_admin_keyboard())
            try:
                await context.bot.send_message(
                    chat_id=int(target_id),
                    text="ℹ️ Tu acceso de prueba ha finalizado. ¡Gracias por participar!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    elif data == "toggle_mode":
        global PUBLIC_MODE
        PUBLIC_MODE = not PUBLIC_MODE
        sync_whitelist_to_github()
        record_audit_event("AUTH_MODE_TOGGLED", {"public_mode": PUBLIC_MODE}, user=query.from_user)
        await query.edit_message_reply_markup(reply_markup=build_admin_keyboard())

    elif data == "refresh_admin":
        load_whitelist()
        await query.edit_message_reply_markup(reply_markup=build_admin_keyboard())

    elif data == "view_logs":
        await logs_command(update, context)


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el registro cronológico y secuencial de auditoría."""
    user = update.effective_user
    if ALLOWED_USER_ID != 0 and user.id != ALLOWED_USER_ID:
        return

    if not RECENT_LOGS:
        msg = "📜 **El registro de auditoría está vacío por ahora.**"
        if update.callback_query:
            await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # Tomar los últimos 6 eventos cronológicos
    logs_to_show = list(RECENT_LOGS)[-6:]
    lines = ["📜 **Registro Cronológico e Imborrable (Últimos eventos):**\n"]
    for l in logs_to_show:
        user_name = l['user']['first_name'] if l.get('user') and l['user'].get('first_name') else "⚙️ Sistema"
        details_summary = json.dumps(l['details'], ensure_ascii=False)
        if len(details_summary) > 65:
            details_summary = details_summary[:62] + "..."
        lines.append(
            f"• **[#{l['seq']:03d}]** `{l['timestamp'][11:19]} UTC` — `{l['event']}`\n"
            f"  👤 {user_name} | ℹ️ _{details_summary}_"
        )

    github_url = f"https://github.com/{GITHUB_REPO}/tree/main/{LOGS_FOLDER}"
    keyboard = [[InlineKeyboardButton("📂 Ver historial completo en GitHub", url=github_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    response_text = "\n\n".join(lines)
    if update.callback_query:
        await update.callback_query.message.reply_text(response_text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(response_text, parse_mode="Markdown", reply_markup=reply_markup)


# ================= COMANDOS GENERALES Y MENSAJES =================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start."""
    user = update.effective_user
    if not is_user_authorized(user.id):
        await update.message.reply_text(
            f"⏳ **Acceso Restringido (Modo Pruebas)**\n\n"
            f"Tu Telegram ID es: `{user.id}`\n\n"
            f"He enviado una solicitud al creador del bot (Leonardo) para que autorice tu acceso.",
            parse_mode="Markdown"
        )
        await notify_unauthorized_attempt(user, context)
        return

    is_admin = (user.id == ALLOWED_USER_ID)
    admin_help = "\n\n⚙️ **Controles de Administrador:**\n• `/admin` - Gestionar quién puede usar el bot." if is_admin else ""

    await update.message.reply_text(
        f"🌌 **¡Hola {user.first_name}! Soy el Cartógrafo de Obsesiones.**\n\n"
        f"Envíame cualquier pensamiento, idea fugaz, hábito o curiosidad.\n"
        f"• Conectaré tu idea con **DeepSeek** para trazar el grafo en **Obsidian**.\n"
        f"• Crearé enlaces conceptuales automáticos entre tus pensamientos.{admin_help}\n\n"
        f"Comandos útiles:\n"
        f"• `/sintesis` - Genera una Micro-Tesis inédita cruzando tus notas.\n"
        f"• `/status` - Consulta el estado del grafo.",
        parse_mode="Markdown"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica estado de GitHub y número de notas en el grafo."""
    user = update.effective_user
    if not is_user_authorized(user.id):
        return

    notes = get_existing_notes()
    await update.message.reply_text(
        f"📊 **Estado del Grafo:**\n"
        f"• Repositorio: `{GITHUB_REPO or 'No configurado'}`\n"
        f"• Carpeta: `{NOTES_FOLDER}`\n"
        f"• Nodos en la bóveda: **{len(notes)} notas**\n"
        f"• Invitados activos: **{len(AUTHORIZED_USERS)}**\n"
        f"• Modelo IA: `deepseek-chat` / `deepseek-reasoner`",
        parse_mode="Markdown"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa cada mensaje con máxima densidad conceptual y mínimo consumo de tokens."""
    user = update.effective_user
    if not is_user_authorized(user.id):
        await update.message.reply_text(
            f"⏳ **Acceso Restringido.**\nTu Telegram ID es: `{user.id}`\n\n"
            f"Se ha enviado una solicitud a Leonardo para que te habilite.",
            parse_mode="Markdown"
        )
        await notify_unauthorized_attempt(user, context)
        return

    user_text = update.message.text
    record_audit_event("USER_INPUT_RECEIVED", {"length": len(user_text), "preview": user_text[:80]}, user=user)
    t_start = time.time()
    status_msg = await update.message.reply_text("⚡ Sintetizando idea y trazando grafo...")

    # 1. Obtener notas y filtrar solo las más relevantes (ahorro de tokens)
    all_notes = get_existing_notes()
    relevant_notes = get_relevant_notes(user_text, all_notes, top_k=12)
    context_notes_str = ", ".join([f"[[{n}]]" for n in relevant_notes]) if relevant_notes else "Bóveda vacía"

    today = datetime.date.today().isoformat()

    # Prompt hiper-optimizado con salvaguardas contra analogias forzadas
    system_prompt = f"""Actúa como un sintetizador de conocimiento riguroso, analítico y de alta densidad (Zettelkasten).
Notas existentes en la bóveda: {context_notes_str}

Reglas estrictas de precisión y sensatez:
1. Precisión conceptual: Explica el concepto de forma TÉCNICA, REALISTA Y EXACTA. Está terminantemente PROHIBIDO inventar metáforas forzadas o mezclar temas sin sentido (por ejemplo, no compares hardware electrónico moderno con civilizaciones antiguas ni llames chasqui a un sensor).
2. TÍTULO: Claro, profesional y fiel a la idea (3 a 5 palabras, ej: 'Fotometría en Ratones Ópticos').
3. INSIGHT: 1 sola frase precisa con el principio real de funcionamiento o la verdad científica central.
4. CONEXIONES EN EL GRAFO:
   - Revisa las notas existentes. SOLO enlaza una nota existente si existe una relación lógica, temática o de ingeniería REAL y directa.
   - Si ninguna nota existente tiene relación auténtica, NO las fuerces. En su lugar, propone enlaces conceptuales nuevos y naturales del mismo campo (ejemplo: [[Sensores CMOS]], [[Procesamiento Digital de Señales]], [[Optoelectrónica]]).
5. Formato de respuesta EXACTO:
TITULO: <Título preciso de 3-5 palabras>
INSIGHT: <1 frase con la explicación central del concepto>
ENLACES: [[Concepto1]], [[Concepto2]]
CONTENIDO:
---
fecha: {today}
tags: [tag1, tag2, tag3]
autor: {user.first_name}
---
# <Mismo Título>

### Núcleo Conceptual
<2 o 3 oraciones rigurosas, claras y bien fundamentadas>

### Tensión o Pregunta Abierta
<1 pregunta reflexiva o técnica para profundizar>

### Conexiones en el Grafo
- [[Concepto]]: <1 frase explicando el enlace>
"""

    try:
        response = ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.3,
            max_tokens=500
        )
        ai_reply = response.choices[0].message.content.strip()
        duration_sec = round(time.time() - t_start, 2)
        record_audit_event("AI_INFERENCE_SUCCESS", {"model": "deepseek-chat", "duration_sec": duration_sec}, user=user)

        # Parseo estructurado
        title = "Nueva_Idea"
        insight = "Idea registrada en el grafo."
        links = "Ninguno"
        content_lines = []
        is_content = False

        for line in ai_reply.split("\n"):
            if line.startswith("TITULO:"):
                title = line.replace("TITULO:", "").strip()
            elif line.startswith("INSIGHT:"):
                insight = line.replace("INSIGHT:", "").strip()
            elif line.startswith("ENLACES:"):
                links = line.replace("ENLACES:", "").strip()
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
            f"Obsidian Bot: {clean_title} (vía {user.first_name})"
        )

        if success:
            record_audit_event("GRAPH_NODE_COMMITTED", {"file_path": file_path, "title": clean_title, "links": links}, user=user)
            await status_msg.edit_text(
                f"💎 **¡Nodo incorporado con éxito!**\n\n"
                f"📌 **Nota:** `{clean_title}.md`\n"
                f"💡 **Insight:** _{insight}_\n"
                f"🔗 **Conexiones:** {links}\n\n"
                f"✨ _Sincronizado en tu GitHub y listo para Obsidian._",
                parse_mode="Markdown"
            )
        else:
            record_audit_event("GITHUB_WRITE_ERROR", {"file_path": file_path, "error": err}, user=user, level="ERROR")
            await status_msg.edit_text(f"❌ Error al guardar en GitHub:\n`{err}`", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error procesando nota: {e}")
        record_audit_event("PROCESSING_EXCEPTION", {"error": str(e)}, user=user, level="ERROR")
        await status_msg.edit_text(f"❌ Error con DeepSeek o conexión: `{str(e)}`", parse_mode="Markdown")


async def generate_synthesis(context: ContextTypes.DEFAULT_TYPE, manual_trigger=False):
    """Genera una Micro-Tesis Inédita usando DeepSeek-R1."""
    notes = get_existing_notes()
    if len(notes) < 2:
        msg = "Aún hay muy pocas notas en el grafo (mínimo 2). ¡Sigue compartiendo más ideas!"
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

        today = datetime.date.today().isoformat()
        synthesis_title = f"Sintesis-{today}"
        synthesis_md = f"---\nfecha: {today}\ntags: [sintesis-cruzada, micro-tesis]\n---\n# Micro-Tesis: {today}\n\n{synthesis}"

        save_file_to_github(
            f"{NOTES_FOLDER}/Sintesis/{synthesis_title}.md",
            synthesis_md,
            f"Obsidian Bot: Síntesis semanal {today}"
        )
        record_audit_event("SYNTHESIS_GENERATED", {"title": synthesis_title, "notes_count": len(notes)})

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
    """Comando manual /sintesis."""
    user = update.effective_user
    if not is_user_authorized(user.id):
        return

    await update.message.reply_text("🧐 DeepSeek Reasoner está analizando el grafo en busca de conexiones ocultas...")
    context.job_queue.run_once(
        lambda ctx: generate_synthesis(ctx, manual_trigger=True),
        when=1,
        chat_id=update.effective_chat.id
    )


def main():
    if not TELEGRAM_TOKEN:
        print("❌ ERROR: Falta TELEGRAM_TOKEN en las variables de entorno.")
        return

    # Cargar usuarios autorizados guardados en GitHub al arrancar
    load_whitelist()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Handlers Generales
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("sintesis", manual_synthesis_command))

    # Handlers del Administrador (Para añadir/quitar usuarios y ver logs)
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("whitelist", admin_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("add", add_user_command))
    app.add_handler(CommandHandler("remove", remove_user_command))
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    # Handler de Mensajes de Texto
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    # Tarea proactiva semanal (cada 7 días)
    if app.job_queue:
        app.job_queue.run_repeating(
            generate_synthesis,
            interval=604800,
            first=86400
        )

    # Iniciar trabajador de logs en segundo plano (Append-Only a GitHub)
    threading.Thread(target=log_worker, daemon=True).start()

    # Registrar evento de arranque
    record_audit_event("AGENT_STARTUP", {"version": "2.2", "repo": GITHUB_REPO, "folder": NOTES_FOLDER})

    logger.info("Bot persistente iniciado con sistema de auditoría y logs inmutables.")

    # Iniciar servidor de health check en segundo plano
    threading.Thread(target=run_health_check_server, daemon=True).start()

    app.run_polling()


if __name__ == "__main__":
    main()
