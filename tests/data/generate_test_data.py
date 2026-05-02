#!/usr/bin/env python3
"""
Genera datos de prueba en mongo-source para testear db-tool.

Requisitos:
    pip install pymongo faker

Uso:
    docker compose up -d
    python generate_test_data.py

    # nombres de DB personalizados
    python generate_test_data.py --business-db foo_business --analytics-db foo_analytics

    # URI remota
    python generate_test_data.py --uri mongodb://user:pass@host:27017
"""

import argparse
import random
import time
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from faker import Faker
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

MONGO_SOURCE_URI = "mongodb://localhost:27017"
BATCH_SIZE = 500
MAX_RETRIES = 12
RETRY_BACKOFF_BASE = 2.0

fakers = {
    "es_AR": Faker("es_AR"),
    "es_MX": Faker("es_MX"),
    "es_ES": Faker("es_ES"),
    "pt_BR": Faker("pt_BR"),
    "en_US": Faker("en_US"),
}
faker = Faker()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _oid() -> ObjectId:
    return ObjectId()


def _dt(days_ago_max: int = 548, days_ago_min: int = 0) -> datetime:
    """Random datetime within the last `days_ago_max` days."""
    delta = random.randint(days_ago_min * 86400, days_ago_max * 86400)
    return datetime.now(tz=timezone.utc) - timedelta(seconds=delta)


