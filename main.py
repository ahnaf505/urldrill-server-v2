import json
import asyncio
import random
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    Header,
    Request,
    Form,
    HTTPException,
    status
)

from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
from db import *
from datetime import datetime, timezone
import time
import os
from auth import *
from generator import *
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

async def get_worker_auth(
    worker_id: str = Header(..., alias="X-Worker-ID"),
    api_key: str = Header(..., alias="X-API-Key")
):
    if not db_authenticate_worker(worker_id, api_key):
        raise HTTPException(status_code=401, detail="Invalid worker credentials")
    return worker_id


def format_bytes(value: int) -> str:
    """
    Converts bytes to a human-readable format (MB/GB).
    """
    if value >= 1 << 30:  # 1 GB
        return f"{value / (1 << 30):.2f} GB"
    elif value >= 1 << 20:  # 1 MB
        return f"{value / (1 << 20):.2f} MB"
    elif value >= 1 << 10:  # 1 KB
        return f"{value / (1 << 10):.2f} KB"
    return f"{value} B"

def authorize_api(request: Request):
    key1 = request.cookies.get("keyone")
    key2 = request.cookies.get("keytwo")
    key3 = request.cookies.get("keythree")

    if not integrity_check(request.cookies):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session integrity",
        )

    if not check_session(key1, key2, key3):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session keys",
        )

    return (key1, key2, key3)


# Mount static directory for assets like CSS, JS, images
templates = Jinja2Templates(directory="templates")
templates.env.filters["format_bytes"] = format_bytes


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    key1 = request.cookies.get("keyone")
    key2 = request.cookies.get("keytwo")
    key3 = request.cookies.get("keythree")

    if integrity_check(request.cookies):
        session_valid = await asyncio.to_thread(check_session, key1, key2, key3)
        if session_valid:
            return templates.TemplateResponse("index.html", {"request": request})
        else:
            return templates.TemplateResponse("login.html", {"request": request})
    else:
        return templates.TemplateResponse("login.html", {"request": request})

@app.post("/", response_class=JSONResponse)
async def dashboard_data(request: Request, auth: tuple = Depends(authorize_api)):
    # Run blocking DB and processing calls in thread pool
    stats = await asyncio.to_thread(getstats)
    workers = await asyncio.to_thread(db_read_all_workers)
    processed_workers = await asyncio.to_thread(process_workers, workers)
    hold_worker = await asyncio.to_thread(read_hold_worker)
    hold_queue = await asyncio.to_thread(read_hold_queue)
    batch_delay = await asyncio.to_thread(read_delay)

    data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **stats,
        **processed_workers,
        "hold_worker": hold_worker,
        "hold_queue": hold_queue,
        "batch_delay": batch_delay
    }

    return JSONResponse(data)


@app.post("/actions", response_class=JSONResponse)
async def update_actions(request: Request, auth: tuple = Depends(authorize_api)):
    try:
        payload = await request.json()  # read JSON manually
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    state_type = payload.get("state_type")
    value = payload.get("value")

    if state_type is None or value is None:
        raise HTTPException(status_code=400, detail="Missing 'state_type' or 'value'")

    if state_type == "worker_hold":
        update_hold_worker(value)
    elif state_type == "queue_hold":
        update_hold_queue(value)
    elif state_type == "delay_per_batch":
        update_delay(value)
    elif state_type == "revoke_all_admin_cookies":
        revoke_all_admin_cookie()
    elif state_type == "wipe_worker_db":
        clear_workers_db()
    elif state_type == "restart_workers":
        db_restart_all_worker()
    elif state_type == "cleanup_db":
        db_remove_idle_workers()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown state_type: {state_type}")

    if None:
        raise HTTPException(status_code=500, detail="Failed to update state")

    return JSONResponse(
        content={
            "message": "Action executed successfully",
            "state_type": state_type,
            "value": value,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

@app.post("/login")
async def login(request: Request):
    # Parse the request body manually
    try:
        body = await request.json()
        username = body.get("username")
        password = body.get("password")
        
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username and password are required"
            )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in request body"
        )
    
    # Use the provided login_logic function to validate credentials
    keys = login_logic(username, password)
    
    if not keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Create response with keys
    response_data = {
        "message": "Login successful",
        "keyone": keys[0],
        "keytwo": keys[1],
        "keythree": keys[2]
    }
    
    response = JSONResponse(response_data)
    
    # Set cookies with 10-day expiration
    expires = datetime.utcnow() + timedelta(days=10)
    response.set_cookie(
        key="keyone", 
        value=keys[0], 
        expires=expires.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        httponly=True,
        secure=True,
        samesite="strict"
    )
    response.set_cookie(
        key="keytwo", 
        value=keys[1], 
        expires=expires.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        httponly=True,
        secure=True,
        samesite="strict"
    )
    response.set_cookie(
        key="keythree", 
        value=keys[2], 
        expires=expires.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        httponly=True,
        secure=True,
        samesite="strict"
    )
    response.set_cookie(
        key="keyhash", 
        value=hash(keys[0]+keys[1]+keys[2]), 
        expires=expires.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        httponly=True,
        secure=True,
        samesite="strict"
    )
    
    return response

