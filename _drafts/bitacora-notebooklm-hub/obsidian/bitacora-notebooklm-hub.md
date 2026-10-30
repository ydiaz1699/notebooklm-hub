---
tipo: bitacora
proyecto: notebooklm-hub
repo: ydiaz1699/notebooklm-hub
rama: main
commit: e5e9683
gitleaks: sin-filtraciones
tags: [bitacora, git, seguridad, gitleaks]
---

# Bitácora técnica: NotebookLM Hub

> [!card] Proyecto <span class="badge ok">Publicado en GitHub</span>
> **Repositorio:** `ydiaz1699/notebooklm-hub`
> **Rama:** `main`
> **Último commit:** `e5e9683`
> **Auditoría Gitleaks:** Sin filtraciones detectadas.
> **Estado Git:** Working tree clean.
> <small>Registro de los trabajos realizados durante esta conversación.</small>

## 1. Objetivo del trabajo

Incorporar el proyecto NotebookLM al repositorio `notebooklm-hub`, conservando sus archivos de desarrollo y protegiendo las credenciales.

1. Incorporación del proyecto NotebookLM.
2. Protección de archivos sensibles.
3. Publicación y sincronización con GitHub.
4. Auditoría de seguridad del historial Git.

## 2. Primer problema: archivo `auth.json`

> [!danger] Archivo sensible
> `_drafts/notebooklm/auth.json` contiene datos de autenticación y no debía publicarse.
> Git lo seguía mostrando como `?? _drafts/notebooklm/auth.json`.

**Solución**

```bash
git rm --cached -- _drafts/notebooklm/auth.json      # lo saca del índice, lo conserva en disco
echo '/_drafts/notebooklm/auth.json' >> .gitignore
git check-ignore -v _drafts/notebooklm/auth.json
```

```text
.gitignore:46:/_drafts/notebooklm/auth.json
```

> [!success] Problema solucionado
> El archivo quedó excluido de Git y sigue disponible localmente.

## 3. Segundo problema: protección insuficiente de credenciales

Reglas que ya tenía el `.gitignore` raíz:

```gitignore
# Additional local secrets
.env.*
!.env.example
!.env.sample
secrets/
*.pem
*.key
*.p12
*.pfx
*_credentials.json
credentials.json
secrets.json
token.json
```

Regla añadida:

```gitignore
/_drafts/notebooklm/auth.json
```

## 4. Tercer problema: ¿Git rastreaba secretos?

```bash
# Archivos sensibles rastreados
git ls-files | grep -Ei '(^|/)(auth\.json|credentials?\.json|secrets?\.json|token\.json|cookies?\.json|\.env)(\.|$)'
# Claves privadas
git ls-files | grep -Ei '\.(pem|key|p12|pfx)$'
# auth.json concreto
git ls-files _drafts/notebooklm/auth.json
```

> [!info] Resultado
> Sin coincidencias en las tres comprobaciones. Git no rastreaba archivos con esos nombres o patrones.

## 5. Cuarto trabajo: incorporación del proyecto NotebookLM

Se añadió el proyecto completo en `_drafts/notebooklm/`: `.github` (workflows, Dependabot), `docs`, `scripts`, `src`, `tests`, `desktop-extension`, configuración, documentación y licencia.

```bash
git commit -m "Add notebooklm draft project"
#  [main 9336197] 366 files changed, 106638 insertions(+)
git push origin main
#  848b4ef..9336197  main -> main
```

> [!success] Publicación exitosa

## 6. Quinto problema: reglas en el `.gitignore` interno

```bash
git diff -- _drafts/notebooklm/.gitignore
```

Reglas añadidas a `_drafts/notebooklm/.gitignore`:

```gitignore
# NotebookLM authentication secrets
/_drafts/notebooklm/auth.json
/_drafts/notebooklm/*auth*.json
/_drafts/notebooklm/*token*
/_drafts/notebooklm/cookies*.json
```

> [!warning] Observación técnica
> Un `.gitignore` interpreta sus patrones **respecto a su propia carpeta**. Dentro de `_drafts/notebooklm/`, el prefijo `/_drafts/notebooklm/` apunta a `_drafts/notebooklm/_drafts/notebooklm/`, que no existe, así que estas reglas **no tienen efecto**. La protección real de `auth.json` viene del `.gitignore` raíz. Pendiente simplificarlas (ver §14).

