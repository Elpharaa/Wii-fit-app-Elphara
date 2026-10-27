#!/usr/bin/env python3
"""
Elphara Fit - connexion Dolphin

Ce programme tourne sur ton PC pendant que tu joues à Wii Fit Plus sur Dolphin.
1. Il trouve tout seul la sauvegarde Wii Fit Plus de Dolphin et envoie tes résultats
   (tests de forme : poids, IMC, équilibre) à l'appli dès que le jeu enregistre.
2. Si le module dolphin-memory-engine est installé et des adresses sont réglées dans
   elphara_live.json, il envoie aussi des valeurs en direct pendant la partie.

Lancement : double-clic sur « Lancer Elphara.bat », ou :
  python elphara_live.py            mode normal
  python elphara_live.py --demo     fausses valeurs en direct pour tester l'appli
  python elphara_live.py --watch    affiche les valeurs en direct dans la console
  python elphara_live.py --save CHEMIN\\FitPlus0.dat   utiliser un fichier précis
"""
import datetime
import glob
import json
import math
import os
import random
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
ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TYPES = {"u8": (">B", 1), "s8": (">b", 1), "u16": (">H", 2), "s16": (">h", 2),
         "u32": (">I", 4), "s32": (">i", 4), "float": (">f", 4)}
GAMES = {"RFPP": "Wii Fit Plus (Europe)", "RFPE": "Wii Fit Plus (USA)", "RFPJ": "Wii Fit Plus (Japon)",
         "RFNP": "Wii Fit (Europe)", "RFNE": "Wii Fit (USA)", "RFNJ": "Wii Fit (Japon)"}
# dossiers de sauvegarde dans la NAND de Dolphin (titre 00010000/<id>/data)
SAVE_IDS = [("52465050", "FitPlus0.dat"), ("52465045", "FitPlus0.dat"), ("5246504a", "FitPlus0.dat"),
            ("52464e50", "RPHealth.dat"), ("52464e45", "RPHealth.dat"), ("52464e4a", "RPHealth.dat")]

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def rand(n):
    return "".join(random.SystemRandom().choice(ALPHA) for _ in range(n))


# ---------------------------------------------------------------- réglages
def default_values():
    return [
        {"nom": "cop_x", "libelle": "Équilibre gauche/droite", "adresse": "0x80000000", "type": "float", "plage": [-1, 1], "actif": False},
        {"nom": "cop_y", "libelle": "Équilibre avant/arrière", "adresse": "0x80000000", "type": "float", "plage": [-1, 1], "actif": False},
        {"nom": "score", "libelle": "Score", "adresse": "0x80000000", "type": "u32", "actif": False},
    ]


def load_cfg():
    cfg = {}
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    changed = False
    code = str(cfg.get("code", ""))
    if len(code) < 8:
        cfg["code"] = (code + rand(8))[:8] if code else rand(8)
        changed = True
    if len(str(cfg.get("secret", ""))) < 24:
        cfg["secret"] = rand(32)
        changed = True
    cfg.setdefault("frequence_hz", 4)
    cfg.setdefault("dossier_dolphin", "")
    cfg.setdefault("sauvegarde", "")
    cfg.setdefault("valeurs", default_values())
    if changed or not os.path.exists(CFG_PATH):
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