@app.post("/logout")
async def logout(request: Request):
    if logout_logic(request.cookies.get("keyone")):
        return RedirectResponse(url="/", status_code=303)
    else:
        raise HTTPException(status_code=401, detail="Invalid admin cookies")









# Worker Management
@app.get("/register")
async def register_worker():
    worker_id, api_key = await asyncio.to_thread(db_create_worker)
    
    if worker_id:
        return {
            "worker_id": worker_id,
            "api_key": api_key
        }
    else:
        return {
            "message": "Worker not created successfully"
        }

@app.post("/heartbeat")
async def heartbeat(request: Request):
    try:
        worker_id = await get_worker_auth(
            worker_id=request.headers.get("X-Worker-ID"),
            api_key=request.headers.get("X-API-Key")
        )
    except HTTPException:
        return {"status": "restart", "message": "Worker auth failed"}

    payload = await request.json()
    cpu = payload["cpu_usage"]
    ram = payload["ram_usage"]

    disk_name = payload["disk_usage"]["name"]
    disk_usage = payload["disk_usage"]["percent"]

    net_in = payload["network"]["in"]
    net_out = payload["network"]["out"]
    public_ip = payload["public_ip"]

    # Run blocking DB calls in thread pool
    worker_restart = await asyncio.to_thread(db_worker_restart, worker_id)
    hold_worker = await asyncio.to_thread(read_hold_worker)

    if worker_restart:
        status = "restart"
    elif hold_worker:
        status = "hold"
    else:
        status = "continue"

    await asyncio.to_thread(
        db_heartbeat_worker,
        worker_id,
        cpu,
        ram,
        disk_name,
        disk_usage,
        net_in,
        net_out,
        public_ip
    )

    return {"status": status, "message": "Heartbeat updated", "worker_id": worker_id}

@app.get("/tasks")
async def get_tasks(request: Request):
    try:
        worker_id = await get_worker_auth(
            worker_id=request.headers.get("X-Worker-ID"),
            api_key=request.headers.get("X-API-Key")
        )
    except HTTPException:
        return {"status": "restart", "message": "Worker auth failed"}

    # Run blocking calls in thread pool
    hold_queue = await asyncio.to_thread(read_hold_queue)
    if hold_queue:
        return []

    delay = await asyncio.to_thread(read_delay)
    if delay is not None:
        await asyncio.sleep(delay)

    backlog = await asyncio.to_thread(unresolved_retrieve)
    if backlog is not None:
        return backlog

    # These are your synchronous generators
    generated_uid = generate_bitly() + generate_sid() + generate_shorturl()
    #generated_uid = ["https://bit.ly/a"]

    # Insert into queue and update DB asynchronously
    await asyncio.to_thread(batch_insert_queue, generated_uid, worker_id)
    count = len(generated_uid)
    await asyncio.to_thread(db_add_to_queue_count, worker_id, count)

    return generated_uid

@app.post("/result")
async def submit_result(
    request: Request,
    status: str = Form(...),
    unresolved_url: str = Form(...),
    resolved_url: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    full_text_blob: Optional[str] = Form(None)
):
    try:
        worker_id = await get_worker_auth(
            worker_id=request.headers.get("X-Worker-ID"),
            api_key=request.headers.get("X-API-Key")
        )
    except HTTPException:
        return {"status": "restart", "message": "Worker auth failed"}

    # Run blocking functions in thread pool
    await asyncio.to_thread(db_subtract_from_queue_count, worker_id, 1)

    if status == "success":
        try:
            await asyncio.to_thread(delete_task, unresolved_url)
        except:
            pass

        missing_fields = []
        if not resolved_url:
            missing_fields.append("resolved_url")
        if not title:
            missing_fields.append("title")
        if not short_description:
            missing_fields.append("short_description")
        if not full_text_blob:
            missing_fields.append("full_text_blob")

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields for success status: {', '.join(missing_fields)}"
            )

        await asyncio.to_thread(
            db_successful_result,
            worker_id,
            unresolved_url,
            resolved_url,
            title,
            short_description,
            full_text_blob
        )

        return {"status": "success", "message": "Result processed successfully"}

    elif status == "noredirect":
        try:
            await asyncio.to_thread(delete_task, unresolved_url)
        except:
            pass
        await asyncio.to_thread(db_noredirect_result, worker_id, unresolved_url)
        return {"status": "success", "message": "Result processed successfully"}

    elif status == "notfound":
        try:
            await asyncio.to_thread(delete_task, unresolved_url)
        except:
            pass
        await asyncio.to_thread(db_notfound_result)
        return {"status": "success", "message": "Result processed successfully"}

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Must be 'success', 'noredirect', or 'notfound'"
        )