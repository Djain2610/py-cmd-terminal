#! python
"""
main.py — Python-backed Terminal Emulator for Hackathon Backup
"""

import os, sys, shlex, shutil, subprocess, platform, glob, requests
from datetime import datetime

# Optional libs
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

# ---- Config ----
HISTORY_FILE = os.path.expanduser("~/.pyterminal_history")
HISTORY_MAX = 1000

# Hardcoded Gemini API key (temporary for testing)
GEMINI_API_KEY = "AIzaSyBolkCVv0TlTJt1ixBzqECVx-KvDQApmCY"

# ---- Utilities ----
def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except BrokenPipeError:
        try: sys.stdout.close()
        finally: sys.exit(0)

def human_size(n):
    try: n = float(n)
    except Exception: return str(n)
    for unit in ("B","KB","MB","GB","TB"):
        if abs(n) < 1024.0: return f"{n:3.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

def expand_path(p): return os.path.abspath(os.path.expanduser(os.path.expandvars(p)))

# ---- File Ops ----
def list_dir(path=".", all=False, long=False):
    p = expand_path(path)
    if not os.path.exists(p): raise FileNotFoundError(f"No such file or directory: {path}")
    if not os.path.isdir(p): return os.path.basename(p)
    entries = sorted(os.listdir(p))
    if not all: entries = [e for e in entries if not e.startswith(".")]
    if not long: return "  ".join(entries) if entries else "[Empty Directory]"
    lines = []
    for name in entries:
        full = os.path.join(p, name)
        try:
            st = os.stat(full)
            mode = oct(st.st_mode)[-3:]
            size = human_size(st.st_size)
            mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            lines.append(f"{mode}\t{size:>8}\t{mtime}\t{name}")
        except Exception:
            lines.append(f"??\t??\t{name}")
    return "\n".join(lines)

def cmd_ls(args):
    all_flag = long_flag = False; paths = []
    for a in args:
        if a.startswith("-"):
            if "a" in a: all_flag = True
            if "l" in a: long_flag = True
        else: paths.append(a)
    if not paths: paths = ["."]
    out = []
    for p in paths:
        try:
            res = list_dir(p, all=all_flag, long=long_flag)
            header = f"{p}:" if len(paths) > 1 else ""
            out.append((header + ("\n" if header else "") + res).rstrip())
        except Exception as e: out.append(str(e))
    return "\n".join(out)

def cmd_pwd(_): return os.getcwd()

def cmd_cd(args):
    target = args[0] if args else os.path.expanduser("~")
    try: os.chdir(expand_path(target)); return ""
    except FileNotFoundError: return f"cd: no such file or directory: {target}"
    except NotADirectoryError: return f"cd: not a directory: {target}"
    except PermissionError: return f"cd: permission denied: {target}"
    except Exception as e: return f"cd: {e}"

def cmd_mkdir(args):
    if not args: return "mkdir: missing operand"
    outs = []
    for d in args:
        try: os.makedirs(expand_path(d)); outs.append(f"Created directory '{d}'")
        except FileExistsError: outs.append(f"mkdir: cannot create directory '{d}': exists")
        except Exception as e: outs.append(f"mkdir: {e}")
    return "\n".join(outs)

def cmd_rm(args):
    recursive = force = interactive = False; targets = []
    for a in args:
        if a.startswith("-"):
            if "r" in a or "R" in a: recursive = True
            if "f" in a: force = True
            if "i" in a: interactive = True
        else: targets.append(a)
    if not targets: return "rm: missing operand"
    outs = []
    for t in targets:
        p = expand_path(t)
        if not os.path.exists(p):
            if force: continue
            outs.append(f"rm: cannot remove '{t}': No such file"); continue
        if interactive:
            resp = input(f"rm: remove '{t}'? [y/N] ")
            if resp.lower() != "y": continue
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                if not recursive: outs.append(f"rm: cannot remove '{t}': Is a directory"); continue
                shutil.rmtree(p); outs.append(f"Removed dir '{t}'")
            else: os.remove(p); outs.append(f"Removed '{t}'")
        except Exception as e: outs.append(f"rm: {e}")
    return "\n".join(outs)

def cmd_touch(args):
    if not args: return "touch: missing operand"
    outs = []
    for f in args:
        p = expand_path(f)
        try: 
            with open(p,"a"): os.utime(p,None)
            outs.append(f"Touched '{f}'")
        except Exception as e: outs.append(f"touch: {e}")
    return "\n".join(outs)

