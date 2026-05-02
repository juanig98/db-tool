Me quedan pocos tokens. Generame un prompt para solicitar crear datos de pruebas a otro LLM. 
Quiero crear dos contenedores de docker para probar las conexiones, copiado, ofuscado, borrado, etc.
1. El primer contenedor debe tener una base MongoDB con 3 bases:
  1.1. La primer base es de datos de negocio:
    1.1.1. Clientes: del negocio. Al menos 5 registros.
    1.1.2: Administradores: del negocio. Debe existir al menos 30 SUPERADMIN y luego 10 por cada cliente (con rol ADMIN). 
    1.1.3. Bots: utilizados por el cliente. Cada cliente debería tener al menos 3 bots (uno para cada entorno: productivo, stage y testing)
    1.1.4. BotsSkills: habilidades de los bots. Al menos 30 registros por cada Bot. Los bots asociados a entornos testing y stage pueden tener más habilidades que las del entorno productivo (simulando que están en desarrollo).
    1.1.5. Usuarios: serán los clientes de nuestros clientes. Al menos 2 clientes con más de 10000 registros. El resto de clientes puede tener asociado entre 2000 y 8000 registros. Idealmente con datos realistas como nombres, apellidos, correos electrónicos, etc.
    1.1.6. Variables de usuarios (al menos 10000 registros)
    1.1.7. Conversaciones: de los usuarios con los bots. Al menos 10000 registros, con datos realistas como fecha, hora, duración de la conversación, etc.
    1.1.8. Mensajes: de las conversaciones. Al menos 30000 registros, con datos realistas como fecha, hora, contenido del mensaje, etc.
    1.1.9. Feedback: de los usuarios sobre las conversaciones. Al menos 5000 registros, con datos realistas como fecha, hora, calificación, comentarios, etc.
    1.1.10. Otras tablas en cada una de las bases, que sean diferentes en cada una de ellas, con al menos 3000 registros cada una. (puedes darte el lujo de determinar el tipo de negocio y las tablas correspondientes)
  1.2. La segunda base es de analitica:
    1.2.1. Logs de acceso (al menos 10000 registros)
    1.2.2. Logs de errores (al menos 10000 registros)
    1.2.3. Logs de transacciones (al menos 10000 registros)
    1.2.4. Otras tablas relacionadas con analítica, con al menos 3000 registros cada una.
2. El segundo contenedor debe tener una base MongoDB vacía, que se utilizará para probar las operaciones de copia, ofuscación, borrado, etc.



