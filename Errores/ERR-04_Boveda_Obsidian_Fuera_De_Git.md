---
id: ERR-04
fecha: 2026-11-06
tipo: postmortem-cliente
tags: [obsidian, obsidian-git, configuracion, rutas, filesystem]
gravedad: baja
---
# ERR-04: Bóveda de Obsidian Fuera del Repositorio Git

### 💥 Síntoma
Al activar el plugin Obsidian Git, aparecía el aviso de error:
`fatal: --local can only be used inside a git repository (Git is not ready)`

### 🔍 Causa Raíz
Obsidian abrió la bóveda por defecto (`C:\Users\...\Obsidian Vault`), la cual era un directorio plano sin control de versiones, en lugar de abrir la carpeta raíz clonada del proyecto (`telegram-obsidian-agent`) donde Git sí estaba inicializado con el origen remoto.

### 🛠️ Solución Aplicada
Se utilizó la opción **"Open folder as vault"** (Abrir carpeta como bóveda) seleccionando directamente el directorio del repositorio local sincronizado.

### 🛡️ Regla Preventiva (Invariante)
> *"La interfaz de visualización cliente (Obsidian) debe coincidir exactamente con el árbol de directorios que contiene el metadirectorio `.git/` para permitir sincronización bidireccional automática."*

### 🔗 Conexiones en la Red de Errores
- Conectado con: [[ERR-03_Permiso_GitHub_403_Forbidden]] *(La sincronización depende del flujo completo Git)*
- Conectado con: [[Indice_Red_Neuronal_Errores]]
- Principio defensivo: [[Alineacion_Rutas_Sincronizacion]]