def cmd_cat(args):
    if not args: return "cat: missing operand"
    number = False; files = []
    for a in args:
        if a == "-n": number = True
        else: files.append(a)
    out = []
    for f in files:
        p = expand_path(f)
        try:
            with open(p,"r",encoding="utf-8",errors="replace") as fh:
                if number:
                    for i,l in enumerate(fh,1): out.append(f"{i:>4} {l.rstrip()}")
                else: out.append(fh.read())
        except Exception as e: out.append(f"cat: {e}")
    return "\n".join(out)

def cmd_mv(args):
    if len(args)<2: return "mv: missing operand"
    *srcs,dest=args; destp=expand_path(dest); outs=[]
    if len(srcs)>1 and not os.path.isdir(destp): return "mv: target not dir"
    for s in srcs:
        sp=expand_path(s)
        if not os.path.exists(sp): outs.append(f"mv: cannot stat '{s}'"); continue
        try: shutil.move(sp,destp); outs.append(f"Moved '{s}' -> '{dest}'")
        except Exception as e: outs.append(f"mv: {e}")
    return "\n".join(outs)

def cmd_cp(args):
    if len(args)<2: return "cp: missing operand"
    *srcs,dest=args; destp=expand_path(dest); outs=[]
    if len(srcs)>1 and not os.path.isdir(destp): return "cp: target not dir"
    for s in srcs:
        sp=expand_path(s)
        if not os.path.exists(sp): outs.append(f"cp: cannot stat '{s}'"); continue
        try:
            if os.path.isdir(sp): shutil.copytree(sp, os.path.join(destp, os.path.basename(sp)))
            else:
                if os.path.isdir(destp): shutil.copy2(sp, os.path.join(destp, os.path.basename(sp)))
                else: shutil.copy2(sp,destp)
            outs.append(f"Copied '{s}' -> '{dest}'")
        except Exception as e: outs.append(f"cp: {e}")
    return "\n".join(outs)

# ---- Monitoring ----
def cmd_ps(_):
    if PSUTIL_AVAILABLE:
        return "\n".join(f"{p.info['pid']:>6} {p.info.get('username',''):.16} {p.info.get('name','')}"
                         for p in psutil.process_iter(['pid','name','username']))
    try:
        if platform.system()=="Windows": return subprocess.check_output(["tasklist"],text=True)
        else: return subprocess.check_output(["ps","-ef"],text=True)
    except Exception as e: return f"ps: {e}"

def cmd_top(_):
    if PSUTIL_AVAILABLE:
        cpu=psutil.cpu_percent(0.5); mem=psutil.virtual_memory()
        lines=[f"CPU {cpu}%  Mem {mem.percent}% ({human_size(mem.used)}/{human_size(mem.total)})",
               "Top by memory:"]
        procs=sorted(psutil.process_iter(['pid','name','memory_info']),
                     key=lambda p:(p.info.get('memory_info').rss if p.info.get('memory_info') else 0),
                     reverse=True)[:8]
        for p in procs:
            rss=p.info.get('memory_info').rss if p.info.get('memory_info') else 0
            lines.append(f"{p.info['pid']:>6} {human_size(rss):>8} {p.info['name']}")
        return "\n".join(lines)
    return "top: psutil not installed."

def cmd_cpu(_): return f"CPU: {psutil.cpu_percent(0.2)}%" if PSUTIL_AVAILABLE else "cpu: psutil not installed (required for CPU monitoring)"
def cmd_mem(_):
    if PSUTIL_AVAILABLE:
        m=psutil.virtual_memory()
        return f"Mem: {m.percent}% ({human_size(m.used)}/{human_size(m.total)})"
    return "mem: psutil not installed (required for memory monitoring)"

# ---- Extra Commands ----
def cmd_clear(_): os.system("cls" if platform.system()=="Windows" else "clear"); return ""
def cmd_whoami(_): return os.getenv("USER") or os.getenv("USERNAME") or "user"
def cmd_date(_): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def cmd_uptime(_):
    if PSUTIL_AVAILABLE:
        boot=datetime.fromtimestamp(psutil.boot_time())
        return f"Uptime: {datetime.now()-boot}".split(".")[0]
    return "uptime: psutil missing"

