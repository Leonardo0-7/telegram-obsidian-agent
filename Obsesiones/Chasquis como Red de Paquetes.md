---
fecha: 2026-11-06
tags: [redes, inca, chasquis, conmutacion, historia-tecnologia]
---
G# Chasquis como Red de Paquetes

### Núcleo Conceptual
Los chasquis operaban en postas fijas donde cada corredor relevaba el mensaje sin acompañarlo hasta el destino: el contenido (paquete) viajaba, no el emisor (circuito). Esta fragmentación en tramos con reensamblaje implícito —oral o vía quipu— replica la lógica de conmutación de paquetes: sin ruta reservada, con nodos que solo reenvían. La conmutación de circuitos exigiría un corredor dedicado de extremo a extremo, inexistente en el sistema inca.

### Tensión o Pregunta Abierta
¿Puede existir conmutación de paquetes sin direccionamiento explícito, confiando solo en la topología lineal de la calzada?

### Conexiones en el Grafo
- [[Conmutación de Paquetes]]: el relevo por tramos anticipa el principio de fragmentación y reenvío nodo a nodo.
- [[Quipus como Codificación]]: el mensaje debía codificarse para sobrevivir al cambio de portador en cada posta.
- [[Redes de Relevos]]: la infraestructura física de postas define la topología que hace posible el reenvío.