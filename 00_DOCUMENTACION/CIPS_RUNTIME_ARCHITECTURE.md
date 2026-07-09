<!--
=========================================================
Proyecto : CIPS
Release   : 0.3
Sprint    : Software Sprint 004
Documento : Runtime Architecture
Versión   : 1.0
Estado    : DRAFT
=========================================================
-->

# CIPS RUNTIME ARCHITECTURE

## Arquitectura Operativa del Sistema

Versión 1.0

---

# PROPÓSITO

El presente documento define la arquitectura de ejecución del Content Intelligence Production System (CIPS).

Su finalidad consiste en describir el comportamiento operativo del sistema desde el momento en que un usuario crea un proyecto hasta la generación del resultado final.

Este documento constituye el plano de construcción utilizado para implementar el Runtime de CIPS.

---

# ALCANCE

La Runtime Architecture gobierna exclusivamente la ejecución del sistema.

Incluye.

- creación de proyectos;
- carga de configuración;
- carga del conocimiento;
- construcción del contexto;
- generación de prompts;
- validación;
- memoria;
- cambio de etapas;
- finalización del proyecto.

No define reglas editoriales.

No sustituye a la Constitución.

No sustituye al Knowledge Library.

---

# PRINCIPIOS

Toda ejecución del Runtime deberá cumplir simultáneamente.

- modularidad;
- responsabilidad única;
- trazabilidad;
- reproducibilidad;
- validación continua;
- tolerancia a errores.

---

# COMPONENTES DEL RUNTIME

El Runtime oficial de CIPS estará compuesto por los siguientes motores.

```
Project Manager

↓

Knowledge Engine

↓

Context Engine

↓

Prompt Builder

↓

Validator Engine

↓

Memory Engine

↓

Pipeline Engine
```

Cada motor tendrá una única responsabilidad.

Ningún motor ejecutará funciones pertenecientes a otro componente.

---

# OBJETIVO DEL RUNTIME

Transformar un objetivo del usuario en un resultado validado utilizando el menor número posible de pasos manuales.

---

# DECLARACIÓN

La Runtime Architecture constituye el documento operativo que guía la implementación del software del Release 0.3.

Toda implementación deberá respetar el flujo definido en este documento.

---

**FIN DE LA PARTE 1/10**
# ARQUITECTURA RUNTIME

---

# 2.1 DEFINICIÓN

La Runtime Architecture describe cómo se ejecuta CIPS durante una operación real.

Su responsabilidad consiste en definir.

- qué componente inicia;
- qué componente recibe información;
- qué componente procesa;
- qué componente valida;
- qué componente guarda;
- qué componente decide la siguiente etapa.

---

# 2.2 FLUJO GENERAL

El flujo oficial de ejecución será.

```text
Usuario

↓

run.py

↓

Pipeline Engine

↓

Project Manager

↓

Knowledge Engine

↓

Context Engine

↓

Prompt Builder

↓

Modelo IA

↓

Validator Engine

↓

Memory Engine

↓

Pipeline Engine

↓

Siguiente Stage
```

---

# 2.3 REGLA PRINCIPAL

El usuario no deberá decidir manualmente qué módulo ejecutar.

El Runtime deberá determinar automáticamente la siguiente acción según el estado del proyecto.

---

# 2.4 RESPONSABILIDAD DE run.py

`run.py` será únicamente el punto de entrada.

Sus responsabilidades serán.

- iniciar la aplicación;
- mostrar el menú;
- recibir la opción del usuario;
- llamar al Pipeline Engine.

`run.py` no deberá contener lógica de negocio.

---

# 2.5 RESPONSABILIDAD DEL PIPELINE ENGINE

El Pipeline Engine será el coordinador principal de ejecución.

Sus responsabilidades serán.

- leer el estado del proyecto;
- determinar el Stage actual;
- invocar el motor correspondiente;
- actualizar el estado;
- detener el flujo cuando sea necesario.

---

# 2.6 RESPONSABILIDAD DEL PROJECT MANAGER

El Project Manager será responsable de.

- crear proyectos;
- organizar carpetas;
- crear archivos base;
- mantener `proyecto.yaml`;
- mantener `memoria.yaml`.

No deberá construir prompts.

---

# 2.7 RESPONSABILIDAD DEL KNOWLEDGE ENGINE