## 7. Segundo commit y publicación

```bash
git add _drafts/notebooklm/.gitignore
git commit -m "Update draft project gitignore"
#  [main e5e9683] 1 file changed, 7 insertions(+)
git push origin main
#  9336197..e5e9683  main -> main
```

## 8. Sexto trabajo: verificación final de Git

```bash
git status
```

```text
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

```bash
git check-ignore -v _drafts/notebooklm/auth.json
#  .gitignore:46:/_drafts/notebooklm/auth.json
```

## 9. Séptimo problema: Gitleaks no estaba instalado

```text
bash: gitleaks: command not found
```

No era un fallo del repo: Gitleaks no estaba instalado en Windows.

```bash
winget install Gitleaks.Gitleaks
```

## 10. Octavo trabajo: auditoría con Gitleaks

```bash
gitleaks git . --redact
```

```text
INF 12 commits scanned.
INF scanned ~4233366 bytes (4.23 MB) in 838ms
INF no leaks found
```

<div class="stat-card">
  <div class="stat-head"><span>Auditoría Gitleaks</span><span class="badge ok">Superada</span></div>
  <div class="stat-hero">0 filtraciones detectadas</div>
  <div class="stat-grid">
    <div><b>12</b><span>Commits examinados</span></div>
    <div><b>4.23 MB</b><span>Datos analizados</span></div>
    <div><b>838 ms</b><span>Tiempo de análisis</span></div>
    <div><b class="ok-text">0</b><span>Secretos detectados</span></div>
  </div>
</div>

> [!note] Alcance
> Gitleaks no encontró nada que coincida con sus patrones. Eso no garantiza que no exista alguna credencial que sus reglas no reconozcan.

## 11. Resumen de cambios

| Elemento | Acción |
| --- | --- |
| `_drafts/notebooklm/` | Incorporado al repositorio |
| `auth.json` | Excluido de Git |
| `.gitignore` raíz | Modificado |
| `.gitignore` interno | Modificado |
| Archivos de credenciales | Verificados |
| Claves privadas | Verificadas |
| Git | Sincronizado |
| Gitleaks | Instalado y ejecutado |

## 12. Historial de commits

| Commit | Descripción |
| --- | --- |
| `9336197` | Add notebooklm draft project |
| `e5e9683` | Update draft project gitignore |

[Abrir notebooklm-hub en GitHub](https://github.com/ydiaz1699/notebooklm-hub)

## 13. Rutina de seguridad antes de publicar

```bash
git status                                                          # 1. estado
git ls-files | grep -Ei 'auth\.json|credentials\.json|secrets\.json|token\.json'   # 2. sensibles rastreados
git check-ignore -v _drafts/notebooklm/auth.json                    # 3. ignorados
git ls-files | grep -Ei '\.(pem|key|p12|pfx)$'                      # 4. claves privadas
gitleaks git . --redact                                             # 5. historial
git add .                                                           # 6. añadir (¡revisar antes!)
git diff --cached --name-only                                       # 7. qué se publicará
git commit -m "Describe your changes"                               # 8. commit
git push origin main                                                # 9. publicar
git status                                                          # 10. sincronización
```

> [!warning] Antes de `git add .`
> Revisa qué vas a incorporar. Las comprobaciones por nombre no detectan secretos dentro de código, documentación o configuración.

## 14. Recomendaciones pendientes

- [ ] Corregir los patrones del `.gitignore` interno para que funcionen desde su carpeta (`auth.json`, `*auth*.json`, `*token*`, `cookies*.json` sin prefijo).
- [ ] Automatizar Gitleaks en GitHub Actions.
- [ ] Revisar los workflows publicados: uso de secretos y permisos mínimos.
- [ ] Verificar el historial remoto por si `auth.json` se publicó antes, y rotar cualquier credencial expuesta.

## Conclusión

> [!success] Trabajo completado
> Proyecto NotebookLM incorporado, `auth.json` excluido, reglas de exclusión ampliadas, dos commits publicados y auditoría Gitleaks sin filtraciones. Repositorio sincronizado y limpio.
