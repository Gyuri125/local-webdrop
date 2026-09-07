import os
import time
import secrets
import zipfile
import asyncio
import psutil
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, Form, File, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.state import state
from app.utils import extract_text_from_rtf, generate_thumbnail, show_native_notification

app = FastAPI(title="Local Webdrop Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "index.html")


def is_ip_locked(client_ip: str) -> tuple[bool, int]:
    now = time.time()
    locked_until = state.lockout_until.get(client_ip, 0)
    if now < locked_until:
        return True, int(locked_until - now)
    return False, 0


def register_failed_attempt(client_ip: str) -> int:
    attempts = state.failed_attempts.get(client_ip, 0) + 1
    state.failed_attempts[client_ip] = attempts
    if attempts >= 5:
        state.lockout_until[client_ip] = time.time() + 60
        state.failed_attempts[client_ip] = 0
        return 60
    return 0


def reset_ip_lock(client_ip: str):
    state.failed_attempts.pop(client_ip, None)
    state.lockout_until.pop(client_ip, None)


def is_authorized(token: str) -> bool:
    if not state.pin_enabled:
        return True
    return token in state.authenticated_tokens


@app.get("/", response_class=HTMLResponse)
async def get_index():
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Webdrop: index.html not found!</h1>"


@app.get("/pin_status")
async def get_pin_status():
    return JSONResponse({"enabled": state.pin_enabled})


@app.post("/verify_pin")
async def verify_pin(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    locked, remaining = is_ip_locked(client_ip)
    if locked:
        return JSONResponse({"status": "locked", "remaining": remaining}, status_code=429)

    body = await request.json()
    pin = str(body.get("pin", "")).strip()

    if not state.pin_enabled or pin == state.current_pin:
        reset_ip_lock(client_ip)
        token = secrets.token_hex(16)
        state.authenticated_tokens.add(token)
        return JSONResponse({"status": "success", "token": token})

    lock_time = register_failed_attempt(client_ip)
    if lock_time > 0:
        return JSONResponse({"status": "locked", "remaining": lock_time}, status_code=429)
    return JSONResponse({"status": "error", "message": "Invalid PIN"}, status_code=403)


@app.get("/upload_status")
async def check_upload_status(filename: str, target: str, token: str = ""):
    if not is_authorized(token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    clean_name = os.path.basename(filename)
    save_path = state.save_dir if target == "pc" else os.path.join(state.save_dir, "Relay_Temp")
    act_file = state.active_uploads.get(clean_name, clean_name)
    target_path = os.path.join(save_path, act_file)
    if os.path.exists(target_path):
        chunks = os.path.getsize(target_path) // (5 * 1024 * 1024)
        return {"received_chunks": chunks}
    return {"received_chunks": 0}


@app.post("/upload")
async def upload_chunk(
    file: UploadFile = File(...),
    filename: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file_size: int = Form(...),
    target: str = Form("pc"),
    sender: str = Form("Client"),
    token: str = Form("")
):
    if not is_authorized(token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        clean_filename = os.path.basename(filename)
        if not clean_filename:
            raise HTTPException(status_code=400, detail="Invalid filename.")

        is_relay = target != "pc"
        save_path = os.path.join(state.save_dir, "Relay_Temp") if is_relay else state.save_dir
        os.makedirs(save_path, exist_ok=True)

        if chunk_index == 0:
            b, ext = os.path.splitext(clean_filename)
            unique_name = clean_filename
            c = 1
            while os.path.exists(os.path.join(save_path, unique_name)):
                unique_name = f"{b}_{c}{ext}"
                c += 1
            state.active_uploads[clean_filename] = unique_name

        act_file = state.active_uploads.get(clean_filename, clean_filename)
        target_path = os.path.join(save_path, act_file)

        with open(target_path, "ab") as f:
            f.write(await file.read())

        if state.gui_instance and not is_relay:
            state.gui_instance.update_upload_progress(act_file, chunk_index, total_chunks)

        if chunk_index == total_chunks - 1:
            if is_relay:
                state.relay_files[act_file] = target_path
                payload = [{"filename": act_file, "thumbnail": None, "url": f"/download_relay/{act_file}", "source": sender}]
                if state.server_loop:
                    asyncio.run_coroutine_threadsafe(
                        notify_clients({"event": "files_shared", "files": payload, "is_relay": True}, target_name=target),
                        state.server_loop
                    )
                if state.gui_instance:
                    state.gui_instance.log(f"Relay ({sender} -> {target}): {act_file}")
            else:
                txt_path = extract_text_from_rtf(target_path) if act_file.lower().endswith('.rtf') else None
                fin_path = target_path

                if state.incoming_mode == "Timestamp Mappa":
                    ts_dir = os.path.join(state.save_dir, datetime.now().strftime("Drop_%Y%m%d_%H%M%S"))
                    os.makedirs(ts_dir, exist_ok=True)
                    os.rename(target_path, os.path.join(ts_dir, act_file))
                    if txt_path and os.path.exists(txt_path):
                        os.rename(txt_path, os.path.join(ts_dir, os.path.basename(txt_path)))
                    fin_path = ts_dir
                elif state.incoming_mode == "Automata ZIP":
                    zip_path = os.path.join(state.save_dir, act_file + ".zip")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                        z.write(target_path, act_file)
                        if txt_path and os.path.exists(txt_path):
                            z.write(txt_path, os.path.basename(txt_path))
                            os.remove(txt_path)
                    os.remove(target_path)
                    fin_path = zip_path

                if state.gui_instance:
                    state.gui_instance.log(f"Received: {act_file}", "SUCCESS")
                    show_native_notification("Received", f"File: {act_file}")
                    state.gui_instance.add_to_history("RECEIVED", act_file, fin_path)

            state.active_uploads.pop(clean_filename, None)

        return {"status": "success"}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/download/{file_index}")
async def download_file(file_index: int, token: str = ""):
    if not is_authorized(token):
        return HTMLResponse("Unauthorized - Valid PIN session required", status_code=401)

    if file_index < len(state.shared_files):
        target_path = state.shared_files[file_index]
        if os.path.exists(target_path):
            if state.gui_instance:
                state.gui_instance.add_to_history("SENT/STREAM", os.path.basename(target_path), target_path)
            return FileResponse(target_path, headers={"Accept-Ranges": "bytes"})
    return JSONResponse({"error": "File not found"}, status_code=404)


@app.get("/download_relay/{filename}")
async def download_relay(filename: str, token: str = ""):
    if not is_authorized(token):
        return HTMLResponse("Unauthorized - Valid PIN session required", status_code=401)

    clean_name = os.path.basename(filename)
    if clean_name in state.relay_files and os.path.exists(state.relay_files[clean_name]):
        target = state.relay_files[clean_name]

        async def chunk_gen():
            with open(target, "rb") as f:
                while chunk := f.read(512 * 1024):
                    yield chunk
                    await asyncio.sleep(0.001)
            try:
                os.remove(target)
                state.relay_files.pop(clean_name, None)
            except Exception:
                pass

        return StreamingResponse(chunk_gen(), media_type="application/octet-stream",
                                 headers={"Content-Disposition": f"attachment; filename={clean_name}"})
    return JSONResponse({"error": "File not found"}, status_code=404)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.connected_clients[websocket] = {"name": "Unknown", "authenticated": False}

    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")

            if event == "register":
                token = data.get("token", "")
                is_auth = is_authorized(token)
                state.connected_clients[websocket] = {
                    "name": data.get("name", "Unknown"),
                    "authenticated": is_auth
                }

                if state.gui_instance:
                    state.gui_instance.safe_update_clients()
                await broadcast_client_list()

                if not is_auth and state.pin_enabled:
                    await websocket.send_json({"event": "auth_required"})
                else:
                    await send_initial_data(websocket)

            elif event == "authenticate":
                token = data.get("token", "")
                if is_authorized(token):
                    state.connected_clients[websocket]["authenticated"] = True
                    await websocket.send_json({"event": "auth_success"})
                    await send_initial_data(websocket)
                    await broadcast_client_list()
                else:
                    await websocket.send_json({"event": "auth_required"})

            elif event == "clipboard":
                client_info = state.connected_clients.get(websocket, {})
                if state.pin_enabled and not client_info.get("authenticated", False):
                    await websocket.send_json({"event": "auth_required"})
                    continue

                state.clipboard_text = data.get("text", "")
                if state.gui_instance:
                    state.gui_instance.sync_clipboard_to_pc_ui(state.clipboard_text)
                    show_native_notification("Clipboard", "Clipboard synchronized from web.")
                await notify_clients({"event": "clipboard", "text": state.clipboard_text}, exclude=websocket)

    except WebSocketDisconnect:
        state.connected_clients.pop(websocket, None)
        if state.gui_instance:
            state.gui_instance.safe_update_clients()
        await broadcast_client_list()


async def send_initial_data(websocket: WebSocket):
    if state.shared_files:
        payload = [
            {"filename": os.path.basename(p), "thumbnail": generate_thumbnail(p), "url": f"/download/{i}", "source": "pc"}
            for i, p in enumerate(state.shared_files)
        ]
        await websocket.send_json({"event": "files_shared", "files": payload, "is_relay": False})
    if state.clipboard_text:
        await websocket.send_json({"event": "clipboard", "text": state.clipboard_text})


async def broadcast_client_list():
    names = list(set([
        info["name"] for info in state.connected_clients.values()
        if info["name"] != "Unknown" and (not state.pin_enabled or info["authenticated"])
    ]))
    await notify_clients({"event": "client_list", "clients": names})


async def notify_clients(event_data, exclude=None, target_name=None):
    for ws_client, info in list(state.connected_clients.items()):
        if ws_client == exclude:
            continue
        if target_name and info["name"] != target_name:
            continue
        if state.pin_enabled and not info["authenticated"] and event_data.get("event") not in ("security_status", "auth_required"):
            continue
        try:
            await ws_client.send_json(event_data)
        except Exception:
            state.connected_clients.pop(ws_client, None)


async def broadcast_stats():
    while True:
        if state.connected_clients:
            await notify_clients({
                "event": "server_stats",
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent
            })
        await asyncio.sleep(2)