El Knowledge Engine será responsable de.

- cargar Knowledge Modules;
- seleccionar módulos relevantes;
- resolver dependencias;
- entregar conocimiento estructurado al Context Engine.

No deberá generar prompts.

---

# 2.8 RESPONSABILIDAD DEL CONTEXT ENGINE

El Context Engine será responsable de.

- recibir Knowledge Modules;
- ordenar el contexto;
- eliminar redundancias;
- preparar un Context Object.

No deberá comunicarse con modelos IA.

---

# 2.9 RESPONSABILIDAD DEL PROMPT BUILDER

El Prompt Builder será responsable de.

- recibir el Context Object;
- recibir el objetivo del Stage;
- construir el Prompt Object;
- renderizar el prompt final en Markdown.

No deberá seleccionar conocimiento.

---

# 2.10 RESPONSABILIDAD DEL VALIDATOR ENGINE

El Validator Engine será responsable de.

- verificar estructura;
- verificar formato;
- verificar consistencia;
- detectar errores críticos;
- aprobar o rechazar resultados.

---

# 2.11 RESPONSABILIDAD DEL MEMORY ENGINE

El Memory Engine será responsable de.

- registrar avances;
- guardar decisiones;
- actualizar memoria del proyecto;
- registrar próximos pasos.

No deberá modificar conocimiento permanente.

---

# 2.12 REGLA DE SEPARACIÓN

Cada Engine deberá realizar únicamente su responsabilidad.

Cuando un Engine necesite información de otro, deberá recibirla mediante entradas explícitas.

Nunca deberá acceder de forma oculta a responsabilidades ajenas.

---

**FIN DE LA PARTE 2/10**
# CICLO DE VIDA DE UN PROYECTO

---

# 3.1 PROPÓSITO

Todo proyecto administrado por CIPS seguirá un ciclo de vida único y bien definido.

El objetivo consiste en garantizar que cada proyecto avance de forma controlada, verificable y reproducible.

Ningún proyecto podrá omitir etapas.

---

# 3.2 ESTADOS OFICIALES

Todo proyecto podrá encontrarse únicamente en uno de los siguientes estados.

```
Creado

↓

En ejecución

↓

En validación

↓

Completado

↓

Archivado
```

No existirán estados adicionales.

---

# 3.3 CREACIÓN

Cuando el usuario cree un nuevo proyecto.

El sistema deberá.

- asignar un identificador;
- crear la estructura de carpetas;
- generar los archivos base;
- inicializar la memoria;
- establecer el primer Stage.

Resultado.

```
Proyecto listo para iniciar.
```

---

# 3.4 INICIO DE EJECUCIÓN

Cuando el usuario solicite continuar un proyecto.

El Pipeline Engine deberá.

- leer `proyecto.yaml`;
- identificar el Stage actual;
- verificar que existan los archivos necesarios;
- cargar la configuración.

Si todo es correcto.

Iniciará el Stage correspondiente.

---

# 3.5 EJECUCIÓN DEL STAGE

Durante un Stage el Runtime deberá seguir siempre el mismo flujo.

```
Leer Stage

↓

Cargar conocimiento

↓

Construir contexto

↓

Construir Prompt

↓

Enviar al modelo IA

↓

Validar respuesta

↓

Guardar resultado
```

Este flujo será idéntico para todas las etapas del Pipeline.

---

# 3.6 VALIDACIÓN

Una vez obtenida la respuesta.

El Validator Engine comprobará.

- estructura;
- formato;
- contenido mínimo;
- cumplimiento del objetivo.

Si la validación falla.

El Stage no avanzará.

---

# 3.7 ACTUALIZACIÓN DE MEMORIA

Cuando una etapa sea aprobada.

El Memory Engine deberá registrar.

- Stage completado;
- fecha;
- resultado generado;
- siguiente Stage;
- observaciones relevantes.

---

# 3.8 TRANSICIÓN

Después de actualizar la memoria.

El Pipeline Engine modificará el estado del proyecto.

Ejemplo.

```
Investigación

↓

Verificación

↓

Guion

↓

Storyboard

↓

SEO

↓

Publicación

↓

Final
```

El cambio será automático.

---

# 3.9 FINALIZACIÓN

Cuando el último Stage sea completado.

