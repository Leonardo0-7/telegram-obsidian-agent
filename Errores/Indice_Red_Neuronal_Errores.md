---
id: MOC-ERRORES
fecha: 2026-11-06
tipo: mapa-de-contenido-moc
tags: [red-neuronal, aprendizaje-continuo, postmortem, arquitectura, inmunidad-errores]
---
# 🧠 Red Neuronal de Errores y Aprendizajes (Memoria Anti-Patrones)

Este nodo central actúa como la **corteza de memoria inmunológica** del Agente. Su objetivo es transformar cada incidente técnico o conceptual en un nodo de conocimiento estructurado para **evitar cometer el mismo error dos veces**.

---

## 🕸️ Topología de la Red de Errores

```
          [ MOC: Red de Errores ]
                     │
    ┌────────────────┼────────────────┐
    ▼                ▼                ▼
[ DevOps / Infra ] [ Seguridad / Auth ] [ IA / Cognición ]
    │                │                │
    ├─ [[ERR-01]]    ├─ [[ERR-02]]    └─ [[ERR-05]] (Chasqui Óptico)
    ├─ [[ERR-04]]    └─ [[ERR-03]]
    └─ [[ERR-06]] (Bucle Auto-Deploy)
```

---

## 📂 Nodos de Incidentes Registrados

1. **[[ERR-01_Incompatibilidad_Httpx_OpenAI]]:** Colisión de librerías por breaking-change en `httpx`.
2. **[[ERR-02_Token_Telegram_Invalido]]:** Falla de autenticación inicial por sanitización de credenciales.
3. **[[ERR-03_Permiso_GitHub_403_Forbidden]]:** Bloqueo de escritura por alcance (*scope*) insuficiente del PAT.
4. **[[ERR-04_Boveda_Obsidian_Fuera_De_Git]]:** Desconexión entre la UI de Obsidian y el árbol de carpetas con `.git/`.
5. **[[ERR-05_Analogias_Forzadas_Por_LLM]]:** Distorsión conceptual por sobre-enlace forzado en grafos vacíos.
6. **[[ERR-06_Bucle_Infinito_Autodeploy_Render]]:** Bucle recursivo de despliegues por commits de la máquina sobre el repositorio de CI/CD.

---

## 🛡️ Principios Defensivos Derivados (Invariantes de Ingeniería)

* [[Gestion_Segura_Dependencias]]: Version pinning estricto en contenedores.
* [[Validacion_Estricta_Credenciales]]: Sanitización y pre-chequeo antes de arrancar bucles de red.
* [[Principio_Minimo_Privilegio_Operativo]]: Tokens acotados con alcance exacto de lectura/escritura.
* [[Alineacion_Rutas_Sincronizacion]]: Correspondencia 1:1 entre frontend local y backend Git.
* [[Salvaguardas_Grounding_Grafos]]: Permiso de desacoplamiento para crear ramas y clústeres independientes.
* [[Desacoplamiento_Almacenamiento_Despliegue]]: Uso obligatorio de `[skip ci]` en agentes que escriben en su propio código.
