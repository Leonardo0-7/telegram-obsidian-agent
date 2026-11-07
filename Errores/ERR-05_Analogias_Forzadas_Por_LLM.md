---
id: ERR-05
fecha: 2026-11-06
tipo: postmortem-ia
tags: [prompt-engineering, llm, deepseek, alucinacion, grafos-conocimiento, chasqui-optico]
gravedad: media
---
# ERR-05: Analogías Metéricas Forzadas por el LLM (El "Chasqui Óptico")

### 💥 Síntoma
Al consultar sobre el principio físico de la luz de un ratón de computadora, el modelo generó una nota titulada `Chasqui Óptico y Atención.md`, afirmando que el sensor del mouse es un "chasqui que corre cuando la mano lo interrumpe", forzando una conexión metafórica absurda con los mensajeros incas.

### 🔍 Causa Raíz
El prompt del sistema contenía una directiva que exigía enlazar obligatoriamente con las notas existentes en la bóveda. Como la bóveda solo contaba con 2 notas (`Chasquis` e `Interrupciones`), el modelo estiró su razonamiento analógico para cumplir el mandato de conexión a toda costa, distorsionando la realidad técnica del sensor óptico CMOS.

### 🛠️ Solución Aplicada
Se reescribió el prompt del sistema implementando **Salvaguardas de Sensatez Técnica y Desacoplamiento de Grafos**:
1. Prohibición expresa de metáforas forzadas y mezclas incoherentes.
2. Cláusula de condicionalidad: solo conectar si existe relación directa de ingeniería/ciencia real.
3. Autorización explícita para crear nuevos clústeres independientes (ej: `[[Sensores CMOS]]`, `[[Optoelectrónica]]`).

### 🛡️ Regla Preventiva (Invariante)
> *"En sistemas de grafos de conocimiento basados en LLM, nunca se debe forzar la interconexión obligatoria sobre grafos incipientes o con pocos nodos. Debe existir una válvula de escape que permita la creación de ramas desconectadas (*subgrafos o clústeres emergentes*) para preservar la fidelidad semántica."*

### 🔗 Conexiones en la Red de Errores
- Conectado con: [[Indice_Red_Neuronal_Errores]]
- Principio defensivo: [[Salvaguardas_Grounding_Grafos]]
- Principio defensivo: [[Topologia_Clustering_Emergente]]
