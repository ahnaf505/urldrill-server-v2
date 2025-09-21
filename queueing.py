import asyncio
from collections import defaultdict
from db import *

queue = asyncio.Queue()

# ---- Producer ----
async def queue_subtract_job(worker_id, count):
    await queue.put(("subtract", worker_id, count))

# ---- Producer: Delete ----
async def queue_delete_job(unresolved_url):
    await queue.put(("delete", unresolved_url))


async def queue_successful_result(
    worker_id: str,
    unresolved_url: str,
    resolved_url: str,
    title: str,
    short_description: str,
    full_text_blob: str
):
    row = (worker_id, unresolved_url, resolved_url, title, short_description, full_text_blob)
    await queue.put(("success", row))


# ---- Producer: NoRedirect ----
async def queue_noredirect_result(worker_id: str, unresolved_url: str):
    row = (worker_id, unresolved_url)
    await queue.put(("noredirect", row))

async def queue_notfound_result():
    await queue.put(("notfound", 1))


# ---- Consumer ----
async def queue_worker():
    while True:
        worker_counts = defaultdict(int)
        delete_urls = []
        success_rows = []
        noredirect_rows = []
        notfound_count = 0

        # Wait for at least one job
        job = await queue.get()
        if job is None:
            queue.task_done()
            break

        job_type, *payload = job

        if job_type == "subtract":
            worker_id, count = payload
            worker_counts[worker_id] += count
        elif job_type == "delete":
            unresolved_url, = payload
            delete_urls.append(unresolved_url)
        elif job_type == "success":
            row, = payload
            success_rows.append(row)
        elif job_type == "noredirect":
            row, = payload
            noredirect_rows.append(row)
        elif job_type == "notfound":
            notfound_count += 1

        queue.task_done()

        # Drain remaining jobs
        while not queue.empty():
            next_job = await queue.get()
            if next_job is None:
                queue.task_done()
                await queue.put(None)
                break

            job_type, *payload = next_job

            if job_type == "subtract":
                wid, c = payload
                worker_counts[wid] += c
            elif job_type == "delete":
                unresolved_url, = payload
                delete_urls.append(unresolved_url)
            elif job_type == "success":
                row, = payload
                success_rows.append(row)
            elif job_type == "noredirect":
                row, = payload
                noredirect_rows.append(row)

            queue.task_done()

        # Throttle batching
        await asyncio.sleep(2)

        # Perform DB ops with debug prints
        if worker_counts:
            print(f"[DEBUG] Processing subtract batch: {dict(worker_counts)}")
            for wid, total in worker_counts.items():
                await db_subtract_from_queue_count(wid, total)

        if delete_urls:
            print(f"[DEBUG] Processing delete batch: {len(delete_urls)} urls")
            await db_delete_tasks(delete_urls)

        if success_rows:
            print(f"[DEBUG] Processing success batch: {len(success_rows)} rows")
            await db_successful_results(success_rows)

        if noredirect_rows:
            print(f"[DEBUG] Processing noredirect batch: {len(noredirect_rows)} rows")
            await db_noredirect_results(noredirect_rows)

        if notfound_count:
            print(f"[DEBUG] Processing notfound batch: {notfound_count}")
            await db_notfound_results(notfound_count)