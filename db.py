import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
import string
import secrets
from decimal import Decimal
import hashlib
from datetime import datetime, timezone, timedelta
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv

# Connection string (replace with yours as needed)
load_dotenv()

DB_URL = os.getenv("DB_URL")

def get_connection():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    conn.autocommit = True  # <-- enable auto-commit
    return conn

# ---- CRUD FUNCTIONS ----
def db_create_worker():
    worker_id = str(uuid.uuid4())
    api_key = secrets.token_urlsafe(33)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workers (worker_id, api_key)
                VALUES (%s, %s)
                RETURNING *;
                """,
                (worker_id, api_key)
            )
            conn.commit()
            return worker_id, api_key

def db_heartbeat_worker(worker_id, cpu_usage, ram_usage, disk_name, disk_usage, net_in, net_out, public_ip):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
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
            conn.commit()


def db_read_worker(worker_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM workers WHERE worker_id = %s;", (worker_id,))
            return cur.fetchone()

def db_worker_restart(worker_id):
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
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(check_query, (worker_id,))
            result = cur.fetchone()
            if result:
                cur.execute(update_query, (worker_id,))
                conn.commit()
                return True
            else:
                return None

def db_restart_all_worker():
    query = """
        UPDATE workers
        SET has_restarted = false;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()

def db_remove_idle_workers():
    query = """
        DELETE FROM workers
        WHERE last_updated < NOW() - INTERVAL '1 minute';
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()

def db_authenticate_worker(worker_id, api_key):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM workers WHERE worker_id = %s AND api_key = %s;",
                (worker_id, api_key)
            )
            return True if cur.fetchone() else None

def db_delete_worker(worker_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM workers WHERE worker_id = %s;", (worker_id,))
            conn.commit()
            return cur.rowcount > 0

def db_read_all_workers():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
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
            rows = cur.fetchall()

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
def db_add_to_queue_count(worker_id, amount):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check if worker exists
            cur.execute("SELECT queue FROM workers WHERE worker_id = %s;", (worker_id,))
            row = cur.fetchone()
            if not row:
                return False

            # Update queue by adding amount
            cur.execute(
                "UPDATE workers SET queue = queue + %s WHERE worker_id = %s RETURNING queue;",
                (amount, worker_id,)
            )
            cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = %s",
                (amount, 'queue_size')
            )
            cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = %s",
                (amount, 'total_url')
            )
            conn.commit()

            return True

def db_subtract_from_queue_count(worker_id, amount):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Get current count
            cur.execute("SELECT queue FROM workers WHERE worker_id = %s;", (worker_id,))
            row = cur.fetchone()
            if not row:
                return False

            current_count = row["queue"]
            if current_count - amount < 0:
                return False

            # Update value
            cur.execute(
                "UPDATE workers SET queue = queue - %s WHERE worker_id = %s RETURNING queue;",
                (amount, worker_id)
            )
            cur.execute(
                "UPDATE statistics SET count = count - %s WHERE stat_type = %s",
                (amount, 'queue_size')
            )
            conn.commit()

            return True

def db_get_queue_count(worker_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT queue FROM workers WHERE worker_id = %s;", (worker_id,))
            row = cur.fetchone()
            if not row:
                return -1
            return row["queue"]

def db_subtract_redirect_failed(amount):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE statistics SET count = count - %s WHERE stat_type = %s",
                (amount, 'redirect_failed')
            )

def db_notfound_result():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = %s",
                (1, 'url_not_found')
            )

# Scraping Result Handling

def db_successful_result(worker_id, unresolved_url, resolved_url, title, short_description, full_text_blob):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraped_pages (
                    worker_id, 
                    unresolved_url, 
                    resolved_url, 
                    title, 
                    short_description, 
                    full_text_blob, 
                    scraped_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    worker_id,
                    unresolved_url,
                    resolved_url,
                    title,
                    short_description,
                    full_text_blob,
                    datetime.utcnow()  # store UTC timestamp
                )
            )
            cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = %s",
                (1, 'scraped_pages')
            )
            conn.commit()

def db_noredirect_result(worker_id, unresolved_url):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO noredirect (
                    worker_id, 
                    unresolved_url, 
                    scraped_at
                )
                VALUES (%s, %s, %s);
                """,
                (
                    worker_id,
                    unresolved_url,
                    datetime.utcnow()
                )
            )
            cur.execute(
                "UPDATE statistics SET count = count + %s WHERE stat_type = %s",
                (1, 'redirect_failed')
            )
            conn.commit()

def update_state(service_name, last_index):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE lastcount
                SET last_index = %s
                WHERE service = %s;
            """, (last_index, service_name))
            
            conn.commit()

def get_state(service_name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT service, last_index
                FROM lastcount
                WHERE service = %s;
            """, (service_name,))
            res = cur.fetchone()
            return int(res['last_index']) if res else None

