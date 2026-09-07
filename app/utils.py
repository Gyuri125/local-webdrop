import os
import re
import socket
import base64
from io import BytesIO
from PIL import Image as PilImage

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except Exception:
    PLYER_AVAILABLE = False

try:
    from zeroconf import ServiceInfo, Zeroconf
    ZC_AVAILABLE = True
except Exception:
    ZC_AVAILABLE = False


def get_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def setup_zeroconf(ip: str, port: int):
    if not ZC_AVAILABLE:
        return None
    try:
        info = ServiceInfo(
            "_http._tcp.local.",
            "Webdrop._http._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=port,
            server="webdrop.local."
        )
        zc = Zeroconf()
        zc.register_service(info)
        return zc
    except Exception:
        return None


def show_native_notification(title: str, msg: str):
    if PLYER_AVAILABLE:
        try:
            notification.notify(title=title, message=msg, app_name="Webdrop Pro", timeout=5)
        except Exception:
            pass


def extract_text_from_rtf(rtf_path: str):
    try:
        with open(rtf_path, "rb") as f:
            raw_data = f.read()
        content = raw_data.decode("utf-8", errors="ignore")
        if r'{\rtf1' in content:
            content = content[content.find(r'{\rtf1'):]
        content = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes.fromhex(m.group(1)).decode('cp1252', 'ignore'), content)
        content = re.sub(r"\\u(-?[0-9]+) ?", lambda m: chr(int(m.group(1)) & 0xFFFF), content)
        text = re.sub(r'\\[a-zA-Z0-9\-]+ ?', '', content)
        clean_text = "\n".join([line.strip() for line in re.sub(r'[{}]', '', text).splitlines() if line.strip()])
        if clean_text:
            txt_path = os.path.splitext(rtf_path)[0] + "_tisztitott.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(clean_text)
            return txt_path
    except Exception:
        pass
    return None


def generate_thumbnail(file_path: str):
    try:
        if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            with PilImage.open(file_path) as img:
                img.thumbnail((200, 200))
                buffered = BytesIO()
                img.save(buffered, format="JPEG")
                return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
    except Exception:
        pass
    return None