El sistema deberá.

- marcar el proyecto como finalizado;
- registrar la fecha de cierre;
- generar el Output final;
- impedir nuevas etapas.

El proyecto quedará disponible únicamente para consulta o exportación.

---

# 3.10 REANUDACIÓN

Si la ejecución se interrumpe.

El Runtime deberá ser capaz de continuar exactamente desde el último Stage validado.

Nunca deberá reiniciar el proyecto completo.

---

# 3.11 REGLA DE ORO

El estado del proyecto siempre será determinado por el último Stage validado.

Nunca por el último Stage ejecutado.

Esta regla evita pérdidas de información cuando una ejecución falla.

---

# DIAGRAMA DEL CICLO DE VIDA

```text
Nuevo Proyecto

↓

Inicialización

↓

Stage Actual

↓

Prompt

↓

LLM

↓

Validator

↓

Memory

↓

¿Último Stage?

↓

No ────────────── Sí

↓                  ↓

Siguiente Stage    Proyecto Finalizado
```

---

# CONCLUSIÓN

El ciclo de vida oficial garantiza que todos los proyectos recorran exactamente el mismo flujo operativo.

Gracias a esta uniformidad, el Pipeline Engine podrá coordinar la ejecución de cualquier proyecto sin depender de lógica específica para cada caso, simplificando la implementación y facilitando la automatización.

---

**FIN DE LA PARTE 3/10**
# MOTORES DEL SISTEMA

---

# 4.1 PROPÓSITO

Los Engines constituyen los componentes operativos del Runtime de CIPS.

Cada Engine posee una responsabilidad exclusiva y colabora con los demás mediante entradas y salidas claramente definidas.

Ningún Engine deberá asumir responsabilidades ajenas.

---

# 4.2 ARQUITECTURA GENERAL

El Runtime estará compuesto por los siguientes Engines.

```
Pipeline Engine

↓

Project Manager

↓

Knowledge Engine

↓

Context Engine

↓

Prompt Builder

↓

Validator Engine

↓

Memory Engine
```

Cada Engine será independiente.

---

# 4.3 PIPELINE ENGINE

## Responsabilidad

Coordinar toda la ejecución del proyecto.

## Entradas

- Proyecto.
- Estado actual.
- Configuración.

## Salidas

- Stage actualizado.
- Resultado del Stage.
- Estado del Pipeline.

## Funciones

- iniciar ejecución;
- determinar el Stage;
- coordinar Engines;
- controlar errores;
- finalizar ejecución.

---

# 4.4 PROJECT MANAGER

## Responsabilidad

Administrar la estructura física del proyecto.

## Entradas

- Datos del proyecto.

## Salidas

- Carpetas.
- Archivos.
- Configuración inicial.

## Funciones

- crear proyecto;
- abrir proyecto;
- actualizar proyecto;
- guardar cambios.

---

# 4.5 KNOWLEDGE ENGINE

## Responsabilidad

Seleccionar el conocimiento necesario para la tarea.

## Entradas

- Stage.
- Objetivo.
- Configuración.

## Salidas

- Lista de Knowledge Modules.

## Funciones

- localizar módulos;
- resolver dependencias;
- eliminar duplicados;
- preparar conocimiento.

---

# 4.6 CONTEXT ENGINE

## Responsabilidad

Construir el contexto que utilizará el Prompt Builder.

## Entradas

- Knowledge Modules.

## Salidas

- Context Object.

## Funciones

- ordenar información;
- eliminar redundancia;
- estructurar contexto;
- calcular tamaño.

---

# 4.7 PROMPT BUILDER

## Responsabilidad

Transformar el Context Object en un prompt listo para el modelo IA.

## Entradas

- Context Object.
- Objetivo.
- Plantilla.

## Salidas

- Prompt Object.
- Archivo Markdown.

## Funciones

- ensamblar prompt;
- aplicar plantilla;
- validar estructura.

---

# 4.8 VALIDATOR ENGINE

## Responsabilidad

Evaluar la calidad del resultado.

## Entradas

- Respuesta IA.
- Stage.

## Salidas

- Resultado validado.
- Lista de observaciones.

## Funciones

- validar formato;
- validar contenido;
- validar estructura;
- aprobar o rechazar.

---

# 4.9 MEMORY ENGINE

## Responsabilidad

