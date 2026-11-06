# 🌌 Agente Persistente: Cartógrafo de Obsesiones (Telegram + DeepSeek + Obsidian)

Este agente vive en la nube 24/7 y te permite enviarle cualquier idea fugaz, nota de voz o pensamiento desde tu teléfono por **Telegram**. 

El agente:
1. Analiza tu idea con **DeepSeek**.
2. Consulta el índice de notas que ya tienes en tu bóveda de **Obsidian**.
3. Encuentra conexiones conceptuales y genera una nota estructurada con enlaces bidireccionales `[[wikilinks]]`.
4. Hace un commit directo vía API a tu repositorio privado de **GitHub**.
5. Cada semana (de forma proactiva) usa el modelo de razonamiento **DeepSeek Reasoner (R1)** para cruzar disciplinas y enviarte una **Micro-Tesis Inédita** directamente a Telegram.

---

## 🛠️ Requisitos Previos (Las 4 Credenciales)

Antes de desplegar, necesitas tener estas 4 claves:

1. **`TELEGRAM_TOKEN`**: Habla con [@BotFather](https://t.me/botfather) en Telegram, crea un bot con `/newbot` y copia el token.
2. **`ALLOWED_USER_ID`**: Habla con [@userinfobot](https://t.me/userinfobot) en Telegram. Te dirá tu `Id` numérico. Esto evita que personas ajenas gasten tus tokens de DeepSeek o escriban en tu Obsidian.
3. **`DEEPSEEK_API_KEY`**: Consíguela en [platform.deepseek.com](https://platform.deepseek.com) (usa tus tokens recargados).
4. **`GITHUB_TOKEN` & `GITHUB_REPO`**:
   - Crea un repositorio privado en GitHub (ej. `mi-boveda-obsidian`).
   - Ve a **GitHub > Settings > Developer Settings > Personal access tokens (Tokens classic)**.
   - Crea un token con el permiso marcado en **`repo`**.

---

## 🚀 Despliegue en la Nube 24/7 Gratis (Sin tener tu PC prendido)

La opción más fácil y 100% gratuita es **Koyeb**:

1. Sube esta carpeta (`telegram-obsidian-agent`) a un repositorio en tu GitHub (puede ser público o privado, el archivo `.env` nunca se sube gracias al `.gitignore`).
2. Entra en [Koyeb.com](https://www.koyeb.com/) y regístrate con tu GitHub.
3. Haz clic en **Create Service** > Elige **GitHub**.
4. Selecciona tu repositorio.
5. Elige el tipo de despliegue: **Dockerfile** (lo detectará automáticamente) y selecciona el plan gratuito (**Eco / Free Instance**).
6. En la sección **Environment variables**, agrega las siguientes 6 variables:
   - `TELEGRAM_TOKEN`
   - `ALLOWED_USER_ID`
   - `DEEPSEEK_API_KEY`
   - `GITHUB_TOKEN`
   - `GITHUB_REPO` (ejemplo: `tu_usuario/mi-boveda-obsidian`)
   - `NOTES_FOLDER` (opcional, por defecto es `Obsesiones`)
7. Haz clic en **Deploy**. 

¡Listo! El bot estará corriendo en la nube permanentemente.

---

## 📱 Sincronización con tu Teléfono y PC (Obsidian)

Para ver las notas y el grafo en tu teléfono y computador:

### En tu Computador (PC / Mac):
1. Abre tu bóveda de Obsidian conectada a ese repositorio de GitHub.
2. Ve a **Ajustes > Community Plugins** y busca **Obsidian Git**.
3. Actívalo y en sus opciones activa **Auto Pull** (por ejemplo, cada 10 minutos).

### En tu Teléfono:
* **Android:** Instala el plugin **Obsidian Git** dentro de la app móvil de Obsidian y pon tus credenciales de GitHub.
* **iPhone / iOS:** Puedes sincronizar tu repositorio privado con la app gratuita **Working Copy** o clonando el repo en la carpeta de Obsidian.

---

## 🎮 Comandos de Telegram

* `/start` - Inicia la conversación y verifica permisos.
* `/status` - Te dice cuántas notas y nodos existen actualmente en tu grafo.
* `/sintesis` - Fuerza al modelo de razonamiento DeepSeek a generar una Micro-Tesis cruzando tus notas en ese instante sin esperar la semana.
