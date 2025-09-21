import uuid
import string
import secrets
from decimal import Decimal
import hashlib
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from typing import List, Dict, Any
from contextlib import asynccontextmanager

# Connection string (replace with yours as needed)
load_dotenv()
DB_URL = os.getenv("DB_URL")

# Async connection pool
pool: AsyncConnectionPool | None = None

def init_pool():
    global pool
    if pool is None:
        pool = AsyncConnectionPool(
            conninfo=DB_URL,
            min_size=5,
            max_size=50,  # keep bounded; PgBouncer handles the rest
            kwargs={
                "row_factory": dict_row,
                "prepare_threshold": None  # required for PgBouncer
            }
        )
    return pool

@asynccontextmanager
async def get_connection():
    p = init_pool()
    async with p.connection() as conn:
        yield conn

# ---- CRUD FUNCTIONS ----

async def db_create_worker():
    worker_id = str(uuid.uuid4())
    api_key = secrets.token_urlsafe(33)
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO workers (worker_id, api_key)
                VALUES (%s, %s)
                RETURNING worker_id, api_key;
                """,
                (worker_id, api_key)
            )
            row = await cur.fetchone()
            return row["worker_id"], row["api_key"]

async def db_heartbeat_worker(worker_id, cpu_usage, ram_usage, disk_name, disk_usage, net_in, net_out, public_ip):
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE workers
                SET cpu_usage = %s,
                    ram_usage = %s,
                    disk_name = %s,
                    disk_usage = %s,
                    net_in = %s,
                    net_out = %s,
                    public_ip = %s,
                    last_updated = CURRENT_TIMESTAMP
                WHERE worker_id = %s;
                """,
                (cpu_usage, ram_usage, disk_name, disk_usage, net_in, net_out, public_ip, worker_id)
            )

async def db_read_worker(worker_id):
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM workers WHERE worker_id = %s;", (worker_id,))
            return await cur.fetchone()

async def db_worker_restart(worker_id):
    check_query = """
        SELECT 1
        FROM workers
        WHERE worker_id = %s AND has_restarted = false;
    """
    update_query = """
        UPDATE workers
        SET has_restarted = true
        WHERE worker_id = %s;
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(check_query, (worker_id,))
            result = await cur.fetchone()
            if result:
                await cur.execute(update_query, (worker_id,))
                return True
            else:
                return None

async def db_restart_all_worker():
    query = """
        UPDATE workers
        SET has_restarted = false;
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query)

async def db_remove_idle_workers():
    query = """
        DELETE FROM workers
        WHERE last_updated < NOW() - INTERVAL '1 minute';
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query)

async def db_authenticate_worker(worker_id, api_key):
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM workers WHERE worker_id = %s AND api_key = %s;",
                (worker_id, api_key)
            )
            return True if (await cur.fetchone()) else None

async def db_read_all_workers():
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    worker_id,
                    api_key,
                    cpu_usage,
                    ram_usage,
                    disk_name,
                    disk_usage,
                    net_in,
                    net_out,
                    public_ip,
                    created_on,
                    last_updated,
                    queue
                FROM workers;
            """)
            rows = await cur.fetchall()

            workers = []
            for r in rows:
                workers.append({
                    "worker_id": r["worker_id"],
                    "api_key": r["api_key"],
                    "cpu_usage": float(r["cpu_usage"]) if r["cpu_usage"] is not None else None,
                    "ram_usage": float(r["ram_usage"]) if r["ram_usage"] is not None else None,
                    "disk_name": r["disk_name"],
                    "disk_usage": float(r["disk_usage"]) if r["disk_usage"] is not None else None,
                    "net_in": int(r["net_in"]) if r["net_in"] is not None else None,
                    "net_out": int(r["net_out"]) if r["net_out"] is not None else None,
                    "public_ip": str(r["public_ip"]) if r["public_ip"] is not None else None,
                    "created_on": r["created_on"].isoformat() if r["created_on"] else None,
                    "last_updated": r["last_updated"].isoformat() if r["last_updated"] else None,
                    "queue": r["queue"] if r["queue"] else 0,
                })
            return workers