# ---- Natural Language via Gemini API ----
def run_nl(t):
    if not GEMINI_API_KEY:
        return "nl: Gemini API key missing!"
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json","X-goog-api-key": GEMINI_API_KEY}
    payload = {"contents":[{"parts":[{"text": t}]}]}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            return f"nl: API returned {resp.status_code}: {resp.text}"
        data = resp.json()
        # Extract text from the first part of the first candidate
        candidates = data.get("candidates", [])
        if not candidates:
            return "[No content returned]"
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return "[No content returned]"
        # Join all parts text (if multiple) into a single string
        return "\n".join(part.get("text","") for part in parts)
    except Exception as e:
        return f"nl: API call failed: {e}"


# ---- Command Map ----
INTERNAL_CMDS={
 "ls":cmd_ls,"pwd":cmd_pwd,"cd":cmd_cd,"mkdir":cmd_mkdir,"rm":cmd_rm,"touch":cmd_touch,
 "cat":cmd_cat,"mv":cmd_mv,"cp":cmd_cp,"ps":cmd_ps,"top":cmd_top,"cpu":cmd_cpu,"mem":cmd_mem,
 "clear":cmd_clear,"whoami":cmd_whoami,"date":cmd_date,"uptime":cmd_uptime,
 "help":lambda a: help_text(),"history":lambda a: show_history(),"nl":lambda a: run_nl(" ".join(a))
}

def help_text(): return """Commands: ls, cd, pwd, mkdir, rm, touch, cat, mv, cp
Monitoring: ps, top, cpu, mem
Extras: clear, whoami, date, uptime
AI: nl: <text>
Other: history, help, exit, quit"""

# ---- History / Completion ----
_history=[]
def load_history():
    """
    Previously loaded commands from disk. 
    Now: start with empty history for each session.
    """
    # Do nothing — empty history
    pass

def save_history():
    """
    Previously saved commands to disk. 
    Now: we don't persist anything.
    """
    # Do nothing — don't save to disk

def show_history(): 
    return "\n".join(f"{i+1} {_history[i]}" for i in range(len(_history)))

def completer(text,state):
    buffer=readline.get_line_buffer()
    try: tokens=shlex.split(buffer)
    except: tokens=buffer.split()
    if buffer.endswith(" "): tokens.append("")
    if len(tokens)<=1: cands=[c for c in INTERNAL_CMDS if c.startswith(text)]
    else: cands=glob.glob(text+"*")+glob.glob(expand_path(text)+"*")
    return cands[state] if state<len(cands) else None

# ---- Executor ----
def run_external_command(parts):
    try: 
        result = subprocess.run(parts, capture_output=True, text=True)
        return result.stdout + result.stderr
    except FileNotFoundError: 
        return f"{parts[0]}: command not found"
    except Exception as e: 
        return str(e)

def execute_line_internal(line,record_history=True):
    line=line.strip()
    if not line: return ""
    if record_history: _history.append(line)
    if line.startswith("nl:"): return run_nl(line.split(":",1)[1])
    try: parts=shlex.split(line)
    except Exception as e: return f"Parse error: {e}"
    if not parts: return ""
    cmd,args=parts[0],parts[1:]
    if cmd in ("exit","quit"): save_history(); safe_print("bye 👋"); sys.exit(0)
    if cmd in INTERNAL_CMDS:
        try: return INTERNAL_CMDS[cmd](args)
        except Exception as e: return f"{cmd}: {e}"
    return run_external_command(parts)

# ---- Main ----
def initialize():
    if READLINE_AVAILABLE:
        readline.set_completer(completer); readline.parse_and_bind("tab: complete")
    load_history()
    if not PSUTIL_AVAILABLE: safe_print("[notice] psutil not installed")
    if not READLINE_AVAILABLE: safe_print("[notice] readline not installed")

def main_loop():
    initialize(); safe_print("pyterminal ready. Type 'help' for commands.")
    try:
        while True:
            try: line=input(f"\033[1;32m{cmd_whoami([])}\033[0m:\033[1;34m{os.getcwd()}\033[0m$ ")
            except EOFError: break
            out=execute_line_internal(line)
            if out: safe_print(out)
    except KeyboardInterrupt: safe_print("\nInterrupted.")
    finally: save_history()

if __name__=="__main__": main_loop()
