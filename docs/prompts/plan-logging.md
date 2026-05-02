Debemos definir una estrategia de lectura de logs para todo el codebase de este programa.
Actualmente solo existe la implementación de logging para los archivos app.py (db_tool/tui/app.py), main_menu (db_tool/tui/screens/main_menu.py) y progress (db_tool/tui/screens/progress.py) pero no para el resto del codigo.
Tampoco existe un mecanismo sencillo de lectura de logs para el usuario. Actualmente se lee del archivo /tmp/db-tool.log lo cual es un poco engorroso para el usuario. Deberíamos crear una sección en la interfaz de usuario para mostrar los logs de manera más accesible y amigable.

Me gustaría algo como poder ejecutar tui --debug y que esto abra una nueva terminar con los logs directamente (hacer tail -f /tmp/db-tool.log) o algo similar. 
También podríamos crear una sección en la interfaz de usuario donde se muestren los logs de manera más accesible, con opciones para filtrar por nivel de log (info, warning, error).

Dame opciones y hacemos un plan final de acción para implementar esto.
