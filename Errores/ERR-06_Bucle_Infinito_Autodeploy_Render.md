---
id: ERR-06
fecha: 2026-11-06
tipo: postmortem-devops
tags: [render, gitops, cicd, bucle-infinito, autodeploy, skip-ci]
gravedad: critica
---
# ERR-06: Bucle Infinito de Autodespliegues en Render (Auto-Deploy Feedback Loop)

### 💥 Síntoma
El bot de Telegram dejó de responder repentinamente tras una hora de funcionamiento normal. En el registro se evidenciaron más de 400 reinicios y despliegues automáticos sucesivos cada 25 segundos, hasta que Render suspendió temporalmente el contenedor.

### 🔍 Causa Raíz
El agente estaba programado para persistir sus registros de auditoría y notas directamente en el repositorio de GitHub mediante commits. Simultáneamente, el servicio en Render tenía activada la funcionalidad **Auto-Deploy** vigilando la rama `main`. Cada vez que el bot escribía un log o nota, Render interpretaba el commit como un cambio de código, reiniciando el contenedor, el cual al arrancar escribía otro evento de inicio (`AGENT_STARTUP`), retroalimentando un bucle recursivo destructivo de despliegues continuos.

### 🛠️ Solución Aplicada
1. Se añadió la directiva oficial de GitOps **`[skip ci]`** a todos los mensajes de commit generados por el bot (`save_file_to_github` y `append_logs_batch_to_github`).
2. Se reemplazó la escritura inmediata de logs por un sistema de **procesamiento en lotes (*batching*)** en segundo plano.
3. Se excluyó el evento `AGENT_STARTUP` de la persistencia inmediata en GitHub.
4. Se recomendó configurar `Auto-Deploy: No` en los ajustes de Render para desacoplar el ciclo de CI/CD del almacenamiento de datos.

### 🛡️ Regla Preventiva (Invariante)
> *"Cuando un agente autónomo utiliza el mismo repositorio de control de versiones como backend de almacenamiento y como fuente de despliegue continuo (GitOps reflexivo), todo commit generado por la máquina DEBE incluir etiquetas de omisión de CI/CD (`[skip ci]`) o apuntar a una rama de datos separada para prevenir bucles de recursión infinita."*

### 🔗 Conexiones en la Red de Errores
- Conectado con: [[ERR-01_Incompatibilidad_Httpx_OpenAI]] *(Costos de despliegues y reinicios repetidos)*
- Conectado con: [[ERR-03_Permiso_GitHub_403_Forbidden]] *(Operaciones de escritura sobre GitHub)*
- Conectado con: [[Indice_Red_Neuronal_Errores]]
- Principio defensivo: [[Desacoplamiento_Almacenamiento_Despliegue]]