Registrar el estado del proyecto.

## Entradas

- Resultado validado.

## Salidas

- Memoria actualizada.

## Funciones

- registrar progreso;
- guardar decisiones;
- actualizar memoria;
- preparar siguiente Stage.

---

# 4.10 INTERFAZ COMÚN

Todos los Engines deberán implementar la misma interfaz pública.

```python
execute(project)
```

La implementación interna podrá variar.

La interfaz pública permanecerá constante.

---

# 4.11 DEPENDENCIAS

Los Engines únicamente podrán comunicarse mediante datos de entrada y salida.

No deberán acceder directamente al estado interno de otros Engines.

Esta regla garantiza el desacoplamiento del sistema.

---

# MATRIZ DE RESPONSABILIDADES

| Engine | Entrada | Salida |
|---------|----------|---------|
| Pipeline Engine | Proyecto | Flujo coordinado |
| Project Manager | Datos | Proyecto inicializado |
| Knowledge Engine | Stage | Knowledge Modules |
| Context Engine | Knowledge | Context Object |
| Prompt Builder | Context | Prompt |
| Validator Engine | Respuesta | Resultado validado |
| Memory Engine | Resultado | Memoria actualizada |

---

# CONCLUSIÓN

La separación de responsabilidades permite que cada Engine evolucione de manera independiente sin afectar al resto del Runtime.

Esta modularidad constituye uno de los principios fundamentales de la arquitectura de CIPS y facilitará tanto el mantenimiento como la incorporación de nuevas capacidades en versiones futuras.

---

**FIN DE LA PARTE 4/10**
# FLUJO DE EJECUCIÓN

---

# 5.1 PROPÓSITO

El Runtime de CIPS seguirá un flujo único de ejecución para todos los proyectos.

La finalidad consiste en eliminar decisiones manuales y garantizar que todas las etapas recorran exactamente el mismo proceso operativo.

---

# 5.2 FLUJO OFICIAL

```
Usuario

↓

Selecciona Proyecto

↓

Pipeline Engine

↓

Lee proyecto.yaml

↓

Identifica Stage

↓

Knowledge Engine

↓

Context Engine

↓

Prompt Builder

↓

Modelo IA

↓

Validator Engine

↓

Memory Engine

↓

Actualizar proyecto.yaml

↓

¿Existe siguiente Stage?

↓

Sí → Continuar

↓

No → Finalizar Proyecto
```

---

# 5.3 INICIO

Toda ejecución comenzará cuando el usuario solicite continuar un proyecto.

El Pipeline Engine será responsable de iniciar el flujo.

Antes de ejecutar cualquier acción deberá verificar.

- existencia del proyecto;
- existencia de proyecto.yaml;
- existencia del Stage actual;
- configuración válida.

---

# 5.4 EJECUCIÓN

Cada Stage seguirá exactamente la misma secuencia.

```
1.
Leer estado

↓

2.
Construir conocimiento

↓

3.
Construir contexto

↓

4.
Construir Prompt

↓

5.
Enviar al modelo IA

↓

6.
Validar respuesta

↓

7.
Guardar resultado

↓

8.
Actualizar memoria

↓

9.
Cambiar Stage
```

El Runtime nunca modificará esta secuencia.

---

# 5.5 DECISIONES

El Runtime tomará únicamente tres decisiones.

## Primera

¿El proyecto existe?

Si no.

Finalizar.

---

## Segunda

¿La respuesta fue validada?

Si no.

Permanecer en el mismo Stage.

---

## Tercera

¿Existe un siguiente Stage?

Si existe.

Continuar.

Si no.

Finalizar proyecto.

---

# 5.6 COMUNICACIÓN ENTRE ENGINES

La comunicación será exclusivamente mediante objetos.

Ejemplo.

```
Knowledge Engine

↓

KnowledgeResult

↓

Context Engine

↓

ContextResult

↓

Prompt Builder

↓

PromptResult

↓

Validator

↓

ValidationResult

↓

Memory Engine
```

Los Engines nunca compartirán variables internas.

---

# 5.7 ACTUALIZACIÓN DEL PROYECTO

Al finalizar correctamente un Stage.

El Pipeline Engine actualizará.

```
proyecto.yaml
```

Campos mínimos.

- stage_actual
- estado
- fecha_actualizacion

