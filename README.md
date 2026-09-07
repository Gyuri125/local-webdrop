# Local Webdrop

Local Webdrop is a lightweight, zero-configuration local network file transfer, media streaming, and live clipboard synchronization utility. It bridges desktop environments and mobile devices across the same Local Area Network (LAN) without relying on external cloud providers, third-party servers, or internet access.

---

## Key Benefits

* Complete Privacy: Data never leaves the local subnet; no telemetry, cloud storage, or external relay servers.
* Memory-Efficient Transfers: Asynchronous chunked transfer mechanism (5 MB chunk size) ensures high throughput with minimal RAM consumption.
* Instant Device Discovery: Zero-configuration networking via mDNS (Zeroconf), enabling direct resolution at `webdrop.local` alongside dynamic QR code pairing.
* Live Bi-Directional Synchronization: Low-latency WebSockets provide real-time clipboard updates and multi-device connection state tracking.
* In-Browser Streaming: Native HTTP byte-range support allows immediate playback of shared audio and video files on mobile clients without requiring full downloads.
* Direct Relay Mode: Facilitates direct file transfers between separate mobile clients utilizing the host machine as an in-memory relay.

---

## Multi-Monitor Operation

The desktop interface is built to function reliably in multi-display setups:

* Per-Monitor DPI Awareness: Window dimensions, typography, and QR code assets maintain consistent scaling when dragged across displays with mismatched resolutions or scale factors.
* Boundary-Safe Drag and Drop: The global Drag-and-Drop file staging layer operates across all active monitor coordinates, allowing direct file drops from primary or secondary screens.
* Window State Persistence: Closing the desktop window minimizes the service directly to the system tray, preserving viewport placement when restored on multi-screen workspaces.

---

## Keyboard Shortcuts

| Shortcut | Context | Action |
| :--- | :--- | :--- |
| `Ctrl + V` | Live Clipboard View | Paste system clipboard content directly into the live broadcast queue |
| `Ctrl + C` | Live Clipboard View | Copy the synchronized remote clipboard content to the local system |
| `Ctrl + S` | File Staging | Trigger archive packaging (ZIP) for all currently selected files |
| `Escape` | Web Client Modal | Close the active in-browser video/audio streaming overlay |
| `Ctrl + Q` | Desktop Application | Terminate the application, unregister mDNS services, and stop the server |

---

## Tech Stack

* Backend & Networking: Python 3.10+, FastAPI, Uvicorn, WebSockets, Zeroconf
* Desktop Interface: CustomTkinter, TkinterDnD2, Pystray
* Web Client: Vanilla JavaScript (ES6+), Tailwind CSS, HTML5 Media APIs
* System Integration: Psutil, Pillow, Plyer

---

## Architecture Overview

```text
[ Mobile / Web Client ] <==== WebSocket (State/Sync) ====> [ FastAPI Server ]
                         <==== HTTP Chunked / Stream =====>       ||
                                                                  \/
                                                       [ CustomTkinter GUI ]
```

---

## Getting Started

### Prerequisites

* Python 3.10 or higher
* All target devices connected to the same local network subnet

### Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/your-username/local-webdrop.git](https://github.com/your-username/local-webdrop.git)
   cd local-webdrop
   ```

2. Configure a virtual environment:
   ```bash
   python -m venv .venv
   
   # Windows:
   .venv\Scripts\activate
   
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. Install required dependencies:
   ```bash
   pip install fastapi uvicorn websockets customtkinter qrcode pillow psutil pystray plyer zeroconf tkinterdnd2
   ```

### Execution

Start the desktop controller and embedded web server:

```bash
python main.py
```

1. Open the generated network address (e.g., `http://192.168.1.X:8080` or `http://webdrop.local:8080`) on any client browser, or scan the QR code displayed on the desktop UI.
2. Drag and drop files directly onto the desktop interface to expose them to connected clients, or use the web interface to upload files back to the host.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for complete details.