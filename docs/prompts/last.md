En la última iteración estabamos arreglando el problema que al iniciar una tarea (post seleccion y configuración de copiado) y darle al botón "Iniciar" la aplicación quedaba congelada y no respondía (tampoco empezaba el proceso). Tu ultimo comentario fue:


Encontré la causa raíz. call_from_thread en Textual 8.x bloquea el worker thread con future.result() hasta que el event loop procese el callback. Si ese callback intenta actualizar widgets que aún no están montados (la pantalla no terminó de montar antes de que el thread empezara), Textual puede entrar en un estado inconsistente.

La solución correcta para Textual 8.x es usar @work(thread=True) dentro del ProgressScreen y arrancar la operación desde on_mount, que garantiza que los widgets ya están listos. Voy a reestructurar el flujo:

¿Puedes continuar con eso?