Prompt: Generación de entorno Docker con datos de prueba para db-tool

  Objetivo

  Generá un script Python completo (generate_test_data.py) y un docker-compose.yml que levanten dos contenedores MongoDB y poblen el primero con datos de prueba realistas para testear operaciones de copia, ofuscación,
  sincronización y borrado.

  ---
  docker-compose.yml

  Dos servicios:

  - mongo-source — puerto 27017 — contendrá los datos de prueba
  - mongo-target — puerto 27018 — vacío, destino de operaciones

  Ambos sin autenticación (entorno local de testing).

  ---
  Script de generación (generate_test_data.py)

  Conectarse a mongo-source y crear dos bases de datos:

  ---
  Base 1: mydblocal_business (base de negocio — SaaS de chatbots)

  El negocio es una plataforma SaaS que vende bots de atención al cliente a empresas (clientes). Los bots conversan con los usuarios finales de esas empresas.

  Colección clients — 5 registros

  Empresas cliente de la plataforma. Campos sugeridos: _id, name, industry (retail, fintech, salud, educación, logística), plan (basic/pro/enterprise), country, created_at, active.

  Colección admins — mínimo 130 registros

  - 30 con role: SUPERADMIN (no asociados a ningún cliente)
  - 10 por cada cliente con role: ADMIN y referencia client_id
  - Campos: _id, client_id (null para SUPERADMIN), role, name, email, password_hash (bcrypt simulado: string fijo tipo $2b$12$...), created_at, last_login

  Colección bots — 3 por cliente = 15 registros

  Un bot por entorno: production, stage, testing.
  Campos: _id, client_id, name, environment, language, created_at, active, model_version.

  Colección bot_skills — mínimo 30 por bot = 450+ registros

  Habilidades de cada bot. Los bots de testing y stage tienen entre 45 y 60 skills (en desarrollo); los de production tienen exactamente 30.
  Campos: _id, bot_id, client_id, name, description, intent, enabled, confidence_threshold, created_at, updated_at.

  Colección users — mínimo 36000 registros

  Usuarios finales de los clientes (los que hablan con los bots).
  - 2 clientes con más de 10000 usuarios cada uno
  - Los 3 clientes restantes con entre 2000 y 8000 usuarios cada uno
  - Datos realistas: _id, client_id, first_name, last_name, email, phone, country, city, birth_date, created_at, last_active, active
  - Usar la librería faker con locales variados (es_AR, es_MX, es_ES, pt_BR, en_US) según el país del cliente

  Colección user_variables — mínimo 10000 registros

  Variables de contexto por usuario (tipo clave-valor).
  Campos: _id, user_id, client_id, bot_id, key, value, updated_at.
  Keys ejemplo: preferred_language, subscription_tier, last_purchase_category, loyalty_points, onboarding_completed.

  Colección conversations — mínimo 10000 registros

  Campos: _id, user_id, bot_id, client_id, started_at, ended_at, duration_seconds, channel (web/whatsapp/telegram/sms), resolved, handoff_to_human.
  Fechas en los últimos 18 meses. Duración entre 30 y 900 segundos.

  Colección messages — mínimo 30000 registros

  Mensajes dentro de conversaciones (3 por conversación en promedio, con variación).
  Campos: _id, conversation_id, user_id, bot_id, client_id, sender (user/bot), content, timestamp, message_type (text/button/image/file).
  Contenido del mensaje: frases cortas realistas según el tipo de industria del cliente.

  Colección feedback — mínimo 5000 registros

  Feedback de usuarios al finalizar conversaciones.
  Campos: _id, conversation_id, user_id, bot_id, client_id, rating (1-5), comment, submitted_at.
  Distribución realista: mayoría de ratings 4-5, comentarios faker en español/inglés.

  Colecciones adicionales de negocio — al menos 3000 registros cada una

  Dado que el negocio es una plataforma de chatbots SaaS, agregá estas colecciones:

  - billing_invoices — facturas emitidas a clientes. Campos: _id, client_id, amount, currency, status (paid/pending/overdue), issued_at, due_at, paid_at.
  - webhook_events — eventos enviados a sistemas externos de los clientes. Campos: _id, client_id, bot_id, event_type, payload_summary, status (delivered/failed/retrying), sent_at, attempts.
  - knowledge_base_articles — artículos de la base de conocimiento usada por los bots. Campos: _id, client_id, bot_id, title, content (texto largo faker), tags, language, created_at, updated_at, active.

  ---
  Base 2: mydblocal_analytics (analítica)

  Colección access_logs — mínimo 10000 registros

  Campos: _id, timestamp, user_id, client_id, bot_id, endpoint, method, status_code, response_time_ms, ip_address, user_agent.

  Colección error_logs — mínimo 10000 registros

  Campos: _id, timestamp, client_id, bot_id, error_code, error_message, stack_trace_summary, severity (warning/error/critical), resolved, resolved_at.

  Colección transaction_logs — mínimo 10000 registros

  Campos: _id, timestamp, client_id, user_id, transaction_type (message_sent/skill_triggered/handoff/session_start/session_end), metadata, duration_ms.

  Colecciones adicionales de analítica — al menos 3000 registros cada una

  - daily_metrics — métricas agregadas por día/cliente/bot. Campos: _id, date, client_id, bot_id, total_conversations, total_messages, avg_rating, resolution_rate, handoff_rate.
  - funnel_events — eventos de embudo de conversión dentro de conversaciones. Campos: _id, timestamp, conversation_id, client_id, bot_id, step, completed, drop_off_reason.
  - ab_test_results — resultados de A/B tests de skills. Campos: _id, client_id, bot_id, test_name, variant, users_count, conversion_rate, avg_rating, started_at, ended_at.

  ---
  Requisitos del script

  - Usar pymongo y faker
  - Generar datos con referencias consistentes (user_id en mensajes debe existir en users, etc.)
  - Usar bulk_write o insert_many en batches de 500-1000 docs para performance
  - Mostrar progreso por colección: ✓ users: 36.420 docs inserted
  - Al finalizar, imprimir un resumen con conteos reales de cada colección
  - Manejo de errores: si el contenedor no está listo, reintentar con backoff

  Requisitos del docker-compose

  - Volumen nombrado para mongo-source para que los datos persistan entre reinicios
  - mongo-target sin volumen (efímero, simula destino limpio)
  - Healthcheck en ambos servicios
  - Instrucciones comentadas al inicio del archivo para ejecutar:
  docker compose up -d
  python generate_test_data.py