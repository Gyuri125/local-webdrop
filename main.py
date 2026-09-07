import threading
import asyncio
import uvicorn
from tkinter import messagebox

from app.state import state
from app.utils import get_ip, setup_zeroconf
from app.server import app, broadcast_stats
from app.gui import WebdropGUI


def silence_winerror_10054(loop, context):
    """Elnyeli az ártalmatlan Windows-specifikus ConnectionResetError (10054) kivételeket."""
    exception = context.get("exception")
    msg = str(context.get("message", ""))
    if isinstance(exception, ConnectionResetError) or "10054" in str(exception) or "10054" in msg:
        return
    loop.default_exception_handler(context)


def run_fastapi():
    state.server_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(state.server_loop)

    # Elnémítjuk a Windowsos socket lezárási konzolzajt
    state.server_loop.set_exception_handler(silence_winerror_10054)

    state.server_loop.create_task(broadcast_stats())

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="warning",
        ssl_keyfile="webdrop_key.pem",
        ssl_certfile="webdrop_cert.pem"
    )
    server = uvicorn.Server(config)
    state.server_loop.run_until_complete(server.serve())


if __name__ == "__main__":
    ip = get_ip()
    if ip == '127.0.0.1':
        messagebox.showerror("Hálózati hiba", "Nem található aktív hálózati kapcsolat!")
        exit(1)

    zc = setup_zeroconf(ip, 8080)
    server_thread = threading.Thread(target=run_fastapi, daemon=True)
    server_thread.start()

    gui = WebdropGUI(ip, 8080, zc_instance=zc)
    gui.mainloop()