# Queue Counter
async def db_add_to_queue_count(worker_id, amount):
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            # Check if worker exists
            await cur.execute("SELECT queue FROM workers WHERE worker_id = %s;", (worker_id,))
            row = await cur.fetchone()
            if not row:
                return False

            # Update queue by adding amount
            await cur.execute(
                "UPDATE workers SET queue = queue + %s WHERE worker_id = %s RETURNING queue;",
                (amount, worker_id,)
            )
            
            # Update statistics directly
            await cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = 'queue_size'",
                (amount,)
            )
            await cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = 'total_url'",
                (amount,)
            )

            return True

async def db_subtract_from_queue_count(worker_id, amount):
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            # Get current count
            await cur.execute("SELECT queue FROM workers WHERE worker_id = %s;", (worker_id,))
            row = await cur.fetchone()
            if not row:
                return False

            current_count = row["queue"]
            if current_count - amount < 0:
                return False

            # Update value
            await cur.execute(
                "UPDATE workers SET queue = queue - %s WHERE worker_id = %s RETURNING queue;",
                (amount, worker_id)
            )
            
            # Update statistics directly
            await cur.execute(
                "UPDATE statistics SET count = count - %s WHERE stat_type = 'queue_size'",
                (amount,)
            )

            return True

async def db_notfound_results(count: int):
    """
    Batch update 'not found' results in statistics.
    count: number of notfound events to add
    """
    if count <= 0:
        return 0

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = 'url_not_found'",
                (count,)
            )
    return count


# Scraping Result Handling
async def db_noredirect_results(rows: list[tuple[str, str]]):
    """
    Insert multiple 'no redirect' results in one batch.
    rows: list of (worker_id, unresolved_url)
    """
    if not rows:
        return 0

    now = datetime.utcnow()
    values = [(worker_id, unresolved_url, now) for (worker_id, unresolved_url) in rows]

    placeholders = ", ".join(["(%s, %s, %s)"] * len(values))

    query = f"""
        INSERT INTO noredirect (
            worker_id,
            unresolved_url,
            scraped_at
        )
        VALUES {placeholders};
    """

    flat_values = [item for row in values for item in row]

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, flat_values)
            await cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = 'redirect_failed'",
                (len(rows),)
            )

    return len(rows)


async def db_successful_results(rows: list[tuple]):
    """
    rows: list of tuples like
        (worker_id, unresolved_url, resolved_url, title, short_description, full_text_blob)
    """

    if not rows:
        return 0

    now = datetime.utcnow()
    values = [
        (worker_id, unresolved_url, resolved_url, title, short_description, full_text_blob, now)
        for (worker_id, unresolved_url, resolved_url, title, short_description, full_text_blob) in rows
    ]

    placeholders = ", ".join(["(%s, %s, %s, %s, %s, %s, %s)"] * len(values))

    query = f"""
        INSERT INTO scraped_pages (
            worker_id,
            unresolved_url,
            resolved_url,
            title,
            short_description,
            full_text_blob,
            scraped_at
        )
        VALUES {placeholders}
    """

    flat_values = [item for row in values for item in row]

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, flat_values)
            await cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = 'scraped_pages'",
                (len(values),)
            )

async def update_state(service_name, last_index):
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE lastcount
                SET last_index = %s
                WHERE service = %s;
            """, (last_index, service_name))

async def get_state(service_name):
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT service, last_index
                FROM lastcount
                WHERE service = %s;
            """, (service_name,))
            res = await cur.fetchone()
            return int(res['last_index']) if res else None