def getstats():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT stat_type, percentage, count, change_value FROM statistics;")
            rows = cur.fetchall()
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
            cur.execute("SELECT pg_database_size(current_database()) AS size;")
            row = cur.fetchone()
            if not row:
                return -1
            size_bytes = row["size"]
            size_mb = size_bytes / (1024 * 1024)

            one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
            cur.execute(
                """
                SELECT *
                FROM scraped_pages
                WHERE scraped_at >= %s;
                """,
                (one_minute_ago,)
            )
            last1 = cur.fetchall()
            cur.execute("SELECT count FROM statistics WHERE stat_type = %s;", ('scraped_pages',))
            scraped_count = cur.fetchone()['count']
            cur.execute("SELECT last_index FROM lastcount;")
            rows_lasc = cur.fetchall()
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
            cur.execute("SELECT COUNT(*) AS total FROM workers;")
            total_workers = cur.fetchone()['total']  # dict cursor

            # Get active workers (last_updated within 30 seconds)
            cur.execute("""
                SELECT COUNT(*) AS active
                FROM workers
                WHERE last_updated >= NOW() - INTERVAL '30 seconds';
            """)
            active_workers = cur.fetchone()['active']
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

        # Dummy URLs processed

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
def create_admin(username: str, password_hash: str):
    key1 = generate_key()
    key2 = generate_key()
    key3 = generate_key()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraper_admin (username, password_hash, key1, key2, key3)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (username, password_hash, key1, key2, key3)
            )
    return key1, key2, key3  # return generated keys if needed


# --- READ function ---
def get_admin(username: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, password_hash, key1, key2, key3 FROM scraper_admin WHERE username=%s",
                (username,)
            )
            return cur.fetchone()


# --- DELETE function ---
def delete_admin(username: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM scraper_admin WHERE username=%s",
                (username,)
            )


# --- LOGIN ---
def login_logic(username: str, password: str) -> tuple[str, str, str] | None:
    """
    Verifies credentials and generates new keys for the session.
    Returns a tuple (key1, key2, key3) if login succeeds, None otherwise.
    """
    admin = get_admin(username)
    if not admin:
        return None

    stored_hash = admin['password_hash']
    if not verify_sha256(password, stored_hash):
        return None

    # Generate new session keys
    key1 = generate_key()
    key2 = generate_key()
    key3 = generate_key()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE scraper_admin SET key1=%s, key2=%s, key3=%s WHERE username=%s",
                (key1, key2, key3, username)
            )

    return key1, key2, key3


# --- LOGOUT ---
def logout_logic(key1: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE scraper_admin SET key1=NULL, key2=NULL, key3=NULL WHERE key1=%s AND (key1 IS NOT NULL OR key2 IS NOT NULL OR key3 IS NOT NULL)",
                (key1,)
            )
            return cur.rowcount > 0


# --- CHECK LOGIN ---
def is_logged_in_logic(keys: tuple[str, str, str]) -> bool:
    key1, key2, key3 = keys
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key1, key2, key3 FROM scraper_admin WHERE key1=%s",
                (key1,)
            )
            row = cur.fetchone()
            return bool(row) and row['key1'] == key1 and row['key2'] == key2 and row['key3'] == key3   


# Handling unresolved task
def batch_insert_queue(urls, worker_id=None):
    if not urls:
        return
    query = """
        INSERT INTO big_queue (worker_id, unresolved_url, assigned_at)
        VALUES %s
    """
    
    assigned_at = datetime.utcnow() if worker_id else None
    values = [(worker_id, url, assigned_at) for url in urls]

    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, query, values)

def unresolved_retrieve():
    three_hours_ago = datetime.utcnow() - timedelta(hours=1)

    query = """
        SELECT unresolved_url
        FROM big_queue
        WHERE assigned_at < %s
        ORDER BY random()
        LIMIT 33;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (three_hours_ago,))
            rows = cur.fetchall()
            if not rows:
                return None
            return [row['unresolved_url'] for row in rows]

def delete_task(unresolved_url):

    query = """
        DELETE FROM big_queue
        WHERE unresolved_url = %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (unresolved_url,))
            return cur.rowcount  # number of rows deleted


def update_hold_worker(condition):
    query = """
        UPDATE statefull
        SET state = %s
        WHERE state_type = 'worker_hold';
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (condition,))
            conn.commit()

def read_hold_worker():
    query = """
        SELECT state
        FROM statefull
        WHERE state_type = 'worker_hold';
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            result = cur.fetchone()
            return result['state'] if result else None

def update_hold_queue(condition):
    query = """
        UPDATE statefull
        SET state = %s
        WHERE state_type = 'queue_hold';
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (condition,))
            conn.commit()

def read_hold_queue():
    query = """
        SELECT state
        FROM statefull
        WHERE state_type = 'queue_hold';
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            result = cur.fetchone()
            return result['state'] if result else None

def update_delay(delay):
    query = """
        UPDATE statefull
        SET value = %s
        WHERE state_type = 'delay';
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (delay,))
            conn.commit()

def read_delay():
    query = """
        SELECT value
        FROM statefull
        WHERE state_type = 'delay';
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            result = cur.fetchone()
            return result['value'] if result else None

def revoke_all_admin_cookie():
    query = """
        UPDATE scraper_admin
        SET key1 = 'revoked_waiting_for_login',
            key2 = 'revoked_waiting_for_login',
            key3 = 'revoked_waiting_for_login';
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            conn.commit()

def clear_workers_db():
    query = "DELETE FROM workers;"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            conn.commit()
