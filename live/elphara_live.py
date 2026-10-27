#!/usr/bin/env python3
"""
Elphara Fit Live : lit Wii Fit Plus dans Dolphin et envoie les valeurs
en direct à l'appli Elphara Fit (téléphone) et à l'overlay OBS.

Utilisation :
  python elphara_live.py          -> mode normal (Dolphin + Wii Fit Plus lancés)
  python elphara_live.py --demo   -> envoie de fausses valeurs pour tester l'appli
  python elphara_live.py --watch  -> affiche aussi les valeurs lues dans la console

Les adresses mémoire à lire se règlent dans elphara_live.json (créé au premier lancement).
"""
import json
import math
import os
import random
import string
import struct
import sys
import time
import urllib.error
import urllib.request

SUPABASE_URL = "https://zpxkizajcgyshtqzahrq.supabase.co"
SUPABASE_KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpweGtpemFqY2d5c2h0cXph"
                "aHJxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE1ODU5ODEsImV4cCI6MjEwNzE2MTk4MX0.g7U6zqRtM4MVujREaRjvCJjxDBxEiJWoahfz9OYFgrs")
APP_URL = "https://elpharaa.github.io/Wii-fit-app-Elphara/"
HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "elphara_live.json")
TYPES = {"u8": (">B", 1), "s8": (">b", 1), "u16": (">H", 2), "s16": (">h", 2),
         "u32": (">I", 4), "s32": (">i", 4), "float": (">f", 4)}
GAMES = {"RFPP": "Wii Fit Plus (Europe)", "RFPE": "Wii Fit Plus (USA)", "RFPJ": "Wii Fit Plus (Japon)",
         "RFNP": "Wii Fit (Europe)", "RFNE": "Wii Fit (USA)", "RFNJ": "Wii Fit (Japon)"}

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def new_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(6))


def default_cfg():
    return {
        "code": new_code(),
        "frequence_hz": 4,
        "valeurs": [
            {"nom": "cop_x", "libelle": "Équilibre gauche/droite", "adresse": "0x80000000", "type": "float",
             "plage": [-1, 1], "actif": False},
            {"nom": "cop_y", "libelle": "Équilibre avant/arrière", "adresse": "0x80000000", "type": "float",
             "plage": [-1, 1], "actif": False},
            {"nom": "poids", "libelle": "Poids", "adresse": "0x80000000", "type": "float", "unite": "kg",
             "actif": False},
            {"nom": "score", "libelle": "Score", "adresse": "0x80000000", "type": "u32", "actif": False},
        ],
    }