---

# 5.8 REGLA DE CONTINUIDAD

Cada Stage únicamente podrá comenzar cuando el Stage anterior haya sido validado.

No existirán saltos entre etapas.

---

# 5.9 FINALIZACIÓN

Cuando el último Stage concluya correctamente.

El Runtime deberá.

- actualizar estado;
- registrar fecha de finalización;
- generar Output final;
- cerrar ejecución.

---

# DIAGRAMA OPERATIVO

```
Proyecto

↓

Stage

↓

Knowledge

↓

Context

↓

Prompt

↓

LLM

↓

Validator

↓

Memory

↓

Actualizar Proyecto

↓

Siguiente Stage
```

---

# CHECKLIST

Antes de ejecutar un Stage.

□ Proyecto encontrado.

□ Configuración válida.

□ Stage identificado.

□ Knowledge disponible.

□ Prompt construido.

□ Validator preparado.

□ Memory disponible.

---

# CONCLUSIÓN

El flujo de ejecución constituye el comportamiento operativo permanente del Runtime.

Gracias a esta secuencia fija, el Pipeline Engine podrá coordinar cualquier proyecto sin lógica específica para cada etapa, reduciendo la complejidad del sistema y facilitando su mantenimiento.

---

**FIN DE LA PARTE 5/10**
# MANEJO DE ERRORES

---

# 6.1 PROPÓSITO

El Runtime deberá detectar, registrar y manejar los errores sin comprometer la integridad del proyecto.

Todo error deberá producir un estado conocido.

Nunca un estado incierto.

---

# 6.2 PRINCIPIO GENERAL

Cuando ocurra un error.

El Runtime deberá.

- detener únicamente el proceso afectado;
- conservar la información existente;
- registrar el incidente;
- permitir continuar posteriormente.

Nunca deberá corromper el proyecto.

---

# 6.3 CLASIFICACIÓN

Los errores se clasifican en tres niveles.

## Advertencia (Warning)

El proceso puede continuar.

Ejemplos.

- información opcional ausente;
- advertencias del Validator;
- metadatos incompletos.

---

## Error Recuperable

El Stage no podrá completarse.

El proyecto permanecerá en el mismo Stage.

Ejemplos.

- respuesta IA inválida;
- Prompt incompleto;
- archivo esperado inexistente.

---

## Error Crítico

La ejecución deberá detenerse inmediatamente.

Ejemplos.

- proyecto inexistente;
- configuración corrupta;
- memoria ilegible;
- fallo interno del Runtime.

---

# 6.4 RESPONSABILIDADES

## Pipeline Engine

Decidir si continúa o detiene la ejecución.

---

## Validator Engine

Detectar errores de contenido.

---

## Memory Engine

Registrar el incidente.

---

## Project Manager

Garantizar que el proyecto permanezca íntegro.

---

# 6.5 REGLA DE RECUPERACIÓN

Cuando un Stage falle.

El Runtime.

No modificará.

- proyecto.yaml
- memoria.yaml
- Stage actual

El usuario podrá corregir el problema y reanudar la ejecución.

---

# 6.6 LOGS

Todo error deberá registrarse.

Información mínima.

- fecha;
- proyecto;
- Stage;
- Engine;
- tipo de error;
- descripción.

Los registros se almacenarán en.

```
07_LOGS/
```

---

# 6.7 MENSAJES

Los mensajes deberán ser.

- claros;
- accionables;
- específicos.

Ejemplo.

Incorrecto.

```
Error inesperado.
```

Correcto.

```
No fue posible cargar el archivo proyecto.yaml.

Verifique que el proyecto exista y vuelva a intentarlo.
```

---

# 6.8 RECUPERACIÓN

Después de corregir un error.

El usuario podrá ejecutar nuevamente el Pipeline.

El Runtime continuará desde el último Stage validado.

Nunca desde el inicio.

---

# 6.9 DIAGRAMA

```
Stage

↓

Error

↓

Registrar

↓

¿Recuperable?

↓

Sí

↓

Esperar corrección

↓

Reintentar

──────────────

No

↓

Detener Runtime
```

---

# CHECKLIST

Cuando ocurra un error.

□ Registrar.

□ No perder información.

□ No modificar el Stage.

□ Informar claramente.

□ Permitir recuperación.