# ---------------------------------------------------------------- réseau
def post(path, body, timeout=8):
    req = urllib.request.Request(SUPABASE_URL + path, data=json.dumps(body).encode(), method="POST", headers={
        "apikey": SUPABASE_KEY, "Authorization": "Bearer " + SUPABASE_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.read()
    except urllib.error.HTTPError as e:
        return False, e.read()[:300]
    except Exception as e:
        return False, str(e).encode()


def broadcast(code, event, payload):
    ok, _ = post("/realtime/v1/api/broadcast",
                 {"messages": [{"topic": "elphara-" + code, "event": event, "payload": payload}]}, timeout=4)
    return ok


# ---------------------------------------------------------------- sauvegarde Wii Fit
def dolphin_roots(cfg):
    roots = []
    if cfg.get("dossier_dolphin"):
        roots.append(cfg["dossier_dolphin"])
    home = os.path.expanduser("~")
    for env, sub in (("APPDATA", "Dolphin Emulator"), ("USERPROFILE", os.path.join("Documents", "Dolphin Emulator"))):
        if os.environ.get(env):
            roots.append(os.path.join(os.environ[env], sub))
    for d in dolphin_exe_dirs():
        roots += [os.path.join(d, "User"), d]
    roots += [os.path.join(home, "Documents", "Dolphin Emulator"),
              os.path.join(home, ".local", "share", "dolphin-emu"),
              os.path.join(home, ".dolphin-emu"),
              os.path.join(home, "Library", "Application Support", "Dolphin")]
    return roots


def nand_dirs(root):
    dirs = [os.path.join(root, "Wii")]
    ini = os.path.join(root, "Config", "Dolphin.ini")
    try:
        with open(ini, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.strip().lower().startswith("nandrootpath"):
                    p = line.split("=", 1)[1].strip()
                    if p:
                        dirs.insert(0, p)
    except OSError:
        pass
    return dirs


SAVE_NAMES = ("FitPlus0.dat", "RPHealth.dat")


def save_in(path):
    """Accepte un fichier de sauvegarde ou un dossier qui en contient un."""
    path = os.path.expandvars(os.path.expanduser(str(path).strip().strip('"')))
    if os.path.isfile(path) and os.path.basename(path) in SAVE_NAMES:
        return path
    if os.path.isdir(path):
        for n in SAVE_NAMES:
            for cand in (os.path.join(path, n), os.path.join(path, "data", n)):
                if os.path.isfile(cand):
                    return cand
    return None


def dolphin_exe_dirs():
    """Dossiers où tourne Dolphin (pour la version portable)."""
    dirs = []
    if os.name == "nt":
        try:
            import subprocess
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "Get-Process | Where-Object {$_.ProcessName -like 'Dolphin*'} | ForEach-Object {$_.Path}"],
                                 capture_output=True, text=True, timeout=10).stdout
            dirs = [os.path.dirname(l.strip()) for l in out.splitlines() if l.strip()]
        except Exception:
            pass
    return dirs


def deep_search(max_seconds=20):
    """Cherche FitPlus0.dat dans le dossier utilisateur et à côté de Dolphin."""
    roots = dolphin_exe_dirs() + [os.path.expanduser("~")]
    skip = {"node_modules", ".git", "temp", "tmp", "cache", "caches", "windows", "$recycle.bin", "packages", "microsoft"}
    t0, found = time.time(), []
    for root in roots:
        for cur, dirs, files in os.walk(root):
            if time.time() - t0 > max_seconds:
                return found
            depth = cur[len(root):].count(os.sep)
            dirs[:] = [d for d in dirs if d.lower() not in skip and depth < 9]
            for n in SAVE_NAMES:
                if n in files and os.path.basename(os.path.dirname(cur)).lower().startswith("5246"):
                    found.append(os.path.join(cur, n))
    return found


def find_save(cfg, deep=False):
    if cfg.get("sauvegarde"):
        p = save_in(cfg["sauvegarde"])
        if p:
            return p
    found = []
    for root in dolphin_roots(cfg):
        for nand in nand_dirs(root):
            for tid, fname in SAVE_IDS:
                p = os.path.join(nand, "title", "00010000", tid, "data", fname)
                if os.path.isfile(p):
                    found.append(p)
    if not found and deep:
        found = deep_search()
    # sauvegarde la plus récente en premier
    found = sorted(set(found), key=lambda p: os.path.getmtime(p), reverse=True)
    return found[0] if found else None


def bcd(b):
    return (b >> 4) * 10 + (b & 15)


def parse_save(data):
    starts, i = [], data.find(b"RPHE0000")
    while i != -1:
        starts.append(i)
        i = data.find(b"RPHE0000", i + 0x3000)
    profiles = []
    for k, s in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(data)
        if s + 0x38A1 > end:
            continue
        raw = data[s + 8:s + 30]
        name = ""
        for j in range(0, 22, 2):
            c = struct.unpack(">H", raw[j:j + 2])[0]
            if not c:
                break
            name += chr(c)
        name = name.strip()
        height = data[s + 0x1F]
        by = bcd(data[s + 0x20]) * 100 + bcd(data[s + 0x21])
        bm, bd = bcd(data[s + 0x22]), bcd(data[s + 0x23])
        birth = "%04d-%02d-%02d" % (by, bm, bd) if 1900 < by < 2030 and 1 <= bm <= 12 and 1 <= bd <= 31 else None
        tests = []
        o = s + 0x38A1
        while o + 21 <= end and len(tests) < 6000:
            rec = data[o:o + 21]
            o += 21
            p, kg, bmi, bal = struct.unpack(">I3H", rec[:10])
            y = p >> 20 & 0x7FF
            if not y:
                break
            mo, d, h, mi = (p >> 16 & 0xF) + 1, p >> 11 & 0x1F, p >> 6 & 0x1F, p & 0x3F
            if not (2007 <= y <= 2040 and mo <= 12 and 1 <= d <= 31 and h <= 23 and mi <= 59 and 100 <= kg <= 2500):
                continue
            tests.append(["%04d-%02d-%02dT%02d:%02d" % (y, mo, d, h, mi), kg / 10,
                          bmi / 100 if 500 < bmi < 8000 else None, bal / 10 if 0 < bal <= 1000 else None, rec[10:].hex()])
        if name or tests:
            profiles.append({"name": name or "Mii sans nom", "height": height if 50 <= height <= 230 else None,
                             "birth": birth, "tests": tests, "head": data[s + 0x24:s + 0x95].hex()})
    return profiles


def sync_save(cfg, path):
    with open(path, "rb") as f:
        data = f.read()
    profiles = parse_save(data)
    if not profiles:
        print("La sauvegarde a été trouvée mais aucun profil n'a pu être lu :", path)
        return False
    tid = os.path.basename(os.path.dirname(os.path.dirname(path)))
    payload = {"v": 1, "game": bytes.fromhex(tid).decode("ascii", "replace"),
               "saved": datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds"),
               "profiles": profiles}
    ok, res = post("/rest/v1/rpc/wf_push", {"p_code": cfg["code"], "p_secret": cfg["secret"], "p_data": payload})
    if not ok:
        print("Synchro refusée :", res.decode("utf-8", "replace"))
        return False
    broadcast(cfg["code"], "sync", {"t": time.time()})
    resume = ", ".join("%s (%d tests)" % (p["name"], len(p["tests"])) for p in profiles)
    print(time.strftime("%H:%M:%S"), "Sauvegarde Wii Fit envoyée à l'appli :", resume)
    return True


# ---------------------------------------------------------------- direct (mémoire)
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


def banner(cfg, demo, save, dme_ok):
    code = cfg["code"]
    print("=" * 62)
    print("  Elphara Fit - connexion Dolphin" + ("  (mode démo)" if demo else ""))
    print()
    print("  TON CODE :", code)
    print("  Sur le téléphone ou le PC : ouvre ce lien une fois")
    print("   ", APP_URL + "#live-" + code)
    print("  (ou onglet Jeux > En direct > tape le code)")
    print()
    print("  Sauvegarde Wii Fit :", save or "pas encore trouvée (lance Wii Fit Plus dans Dolphin une fois)")
    print("  Direct mémoire     :", "prêt" if dme_ok else "désactivé (pip install dolphin-memory-engine pour l'activer)")
    print("  Overlay OBS        :", APP_URL + "overlay.html?c=" + code)
    print("  Laisse cette fenêtre ouverte. Ctrl+C pour arrêter.")
    print("=" * 62)


def main():
    cfg = load_cfg()
    demo = "--demo" in sys.argv
    watch = "--watch" in sys.argv
    forced = None
    if "--save" in sys.argv:
        i = sys.argv.index("--save")
        if i + 1 < len(sys.argv):
            forced = sys.argv[i + 1]
    try:
        import dolphin_memory_engine as dme
    except ImportError:
        dme = None
    save = save_in(forced) if forced else find_save(cfg)
    if not save:
        print("Recherche de la sauvegarde Wii Fit Plus dans tes dossiers (jusqu'à 20 secondes)…")
        save = find_save(cfg, deep=True)
    if not save and sys.stdin and sys.stdin.isatty():
        print()
        print("Je n'ai pas trouvé la sauvegarde Wii Fit Plus.")
        print("Dans Dolphin : clic droit sur Wii Fit Plus > « Ouvrir le dossier de sauvegarde Wii ».")
        print("Glisse le fichier FitPlus0.dat (ou le dossier) dans cette fenêtre, puis appuie sur Entrée.")
        print("(Entrée sans rien pour continuer sans la sauvegarde)")
        try:
            typed = input("> ").strip()
        except EOFError:
            typed = ""
        if typed:
            save = save_in(typed)
            if save:
                cfg["sauvegarde"] = save
                with open(CFG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
                print("Merci ! Je retiens cet emplacement.")
            else:
                print("Ce n'est pas une sauvegarde Wii Fit (il faut FitPlus0.dat). On continue sans.")
    if save:
        cfg["sauvegarde"] = save
    banner(cfg, demo, save, dme is not None)

    values = [v for v in cfg.get("valeurs", []) if v.get("actif", False)]
    meta = {v["nom"]: {k: v[k] for k in ("libelle", "unite", "plage", "noms") if k in v} for v in values}
    rate = max(1, min(10, float(cfg.get("frequence_hz", 4))))
    last_mtime, last_check, last_sent, last_vals, t0, score = None, 0.0, 0.0, None, time.time(), 0
    hooked_once = False

    while True:
        now = time.time()
        # 1) sauvegarde : vérifiée toutes les 4 secondes
        if now - last_check > 4:
            last_check = now
            if not save:
                save = find_save(cfg)
                if save:
                    print("Sauvegarde Wii Fit trouvée :", save)
            if save and os.path.isfile(save):
                m = os.path.getmtime(save)
                if m != last_mtime:
                    time.sleep(0.5)  # laisse Dolphin finir d'écrire
                    if sync_save(cfg, save):
                        last_mtime = m
        # 2) direct
        payload = None
        if demo:
            t = now - t0
            if random.random() < 0.08:
                score += 1
            vals = {"cop_x": round(math.sin(t * 0.9) * 0.6, 3), "cop_y": round(math.cos(t * 0.6) * 0.4, 3),
                    "score": score, "activite": "Démo : table inclinée"}
            payload = {"hooked": True, "game": "DEMO", "jeu": "Mode démo", "values": vals,
                       "meta": {"cop_x": {"libelle": "Équilibre", "plage": [-1, 1]}, "cop_y": {"plage": [-1, 1]},
                                "score": {"libelle": "Score"}}}
        elif dme is not None:
            if not dme.is_hooked():
                try:
                    dme.hook()
                except Exception:
                    pass
            if dme.is_hooked():
                if not hooked_once:
                    print("Dolphin trouvé : direct activé.")
                    hooked_once = True
                try:
                    gid = dme.read_bytes(0x80000000, 6).decode("ascii", "replace")
                    vals = {}
                    for v in values:
                        try:
                            vals[v["nom"]] = read_value(dme, v)
                        except Exception:
                            vals[v["nom"]] = None
                    payload = {"hooked": True, "game": gid, "jeu": GAMES.get(gid[:4], gid), "values": vals, "meta": meta}
                except Exception:
                    try:
                        dme.un_hook()
                    except Exception:
                        pass
            if payload is None:
                payload = {"hooked": False}
        else:
            payload = {"hooked": None}
        vals_now = payload.get("values")
        if vals_now != last_vals or now - last_sent > 3:
            payload["t"] = now
            payload["sync"] = last_mtime
            ok = broadcast(cfg["code"], "state", payload)
            last_vals, last_sent = vals_now, now
            if watch and vals_now:
                print(("OK " if ok else "ERREUR ") + json.dumps(vals_now, ensure_ascii=False))
        time.sleep(1 / rate if (demo or values) else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        try:
            broadcast(load_cfg()["code"], "state", {"hooked": False, "t": time.time()})
        except Exception:
            pass
        print("\nArrêté.")