def load_cfg():
    if not os.path.exists(CFG_PATH):
        cfg = default_cfg()
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print("Fichier de réglages créé :", CFG_PATH)
        return cfg
    with open(CFG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("code"):
        cfg["code"] = new_code()
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def send(code, payload):
    body = json.dumps({"messages": [{"topic": "elphara-" + code, "event": "state", "payload": payload}]}).encode()
    req = urllib.request.Request(SUPABASE_URL + "/realtime/v1/api/broadcast", data=body, method="POST", headers={
        "apikey": SUPABASE_KEY, "Authorization": "Bearer " + SUPABASE_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        print("Envoi refusé par le serveur :", e.code, e.read()[:200])
    except Exception as e:
        print("Envoi impossible (connexion internet ?) :", e)
    return False


def meta_of(values):
    return {v["nom"]: {k: v[k] for k in ("libelle", "unite", "plage", "noms") if k in v} for v in values}


def to_addr(x):
    return int(str(x), 16) if isinstance(x, str) else int(x)


def read_value(dme, v):
    addr = to_addr(v["adresse"])
    for off in v.get("pointeur", []):
        ptr = struct.unpack(">I", dme.read_bytes(addr, 4))[0]
        if not (0x80000000 <= ptr < 0x94000000):
            return None
        addr = ptr + to_addr(off)
    fmt, size = TYPES[v.get("type", "u32")]
    val = struct.unpack(fmt, dme.read_bytes(addr, size))[0]
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        val = round(val, 3)
    if "facteur" in v:
        val = round(val * v["facteur"], 3)
    if "noms" in v:
        return v["noms"].get(str(val), val)
    return val


def banner(code, demo):
    print("=" * 56)
    print("  Elphara Fit Live" + ("  (mode démo)" if demo else ""))
    print("  Ton code :", code)
    print("  Sur le téléphone : onglet Jeux > En direct > tape ce code")
    print("  Lien direct :", APP_URL + "#live-" + code)
    print("  Overlay OBS :", APP_URL + "overlay.html?c=" + code)
    print("  Ctrl+C pour arrêter")
    print("=" * 56)


def run_demo(cfg, watch):
    code = cfg["code"]
    t0 = time.time()
    score = 0
    meta = {"cop_x": {"libelle": "Équilibre gauche/droite", "plage": [-1, 1]},
            "cop_y": {"libelle": "Équilibre avant/arrière", "plage": [-1, 1]},
            "poids": {"libelle": "Poids", "unite": "kg"}, "score": {"libelle": "Score"},
            "activite": {"libelle": "Activité"}}
    while True:
        t = time.time() - t0
        if random.random() < 0.08:
            score += 1
        vals = {"cop_x": round(math.sin(t * 0.9) * 0.6 + random.uniform(-.05, .05), 3),
                "cop_y": round(math.cos(t * 0.6) * 0.4 + random.uniform(-.05, .05), 3),
                "poids": 72.4, "score": score, "activite": "Démo : table inclinée"}
        ok = send(code, {"hooked": True, "game": "DEMO", "jeu": "Mode démo", "values": vals, "meta": meta, "t": time.time()})
        if watch or not ok:
            print(("OK " if ok else "ERREUR ") + json.dumps(vals, ensure_ascii=False))
        time.sleep(0.25)


def run(cfg, watch):
    try:
        import dolphin_memory_engine as dme
    except ImportError:
        print("Il manque le module Dolphin. Installe-le avec :")
        print("    pip install dolphin-memory-engine")
        sys.exit(1)
    code = cfg["code"]
    rate = max(1, min(10, float(cfg.get("frequence_hz", 4))))
    values = [v for v in cfg.get("valeurs", []) if v.get("actif", True)]
    meta = meta_of(values)
    if not values:
        print("Aucune valeur active dans elphara_live.json : l'appli verra seulement si Dolphin et le jeu sont lancés.")
    last_vals, last_send, last_wait = None, 0.0, 0.0
    while True:
        if not dme.is_hooked():
            dme.hook()
            if not dme.is_hooked():
                if time.time() - last_wait > 5:
                    print("En attente de Dolphin… (lance Dolphin puis Wii Fit Plus)")
                    send(code, {"hooked": False, "t": time.time()})
                    last_wait = time.time()
                time.sleep(1)
                continue
            print("Dolphin trouvé !")
        try:
            gid = dme.read_bytes(0x80000000, 6).decode("ascii", "replace")
        except Exception:
            dme.un_hook()
            time.sleep(1)
            continue
        vals = {}
        for v in values:
            try:
                vals[v["nom"]] = read_value(dme, v)
            except Exception:
                vals[v["nom"]] = None
        now = time.time()
        if vals != last_vals or now - last_send > 3:
            payload = {"hooked": True, "game": gid, "jeu": GAMES.get(gid[:4], gid), "values": vals, "meta": meta, "t": now}
            ok = send(code, payload)
            last_vals, last_send = vals, now
            if watch:
                print(("OK " if ok else "ERREUR ") + gid + " " + json.dumps(vals, ensure_ascii=False))
        time.sleep(1 / rate)


if __name__ == "__main__":
    cfg = load_cfg()
    demo = "--demo" in sys.argv
    banner(cfg["code"], demo)
    try:
        run_demo(cfg, "--watch" in sys.argv) if demo else run(cfg, "--watch" in sys.argv)
    except KeyboardInterrupt:
        send(cfg["code"], {"hooked": False, "t": time.time()})
        print("\nArrêté.")