---

# CONCLUSIÓN

El manejo de errores de CIPS prioriza la integridad del proyecto sobre la continuidad de la ejecución.

Todo error deberá dejar el sistema en un estado consistente y permitir que el trabajo continúe una vez corregida la causa del problema.

---

**FIN DE LA PARTE 6/10**
# ESTADOS DEL PROYECTO

---

# 7.1 PROPÓSITO

El Runtime administrará el avance de cada proyecto mediante un conjunto reducido de estados oficiales.

Los estados representan la situación actual del proyecto y permiten al Pipeline Engine determinar automáticamente la siguiente acción.

Todo proyecto deberá encontrarse siempre en un único estado.

---

# 7.2 ESTADOS OFICIALES

Se establecen los siguientes estados.

```
CREATED

↓

READY

↓

RUNNING

↓

WAITING_RESPONSE

↓

VALIDATING

↓

COMPLETED

↓

ERROR

↓

ARCHIVED
```

No existirán estados adicionales.

---

# 7.3 CREATED

Representa un proyecto recién creado.

Características.

- estructura generada;
- archivos creados;
- configuración inicial;
- primer Stage asignado.

El proyecto todavía no ha iniciado su ejecución.

---

# 7.4 READY

El proyecto está preparado para comenzar.

El Runtime verificó.

- configuración;
- archivos;
- memoria;
- Stage.

Puede ejecutarse inmediatamente.

---

# 7.5 RUNNING

El Pipeline está ejecutando un Stage.

Durante este estado.

- ningún otro Stage podrá iniciarse;
- únicamente un Engine podrá ejecutarse a la vez;
- el proyecto permanecerá bloqueado hasta terminar.

---

# 7.6 WAITING_RESPONSE

El Prompt fue generado correctamente.

El Runtime espera la respuesta del modelo IA.

Este estado permite mantener la continuidad del proyecto cuando la generación de la respuesta no sea inmediata.

---

# 7.7 VALIDATING

La respuesta fue recibida.

El Validator Engine comprobará.

- estructura;
- contenido;
- formato;
- cumplimiento del objetivo.

Hasta concluir la validación el proyecto no podrá avanzar.

---

# 7.8 COMPLETED

Todos los Stages fueron ejecutados y validados.

El proyecto queda disponible para.

- consulta;
- exportación;
- archivado.

No podrán iniciarse nuevas etapas.

---

# 7.9 ERROR

La ejecución fue interrumpida.

El Runtime registrará.

- causa;
- Engine;
- Stage;
- fecha.

El proyecto conservará toda la información válida.

Podrá reanudarse posteriormente.

---

# 7.10 ARCHIVED

El proyecto finalizó completamente.

Ya no participará en el Pipeline.

Permanecerá únicamente como histórico.

---

# 7.11 TRANSICIONES

Las transiciones permitidas son.

```
CREATED

↓

READY

↓

RUNNING

↓

WAITING_RESPONSE

↓

VALIDATING

↓

COMPLETED
```

En cualquier momento podrá ocurrir.

```
ERROR
```

Desde ERROR.

```
READY
```

Una vez corregido el problema.

Finalmente.

```
ARCHIVED
```

---

# 7.12 REGLAS

El Runtime deberá cumplir.

- un único estado activo;
- transiciones válidas únicamente;
- registro obligatorio del cambio;
- actualización inmediata de proyecto.yaml.

---

# 7.13 REPRESENTACIÓN EN PROYECTO.YAML

Ejemplo.

```yaml
estado: RUNNING

stage_actual: investigacion

ultimo_stage_validado: tema

fecha_actualizacion: 2026-07-09T09:30:00
```

---

# DIAGRAMA

```
CREATED

↓

READY

↓

RUNNING

↓

WAITING_RESPONSE

↓

VALIDATING

↓

COMPLETED

↓

ARCHIVED
```

Errores.

```
RUNNING

↓

ERROR

↓

READY
```

---

# CHECKLIST

Antes de modificar el estado.

□ Estado actual válido.

□ Transición permitida.

□ Proyecto actualizado.

□ Memoria sincronizada.

□ Log registrado.

---

# CONCLUSIÓN

Los estados oficiales representan la máquina de estados del Runtime.

