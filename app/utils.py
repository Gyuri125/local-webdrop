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


def ensure_ssl_certificates(cert_path: str = "webdrop_cert.pem", key_path: str = "webdrop_key.pem", ip: str = None) -> tuple[str, str]:
    """
    Checks if SSL certificate and private key exist. If missing, automatically generates
    a secure self-signed X.509 certificate and RSA keypair valid for LAN & local resolution.
    """
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    try:
        import ipaddress
        import datetime
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        # 2048-bit RSA key
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "webdrop.local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Local Webdrop"),
        ])

        alt_names = [
            x509.DNSName("webdrop.local"),
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]

        if ip and ip != "127.0.0.1":
            try:
                alt_names.append(x509.IPAddress(ipaddress.ip_address(ip)))
            except Exception:
                pass

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365 * 3))
            .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
            .sign(key, hashes.SHA256())
        )

        with open(key_path, "wb") as f:
            f.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        return cert_path, key_path
    except Exception as e:
        import shutil
        import subprocess
        if shutil.which("openssl"):
            try:
                cmd = [
                    "openssl", "req", "-x509", "-newkey", "rsa:2048",
                    "-keyout", key_path, "-out", cert_path,
                    "-days", "1095", "-nodes", "-subj", "/CN=webdrop.local"
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return cert_path, key_path
            except Exception:
                pass
        raise RuntimeError(
            f"Could not generate SSL certificates automatically: {e}. "
            f"Please generate {cert_path} and {key_path} using OpenSSL."
        )


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