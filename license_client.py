"""Email-only licensing: anonymous device identity, Firestore lease, Windows DPAPI.

No admin SDK, service account, password, offline activation or local active flag.
Server rules control activation, device binding and the single running session.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import secrets
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

CONFIG_PATH = Path(__file__).resolve().parent / "license_config.json"
LEASE_SECONDS = 120
RENEW_SECONDS = 25
SAFETY_SECONDS = 15
NETWORK_TIMEOUT = 8


class LicenseError(RuntimeError):
    pass


class ServiceError(LicenseError):
    def __init__(self, code: str, retryable: bool = False):
        self.code, self.retryable = code, retryable
        super().__init__("Connessione licenze non disponibile. Controlla Internet e riprova."
                         if retryable else "Verifica licenza rifiutata. Controlla email, attivazione e dispositivo.")


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+\-=?^_`{|}~]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+", value):
        raise LicenseError("Inserisci un indirizzo email valido.")
    return value


def load_config(path: Path = CONFIG_PATH) -> dict:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,29}", config["projectId"]):
            raise ValueError()
        if not re.fullmatch(r"AIza[\w-]{30,50}", config["apiKey"]):
            raise ValueError()
        if config.get("databaseId") != "(default)":
            raise ValueError()
        return config
    except (OSError, ValueError, KeyError, TypeError):
        raise LicenseError("Configurazione licenze mancante o non valida. Scarica la versione completa dell'app.") from None


def _json_request(url: str, data=None, *, token=None, method=None, form=False):
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = (urllib.parse.urlencode(data).encode() if form
                else json.dumps(data, separators=(",", ":")).encode())
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            return json.loads(response.read(1_048_576))
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read(65536)).get("error", {})
            code = detail.get("status") or detail.get("message", "REQUEST_FAILED").split(" : ")[0]
        except (ValueError, AttributeError):
            code = "REQUEST_FAILED"
        raise ServiceError(code, error.code in (408, 429, 500, 502, 503, 504)) from None
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        raise ServiceError("NETWORK", True) from None


def _dpapi(data: bytes, decrypt=False) -> bytes:
    if os.name != "nt":
        raise LicenseError("Questa edizione e' destinata a Windows.")
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise LicenseError("Impossibile leggere le credenziali su questo PC. Contatta il titolare per il ripristino dispositivo.")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


class ProtectedStore:
    def __init__(self, project: str, directory: Path | None = None):
        self.directory = directory or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VanishCam" / "licensing" / project
        self.path = self.directory / "identity.bin"

    def read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(_dpapi(self.path.read_bytes(), decrypt=True))
        except (ValueError, OSError):
            raise LicenseError("Dati licenza locali danneggiati. Richiedi il ripristino del dispositivo.") from None

    def save(self, data: dict):
        self.directory.mkdir(parents=True, exist_ok=True)
        encrypted = _dpapi(json.dumps(data).encode())
        descriptor, temporary = tempfile.mkstemp(prefix="identity-", dir=self.directory)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(encrypted)
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)


def device_id() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            machine = winreg.QueryValueEx(key, "MachineGuid")[0]
        if not isinstance(machine, str) or len(machine) < 16:
            raise ValueError()
        return hashlib.sha256(("VanishCam/license-device/v1/" + machine).encode()).hexdigest()
    except (OSError, ValueError, ImportError):
        raise LicenseError("Identificazione del dispositivo non riuscita. Riavvia l'app su un PC Windows.") from None


class LocalInstance:
    """All EXE editions share a per-user Windows mutex, before reading tokens."""
    def __init__(self, identity_path: Path):
        if os.name != "nt":
            raise LicenseError("Questa edizione richiede Windows.")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        self.kernel.CreateMutexW.restype = ctypes.c_void_p
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        name = "Local\\VanishCam-License-" + hashlib.sha256(str(identity_path).lower().encode()).hexdigest()
        self.handle = self.kernel.CreateMutexW(None, False, name)
        error = ctypes.get_last_error()
        if not self.handle:
            raise LicenseError("Impossibile bloccare la sessione locale.")
        if error == 183:
            self.close()
            raise LicenseError("Un'altra versione di VanishCam e' gia' aperta su questo PC. Chiudila prima di continuare.")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class DeviceAuth:
    def __init__(self, config: dict, store: ProtectedStore):
        self.config, self.store = config, store
        self.state = store.read()
        self.token = None
        self.expires = 0.0

    def authenticate(self):
        key = urllib.parse.quote(self.config["apiKey"], safe="")
        started = time.monotonic()
        if self.state.get("refreshToken"):
            result = _json_request("https://securetoken.googleapis.com/v1/token?key=" + key,
                                   {"grant_type": "refresh_token", "refresh_token": self.state["refreshToken"]}, form=True)
            self.token = result["id_token"]
            self.state.update(uid=result["user_id"], refreshToken=result["refresh_token"])
            ttl = int(result["expires_in"])
        else:
            result = _json_request("https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=" + key,
                                   {"returnSecureToken": True})
            self.token = result["idToken"]
            self.state.update(uid=result["localId"], refreshToken=result["refreshToken"])
            ttl = int(result["expiresIn"])
        self.expires = started + ttl - 90
        self.store.save(self.state)  # Save BEFORE binding; a lost response must not lose this identity.

    def id_token(self):
        if not self.token or time.monotonic() >= self.expires:
            self.authenticate()
        return self.token


def _fields(values: dict) -> dict:
    return {name: ({"booleanValue": value} if isinstance(value, bool) else {"stringValue": value})
            for name, value in values.items()}


def _value(doc, name, default=None):
    field = (doc or {}).get("fields", {}).get(name, {})
    return next(iter(field.values()), default)


class FirestoreLicense:
    def __init__(self, config: dict, auth: DeviceAuth, email: str, fingerprint: str, mode="full"):
        self.auth = auth
        self.email = normalize_email(email)
        self.fingerprint, self.mode = fingerprint, mode
        self.session_id = secrets.token_hex(32)
        self.base = f"projects/{config['projectId']}/databases/(default)/documents"
        self.api = "https://firestore.googleapis.com/v1/" + self.base

    def _request(self, suffix, data=None, *, method=None):
        return _json_request(self.api + suffix, data, token=self.auth.id_token(), method=method)

    def _document(self, collection):
        suffix = f"/{collection}/{urllib.parse.quote(self.email, safe='')}"
        try:
            return self._request(suffix)
        except ServiceError as error:
            if error.code == "NOT_FOUND":
                return None
            raise

    def _write(self, collection, values, time_field):
        return {"update": {"name": self.base + "/" + collection + "/" + self.email,
                           "fields": _fields(values)},
                "updateTransforms": [{"fieldPath": time_field, "setToServerValue": "REQUEST_TIME"}]}

    def _session_write(self, released=False):
        return self._write("licenseSessions", {
            "uid": self.auth.state["uid"], "deviceId": self.fingerprint,
            "sessionId": self.session_id, "mode": self.mode, "released": released,
        }, "lastSeenAt")

    def acquire(self):
        self.auth.id_token()
        for attempt in range(3):
            try:
                license_doc = self._document("licenses")
                if _value(license_doc, "active") is not True:
                    raise LicenseError("Licenza non attiva per questa email. Contatta il titolare dell'app.")
                binding = self._document("licenseBindings")
                if binding and (_value(binding, "uid") != self.auth.state["uid"]
                                or _value(binding, "deviceId") != self.fingerprint):
                    raise LicenseError("Questa licenza e' associata a un altro PC. Richiedi al titolare il cambio dispositivo.")
                # REST third-party tokens cannot open read/write transactions.
                # Use one atomic commit with optimistic preconditions instead.
                # Rules recheck activation, binding and lease at commit time.
                session = self._document("licenseSessions")
                writes = []
                if not binding:
                    binding_write = self._write("licenseBindings", {
                        "uid": self.auth.state["uid"], "deviceId": self.fingerprint,
                    }, "createdAt")
                    binding_write["currentDocument"] = {"exists": False}
                    writes.append(binding_write)
                session_write = self._session_write()
                session_write["currentDocument"] = ({"updateTime": session["updateTime"]}
                                                    if session else {"exists": False})
                writes.append(session_write)
                request_started = time.monotonic()
                self._request(":commit", {"writes": writes})
                return request_started + LEASE_SECONDS - SAFETY_SECONDS
            except ServiceError as error:
                if error.code in ("ABORTED", "FAILED_PRECONDITION", "ALREADY_EXISTS") and attempt < 2:
                    continue
                if error.code == "PERMISSION_DENIED":
                    raise LicenseError("Licenza gia' in uso o non disponibile. Chiudi l'altra app; dopo un arresto anomalo attendi 2 minuti.") from None
                raise
        raise LicenseError("Impossibile acquisire la licenza. Riprova.")

    def renew(self):
        write = self._session_write()
        write["currentDocument"] = {"exists": True}
        started = time.monotonic()
        self._request(":commit", {"writes": [write]})
        return started + LEASE_SECONDS - SAFETY_SECONDS

    def release(self):
        write = self._session_write(released=True)
        write["currentDocument"] = {"exists": True}
        self._request(":commit", {"writes": [write]})


class LicenseSession:
    def __init__(self, backend: FirestoreLicense, deadline: float, local_instance=None):
        self.backend, self.deadline = backend, deadline
        self.local_instance = local_instance
        self.error = None
        self.stop_event = threading.Event()
        self.worker = None

    def start(self):
        self.worker = threading.Thread(target=self._heartbeat, name="license-heartbeat", daemon=True)
        self.worker.start()
        return self

    def _heartbeat(self):
        delay = RENEW_SECONDS
        while not self.stop_event.wait(delay):
            if time.monotonic() >= self.deadline:
                self.error = "Verifica licenza scaduta. Riconnetti Internet e riavvia l'app."
                return
            try:
                deadline = self.backend.renew()
                if self.stop_event.is_set():
                    return
                # Never resume after the previous lease expired locally.
                if time.monotonic() >= self.deadline:
                    self.error = "Sessione licenza scaduta. Riavvia l'app."
                    return
                self.deadline = deadline
                delay = RENEW_SECONDS
            except ServiceError as error:
                if not error.retryable:
                    self.error = "Licenza disattivata, sessione revocata o dispositivo non autorizzato."
                    return
                delay = 8
            except Exception:
                self.error = "Verifica licenza interrotta. Riavvia l'app."
                return

    def ensure_valid(self):
        if self.error:
            raise LicenseError(self.error)
        if time.monotonic() >= self.deadline:
            raise LicenseError("Verifica online scaduta. Riconnetti Internet e riavvia l'app.")

    def close(self):
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=NETWORK_TIMEOUT + 2)
        try:
            self.backend.release()
        except Exception:
            pass  # Server lease expires even if the PC crashes or goes offline.
        finally:
            if self.local_instance:
                self.local_instance.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _email_dialog(auth: DeviceAuth, config: dict, fingerprint: str):
    """One email field; network work stays off Tk's event loop."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("VanishCam - Attiva licenza")
    root.resizable(False, False)
    panel = ttk.Frame(root, padding=26)
    panel.pack()
    ttk.Label(panel, text="Attiva VanishCam", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(panel, text="Inserisci l'email associata alla tua licenza.\nLa licenza viene associata a questo PC.",
              padding=(0, 10, 0, 15)).pack(anchor="w")
    email = tk.StringVar(value=auth.state.get("email", ""))
    entry = ttk.Entry(panel, textvariable=email, width=48)
    entry.pack(fill="x")
    status = tk.StringVar()
    ttk.Label(panel, textvariable=status, wraplength=360, padding=(0, 12)).pack(fill="x")
    pending = False
    result = None
    events = queue.Queue()

    def activate():
        nonlocal pending
        if pending:
            return
        try:
            address = normalize_email(email.get())
        except LicenseError as error:
            status.set(str(error))
            return
        pending = True
        entry.configure(state="disabled")
        button.configure(state="disabled")
        status.set("Verifica della licenza in corso...")

        def work():
            backend = FirestoreLicense(config, auth, address, fingerprint)
            try:
                deadline = backend.acquire()
                auth.state["email"] = address
                auth.store.save(auth.state)
                events.put((backend, deadline, None))
            except Exception as error:
                events.put((backend, None, error))
        threading.Thread(target=work, daemon=True).start()

    def poll():
        nonlocal pending, result
        try:
            backend, deadline, error = events.get_nowait()
        except queue.Empty:
            root.after(80, poll)
            return
        pending = False
        if error:
            status.set(str(error) if isinstance(error, LicenseError) else "Verifica non riuscita. Riprova.")
            button.configure(state="normal")
            entry.configure(state="normal")
            root.after(80, poll)
        else:
            result = (backend, deadline)
            root.destroy()

    def cancel():
        # A successful in-flight acquisition must not leave a live session
        # behind a dismissed activation window. Wait for the bounded request.
        if pending:
            status.set("Attendi il completamento della verifica, poi chiudi la finestra.")
        else:
            root.destroy()

    button = ttk.Button(panel, text="Attiva e avvia", command=activate)
    button.pack(fill="x")
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.bind("<Return>", lambda event: activate())
    root.bind("<Escape>", lambda event: cancel())
    root.update_idletasks()
    root.geometry(f"+{max(0, (root.winfo_screenwidth()-root.winfo_width())//2)}+{max(0, (root.winfo_screenheight()-root.winfo_height())//2)}")
    entry.focus_set()
    root.after(80, poll)
    root.mainloop()
    return result


def activate_license():
    config = load_config()
    store = ProtectedStore(config["projectId"])
    instance = LocalInstance(store.path)
    try:
        auth = DeviceAuth(config, store)
        fingerprint = device_id()
        # Returning users still perform a fresh online acquire on every start.
        saved_email = auth.state.get("email")
        result = None
        if saved_email:
            backend = FirestoreLicense(config, auth, saved_email, fingerprint)
            try:
                result = (backend, backend.acquire())
            except LicenseError:
                pass  # Show the email form so a typo/account can be corrected.
        if result is None:
            result = _email_dialog(auth, config, fingerprint)
        if result is None:
            instance.close()
            return None
        backend, deadline = result
        return LicenseSession(backend, deadline, instance).start()
    except Exception:
        instance.close()
        raise


def show_license_error(message):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showerror("VanishCam - Licenza", str(message), parent=root)
    finally:
        root.destroy()