Gracias a este modelo, el Pipeline Engine podrá determinar automáticamente la situación de cualquier proyecto, decidir la siguiente acción y reanudar la ejecución sin pérdida de información.

---

**FIN DE LA PARTE 7/10**
# ENTRADAS Y SALIDAS DEL RUNTIME

---

# 8.1 PROPÓSITO

Todo Engine del Runtime deberá recibir entradas claramente definidas y producir salidas estructuradas.

El intercambio de información entre componentes nunca dependerá de variables globales ni del estado interno de otros Engines.

Toda comunicación deberá realizarse mediante objetos de intercambio.

---

# 8.2 PRINCIPIO GENERAL

Cada Engine será tratado como una caja negra.

Recibe información.

↓

Procesa.

↓

Devuelve un resultado.

El Pipeline Engine será el único responsable de coordinar este intercambio.

---

# 8.3 ENTRADA DEL RUNTIME

Toda ejecución comenzará con un único objeto.

```text
Project
```

Este objeto representa el proyecto completo.

Contiene únicamente la información necesaria para ejecutar el Stage actual.

---

# 8.4 FLUJO DE OBJETOS

El Runtime intercambiará objetos siguiendo el siguiente flujo.

```text
Project

↓

KnowledgeResult

↓

ContextResult

↓

PromptResult

↓

LLMResponse

↓

ValidationResult

↓

MemoryResult
```

Cada objeto tendrá una única responsabilidad.

---

# 8.5 PROJECT

Representa el estado completo del proyecto.

Información mínima.

- id
- nombre
- stage_actual
- estado
- configuración
- memoria

Será la entrada principal del Pipeline.

---

# 8.6 KNOWLEDGERESULT

Resultado producido por el Knowledge Engine.

Información mínima.

- módulos encontrados
- dependencias
- advertencias
- errores

---

# 8.7 CONTEXTRESULT

Resultado producido por el Context Engine.

Información mínima.

- contexto
- tamaño
- módulos utilizados
- metadatos

---

# 8.8 PROMPTRESULT

Resultado producido por el Prompt Builder.

Información mínima.

- Prompt Object
- archivo Markdown generado
- plantilla utilizada

---

# 8.9 LLMRESPONSE

Representa la respuesta obtenida del modelo IA.

Información mínima.

- contenido
- modelo utilizado
- fecha
- metadatos

El Runtime no interpretará directamente esta respuesta.

Siempre será enviada al Validator.

---

# 8.10 VALIDATIONRESULT

Resultado del Validator.

Información mínima.

- aprobado
- observaciones
- advertencias
- errores

El Pipeline decidirá el siguiente paso utilizando únicamente este objeto.

---

# 8.11 MEMORYRESULT

Resultado producido por el Memory Engine.

Información mínima.

- memoria actualizada
- Stage registrado
- fecha
- próximo Stage

---

# 8.12 ENGINE RESULT

Todos los Engines devolverán un objeto común denominado.

```
EngineResult
```

Información mínima.

```text
success

data

warnings

errors

message

metadata
```

Cada Engine podrá extender el contenido de "data" según sus necesidades.

La estructura externa permanecerá constante.

---

# 8.13 BENEFICIOS

La utilización de objetos estandarizados permite.

- desacoplar Engines;
- simplificar pruebas unitarias;
- facilitar futuras integraciones;
- mejorar la mantenibilidad.

---

# CHECKLIST

Todo Engine deberá.

□ Recibir entradas definidas.

□ No acceder a otros Engines.

□ Devolver EngineResult.

□ No modificar Project directamente.

□ Comunicar errores mediante EngineResult.

---

# CONCLUSIÓN

La comunicación mediante objetos estandarizados constituye uno de los pilares del Runtime.

Gracias a este mecanismo, el Pipeline Engine podrá coordinar la ejecución completa sin depender de la implementación interna de ninguno de los Engines.

---

**FIN DE LA PARTE 8/10**
# DIAGRAMA GENERAL DEL RUNTIME

---

# 9.1 PROPÓSITO

El presente diagrama resume la operación completa del Runtime de CIPS.

Su finalidad consiste en mostrar cómo colaboran todos los componentes durante la ejecución de un proyecto.

Este diagrama representa el flujo oficial del Release 0.3.

---

# DIAGRAMA GENERAL

