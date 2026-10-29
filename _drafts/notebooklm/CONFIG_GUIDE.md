# NotebookLM MCP Server - Guía de Configuración Centralizada

Esta carpeta contiene todo lo necesario para ejecutar el servidor MCP de NotebookLM de forma local, independiente y autocontenida:

* **Repositorio oficial:** https://github.com/jacob-bd/notebooklm-mcp
* **Entorno virtual propio:** `.venv/`
* **Ejecutable MCP:** `.venv/Scripts/notebooklm-mcp.exe`
* **Ejecutable Auth:** `.venv/Scripts/notebooklm-mcp-auth.exe`
* **Credenciales de sesión:** `auth.json`

---

## 1. Configuración en cualquier IDE o LLM

### En VS Code / OpenCode
Archivo: `%APPDATA%\Code\User\mcp.json`
```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "C:\\Users\\Alex\\mcp-servers\\notebooklm\\.venv\\Scripts\\notebooklm-mcp.exe",
      "args": []
    }
  }
}
```

### En Claude Desktop
Archivo: `%APPDATA%\Claude\claude_desktop_config.json`
```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "C:\\Users\\Alex\\mcp-servers\\notebooklm\\.venv\\Scripts\\notebooklm-mcp.exe",
      "args": []
    }
  }
}
```

### En Cursor / Windsurf / Cline / Roo Code
En la sección de MCP Servers del asistente:
* **Name:** `notebooklm`
* **Type:** `command` (stdio)
* **Command:** `C:\Users\Alex\mcp-servers\notebooklm\.venv\Scripts\notebooklm-mcp.exe`
* **Args:** `[]`

### En Antigravity
Archivo: `%USERPROFILE%\.gemini\config\mcp_config.json`
```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "C:\\Users\\Alex\\mcp-servers\\notebooklm\\.venv\\Scripts\\notebooklm-mcp.exe",
      "args": []
    }
  }
}
```

---

## 2. Cómo autenticarse o refrescar la sesión

Si la sesión expira o necesitas cambiar de cuenta, abre una terminal en esta carpeta y ejecuta:
```powershell
.\.venv\Scripts\notebooklm-mcp-auth.exe
```
O simplemente inicia sesión en tu navegador en `https://notebook.google.com`.