async def getstats():
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT stat_type, percentage, count, change_value FROM statistics;")
            rows = await cur.fetchall()
            def get_value(stat_type: str, field: str, default=None):
                for r in rows:
                    if r.get("stat_type") == stat_type:
                        return r.get(field) if r.get(field) is not None else default
                return default
            # Common lookups
            total_urls = get_value("total_url", "count", 0)
            total_workers = get_value("total_workers", "count", 1)
            active_workers = get_value("active_workers", "count", 0)
            active_percent = get_value("active_workers", "percentage", Decimal("0.00"))
            url_not_found_percent = get_value("url_not_found", "percentage", Decimal("0.00"))
            url_not_found_count = get_value("url_not_found", "count", 0)
            redirect_failed_percent = get_value("redirect_failed", "percentage", Decimal("0.00"))
            redirect_failed_count = get_value("redirect_failed", "count", 0)
            await cur.execute("SELECT pg_database_size(current_database()) AS size;")
            row = await cur.fetchone()
            if not row:
                return -1
            size_bytes = row["size"]
            size_mb = size_bytes / (1024 * 1024)
            one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
            await cur.execute(
                """
                SELECT *
                FROM scraped_pages
                WHERE scraped_at >= %s;
                """,
                (one_minute_ago,)
            )
            last1 = await cur.fetchall()
            await cur.execute("SELECT count FROM statistics WHERE stat_type = %s;", ('scraped_pages',))
            scraped_count = (await cur.fetchone())['count']
            await cur.execute("SELECT last_index FROM lastcount;")
            rows_lasc = await cur.fetchall()
            lastcount = sum(row['last_index'] for row in rows_lasc)
            # Scraping stats
            scraping_stats = {
                "url_failures": {
                    "value": float(get_value("url_failures", "percentage", Decimal("0.00"))),
                    "count": get_value("url_failures", "count", 0),
                    "total": total_urls,
                    "change": float(get_value("url_failures", "change_value", Decimal("0.00"))),
                },
                "data_size": {
                    "value": size_mb,
                    "change": float(get_value("data_size", "change_value", Decimal("0.00"))),
                },
                "urls_count": {
                    "value": total_urls
                },
                "queue_size": {
                    "value": get_value("queue_size", "count", 0),
                    "change": float(get_value("queue_size", "change_value", Decimal("0.00"))),
                },
                "lastcount": lastcount
            }
            # Get total workers
            await cur.execute("SELECT COUNT(*) AS total FROM workers;")
            total_workers = (await cur.fetchone())['total']
            # Get active workers (last_updated within 30 seconds)
            await cur.execute(
                """
                SELECT COUNT(*) AS active
                FROM workers
                WHERE last_updated >= NOW() - INTERVAL '30 seconds';
                """
            )
            active_workers = (await cur.fetchone())['active']
            # Stats overview
            stats_overview = {
                "active_workers": {
                    "count": active_workers,
                    "total": total_workers,
                },
                "url_not_found": {
                    "value": float(url_not_found_percent),
                    "count": url_not_found_count,
                    "total": total_urls,
                },
                "scraped_pages": {
                    "value": scraped_count,
                    "change": len(last1),
                },
                "redirect_failed": {
                    "value": float(redirect_failed_percent),
                    "count": redirect_failed_count,
                    "total": total_urls,
                },
            }
            return {
                "scraping_stats": scraping_stats,
                "stats_overview": stats_overview,
            }

def process_workers(raw_workers):
    worker_nodes = []
    now = datetime.now()

    for i, w in enumerate(raw_workers, start=1):
        # Parse and force UTC timezone
        last_updated = datetime.fromisoformat(w["last_updated"])

        diff_sec = (now - last_updated).total_seconds()

        # Status check (idle if >30s old)
        status = "active" if diff_sec <= 60 else "idle"
        # RAM (assuming 16 GB total)
        ram_total = 16
        ram_percent = round(w["ram_usage"])
        ram_used = round((ram_percent / 100) * ram_total)

        # Disk (assuming 250 GB total)
        disk_total = 250
        disk_percent = round(w["disk_usage"])
        disk_used = round((disk_percent / 100) * disk_total)

        # Last active (human readable)
        if diff_sec <= 30:
            last_active = "just now"
        elif diff_sec < 60:
            last_active = f"{int(diff_sec)}s ago"
        elif diff_sec < 3600:
            last_active = f"{int(diff_sec//60)}m ago"
        else:
            last_active = f"{int(diff_sec//3600)}h ago"

        worker_nodes.append({
            "id": w["worker_id"],
            "worker_id": w["worker_id"],
            "status": status,
            "ip": w["public_ip"] or f"192.168.0.{100+i}",
            "urls_onqueue": w["queue"],
            "cpu_usage": round(w["cpu_usage"]),
            "ram_usage": {
                "used": ram_used,
                "total": ram_total,
                "percent": ram_percent
            },
            "disk_name": w["disk_name"],
            "disk_usage": {
                "used": disk_used,
                "total": disk_total,
                "percent": disk_percent
            },
            "last_active": last_active,
            "network_in": w["net_in"],
            "network_out": w["net_out"]
        })

    return {"worker_nodes": worker_nodes}

