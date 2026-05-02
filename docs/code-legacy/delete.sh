#!/bin/bash

# Script para borrar colecciones que empiecen con un prefix en Cosmos DB (MongoDB API)
# Requiere: mongo shell o mongosh instalado

# === CONFIGURACIÓN ===
CONNECTION_STRING="mongodb://localhost:27017/"
DATABASE_NAME="foo"
PREFIX="bar"

# === BORRADO ===
mongosh "$CONNECTION_STRING" --eval "
  use('$DATABASE_NAME');
  const cols = db.getCollectionNames().filter(c => c.startsWith('$PREFIX'));
  if (cols.length === 0) {
    print('No se encontraron colecciones con prefijo $PREFIX');
  } else {
    cols.forEach(col => {
      db.getCollection(col).drop();
      print('Borrada: ' + col);
    });
    print('Total borradas: ' + cols.length);
  }
"