# Transporte Android gRPC — detalle preservado

Conocimiento destilado de `teng-lin/notebooklm-py` (`docs/android/`) e `ishandutta2007`,
verificado contra la fuente el 2026-10-04. Es el transporte **más difícil de reconstruir**: se
recupera por captura de tráfico + decompilación del binario Flutter de la app. Se preserva aquí
para que `notebooklm-hub` pueda reimplementarlo aunque los originales desaparezcan.

> **No** se copia ningún `.proto`, captura ni body real de esos repos (contienen IDs de notebook,
> texto de fuentes e historial de chat). Esto es la **descripción del método**, no sus datos.

## Servicio y conexión

| Propiedad | Valor |
|---|---|
| Host | `notebooklm-pa.googleapis.com:443` |
| Servicio gRPC | `google.internal.labs.tailwind.orchestration.v1.LabsTailwindOrchestrationService` |
| Path | `/<service>/<Method>` |
| Transporte | HTTP/2 `POST`, `content-type: application/grpc` |
| Framing | 1 mensaje protobuf length-prefixed por body (envelope gRPC de 5 bytes) |
| Auth | header **OAuth bearer** (acuñado por master-token, sin navegador) |
| Éxito | HTTP 200 + trailer `grpc-status: 0` |

La mayoría de métodos son **unarios**. Dos son **server-streaming**:
`GenerateFreeFormStreamed` y `StreamLiveSession`.

## Superficie de métodos

- La app (snapshot `1.46.7`) compila ~**49 métodos en 4 servicios gRPC**; muchos existen pero no
  están cableados a ninguna pantalla móvil → útiles vía gRPC directo aunque la UI no los use.
- Un snapshot posterior (`1.55.10`) subió a ~53 métodos (delta por versión).
- El esquema completo recuperado (por decompilación del binario Flutter con un `blutter` portado a
  Dart) rondaba **326 mensajes / 879 campos** con nombres, tags, tipos y cardinalidad reales.

## Cómo se reconstruye (procedimiento, no datos)

1. **Captura de tráfico** de la app Android (MITM del canal gRPC) → bodies `.pb` length-prefixed.
2. **Decodificación de wire-format** (field `#N` + wire type) para las RPC ejercitadas por la UI.
3. **Decompilación del binario Flutter AOT** (`libNotebookLM_...flutter_artifacts.so` dentro del
   `split_config.arm64_v8a.apk`) con `blutter` para recuperar **nombres de campo** reales.
4. **Enumeración de métodos** extrayendo strings de method-path del `.so`.
5. **Validación en vivo** con probes bearer/gRPC directos (lecturas sobre notebooks reales;
   mutaciones **solo** sobre notebooks desechables, limpiados después).

> Para `notebooklm-hub`: no necesitamos re-capturar desde cero si partimos del esquema ya recuperado
> por los proyectos de referencia (MIT). Si desaparecen, este documento define **qué** recuperar y
> **cómo**, y qué métodos/mensajes buscar.

## Enganche con la arquitectura

- Implementar `core/transport/android_grpc.py` conforme al contrato `Transport` (`core/transport/base.py`).
- El esquema protobuf va en `core/transport/_proto/` (generado), nunca mezclado con las tools.
- `core/auth/` provee el bearer (master-token). gRPC es el **nivel 1** de `cascade.py`.

## Riesgos / notas

- Es reverse-engineering de la app móvil: Google puede cambiarlo entre versiones (de ahí el delta
  `1.46.7` → `1.55.10`). Por eso **nunca** es el único transporte: la cascada cae a web/browser.
- Las mutaciones destructivas deben ir detrás del `confirm`+preview del `_app/` (igual que las demás).