# Admin Auth 
def verify_sha256(password: str, stored_hash: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash

# --- Helper function to generate random keys ---
def generate_key(length=32):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# --- CREATE function with auto-generated keys ---
async def create_admin(username: str, password_hash: str):
    key1 = generate_key()
    key2 = generate_key()
    key3 = generate_key()

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO scraper_admin (username, password_hash, key1, key2, key3)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (username, password_hash, key1, key2, key3)
            )
    return key1, key2, key3  # return generated keys if needed

# --- READ function ---
async def get_admin(username: str):
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT username, password_hash, key1, key2, key3 FROM scraper_admin WHERE username=%s",
                (username,)
            )
            return await cur.fetchone()

# --- LOGIN ---
async def login_logic(username: str, password: str) -> tuple[str, str, str] | None:
    """
    Verifies credentials and generates new keys for the session.
    Returns a tuple (key1, key2, key3) if login succeeds, None otherwise.
    """
    admin = await get_admin(username)
    if not admin:
        return None

    stored_hash = admin['password_hash']
    if not verify_sha256(password, stored_hash):
        return None

    # Generate new session keys
    key1 = generate_key()
    key2 = generate_key()
    key3 = generate_key()

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE scraper_admin SET key1=%s, key2=%s, key3=%s WHERE username=%s",
                (key1, key2, key3, username)
            )

    return key1, key2, key3

# --- LOGOUT ---
async def logout_logic(key1: str) -> bool:
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE scraper_admin SET key1=NULL, key2=NULL, key3=NULL WHERE key1=%s AND (key1 IS NOT NULL OR key2 IS NOT NULL OR key3 IS NOT NULL)",
                (key1,)
            )
            return cur.rowcount > 0

# --- CHECK LOGIN ---
async def is_logged_in_logic(keys: tuple[str, str, str]) -> bool:
    key1, key2, key3 = keys
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT key1, key2, key3 FROM scraper_admin WHERE key1=%s",
                (key1,)
            )
            row = await cur.fetchone()
            return bool(row) and row['key1'] == key1 and row['key2'] == key2 and row['key3'] == key3  

# Handling unresolved task
async def batch_insert_queue(urls, worker_id=None):
    if not urls:
        return
    assigned_at = datetime.utcnow() if worker_id else None
    values = [(worker_id, url, assigned_at) for url in urls]
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO big_queue (worker_id, unresolved_url, assigned_at) VALUES (%s, %s, %s)",
                values,
            )

async def unresolved_retrieve():
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    query = """
        SELECT unresolved_url
        FROM big_queue
        TABLESAMPLE SYSTEM (1)
        WHERE assigned_at < %s
        LIMIT 33;
    """

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (one_hour_ago,))
            rows = await cur.fetchall()
            if not rows:
                return None
            return [row["unresolved_url"] for row in rows]

async def db_delete_tasks(unresolved_urls):
    if not unresolved_urls:
        return 0  # nothing to delete

    placeholders = ", ".join(["%s"] * len(unresolved_urls))
    query = f"""
        DELETE FROM big_queue
        WHERE unresolved_url IN ({placeholders});
    """

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, unresolved_urls)
            return cur.rowcount


async def update_hold_worker(condition):
    query = """
        UPDATE statefull
        SET state = %s
        WHERE state_type = 'worker_hold';
    """

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (condition,))

async def read_hold_worker():
    query = """
        SELECT state
        FROM statefull
        WHERE state_type = 'worker_hold';
    """

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query)
            result = await cur.fetchone()
            return result['state'] if result else None

async def update_hold_queue(condition):
    query = """
        UPDATE statefull
        SET state = %s
        WHERE state_type = 'queue_hold';
    """

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (condition,))

async def read_hold_queue():
    query = """
        SELECT state
        FROM statefull
        WHERE state_type = 'queue_hold';
    """

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query)
            result = await cur.fetchone()
            return result['state'] if result else None

async def update_delay(delay):
    query = """
        UPDATE statefull
        SET value = %s
        WHERE state_type = 'delay';
    """

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (delay,))

async def read_delay():
    query = """
        SELECT value
        FROM statefull
        WHERE state_type = 'delay';
    """

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query)
            result = await cur.fetchone()
            return result['value'] if result else None

async def revoke_all_admin_cookie():
    query = """
        UPDATE scraper_admin
        SET key1 = 'revoked_waiting_for_login',
            key2 = 'revoked_waiting_for_login',
            key3 = 'revoked_waiting_for_login';
    """

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query)

async def clear_workers_db():
    query = "DELETE FROM workers;"

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query)