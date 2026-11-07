---
id: ERR-02
fecha: 2026-11-06
tipo: postmortem-seguridad
tags: [telegram, auth, tokens, credenciales, 401-unauthorized]
gravedad: media
---
# ERR-02: Token de Telegram Inválido o Rechazado (401 Unauthorized)

### 💥 Síntoma
El bot arrancaba pero fallaba durante la llamada `getMe` hacia Telegram con:
`telegram.error.InvalidToken: The token was rejected by the server (401 Unauthorized)`

### 🔍 Causa Raíz
Un error de copiado/pegado o transcripción de caracteres en la variable de entorno `TELEGRAM_TOKEN` proporcionada en el panel de despliegue, impidiendo la autenticación exitosa contra los servidores de Telegram Bot API.

### 🛠️ Solución Aplicada
Se consultó el comando `/mybots` > `API Token` directamente en `@BotFather`, copiando el hash íntegro sin espacios en blanco al inicio o final y actualizándolo en las variables de entorno de Render.

### 🛡️ Regla Preventiva (Invariante)
> *"Las credenciales API nunca deben digitarse manualmente ni transportarse sin sanitización de espacios en blanco; deben validarse en tiempo de inicio antes de disparar el bucle de polling."*

### 🔗 Conexiones en la Red de Errores
- Conectado con: [[ERR-03_Permiso_GitHub_403_Forbidden]] *(Fallas de autenticación y permisos de tokens)*
- Conectado con: [[Indice_Red_Neuronal_Errores]]
- Principio defensivo: [[Validacion_Estricta_Credenciales]]
