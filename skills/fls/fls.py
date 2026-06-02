#!/usr/bin/env python3
"""
Чтение и запись файлов на домашнем файловом сервере fls.penkovmm.ru (filebrowser) по HTTP API.
Только стандартная библиотека Python 3. Полный доступ: чтение, создание, переименование,
перемещение, копирование, удаление, загрузка.

Учётные данные берутся из переменных окружения или из файла ~/.fls_creds:
    FLS_BASE=https://fls.penkovmm.ru
    FLS_USER=opencode
    FLS_PASS=...
Пароль читает сам скрипт – через модель он не проходит. Ограничьте доступ: chmod 600 ~/.fls_creds

Охват: учётка видит корень filebrowser (= /media/hdd/filebrowser/data на сервере) –
рабочие документы (Кадровые_комитеты, «25. Материалы ГПН», Отдел_оценки_и_развития, HR и т.д.).

Примеры чтения:
    python3 fls.py ls                         # корень
    python3 fls.py ls "25. Материалы ГПН"     # подпапка (кириллица/пробелы – как есть)
    python3 fls.py tree HR --depth 2          # дерево с ограничением глубины
    python3 fls.py cat home.yaml              # текст текстового файла
    python3 fls.py get "Адаптация_для ДО_4.pdf"   # скачать -> печатает локальный путь
    python3 fls.py get отчёт.pdf /tmp/o.pdf   # скачать в конкретный путь
    python3 fls.py search ГПН                 # поиск по всему дереву
    python3 fls.py search супервизия "25. Материалы ГПН"  # поиск в подпапке

Примеры записи:
    python3 fls.py mkdir "Новая папка"
    python3 fls.py rm "старый_файл.txt"
    python3 fls.py mv "старое_имя.txt" "новое_имя.txt"
    python3 fls.py cp "файл.txt" "Архив/файл.txt"
    python3 fls.py upload "./локальный.pdf" "Отчёты/локальный.pdf"
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib import request, parse, error

CREDS_FILE = Path.home() / ".fls_creds"
TOKEN_CACHE = Path.home() / ".cache" / "fls_token"
TOKEN_TTL = 5400  # 1.5 ч — JWT filebrowser живёт ~2 ч, обновляемся с запасом
DEFAULT_BASE = "https://fls.penkovmm.ru"
TIMEOUT = 30

# расширения, которые точно бинарные — для cat сразу подсказываем get
BINARY_EXT = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".zip", ".rar",
    ".7z", ".gz", ".tar", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff",
    ".webp", ".svg", ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".heic",
}


# --- учётные данные ---------------------------------------------------------

def load_credentials():
    base = os.environ.get("FLS_BASE")
    user = os.environ.get("FLS_USER")
    password = os.environ.get("FLS_PASS")

    if (not user or not password) and CREDS_FILE.exists():
        for line in CREDS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key == "FLS_BASE" and not base:
                base = val
            elif key == "FLS_USER" and not user:
                user = val
            elif key == "FLS_PASS" and not password:
                password = val

    base = (base or DEFAULT_BASE).rstrip("/")
    if not user or not password:
        sys.exit(
            "Не заданы учётные данные.\n"
            f"Создайте файл {CREDS_FILE} со строками:\n"
            "  FLS_BASE=https://fls.penkovmm.ru\n"
            "  FLS_USER=...\n"
            "  FLS_PASS=...\n"
            "и ограничьте доступ: chmod 600 ~/.fls_creds"
        )
    return base, user, password


# --- HTTP-клиент filebrowser ------------------------------------------------

class Client:
    def __init__(self):
        self.base, self.user, self.password = load_credentials()
        self.token = self._cached_token()

    # токен кэшируется в ~/.cache/fls_token, чтобы не логиниться на каждый вызов
    def _cached_token(self):
        try:
            data = json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
            if data.get("base") == self.base and data.get("user") == self.user:
                if (datetime.now().timestamp() - data.get("ts", 0)) < TOKEN_TTL:
                    return data.get("token")
        except Exception:
            pass
        return None

    def _store_token(self, token):
        try:
            TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_CACHE.write_text(json.dumps({
                "base": self.base, "user": self.user,
                "token": token, "ts": datetime.now().timestamp(),
            }), encoding="utf-8")
            os.chmod(TOKEN_CACHE, 0o600)
        except Exception:
            pass

    def login(self):
        body = json.dumps({
            "username": self.user, "password": self.password, "recaptcha": "",
        }).encode("utf-8")
        req = request.Request(
            self.base + "/api/login", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=TIMEOUT) as resp:
                token = resp.read().decode("utf-8").strip()
        except error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit("Ошибка входа: неверный логин/пароль в ~/.fls_creds.")
            sys.exit(f"Ошибка входа (HTTP {e.code}): {e.reason}")
        except error.URLError as e:
            sys.exit(f"Не удалось подключиться к {self.base}: {e.reason}")
        if not token:
            sys.exit("Сервер вернул пустой токен при входе.")
        self.token = token
        self._store_token(token)
        return token

    def _request(self, url, raw=False, _retried=False):
        """GET с X-Auth; при 401/403 один раз перелогинивается и повторяет."""
        if not self.token:
            self.login()
        req = request.Request(url, headers={"X-Auth": self.token})
        try:
            with request.urlopen(req, timeout=TIMEOUT) as resp:
                payload = resp.read()
                ctype = resp.headers.get("Content-Type", "")
            return (payload, ctype) if raw else json.loads(payload.decode("utf-8"))
        except error.HTTPError as e:
            if e.code in (401, 403) and not _retried:
                self.login()
                return self._request(url, raw=raw, _retried=True)
            if e.code == 404:
                sys.exit("Путь не найден на сервере. Проверьте имя через `ls`.")
            sys.exit(f"Ошибка запроса (HTTP {e.code}): {e.reason}")
        except error.URLError as e:
            sys.exit(f"Сеть недоступна: {e.reason}")

    def _write(self, url, method="POST", data=None, raw_body=None, _retried=False):
        """POST/PATCH/PUT/DELETE с X-Auth; при 401/403 один раз перелогинивается."""
        if not self.token:
            self.login()
        headers = {"X-Auth": self.token}
        if raw_body is not None:
            headers["Content-Type"] = "application/octet-stream"
            body = raw_body
        elif data is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")
        else:
            body = b""
        req = request.Request(url, data=body, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=TIMEOUT) as resp:
                payload = resp.read()
            text = payload.decode("utf-8", errors="replace").strip()
            if not text:
                return {}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        except error.HTTPError as e:
            if e.code in (401, 403) and not _retried:
                self.login()
                return self._write(url, method, data, raw_body, _retried=True)
            if e.code == 404:
                sys.exit("Путь не найден на сервере. Проверьте имя через `ls`.")
            if e.code == 409:
                sys.exit(f"Конфликт: {e.reason}")
            sys.exit(f"Ошибка записи (HTTP {e.code}): {e.reason}")
        except error.URLError as e:
            sys.exit(f"Сеть недоступна: {e.reason}")

    # --- эндпоинты чтения ---
    def resources(self, path):
        url = self.base + "/api/resources/" + parse.quote(path.strip("/"), safe="/")
        return self._request(url)

    def raw(self, path):
        url = self.base + "/api/raw/" + parse.quote(path.strip("/"), safe="/")
        return self._request(url, raw=True)

    def search(self, query, scope):
        url = (self.base + "/api/search/" + parse.quote(scope.strip("/"), safe="/")
               + "?query=" + parse.quote(query))
        payload, _ = self._request(url, raw=True)
        items = []
        for line in payload.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return items

    # --- эндпоинты записи ---
    def mkdir(self, path):
        url = (self.base + "/api/resources/"
               + parse.quote(path.strip("/"), safe="/") + "/")
        return self._write(url, method="POST", data={})

    def rm(self, path):
        url = self.base + "/api/resources/" + parse.quote(path.strip("/"), safe="/")
        return self._write(url, method="DELETE")

    def mv(self, src, dst):
        payload, _ = self.raw(src)
        self._write(
            self.base + "/api/resources/" + parse.quote(dst.strip("/"), safe="/"),
            method="POST", raw_body=payload,
        )
        self.rm(src)

    def cp(self, src, dst):
        payload, _ = self.raw(src)
        self._write(
            self.base + "/api/resources/" + parse.quote(dst.strip("/"), safe="/"),
            method="POST", raw_body=payload,
        )

    def upload(self, local_path, remote_path):
        with open(local_path, "rb") as f:
            raw_body = f.read()
        url = self.base + "/api/resources/" + parse.quote(remote_path.strip("/"), safe="/")
        return self._write(url, method="POST", raw_body=raw_body)


# --- форматирование ---------------------------------------------------------

def human_size(n):
    n = float(n or 0)
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return (f"{int(n)}{unit}" if unit == "B" else f"{n:.1f}{unit}")
        n /= 1024


def fmt_date(iso):
    if not iso:
        return ""
    try:
        s = iso.replace("Z", "+00:00")
        return datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso[:16]


def is_binary(path, ctype, sample):
    ext = os.path.splitext(path)[1].lower()
    if ext in BINARY_EXT:
        return True
    if ctype and ctype.split(";")[0].strip().startswith("text/"):
        return False
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


# --- команды ----------------------------------------------------------------

def cmd_ls(c, args):
    d = c.resources(args.path)
    items = d.get("items") or []
    if not items:
        print(f'Пусто: /{args.path.strip("/")}')
        return
    dirs = sorted((i for i in items if i.get("isDir")), key=lambda x: x["name"].lower())
    files = sorted((i for i in items if not i.get("isDir")), key=lambda x: x["name"].lower())
    print(f'/{args.path.strip("/")}  —  {d.get("numDirs",0)} папок, {d.get("numFiles",0)} файлов\n')
    for i in dirs:
        print(f'  📁 {i["name"]}/')
    for i in files:
        print(f'  📄 {i["name"]:<48} {human_size(i.get("size")):>8}  {fmt_date(i.get("modified"))}')


def cmd_tree(c, args):
    def walk(path, depth, prefix):
        if depth < 0:
            return
        d = c.resources(path)
        items = sorted(d.get("items") or [], key=lambda x: (not x.get("isDir"), x["name"].lower()))
        for i in items:
            name = i["name"] + ("/" if i.get("isDir") else "")
            print(f"{prefix}{name}")
            if i.get("isDir") and depth > 0:
                child = (path.strip("/") + "/" + i["name"]).strip("/")
                walk(child, depth - 1, prefix + "  ")
    print(f'/{args.path.strip("/")}')
    walk(args.path, args.depth - 1, "  ")


def cmd_cat(c, args):
    payload, ctype = c.raw(args.path)
    if is_binary(args.path, ctype, payload[:4096]):
        sys.exit(
            f'Файл «{args.path}» бинарный (тип {ctype or "?"}, {human_size(len(payload))}).\n'
            f'Скачайте его: python3 fls.py get "{args.path}"  — затем откройте локально.'
        )
    sys.stdout.write(payload.decode("utf-8", errors="replace"))
    if not payload.endswith(b"\n"):
        sys.stdout.write("\n")


def cmd_get(c, args):
    payload, _ = c.raw(args.path)
    dest = args.dest
    if not dest:
        dest = str(Path("/tmp/fls") / os.path.basename(args.path.rstrip("/")))
    dest = os.path.abspath(os.path.expanduser(dest))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(payload)
    print(dest)
    print(f"({human_size(len(payload))})", file=sys.stderr)


def cmd_search(c, args):
    items = c.search(args.query, args.path)
    if not items:
        print(f'Ничего не найдено по запросу «{args.query}».')
        return
    print(f'Найдено {len(items)} (запрос «{args.query}»):\n')
    for i in items:
        kind = "📁" if i.get("dir") else "📄"
        print(f'  {kind} {i.get("path")}')


# --- команды записи ---

def cmd_mkdir(c, args):
    c.mkdir(args.path)
    print(f'Создана папка: /{args.path.strip("/")}')


def cmd_rm(c, args):
    c.rm(args.path)
    print(f'Удалено: /{args.path.strip("/")}')


def cmd_mv(c, args):
    c.mv(args.src, args.dst)
    print(f'Переименовано/перемещено: /{args.src.strip("/")} → /{args.dst.strip("/")}')


def cmd_cp(c, args):
    c.cp(args.src, args.dst)
    print(f'Скопировано: /{args.src.strip("/")} → /{args.dst.strip("/")}')


def cmd_upload(c, args):
    c.upload(args.local, args.remote)
    print(f'Загружено: {args.local} → /{args.remote.strip("/")}')


def main():
    p = argparse.ArgumentParser(
        description="Чтение и запись на fls.penkovmm.ru (filebrowser).")
    sub = p.add_subparsers(dest="command", required=True)

    # --- чтение ---
    pl = sub.add_parser("ls", help="листинг каталога")
    pl.add_argument("path", nargs="?", default="", help="путь (по умолчанию корень)")
    pl.set_defaults(func=cmd_ls)

    pt = sub.add_parser("tree", help="рекурсивное дерево")
    pt.add_argument("path", nargs="?", default="", help="путь (по умолчанию корень)")
    pt.add_argument("--depth", type=int, default=2, help="глубина (по умолчанию 2)")
    pt.set_defaults(func=cmd_tree)

    pc = sub.add_parser("cat", help="вывести текстовый файл")
    pc.add_argument("path", help="путь к файлу")
    pc.set_defaults(func=cmd_cat)

    pg = sub.add_parser("get", help="скачать файл локально (печатает путь)")
    pg.add_argument("path", help="путь к файлу на сервере")
    pg.add_argument("dest", nargs="?", default=None, help="куда сохранить (по умолчанию /tmp/fls/)")
    pg.set_defaults(func=cmd_get)

    ps = sub.add_parser("search", help="поиск по имени")
    ps.add_argument("query", help="строка поиска (кириллица ок)")
    ps.add_argument("path", nargs="?", default="", help="где искать (по умолчанию всё дерево)")
    ps.set_defaults(func=cmd_search)

    # --- запись ---
    pm = sub.add_parser("mkdir", help="создать папку")
    pm.add_argument("path", help="путь к новой папке")
    pm.set_defaults(func=cmd_mkdir)

    pr = sub.add_parser("rm", help="удалить файл или папку")
    pr.add_argument("path", help="путь к файлу или папке")
    pr.set_defaults(func=cmd_rm)

    pv = sub.add_parser("mv", help="переименовать или переместить")
    pv.add_argument("src", help="откуда")
    pv.add_argument("dst", help="куда")
    pv.set_defaults(func=cmd_mv)

    py = sub.add_parser("cp", help="скопировать")
    py.add_argument("src", help="откуда")
    py.add_argument("dst", help="куда")
    py.set_defaults(func=cmd_cp)

    pu = sub.add_parser("upload", help="загрузить локальный файл")
    pu.add_argument("local", help="локальный путь к файлу")
    pu.add_argument("remote", help="путь на сервере (включая имя файла)")
    pu.set_defaults(func=cmd_upload)

    args = p.parse_args()
    client = Client()
    args.func(client, args)


if __name__ == "__main__":
    main()
