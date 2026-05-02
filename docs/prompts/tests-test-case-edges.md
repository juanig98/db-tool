Lo que falta para cubrir todos los casos de prueba

  1. Datos para probar ofuscación correctamente

  Las reglas fijas detectan campos por nombre/valor. Necesitás colecciones con:

  - Campos anidados con PII: { "contact": { "email": "...", "phone": "..." } } — para verificar que el engine traversa nested docs
  - Arrays de objetos con PII: { "recipients": [{ "email": "..." }, ...] } — caso frecuente en mensajes/notificaciones
  - Campos que parecen PII pero no lo son: { "bot_email_template": "...", "phone_format": "E.164" } — para verificar que las reglas fijas no disparan falsos positivos
  - El mismo valor real en múltiples colecciones: el mismo email en users, admins y feedback.contact_email — para verificar que MappingStore produce el mismo valor fake en todas (consistencia referencial)

  2. Datos para probar --pattern (regex de selección)

  El flag --pattern filtra colecciones por nombre. Necesitás colecciones nombradas con prefijos/sufijos distinguibles:

  - mydblocal_client1_orders, mydblocal_client2_orders — para probar mydblocal_client1_.*
  - tmp_import_2024, tmp_import_2025 — para probar tmp_.*
  - archive_conversations_2023 — para probar que quedan excluidas con el patrón correcto

  3. Datos para probar sync (incremental)

  sync copia solo docs nuevos/modificados desde el último run. Necesitás:

  - Colecciones donde los updated_at estén distribuidos en el tiempo (últimos 24h, última semana, último mes, hace 2 años) — para poder verificar qué se sincroniza y qué no según la ventana temporal
  - Al menos una colección con docs sin updated_at — para testear el fallback del sync

  4. Datos para probar delete --pattern con --dry-run

  Colecciones con nombres que matcheen un patrón borrable obvio y otras que no, para verificar que el dry-run lista exactamente lo que borraría sin tocar nada.

  5. Edge cases de documentos

  - Colección con un solo documento — edge case de copy/sync
  - Colección vacía — para verificar que no rompe ninguna operación
  - Documentos con campos null, "" y ausentes en los mismos campos — para que la ofuscación no explote con tipos inesperados
  - Documentos muy grandes (>1MB): un campo content con texto largo faker — para testear batching

  6. Datos que simulan el entorno production bloqueado

  Esto no va en los datos sino en connections.yaml: necesitás un perfil environment: production apuntando a mongo-source y un perfil environment: stage apuntando a mongo-target. Así podés verificar que escribir en production es
   rechazado por validator.py y que las operaciones hacia stage funcionan.

  ---
  Resumen de lo que agregaría al prompt

  7. Agregar en mydblocal_business:
     - notifications (docs con arrays de recipients con email/phone)
     - Una colección vacía: empty_placeholder
     - Una colección con 1 solo doc: singleton_config

  8. Distribuir updated_at en access_logs y conversations
     en 4 bandas temporales: últimas 24h, última semana,
     último mes, hace >1 año.

  9. Colecciones con naming pattern distinguible:
     mydblocal_client1_orders, mydblocal_client2_orders,
     tmp_import_2024, archive_conversations_2023

  10. En al menos 3 colecciones distintas, reusar los
      mismos emails de `users` como valor en otros campos
      (ej: feedback.contact_email, messages.metadata.cc)
      para testear MappingStore.

  11. Instrucciones para connections.yaml:
      - mongo-source → environment: production
      - mongo-target → environment: stage

  El punto más crítico es el 6 (connections.yaml) — sin eso no podés probar la invariante más importante del sistema.