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

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

async def get_worker_auth(
    worker_id: str = Header(..., alias="X-Worker-ID"),
    api_key: str = Header(..., alias="X-API-Key")
):
    if not db_authenticate_worker(worker_id, api_key):
        raise HTTPException(status_code=401, detail="Invalid worker credentials")
    return worker_id

def count_total_items(data_dict):
    total = 0
    
    # Check if it's a dictionary
    if not isinstance(data_dict, dict):
        return 0
    
    for key, value in data_dict.items():
        if isinstance(value, (list, tuple, set)):
            total += len(value)
        elif isinstance(value, dict):
            total += len(value)
        else:
            # Single value counts as 1
            total += 1
    
    return total

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
        if check_session(key1, key2, key3):
            return templates.TemplateResponse("index.html", {"request": request})
        else:
            return templates.TemplateResponse("login.html", {"request": request})
    else:
        return templates.TemplateResponse("login.html", {"request": request})

@app.post("/", response_class=JSONResponse)
async def dashboard_data(request: Request, auth: tuple = Depends(authorize_api)):
    a = getstats()
    workers = db_read_all_workers()
    w = process_workers(workers)
    worker_hold_state = {"hold_worker": read_hold_worker()}
    queue_hold_state = {"hold_queue": read_hold_queue()}
    batch_delay = {"batch_delay": read_delay()}
    data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **a,
        **w,
        **worker_hold_state,
        **queue_hold_state,
        **batch_delay
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
    worker_id, api_key = db_create_worker()
    
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
    # Try to manually run the dependency
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
    disk_usage = payload["disk_usage"]["usage_percent"]

    net_in = payload["network"]["in"]
    net_out = payload["network"]["out"]
    public_ip = payload["public_ip"]

    if db_worker_restart(worker_id):
        status = "restart"
    elif read_hold_worker():
        status = "hold"
    else:
        status = "continue"

    db_heartbeat_worker(worker_id, cpu, ram, disk_name, disk_usage, net_in, net_out, public_ip)

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
    if read_hold_queue() == True:
        return {
            "bitly": [],
            "sid": [],
            "shorturl": []
        }
    delay = read_delay()
    if delay != None:
        await asyncio.sleep(delay)

    generated_uid = {
        "bitly": generate_bitly(),
        "sid": generate_sid(),
        "shorturl": generate_shorturl()
    }
    batch_insert_bitly(generated_uid["bitly"], worker_id)
    batch_insert_sid(generated_uid["sid"], worker_id)
    batch_insert_shorturl(generated_uid["shorturl"], worker_id)
    count = count_total_items(generated_uid)
    db_add_to_queue_count(worker_id, count)
    return generated_uid

@app.post("/result")
async def submit_result(
    request: Request,
    status: str = Form(...),
    unresolved_url: str = Form(...),
    resolved_url: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    full_text_blob: Optional[str] = Form(None),
    scraped_at: Optional[str] = Form(None)
    ):
    try:
        worker_id = await get_worker_auth(
            worker_id=request.headers.get("X-Worker-ID"),
            api_key=request.headers.get("X-API-Key")
        )
    except HTTPException:
        return {"status": "restart", "message": "Worker auth failed"}
    db_subtract_from_queue_count(worker_id, 1)
    if 's.id' in unresolved_url:
        delete_sid_task('/'.join(unresolved_url.split('/')[3:]))
    elif 'bit.ly' in unresolved_url:
        delete_bitly_task('/'.join(unresolved_url.split('/')[3:]))
    elif 'shorturl.at' in unresolved_url:
        delete_shorturl_task('/'.join(unresolved_url.split('/')[3:]))

    if status == "success":
        missing_fields = []
        if not resolved_url:
            missing_fields.append("resolved_url")
        if not title:
            missing_fields.append("title")
        if not short_description:
            missing_fields.append("short_description")
        if not full_text_blob:
            missing_fields.append("full_text_blob")
        if not scraped_at:
            missing_fields.append("scraped_at")
        
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields for success status: {', '.join(missing_fields)}"
            )

        db_successful_result(worker_id,
            unresolved_url,
            resolved_url,
            title,
            short_description,
            full_text_blob)
        
        return {
            "status": "success",
            "message": "Result processed successfully",
        }
    
    
    elif status == "noredirect":
        db_noredirect_result(worker_id, unresolved_url)
        if 's.id' in unresolved_url:
            batch_insert_sid(['/'.join(unresolved_url.split('/')[3:])])
        elif 'bit.ly' in unresolved_url:
            batch_insert_bitly(['/'.join(unresolved_url.split('/')[3:])])
        elif 'shorturl.at' in unresolved_url:
            batch_insert_shorturl(['/'.join(unresolved_url.split('/')[3:])])
    
        return {
            "status": "success",
            "message": "Result processed successfully",
        }
    elif status == "notfound":
        db_notfound_result()
        return {
            "status": "success",
            "message": "Result processed successfully",
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Must be 'success', 'noredirect', or 'notfound'"
        )