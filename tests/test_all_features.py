"""
Local Webdrop - Comprehensive Feature & Integration Test Suite
Tests every major subsystem:
  1. SSL / TLS Certificate Auto-Generation & mDNS Setup
  2. Internationalization (i18n) Engine
  3. Web Client Template & Static Assets
  4. PIN Security, Token Authentication & IP Lockout Protection
  5. Chunked File Upload Pipeline & Storage Guard (HTTP 507)
  6. Multi-Device Upload Isolation (Race Condition Prevention)
  7. File Download & Byte-Range Media Streaming
  8. One-Click "Download All as ZIP" with Background Cleanup
  9. WebSocket Client Hub & Bidirectional Live Clipboard
  10. System Utilities (RTF Text Extraction, Thumbnails, Size Formatting)
"""

import os
import io
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zipfile
import tempfile
from unittest.mock import patch
from collections import namedtuple
import pytest
from fastapi.testclient import TestClient

from app.state import state
from app.server import app, format_file_size, get_template_path
from app.utils import (
    get_ip,
    ensure_ssl_certificates,
    extract_text_from_rtf,
    generate_thumbnail
)
from app.i18n import t, LANGUAGE_MAP

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset transient state before each test case."""
    state.authenticated_tokens.clear()
    state.failed_attempts.clear()
    state.lockout_until.clear()
    state.shared_files.clear()
    state.relay_files.clear()
    state.clipboard_text = ""
    state.pin_enabled = False
    state.current_pin = "123456"
    state.incoming_mode = "Normal"


# ==============================================================================
# 1. SSL / TLS & Network Utilities
# ==============================================================================

def test_ip_resolution():
    ip = get_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4

def test_ssl_auto_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        cert_p = os.path.join(tmpdir, "test_cert.pem")
        key_p = os.path.join(tmpdir, "test_key.pem")
        
        c, k = ensure_ssl_certificates(cert_path=cert_p, key_path=key_p, ip="192.168.1.100")
        assert os.path.exists(c)
        assert os.path.exists(k)
        
        with open(c, "r", encoding="utf-8") as f:
            cert_content = f.read()
            assert "BEGIN CERTIFICATE" in cert_content
            
        with open(k, "r", encoding="utf-8") as f:
            key_content = f.read()
            assert "BEGIN RSA PRIVATE KEY" in key_content


# ==============================================================================
# 2. Internationalization (i18n)
# ==============================================================================

def test_i18n_translations():
    for lang_code in ["en", "hu", "de", "ru"]:
        assert t("app_title", lang_code) == "Webdrop"
        assert t("exit", lang_code) != ""
        assert t("tab_send", lang_code) != ""
    
    assert t("receiving", "en", filename="test.mp4") == "Receiving: test.mp4"
    assert t("receiving", "hu", filename="test.mp4") == "Fogadás: test.mp4"
    assert "Magyar" in LANGUAGE_MAP
    assert LANGUAGE_MAP["Magyar"] == "hu"


# ==============================================================================
# 3. Web Client Template & Static Elements
# ==============================================================================

def test_web_index_serving_and_elements():
    tmpl_path = get_template_path()
    assert os.path.exists(tmpl_path)
    
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    
    # Check essential UI controls
    assert "Webdrop" in html
    assert "dropZone" in html
    assert "clipboard" in html
    assert "speedText" in html
    assert "etaText" in html
    assert "btnDownloadAll" in html
    assert "toast" in html
    assert "pinModal" in html


# ==============================================================================
# 4. PIN Protection, Tokens & Anti-Brute-Force Rate Limiting
# ==============================================================================

def test_pin_status():
    state.pin_enabled = False
    assert client.get("/pin_status").json() == {"enabled": False}

    state.pin_enabled = True
    assert client.get("/pin_status").json() == {"enabled": True}

def test_verify_pin_success():
    state.pin_enabled = True
    state.current_pin = "482619"
    res = client.post("/verify_pin", json={"pin": "482619"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "token" in data
    assert data["token"] in state.authenticated_tokens

def test_verify_pin_brute_force_lockout():
    state.pin_enabled = True
    state.current_pin = "999999"

    for _ in range(4):
        res = client.post("/verify_pin", json={"pin": "000000"})
        assert res.status_code == 403
        assert res.json()["status"] == "error"

    # 5th attempt triggers lockout (HTTP 429)
    res = client.post("/verify_pin", json={"pin": "000000"})
    assert res.status_code == 429
    assert res.json()["status"] == "locked"
    assert res.json()["remaining"] > 0

def test_unauthorized_endpoints_blocked_when_pin_enabled():
    state.pin_enabled = True
    state.current_pin = "111111"

    assert client.get("/upload_status?filename=a.txt&target=pc").status_code == 401
    assert client.get("/download/0").status_code == 401
    assert client.get("/download_relay/a.txt").status_code == 401
    assert client.get("/download_all_zip").status_code == 401


# ==============================================================================
# 5. Chunked Upload Pipeline & Storage Guard
# ==============================================================================

def test_chunked_upload_assembly():
    with tempfile.TemporaryDirectory() as tmpdir:
        state.save_dir = tmpdir
        filename = "test_document.txt"
        
        c0 = b"First chunk data "
        c1 = b"Second chunk data "
        c2 = b"Final chunk data."
        full_content = c0 + c1 + c2
        
        # Upload chunk 0
        r0 = client.post("/upload", data={
            "filename": filename, "chunk_index": 0, "total_chunks": 3,
            "file_size": len(full_content), "target": "pc", "sender": "ClientA"
        }, files={"file": ("c0", c0, "application/octet-stream")})
        assert r0.status_code == 200

        # Upload chunk 1
        r1 = client.post("/upload", data={
            "filename": filename, "chunk_index": 1, "total_chunks": 3,
            "file_size": len(full_content), "target": "pc", "sender": "ClientA"
        }, files={"file": ("c1", c1, "application/octet-stream")})
        assert r1.status_code == 200

        # Upload chunk 2
        r2 = client.post("/upload", data={
            "filename": filename, "chunk_index": 2, "total_chunks": 3,
            "file_size": len(full_content), "target": "pc", "sender": "ClientA"
        }, files={"file": ("c2", c2, "application/octet-stream")})
        assert r2.status_code == 200

        # Validate file on disk
        dest = os.path.join(tmpdir, filename)
        assert os.path.exists(dest)
        with open(dest, "rb") as f:
            assert f.read() == full_content

def test_storage_guard_http_507():
    with tempfile.TemporaryDirectory() as tmpdir:
        state.save_dir = tmpdir
        Usage = namedtuple("usage", ["total", "used", "free"])
        
        # Simulate only 500 bytes free disk space
        with patch("shutil.disk_usage", return_value=Usage(10000, 9500, 500)):
            res = client.post("/upload", data={
                "filename": "heavy_video.mp4", "chunk_index": 0, "total_chunks": 5,
                "file_size": 1000000, "target": "pc", "sender": "Mobile"
            }, files={"file": ("c0", b"data", "application/octet-stream")})
            assert res.status_code == 507
            assert "Insufficient storage" in res.json().get("detail", "")


# ==============================================================================
# 6. Multi-Device Upload Isolation (Race Condition Prevention)
# ==============================================================================

def test_concurrent_upload_isolation():
    with tempfile.TemporaryDirectory() as tmpdir:
        state.save_dir = tmpdir
        filename = "photo.jpg"

        # Sender 1 begins upload
        client.post("/upload", data={
            "filename": filename, "chunk_index": 0, "total_chunks": 2,
            "file_size": 20, "target": "pc", "sender": "iPhone-1"
        }, files={"file": ("c0", b"PHONE1-START-", "application/octet-stream")})

        # Sender 2 begins upload with exact same filename
        client.post("/upload", data={
            "filename": filename, "chunk_index": 0, "total_chunks": 2,
            "file_size": 20, "target": "pc", "sender": "Android-2"
        }, files={"file": ("c0", b"PHONE2-START-", "application/octet-stream")})

        # Sender 1 finishes
        client.post("/upload", data={
            "filename": filename, "chunk_index": 1, "total_chunks": 2,
            "file_size": 20, "target": "pc", "sender": "iPhone-1"
        }, files={"file": ("c1", b"PHONE1-END", "application/octet-stream")})

        # Sender 2 finishes
        client.post("/upload", data={
            "filename": filename, "chunk_index": 1, "total_chunks": 2,
            "file_size": 20, "target": "pc", "sender": "Android-2"
        }, files={"file": ("c1", b"PHONE2-END", "application/octet-stream")})

        f1 = os.path.join(tmpdir, "photo.jpg")
        f2 = os.path.join(tmpdir, "photo_1.jpg")
        assert os.path.exists(f1)
        assert os.path.exists(f2)
        with open(f1, "rb") as f:
            assert f.read() == b"PHONE1-START-PHONE1-END"
        with open(f2, "rb") as f:
            assert f.read() == b"PHONE2-START-PHONE2-END"


# ==============================================================================
# 7. File Download & Byte-Range Streaming
# ==============================================================================

def test_download_and_range_streaming():
    with tempfile.TemporaryDirectory() as tmpdir:
        f = os.path.join(tmpdir, "sample_media.mp4")
        sample_data = b"0123456789ABCDEF" * 100
        with open(f, "wb") as file:
            file.write(sample_data)
            
        state.shared_files = [f]

        # Full download
        res = client.get("/download/0")
        assert res.status_code == 200
        assert res.content == sample_data
        assert res.headers.get("accept-ranges") == "bytes"

        # Byte-range request (streaming playback)
        range_res = client.get("/download/0", headers={"Range": "bytes=0-15"})
        assert range_res.status_code == 206
        assert range_res.content == sample_data[:16]

        # Bounds checking
        assert client.get("/download/-1").status_code == 404
        assert client.get("/download/999").status_code == 404


# ==============================================================================
# 8. "Download All as ZIP" (Web Bundling)
# ==============================================================================

def test_download_all_zip():
    assert client.get("/download_all_zip").status_code == 404

    with tempfile.TemporaryDirectory() as tmpdir:
        f1 = os.path.join(tmpdir, "doc1.txt")
        f2 = os.path.join(tmpdir, "doc2.txt")
        with open(f1, "w", encoding="utf-8") as file:
            file.write("Content of Document 1")
        with open(f2, "w", encoding="utf-8") as file:
            file.write("Content of Document 2")

        state.shared_files = [f1, f2]
        res = client.get("/download_all_zip")
        assert res.status_code == 200
        assert res.headers.get("content-type") == "application/zip"
        assert "Webdrop_" in res.headers.get("content-disposition", "")

        zf = zipfile.ZipFile(io.BytesIO(res.content))
        namelist = zf.namelist()
        assert "doc1.txt" in namelist
        assert "doc2.txt" in namelist
        assert zf.read("doc1.txt") == b"Content of Document 1"
        assert zf.read("doc2.txt") == b"Content of Document 2"


# ==============================================================================
# 9. WebSocket Client Hub & Live Clipboard Sync
# ==============================================================================

def test_websocket_registration_and_clipboard():
    with client.websocket_connect("/ws") as ws:
        # Register device
        ws.send_json({"event": "register", "name": "Tablet-Pro", "token": ""})
        msg = ws.receive_json()
        assert msg.get("event") == "client_list"
        assert "Tablet-Pro" in msg.get("clients", [])

        # Broadcast clipboard
        ws.send_json({"event": "clipboard", "text": "Synchronized text via WS"})
        assert state.clipboard_text == "Synchronized text via WS"


# ==============================================================================
# 10. File Helpers (RTF Extraction, Thumbnails, Size Formatting)
# ==============================================================================

def test_system_utilities():
    assert format_file_size(256) == "256 B"
    assert format_file_size(1024 * 50) == "50.0 KB"
    assert format_file_size(1024 * 1024 * 15) == "15.0 MB"
    assert format_file_size(1024 * 1024 * 1024 * 2) == "2.00 GB"

    with tempfile.TemporaryDirectory() as tmpdir:
        rtf_file = os.path.join(tmpdir, "sample.rtf")
        with open(rtf_file, "w", encoding="utf-8") as f:
            f.write(r"{\rtf1\ansi Test RTF content}")
        extracted = extract_text_from_rtf(rtf_file)
        assert extracted is not None
        assert os.path.exists(extracted)
        with open(extracted, "r", encoding="utf-8") as f:
            assert "Test RTF content" in f.read()

        png_file = os.path.join(tmpdir, "sample.png")
        from PIL import Image as PilImage
        img = PilImage.new("RGB", (300, 300), color="blue")
        img.save(png_file)
        thumb = generate_thumbnail(png_file)
        assert thumb is not None
        assert thumb.startswith("data:image/jpeg;base64,")
