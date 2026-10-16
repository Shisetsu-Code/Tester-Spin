"""Optional local Aislador worker. No dynamic primitive/code installation."""
import json,os,subprocess,sys,threading,sqlite3
from contextlib import closing
from pathlib import Path

_lock=threading.Lock()
_workers={}


def configuration(data_root):
    path=Path(data_root)/"har-learning.json"
    if not path.is_file():return None
    config=json.loads(path.read_text(encoding="utf-8"))
    if config.get("enabled") is not True:return None
    source=Path(config.get("aislador_root",""))
    if not source.is_absolute() or not (source/"aislador/__main__.py").is_file():raise ValueError("Configurá la instalación local de Aislador")
    return config,source


def _reap(process,database,root):
    try:
        if process.wait()!=0:return
        state=root/"har-learning/failures.private.json"
        if not state.is_file():return
        cursor=json.loads(state.read_text(encoding="utf-8"))["cursor"]
        with closing(sqlite3.connect(database.as_uri()+"?mode=ro",uri=True)) as con:
            latest=con.execute("SELECT COALESCE(MAX(id),0) FROM test_results WHERE status IN ('ERROR','PARCIAL')").fetchone()[0]
        if latest>cursor:kick_worker(database)
    except Exception:pass


def kick_worker(database):
    database=Path(database).resolve();root=database.parent
    try:
        configured=configuration(root)
        if configured is None:return False
        config,source=configured;key=str(database)
        with _lock:
            existing=_workers.get(key)
            if existing is not None and existing.poll() is None:return True
            out=root/"har-learning";out.mkdir(parents=True,exist_ok=True)
            command=[config.get("python") or sys.executable,"-m","aislador","follow-failures",
                "--tester-spin-db",str(database),"--out",str(out),"--after-id",str(int(config.get("after_id",0))),
                "--seconds",str(int(config.get("seconds",12)))]
            with (out/"worker.private.log").open("a",encoding="utf-8") as log:
                _workers[key]=subprocess.Popen(command,cwd=source,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
            threading.Thread(target=_reap,args=(_workers[key],database,root),daemon=True,name="har-capture-reap").start()
            return True
    except Exception as exc:
        # Recording a game result must not fail because an optional learner is absent.
        try:
            out=root/"har-learning";out.mkdir(parents=True,exist_ok=True)
            (out/"launcher-error.txt").write_text(str(exc),encoding="utf-8")
        except OSError:pass
        return False


def isolate_capture(har,data_root):
    configured=configuration(data_root)
    if configured is None:raise ValueError("Aislador no está configurado para este programa")
    config,source=configured;har=Path(har).resolve()
    if not har.is_file() or har.suffix.casefold()!=".har":raise ValueError("No se encontró el HAR guardado")
    command=[config.get("python") or sys.executable,"-m","aislador","extract",str(har),"--provider","auto",
             "--out",str(Path(data_root).resolve()/"har-learning/manual"),"--json"]
    completed=subprocess.run(command,cwd=source,capture_output=True,text=True,encoding="utf-8",timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    if completed.returncode:raise ValueError(completed.stderr.strip() or "No se pudo filtrar el HAR")
    return json.loads(completed.stdout)