```text
                     USUARIO
                         │
                         ▼
                    CIPS/run.py
                         │
                         ▼
                 Pipeline Engine
                         │
                         ▼
                 Project Manager
                         │
                         ▼
                  Proyecto (Project)
                         │
                         ▼
                Knowledge Engine
                         │
                 EngineResult
                         │
                         ▼
                 Context Engine
                         │
                 EngineResult
                         │
                         ▼
                 Prompt Builder
                         │
                 EngineResult
                         │
                         ▼
                     LLM
         (ChatGPT / Gemini / Claude)
                         │
                         ▼
                  Validator Engine
                         │
                 EngineResult
                         │
                         ▼
                  Memory Engine
                         │
                 EngineResult
                         │
                         ▼
                 Pipeline Engine
                         │
        ¿Existe siguiente Stage?
               │             │
             Sí              No
              │               │
              ▼               ▼
      Actualizar Proyecto   Finalizar
              │               │
              └───────┬───────┘
                      ▼
                 Fin del Runtime
```

---

# 9.2 ORDEN DE EJECUCIÓN

El Runtime ejecutará siempre los componentes en el siguiente orden.

1.

Project Manager

↓

2.

Knowledge Engine

↓

3.

Context Engine

↓

4.

Prompt Builder

↓

5.

LLM

↓

6.

Validator Engine

↓

7.

Memory Engine

↓

8.

Pipeline Engine

El orden no podrá modificarse.

---

# 9.3 FLUJO DE INFORMACIÓN

Toda la información viajará únicamente hacia adelante.

```text
Project

↓

Knowledge

↓

Context

↓

Prompt

↓

Respuesta

↓

Validación

↓

Memoria

↓

Actualización del Proyecto
```

No existirán dependencias circulares.

---

# 9.4 REGLAS DEL RUNTIME

Durante toda la ejecución deberán cumplirse las siguientes reglas.

- un único Pipeline activo;
- un único Stage activo;
- un único Engine ejecutándose;
- una única respuesta del LLM por ejecución;
- una única actualización del proyecto por Stage.

---

# 9.5 REGLAS PARA LOS ENGINES

Todos los Engines deberán.

- recibir datos;
- procesar datos;
- devolver EngineResult.

Nunca deberán.

- llamar directamente a otro Engine;
- modificar el Pipeline;
- modificar el estado global.

---

# 9.6 RESPONSABILIDAD DEL PIPELINE

El Pipeline Engine será el único componente autorizado para.

- decidir el siguiente Stage;
- detener la ejecución;
- reiniciar un Stage;
- finalizar un proyecto.

Todos los demás componentes actuarán únicamente bajo su coordinación.

---

# 9.7 PRINCIPIO DE DESACOPLAMIENTO

Cada Engine podrá evolucionar independientemente.

Siempre que conserve.

- su interfaz pública;
- EngineResult;
- contrato de entrada.

El Runtime continuará funcionando sin modificaciones.

---

# CHECKLIST

Antes de considerar operativo el Runtime.

□ El flujo completo está definido.

□ Todos los Engines tienen responsabilidad única.

□ Existe un único coordinador.

□ Los objetos de intercambio están definidos.

□ El orden de ejecución es único.

---

# CONCLUSIÓN

La Runtime Architecture establece un flujo único, simple y completamente desacoplado para la ejecución de proyectos.

Gracias a esta arquitectura, cada Engine puede desarrollarse, probarse y mantenerse de forma independiente mientras el Pipeline Engine conserva el control absoluto de la ejecución.

---

**FIN DE LA PARTE 9/10**
# RESUMEN OPERATIVO

---

# 10.1 PROPÓSITO

Este capítulo resume las reglas operativas que deberán guiar la implementación del Runtime de CIPS durante el Release 0.3.

Su objetivo consiste en dejar una referencia breve y directa para comenzar la programación de los Engines.

---

# 10.2 REGLA PRINCIPAL

El Pipeline Engine será el único orquestador del Runtime.

Todos los demás Engines serán componentes especializados que reciben datos, procesan y devuelven un EngineResult.

---

# 10.3 FLUJO OFICIAL

```text
Project

↓

Knowledge Engine

↓

Context Engine

↓

Prompt Builder

↓

LLM

↓

Validator Engine

↓

Memory Engine

↓

Pipeline Engine