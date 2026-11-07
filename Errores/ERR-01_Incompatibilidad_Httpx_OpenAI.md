---
id: ERR-01
fecha: 2026-11-06
tipo: postmortem-tecnico
tags: [dependencias, python, httpx, openai, runtime-error]
gravedad: alta
---
# ERR-01: Incompatibilidad entre Httpx y OpenAI

### 💥 Síntoma
El contenedor en la nube fallaba inmediatamente al arrancar con la excepción:
`TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`

### 🔍 Causa Raíz
La biblioteca `httpx` se actualizó a la versión `>=0.28.0`, eliminando el parámetro obsoleto `proxies` en favor de `proxy`. La versión de `openai` instalada (`1.54.0`) aún enviaba el argumento `proxies` en su cliente síncrono wrapper, provocando una colisión de dependencias transitivas no fijadas (*unpinned dependencies*).

### 🛠️ Solución Aplicada
Se fijó la compatibilidad en `requirements.txt`:
```txt
openai>=1.55.3
httpx<0.28.0
```

### 🛡️ Regla Preventiva (Invariante)
> *"Toda dependencia transitiva crítica que realice peticiones de red debe estar acotada con restricciones de versión estricta para evitar que una actualización externa rompa el contenedor en despliegue."*

### 🔗 Conexiones en la Red de Errores
- Conectado con: [[ERR-06_Bucle_Infinito_Autodeploy_Render]] *(Las fallas de arranque se retroalimentan con los despliegues automáticos)*
- Conectado con: [[Indice_Red_Neuronal_Errores]]
- Principio defensivo: [[Gestion_Segura_Dependencias]]