def _bcrypt_placeholder() -> str:
    salt = faker.lexify("?" * 22, letters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789./")
    hashed = faker.lexify("?" * 31, letters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789./")
    return f"$2b$12${salt}{hashed}"


def bulk_insert(collection, docs: list, label: str) -> int:
    inserted = 0
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        collection.insert_many(batch, ordered=False)
        inserted += len(batch)
    print(f"  ✓ {label}: {inserted:,} docs inserted")
    return inserted


def wait_for_mongo(uri: str) -> MongoClient:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            print(f"  Connected to {uri}")
            return client
        except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"Could not connect to {uri} after {MAX_RETRIES} attempts") from exc
            wait = RETRY_BACKOFF_BASE ** attempt
            print(f"  [{attempt}/{MAX_RETRIES}] MongoDB not ready, retrying in {wait:.0f}s…")
            time.sleep(wait)


# ---------------------------------------------------------------------------
# Industry-aware short phrases for messages
# ---------------------------------------------------------------------------

INDUSTRY_PHRASES = {
    "retail": [
        "¿Cuál es el estado de mi pedido?",
        "Quiero devolver un producto.",
        "¿Tienen descuentos activos?",
        "No recibí mi compra.",
        "Cómo puedo rastrear mi envío?",
        "What's my order status?",
        "I want to return an item.",
    ],
    "fintech": [
        "¿Cuál es mi saldo disponible?",
        "Reportar una transacción desconocida.",
        "¿Cómo activo mi tarjeta?",
        "Necesito mi estado de cuenta.",
        "What is my account balance?",
        "I need to dispute a charge.",
    ],
    "salud": [
        "Quiero agendar una cita.",
        "¿Cuáles son los horarios de atención?",
        "Necesito renovar mi receta.",
        "¿Cómo obtengo mis resultados?",
        "I need to schedule an appointment.",
    ],
    "educación": [
        "¿Cuándo empiezan las clases?",
        "No puedo acceder al campus virtual.",
        "¿Cómo me inscribo al curso?",
        "Necesito mi certificado.",
        "When do classes start?",
    ],
    "logística": [
        "¿Dónde está mi paquete?",
        "Mi envío llegó dañado.",
        "¿Cómo programo un retiro?",
        "Necesito cambiar la dirección de entrega.",
        "Where is my package?",
        "My shipment is delayed.",
    ],
}

BOT_REPLY_PHRASES = [
    "Enseguida lo reviso para usted.",
    "Permítame un momento.",
    "Con gusto lo ayudo.",
    "He procesado su solicitud.",
    "¿Hay algo más en lo que pueda ayudarle?",
    "I'll look into that for you.",
    "Let me check that right away.",
    "Your request has been processed.",
    "Is there anything else I can help you with?",
]

SKILL_NAMES = [
    "order_status", "product_return", "track_shipment", "cancel_order",
    "account_balance", "dispute_transaction", "activate_card", "transfer_funds",
    "book_appointment", "prescription_renewal", "lab_results", "symptom_checker",
    "course_enrollment", "certificate_request", "campus_access", "exam_schedule",
    "package_tracking", "delivery_reschedule", "damage_report", "pickup_request",
    "billing_inquiry", "payment_method", "faq_general", "human_handoff",
    "greeting", "goodbye", "fallback", "escalation", "feedback_collection",
    "lead_capture",
]

VAR_KEYS = [
    "preferred_language", "subscription_tier", "last_purchase_category",
    "loyalty_points", "onboarding_completed", "preferred_channel",
    "notification_opt_in", "last_survey_score", "account_type", "region",
]


# ---------------------------------------------------------------------------
# enigma_business
# ---------------------------------------------------------------------------


def generate_business(db) -> dict:
    """Populate enigma_business. Returns references for analytics."""

    # -- clients ----------------------------------------------------------
    client_configs = [
        {"name": "RetailMax", "industry": "retail", "plan": "enterprise", "country": "AR", "locale": "es_AR"},
        {"name": "FinBot S.A.", "industry": "fintech", "plan": "pro", "country": "MX", "locale": "es_MX"},
        {"name": "SaludAI", "industry": "salud", "plan": "pro", "country": "ES", "locale": "es_ES"},
        {"name": "EduSmart", "industry": "educación", "plan": "basic", "country": "BR", "locale": "pt_BR"},
        {"name": "LogiTrack", "industry": "logística", "plan": "enterprise", "country": "US", "locale": "en_US"},
    ]
    client_user_counts = [12000, 10500, 5000, 3500, 2800]

    clients = []
    for cfg in client_configs:
        clients.append({
            "_id": _oid(),
            "name": cfg["name"],
            "industry": cfg["industry"],
            "plan": cfg["plan"],
            "country": cfg["country"],
            "created_at": _dt(days_ago_max=730, days_ago_min=365),
            "active": True,
            "_locale": cfg["locale"],
        })
    db.clients.drop()
    db.clients.insert_many([{k: v for k, v in c.items() if k != "_locale"} for c in clients])
    print(f"  ✓ clients: {len(clients):,} docs inserted")

    # -- admins -----------------------------------------------------------
    admins = []
    for _ in range(30):
        f = fakers["es_AR"]
        admins.append({
            "_id": _oid(),
            "client_id": None,
            "role": "SUPERADMIN",
            "name": f.name(),
            "email": f.unique.email(),
            "password_hash": _bcrypt_placeholder(),
            "created_at": _dt(730, 180),
            "last_login": _dt(30),
        })
    for client in clients:
        f = fakers[client["_locale"]]
        for _ in range(10):
            admins.append({
                "_id": _oid(),
                "client_id": client["_id"],
                "role": "ADMIN",
                "name": f.name(),
                "email": f.unique.email(),
                "password_hash": _bcrypt_placeholder(),
                "created_at": _dt(730, 90),
                "last_login": _dt(30),
            })
    db.admins.drop()
    bulk_insert(db.admins, admins, "admins")

    # -- bots -------------------------------------------------------------
    bots = []
    for client in clients:
        for env in ("production", "stage", "testing"):
            bots.append({
                "_id": _oid(),
                "client_id": client["_id"],
                "name": f"{client['name']}-{env}",
                "environment": env,
                "language": "es" if client["country"] != "US" else "en",
                "created_at": _dt(730, 90),
                "active": True,
                "model_version": random.choice(["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"]),
            })
    db.bots.drop()
    db.bots.insert_many(bots)
    print(f"  ✓ bots: {len(bots):,} docs inserted")

    # -- bot_skills -------------------------------------------------------
    skills_docs = []
    for bot in bots:
        count = 30 if bot["environment"] == "production" else random.randint(45, 60)
        skill_pool = random.sample(SKILL_NAMES * 5, k=count)
        for skill_name in skill_pool:
            created = _dt(365, 30)
            skills_docs.append({
                "_id": _oid(),
                "bot_id": bot["_id"],
                "client_id": bot["client_id"],
                "name": skill_name,
                "description": faker.sentence(nb_words=8),
                "intent": skill_name.replace("_", "-"),
                "enabled": random.random() > 0.1,
                "confidence_threshold": round(random.uniform(0.6, 0.95), 2),
                "created_at": created,
                "updated_at": created + timedelta(days=random.randint(0, 30)),
            })
    db.bot_skills.drop()
    bulk_insert(db.bot_skills, skills_docs, "bot_skills")

    # -- users ------------------------------------------------------------
    users = []
    user_id_by_client: dict[ObjectId, list[ObjectId]] = {}
    for client, count in zip(clients, client_user_counts):
        f = fakers[client["_locale"]]
        ids = []
        for _ in range(count):
            uid = _oid()
            ids.append(uid)
            users.append({
                "_id": uid,
                "client_id": client["_id"],
                "first_name": f.first_name(),
                "last_name": f.last_name(),
                "email": f.unique.email(),
                "phone": f.phone_number(),
                "country": client["country"],
                "city": f.city(),
                "birth_date": datetime.combine(faker.date_of_birth(minimum_age=18, maximum_age=65), datetime.min.time()).replace(tzinfo=timezone.utc),
                "created_at": _dt(548, 0),
                "last_active": _dt(30),
                "active": random.random() > 0.05,
            })
        user_id_by_client[client["_id"]] = ids
    db.users.drop()
    bulk_insert(db.users, users, "users")

    # -- user_variables ---------------------------------------------------
    bot_by_client: dict[ObjectId, list[ObjectId]] = {}
    for bot in bots:
        bot_by_client.setdefault(bot["client_id"], []).append(bot["_id"])

    uvar_docs = []
    all_user_ids = [u["_id"] for u in users]
    user_map = {u["_id"]: u for u in users}
    sample_users = random.sample(all_user_ids, min(10000, len(all_user_ids)))
    for uid in sample_users:
        user = user_map[uid]
        cid = user["client_id"]
        bid = random.choice(bot_by_client[cid])
        key = random.choice(VAR_KEYS)
        uvar_docs.append({
            "_id": _oid(),
            "user_id": uid,
            "client_id": cid,
            "bot_id": bid,
            "key": key,
            "value": str(faker.word() if key not in ("loyalty_points", "last_survey_score") else random.randint(0, 10000)),
            "updated_at": _dt(30),
        })
    db.user_variables.drop()
    bulk_insert(db.user_variables, uvar_docs, "user_variables")

    # -- conversations ----------------------------------------------------
    conv_docs = []
    channels = ["web", "whatsapp", "telegram", "sms"]
    for client in clients:
        c_users = user_id_by_client[client["_id"]]
        c_bots = bot_by_client[client["_id"]]
        count = max(2000, len(c_users) // 5)
        for _ in range(count):
            started = _dt(548, 0)
            duration = random.randint(30, 900)
            conv_docs.append({
                "_id": _oid(),
                "user_id": random.choice(c_users),
                "bot_id": random.choice(c_bots),
                "client_id": client["_id"],
                "started_at": started,
                "ended_at": started + timedelta(seconds=duration),
                "duration_seconds": duration,
                "channel": random.choice(channels),
                "resolved": random.random() > 0.25,
                "handoff_to_human": random.random() < 0.15,
            })
    db.conversations.drop()
    bulk_insert(db.conversations, conv_docs, "conversations")

    # -- messages ---------------------------------------------------------
    industry_by_client = {c["_id"]: c["industry"] for c in clients}
    msg_docs = []
    for conv in conv_docs:
        cid = conv["client_id"]
        industry = industry_by_client[cid]
        phrases = INDUSTRY_PHRASES.get(industry, ["Hello.", "Hola."])
        n_msgs = random.randint(2, 6)
        ts = conv["started_at"]
        for _ in range(n_msgs):
            ts = ts + timedelta(seconds=random.randint(5, 60))
            sender = random.choice(["user", "bot"])
            content = random.choice(phrases) if sender == "user" else random.choice(BOT_REPLY_PHRASES)
            msg_docs.append({
                "_id": _oid(),
                "conversation_id": conv["_id"],
                "user_id": conv["user_id"],
                "bot_id": conv["bot_id"],
                "client_id": cid,
                "sender": sender,
                "content": content,
                "timestamp": ts,
                "message_type": random.choices(
                    ["text", "button", "image", "file"],
                    weights=[70, 20, 7, 3],
                )[0],
            })
    db.messages.drop()
    bulk_insert(db.messages, msg_docs, "messages")

    # -- feedback ---------------------------------------------------------
    fb_docs = []
    conv_sample = random.sample(conv_docs, min(5000, len(conv_docs)))
    for conv in conv_sample:
        rating = random.choices([1, 2, 3, 4, 5], weights=[3, 5, 10, 35, 47])[0]
        lang = random.choice(["es", "en"])
        comment_faker = fakers["es_AR"] if lang == "es" else fakers["en_US"]
        fb_docs.append({
            "_id": _oid(),
            "conversation_id": conv["_id"],
            "user_id": conv["user_id"],
            "bot_id": conv["bot_id"],
            "client_id": conv["client_id"],
            "rating": rating,
            "comment": comment_faker.sentence(nb_words=random.randint(5, 20)) if random.random() > 0.3 else None,
            "submitted_at": conv["ended_at"] + timedelta(seconds=random.randint(5, 300)),
        })
    db.feedback.drop()
    bulk_insert(db.feedback, fb_docs, "feedback")

    # -- billing_invoices -------------------------------------------------
    invoice_statuses = ["paid", "pending", "overdue"]
    invoice_docs = []
    for client in clients:
        for _ in range(random.randint(600, 800)):
            issued = _dt(730, 30)
            due = issued + timedelta(days=30)
            status = random.choices(invoice_statuses, weights=[75, 15, 10])[0]
            invoice_docs.append({
                "_id": _oid(),
                "client_id": client["_id"],
                "amount": round(random.uniform(500, 15000), 2),
                "currency": "USD",
                "status": status,
                "issued_at": issued,
                "due_at": due,
                "paid_at": due - timedelta(days=random.randint(0, 5)) if status == "paid" else None,
            })
    db.billing_invoices.drop()
    bulk_insert(db.billing_invoices, invoice_docs, "billing_invoices")

    # -- webhook_events ---------------------------------------------------
    wh_statuses = ["delivered", "failed", "retrying"]
    wh_event_types = ["conversation.ended", "handoff.requested", "skill.triggered", "user.created", "feedback.submitted"]
    wh_docs = []
    for client in clients:
        c_bots = bot_by_client[client["_id"]]
        for _ in range(random.randint(600, 800)):
            wh_docs.append({
                "_id": _oid(),
                "client_id": client["_id"],
                "bot_id": random.choice(c_bots),
                "event_type": random.choice(wh_event_types),
                "payload_summary": faker.sentence(nb_words=6),
                "status": random.choices(wh_statuses, weights=[80, 10, 10])[0],
                "sent_at": _dt(180),
                "attempts": random.randint(1, 5),
            })
    db.webhook_events.drop()
    bulk_insert(db.webhook_events, wh_docs, "webhook_events")

    # -- knowledge_base_articles ------------------------------------------
    kb_docs = []
    langs = ["es", "en", "pt"]
    for client in clients:
        c_bots = bot_by_client[client["_id"]]
        for _ in range(random.randint(600, 800)):
            created = _dt(548, 30)
            kb_docs.append({
                "_id": _oid(),
                "client_id": client["_id"],
                "bot_id": random.choice(c_bots),
                "title": faker.sentence(nb_words=6).rstrip("."),
                "content": faker.paragraph(nb_sentences=random.randint(5, 15)),
                "tags": random.sample(["faq", "policy", "how-to", "troubleshooting", "billing", "onboarding"], k=random.randint(1, 3)),
                "language": random.choice(langs),
                "created_at": created,
                "updated_at": created + timedelta(days=random.randint(0, 60)),
                "active": random.random() > 0.1,
            })
    db.knowledge_base_articles.drop()
    bulk_insert(db.knowledge_base_articles, kb_docs, "knowledge_base_articles")

    return {
        "clients": clients,
        "bots": bots,
        "users": users,
        "conversations": conv_docs,
        "user_id_by_client": user_id_by_client,
        "bot_by_client": bot_by_client,
    }


# ---------------------------------------------------------------------------
# enigma_analytics
# ---------------------------------------------------------------------------


def generate_analytics(db, refs: dict) -> None:
    clients = refs["clients"]
    bots = refs["bots"]
    users = refs["users"]
    conversations = refs["conversations"]
    bot_by_client = refs["bot_by_client"]

    all_user_ids = [u["_id"] for u in users]

    endpoints = ["/api/v1/message", "/api/v1/session", "/api/v1/skill", "/api/v1/feedback", "/api/v1/user"]
    methods = ["GET", "POST", "PUT", "DELETE"]
    user_agents_pool = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "okhttp/4.9.3",
        "python-httpx/0.24.0",
        "curl/7.88.1",
    ]

    # -- access_logs ------------------------------------------------------
    access_docs = []
    for _ in range(10000):
        client = random.choice(clients)
        c_bots = bot_by_client[client["_id"]]
        sc = random.choices([200, 201, 400, 401, 404, 500], weights=[60, 15, 10, 5, 7, 3])[0]
        access_docs.append({
            "_id": _oid(),
            "timestamp": _dt(180),
            "user_id": random.choice(all_user_ids),
            "client_id": client["_id"],
            "bot_id": random.choice(c_bots),
            "endpoint": random.choice(endpoints),
            "method": random.choice(methods),
            "status_code": sc,
            "response_time_ms": random.randint(10, 2000),
            "ip_address": faker.ipv4(),
            "user_agent": random.choice(user_agents_pool),
        })
    db.access_logs.drop()
    bulk_insert(db.access_logs, access_docs, "access_logs")

    # -- error_logs -------------------------------------------------------
    error_codes = ["ERR_NLU_TIMEOUT", "ERR_SKILL_NOT_FOUND", "ERR_DB_CONN", "ERR_WEBHOOK_FAIL", "ERR_AUTH_EXPIRED"]
    severities = ["warning", "error", "critical"]
    err_docs = []
    for _ in range(10000):
        client = random.choice(clients)
        c_bots = bot_by_client[client["_id"]]
        resolved = random.random() > 0.4
        ts = _dt(180)
        err_docs.append({
            "_id": _oid(),
            "timestamp": ts,
            "client_id": client["_id"],
            "bot_id": random.choice(c_bots),
            "error_code": random.choice(error_codes),
            "error_message": faker.sentence(nb_words=8),
            "stack_trace_summary": f"at {faker.word()}.{faker.word()}() line {random.randint(1, 500)}",
            "severity": random.choices(severities, weights=[50, 35, 15])[0],
            "resolved": resolved,
            "resolved_at": ts + timedelta(minutes=random.randint(5, 240)) if resolved else None,
        })
    db.error_logs.drop()
    bulk_insert(db.error_logs, err_docs, "error_logs")

    # -- transaction_logs -------------------------------------------------
    tx_types = ["message_sent", "skill_triggered", "handoff", "session_start", "session_end"]
    tx_docs = []
    for _ in range(10000):
        client = random.choice(clients)
        c_bots = bot_by_client[client["_id"]]
        tx_docs.append({
            "_id": _oid(),
            "timestamp": _dt(180),
            "client_id": client["_id"],
            "user_id": random.choice(all_user_ids),
            "transaction_type": random.choice(tx_types),
            "metadata": {"channel": random.choice(["web", "whatsapp", "telegram"])},
            "duration_ms": random.randint(5, 500),
        })
    db.transaction_logs.drop()
    bulk_insert(db.transaction_logs, tx_docs, "transaction_logs")

    # -- daily_metrics ----------------------------------------------------
    dm_docs = []
    base_date = datetime.now(tz=timezone.utc).date() - timedelta(days=180)
    for client in clients:
        c_bots = bot_by_client[client["_id"]]
        for day_offset in range(180):
            date = base_date + timedelta(days=day_offset)
            for bot in random.sample(c_bots, k=min(2, len(c_bots))):
                dm_docs.append({
                    "_id": _oid(),
                    "date": datetime(date.year, date.month, date.day, tzinfo=timezone.utc),
                    "client_id": client["_id"],
                    "bot_id": bot,
                    "total_conversations": random.randint(10, 500),
                    "total_messages": random.randint(30, 2000),
                    "avg_rating": round(random.uniform(3.0, 5.0), 2),
                    "resolution_rate": round(random.uniform(0.5, 0.95), 2),
                    "handoff_rate": round(random.uniform(0.05, 0.25), 2),
                })
    db.daily_metrics.drop()
    bulk_insert(db.daily_metrics, dm_docs, "daily_metrics")

    # -- funnel_events ----------------------------------------------------
    funnel_steps = ["session_start", "first_message", "skill_match", "resolution", "feedback_prompt", "feedback_submitted"]
    funnel_docs = []
    conv_sample = random.sample(conversations, min(3000, len(conversations)))
    for conv in conv_sample:
        for step in funnel_steps:
            if random.random() > 0.2:
                completed = random.random() > 0.15
                funnel_docs.append({
                    "_id": _oid(),
                    "timestamp": conv["started_at"] + timedelta(seconds=random.randint(0, conv["duration_seconds"])),
                    "conversation_id": conv["_id"],
                    "client_id": conv["client_id"],
                    "bot_id": conv["bot_id"],
                    "step": step,
                    "completed": completed,
                    "drop_off_reason": random.choice(["timeout", "user_left", "error", None]) if not completed else None,
                })
    db.funnel_events.drop()
    bulk_insert(db.funnel_events, funnel_docs, "funnel_events")

    # -- ab_test_results --------------------------------------------------
    ab_docs = []
    for client in clients:
        c_bots = bot_by_client[client["_id"]]
        for _ in range(random.randint(600, 800)):
            started = _dt(180, 30)
            ab_docs.append({
                "_id": _oid(),
                "client_id": client["_id"],
                "bot_id": random.choice(c_bots),
                "test_name": f"test_{faker.word()}_{faker.word()}",
                "variant": random.choice(["control", "variant_a", "variant_b"]),
                "users_count": random.randint(100, 5000),
                "conversion_rate": round(random.uniform(0.1, 0.6), 3),
                "avg_rating": round(random.uniform(3.0, 5.0), 2),
                "started_at": started,
                "ended_at": started + timedelta(days=random.randint(7, 30)),
            })
    db.ab_test_results.drop()
    bulk_insert(db.ab_test_results, ab_docs, "ab_test_results")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def print_summary(source_client: MongoClient, business_db: str, analytics_db: str) -> None:
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    for db_name in [business_db, analytics_db]:
        db = source_client[db_name]
        print(f"\n  [{db_name}]")
        for col_name in sorted(db.list_collection_names()):
            count = db[col_name].count_documents({})
            print(f"    {col_name:<30} {count:>10,} docs")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera datos de prueba en MongoDB para db-tool.")
    parser.add_argument("--uri", default=MONGO_SOURCE_URI, help="URI de MongoDB destino (default: %(default)s)")
    parser.add_argument("--business-db", default="enigma_business", metavar="NAME", help="Nombre de la base de datos de negocio (default: %(default)s)")
    parser.add_argument("--analytics-db", default="enigma_analytics", metavar="NAME", help="Nombre de la base de datos de analítica (default: %(default)s)")
    args = parser.parse_args()

    print(f"Conectando a {args.uri}…")
    client = wait_for_mongo(args.uri)

    print(f"\nGenerando {args.business_db}…")
    refs = generate_business(client[args.business_db])

    print(f"\nGenerando {args.analytics_db}…")
    generate_analytics(client[args.analytics_db], refs)

    print_summary(client, args.business_db, args.analytics_db)
    print(f"Listo. Los datos están disponibles en {args.uri}.")


if __name__ == "__main__":
    main()
