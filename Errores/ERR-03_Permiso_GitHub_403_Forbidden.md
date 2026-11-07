---
id: ERR-03
fecha: 2026-11-06
tipo: postmortem-seguridad
tags: [github-api, rbac, permisos, personal-access-token, 403-forbidden]
gravedad: alta
---
# ERR-03: Permiso Insuficiente en Token de GitHub (HTTP 403 Forbidden)

### 💥 Síntoma
DeepSeek procesaba correctamente la idea, pero al momento de persistir la nota en el repositorio, la API de GitHub respondía con error:
`HTTP 403: {"message":"Resource not accessible by personal access token"}`

### 🔍 Causa Raíz
El Personal Access Token (PAT) generado en GitHub no contaba con el alcance (*scope*) de escritura `repo` (Full control of private repositories) o tenía permisos restringidos de solo lectura (*read-only*), bloqueando las operaciones `PUT /repos/{owner}/{repo}/contents/{path}`.

### 🛠️ Solución Aplicada
Se generó un token clásico con el alcance `repo` habilitado (o token de grano fino con permiso `Contents: Read and write`) y se actualizó la variable `GITHUB_TOKEN` en Render.

### 🛡️ Regla Preventiva (Invariante)
> *"Todo agente que use Git como motor de base de datos desacoplada (Headless Git) debe verificar explícitamente sus permisos de escritura sobre el repositorio de destino antes de intentar transacciones de contenido."*

### 🔗 Conexiones en la Red de Errores
- Conectado con: [[ERR-02_Token_Telegram_Invalido]] *(Autenticación de APIs externas)*
- Conectado con: [[ERR-06_Bucle_Infinito_Autodeploy_Render]] *(Interacción del bot con el repositorio GitHub)*
- Conectado con: [[Indice_Red_Neuronal_Errores]]
- Principio defensivo: [[Principio_Minimo_Privilegio_Operativo]]
