# Plan: Vista de gestión de conexiones en la TUI

## Context
Actualmente la TUI no tiene pantalla para gestionar el `connections.yaml`. Los usuarios deben editar el YAML a mano o usar los subcomandos CLI (`db-tool config add|remove|list`). La idea es agregar una pantalla completa en la TUI que permita listar, agregar, editar y eliminar perfiles de conexión, respetando las guardas de producción ya existentes.

---

## Archivos a crear

### `db_tool/tui/screens/connection_management.py`
Pantalla principal con la lista de perfiles. Muestra cada conexión con botones Edit / Delete por fila. Botón "Add new" en la parte inferior.

- Usa el widget existente `ConnectionCard` (`db_tool/tui/widgets/connection_card.py`) para render de cada perfil.
- Llama a `self._loader.load_profiles()` en `on_mount`.
- Para Delete: llama `guard_connection_mutation(profile)` → si falla, `self.notify(error, severity="error")`. Si pasa, llama `self._loader.remove_profile(alias)` y recarga la lista.
- Para Edit / Add: hace `push_screen(ConnectionFormScreen(...), callback)`.

### `db_tool/tui/screens/connection_form.py`
Pantalla de formulario reutilizable para Add y Edit.

- Recibe `profile: ConnectionProfile | None` (None = modo Add).
- Campos:
  - `alias` (Input, deshabilitado en modo Edit)
  - `environment` (Select con opciones: production / stage / dev / local)
  - `type` (Select con opciones: mongodb / bigquery / mysql)
  - `connection_string` (Input, tipo password)
  - `database_name` (Input)
  - `blacklist` (TextArea, una regex por línea)
- En modo Add: `loader.add_profile(profile)`.
- En modo Edit: `loader.update_profile(alias, profile)`.
- Producción bloqueada: si el perfil es production, muestra banner rojo y deshabilita el botón Save (Edit) o muestra advertencia al crear uno nuevo.
- Llama `guard_connection_mutation()` antes de guardar en modo Edit por si acaso.

---

## Archivos a modificar

### `db_tool/tui/screens/main_menu.py`
- Agregar botón "Connections" en `compose()` usando `self._btn("connections", "tui.main_menu.button.connections", "primary")`.
- En `on_button_pressed()`: push `ConnectionManagementScreen(self._loader, self._settings)`.

### `db_tool/i18n/translations/en.json` y `es.json`
Agregar todas las keys nuevas bajo el namespace `tui.connections.*`:

```
tui.main_menu.button.connections
tui.connections.title
tui.connections.no_profiles
tui.connections.button.add
tui.connections.button.edit
tui.connections.button.delete
tui.connections.button.save
tui.connections.button.cancel
tui.connections.label.alias
tui.connections.label.environment
tui.connections.label.type
tui.connections.label.connection_string
tui.connections.label.database_name
tui.connections.label.blacklist
tui.connections.form.title_add
tui.connections.form.title_edit
tui.connections.error.production_protected
tui.connections.success.added
tui.connections.success.updated
tui.connections.success.deleted
tui.connections.warning.production_create
```

### `docs/architecture.md`
Agregar sección documentando las dos nuevas pantallas y su flujo.

---

## Flujo de navegación

```
MainMenuScreen
  └─[Connections]─► ConnectionManagementScreen
                       ├─[Add]────► ConnectionFormScreen(profile=None)
                       │               └─[Save]─► add_profile() → dismiss → reload list
                       ├─[Edit]───► ConnectionFormScreen(profile=existing)
                       │               └─[Save]─► update_profile() → dismiss → reload list
                       └─[Delete]──► guard_connection_mutation() → remove_profile() → reload list
```

---

## Tests a agregar

### `tests/unit/tui/test_connection_form.py`
- Test que en modo Add con alias duplicado muestra error (mock loader).
- Test que en modo Edit con perfil production no permite guardar.
- Test que blacklist se parsea correctamente (split por líneas, strip, filtrar vacíos).

### `tests/unit/tui/test_connection_management.py`
- Test que delete de production muestra error y no llama `remove_profile`.
- Test que delete de non-production llama `remove_profile`.

---

## Verificación
1. `./run.sh` → TUI → botón "Connections" aparece en menú principal.
2. Agregar una conexión local, verificar que aparece en la lista y en `connections.yaml`.
3. Editar la conexión, verificar que se actualiza.
4. Eliminarla, verificar que desaparece.
5. Intentar editar/borrar una conexión production → debe mostrar error y no persistir cambio.
6. `pytest tests/unit/tui/` → todos pasan.
