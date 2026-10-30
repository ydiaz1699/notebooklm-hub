# Bitácora técnica: NotebookLM Hub

<aside>
📁 **Proyecto** · ✅ Publicado en GitHub

**Repositorio:** `ydiaz1699/notebooklm-hub`
**Rama:** `main`
**Último commit:** `e5e9683`
**Auditoría Gitleaks:** Sin filtraciones detectadas.
**Estado Git:** Working tree clean.

*Registro de los trabajos realizados durante esta conversación.*
</aside>

## 1. Objetivo del trabajo

Incorporar el proyecto NotebookLM al repositorio `notebooklm-hub`, conservando sus archivos de desarrollo y protegiendo las credenciales.

1. Incorporación del proyecto NotebookLM.
2. Protección de archivos sensibles.
3. Publicación y sincronización con GitHub.
4. Auditoría de seguridad del historial Git.

## 2. Primer problema: archivo `auth.json`

<aside>
🚨 `_drafts/notebooklm/auth.json` contiene datos de autenticación y no debía publicarse. Git lo seguía mostrando como `?? _drafts/notebooklm/auth.json`.
</aside>

**Solución**

```bash
git rm --cached -- _drafts/notebooklm/auth.json
echo '/_drafts/notebooklm/auth.json' >> .gitignore
git check-ignore -v _drafts/notebooklm/auth.json
```

```
.gitignore:46:/_drafts/notebooklm/auth.json
```

<aside>
✅ **Problema solucionado.** El archivo quedó excluido de Git y sigue disponible localmente.
</aside>

## 3. Segundo problema: protección insuficiente de credenciales

Reglas que ya tenía el `.gitignore` raíz:

```
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

Regla añadida: `/_drafts/notebooklm/auth.json`

## 4. Tercer problema: ¿Git rastreaba secretos?

```bash
git ls-files | grep -Ei '(^|/)(auth\.json|credentials?\.json|secrets?\.json|token\.json|cookies?\.json|\.env)(\.|$)'
git ls-files | grep -Ei '\.(pem|key|p12|pfx)$'
git ls-files _drafts/notebooklm/auth.json
```

<aside>
ℹ️ Sin coincidencias en las tres comprobaciones.
</aside>

## 5. Cuarto trabajo: incorporación del proyecto NotebookLM

Se añadió en `_drafts/notebooklm/`: `.github`, `docs`, `scripts`, `src`, `tests`, `desktop-extension`, configuración, documentación y licencia.

```bash
git commit -m "Add notebooklm draft project"   # [main 9336197] 366 files changed, 106638 insertions(+)
git push origin main                           # 848b4ef..9336197  main -> main
```

<aside>
✅ **Publicación exitosa**
</aside>

## 6. Quinto problema: reglas en el `.gitignore` interno

```
# NotebookLM authentication secrets
/_drafts/notebooklm/auth.json
/_drafts/notebooklm/*auth*.json
/_drafts/notebooklm/*token*
/_drafts/notebooklm/cookies*.json
```

<aside>
⚠️ Un `.gitignore` interpreta sus patrones respecto a su propia carpeta. Dentro de `_drafts/notebooklm/`, el prefijo `/_drafts/notebooklm/` no apunta a nada, así que estas reglas **no tienen efecto**. La protección real viene del `.gitignore` raíz.
</aside>

## 7. Segundo commit y publicación

```bash
git add _drafts/notebooklm/.gitignore
git commit -m "Update draft project gitignore"   # [main e5e9683] 1 file changed, 7 insertions(+)
git push origin main                             # 9336197..e5e9683  main -> main
```

## 8. Sexto trabajo: verificación final de Git

```
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

## 9. Séptimo problema: Gitleaks no estaba instalado

`bash: gitleaks: command not found` → no era un fallo del repo, faltaba el programa en Windows.

```bash
winget install Gitleaks.Gitleaks
```

## 10. Octavo trabajo: auditoría con Gitleaks

```bash
gitleaks git . --redact
```

```
INF 12 commits scanned.
INF scanned ~4233366 bytes (4.23 MB) in 838ms
INF no leaks found
```

<aside>
🛡️ **Auditoría Gitleaks** · ✅ Superada

### 0 filtraciones detectadas

**12** — Commits examinados
**4.23 MB** — Datos analizados
**838 ms** — Tiempo de análisis
**0** — Secretos detectados
</aside>

> Gitleaks no encontró nada que coincida con sus patrones; no garantiza que no exista una credencial que sus reglas no reconozcan.

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
git status
git ls-files | grep -Ei 'auth\.json|credentials\.json|secrets\.json|token\.json'
git check-ignore -v _drafts/notebooklm/auth.json
git ls-files | grep -Ei '\.(pem|key|p12|pfx)$'
gitleaks git . --redact
git add .                        # revisar antes
git diff --cached --name-only
git commit -m "Describe your changes"
git push origin main
git status
```

<aside>
⚠️ Antes de `git add .` revisa qué incorporas: las comprobaciones por nombre no detectan secretos dentro de código o configuración.
</aside>

## 14. Recomendaciones pendientes

- [ ] Corregir los patrones del `.gitignore` interno (sin prefijo `/_drafts/notebooklm/`).
- [ ] Automatizar Gitleaks en GitHub Actions.
- [ ] Revisar los workflows publicados: secretos y permisos mínimos.
- [ ] Verificar el historial remoto por si `auth.json` se publicó antes, y rotar credenciales expuestas.

## Conclusión

<aside>
✅ Proyecto incorporado, `auth.json` excluido, reglas ampliadas, dos commits publicados y Gitleaks sin filtraciones. Repositorio sincronizado y limpio.
</aside>
