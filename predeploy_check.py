"""Pre-deployment check. Run it from the project root:

    python predeploy_check.py

It checks files, leftovers, secrets, Git, data, the saved model, the safety layer,
the test suite, and a full production-mode run of the app. It never changes your files.
"""
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

OLD_NAME = "Haven"          # the name you replaced; it must not appear anywhere any more
EXPECTED_LABELS = {"anger", "fear", "joy", "love", "sadness", "surprise"}
SKIP_DIRS = {"venv", ".venv", ".git", "data", "models", "__pycache__", ".pytest_cache", ".vscode", "node_modules"}
TEXT_SUFFIXES = {".py", ".html", ".js", ".css", ".md", ".yml", ".yaml", ".txt", ".json", ".toml", ".cfg", ".env"}

counts = {"PASS": 0, "WARN": 0, "FAIL": 0}


def report(level, message):
    counts[level] += 1
    print(f"[{level}] {message}")


def check(condition, ok_message, bad_message, level="FAIL"):
    if condition:
        report("PASS", ok_message)
    else:
        report(level, bad_message)
    return bool(condition)


def section(title):
    print(f"\n=== {title} ===")


def project_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name == Path(__file__).name:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"Dockerfile", ".gitignore", ".dockerignore"}:
            yield path


def read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


# ------------------------------------------------------------------ 1
def check_environment():
    section("1. Environment")
    check(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]}", "Python 3.9 or newer is needed")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    check(in_venv, "Running inside the virtual environment", "Not inside a virtual environment (activate venv first)", "WARN")
    for module in ("flask", "sklearn", "pandas", "matplotlib"):
        try:
            __import__(module)
            report("PASS", f"{module} imports correctly")
        except Exception as error:  # a blocked DLL shows up here too
            report("FAIL", f"{module} cannot be imported: {str(error)[:120]}")


# ------------------------------------------------------------------ 2
def check_files():
    section("2. Required files")
    required = [
        "app.py", "wsgi.py", "db.py", "requirements.txt", "README.md", ".gitignore",
        "core/__init__.py", "core/engine.py", "core/safety.py", "core/responses.py", "core/intensity.py",
        "ml/__init__.py", "ml/data.py", "ml/train.py", "ml/predict.py",
        "templates/index.html", "templates/auth.html", "templates/dashboard.html", "templates/_account_nav.html",
        "static/style.css", "static/pages.css", "static/app.js", "static/dashboard.js",
        "tests/test_core.py", "tests/test_api.py", "tests/test_accounts.py",
        "data/train.txt", "data/val.txt", "data/test.txt", ".github/workflows/tests.yml",
    ]
    missing = [name for name in required if not Path(name).is_file()]
    check(not missing, f"All {len(required)} required files exist", f"Missing files: {', '.join(missing)}")
    check(Path("Dockerfile").is_file(), "Dockerfile exists (optional on Render)",
          "No Dockerfile (fine if you only deploy on Render)", "WARN")
    wrong = [p for p in ("Dockerfile.txt", "README.md.txt", "requirements.txt.txt") if Path(p).exists()]
    check(not wrong, "No files with an accidental .txt extension", f"Rename these: {', '.join(wrong)}")


# ------------------------------------------------------------------ 3
def check_leftovers():
    section("3. Leftovers and placeholders")
    old_name, placeholders, todos = [], [], []
    for path in project_text_files():
        text = read(path)
        rel = str(path.relative_to(ROOT))
        if OLD_NAME in text:
            old_name.append(rel)
        if "YOUR_" in text or "12345678+" in text:
            placeholders.append(rel)
        if path.name == "README.md" and "TODO" in text:
            todos.append(rel)
    check(not old_name, f'No "{OLD_NAME}" left anywhere', f'"{OLD_NAME}" still appears in: {", ".join(old_name)}')
    check(not placeholders, "No YOUR_... or example placeholders left",
          f"Placeholders found in: {', '.join(placeholders)}")
    check(not todos, "README has no TODO items left", "README.md still has TODO items (live link, screenshots, error analysis)", "WARN")


# ------------------------------------------------------------------ 4
def check_secrets():
    section("4. Secrets")
    patterns = {
        "Hugging Face token": r"hf_[A-Za-z0-9]{20,}",
        "GitHub token": r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}",
        "hCaptcha secret": r"ES_[0-9a-f]{20,}",
        "long hex string assigned to a key": r"(?i)(secret|token|password|api_?key)\w*\s*[:=]\s*['\"][0-9a-f]{32,}['\"]",
    }
    found = []
    for path in project_text_files():
        text = read(path)
        for label, pattern in patterns.items():
            if re.search(pattern, text):
                found.append(f"{label} in {path.relative_to(ROOT)}")
    check(not found, "No tokens or secrets found in your files", "Possible secrets: " + "; ".join(found))
    check(not Path(".env").exists() or ".env" in read(".gitignore"),
          ".env is absent or ignored by Git", ".env exists but is not in .gitignore")
    lines = read("app.py").splitlines()
    safe = True
    for i, line in enumerate(lines):
        if "debug=True" in line:
            safe = any("__main__" in earlier for earlier in lines[max(0, i - 3):i])
    check(safe, "debug=True appears only in the local-run block", "debug=True may be enabled outside the local-run block", "WARN")


# ------------------------------------------------------------------ 5
def check_git():
    section("5. Git")
    if not Path(".git").exists() or not shutil.which("git"):
        report("WARN", "No Git repository found here (skipped)")
        return

    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()

    tracked = git("ls-files").splitlines()
    forbidden = [f for f in tracked if f.startswith("venv/") or f == "app.db" or f.endswith(".pkl")
                 or f in ("rename_app.py", ".env")]
    check(not forbidden, "Nothing private or generated is tracked", f"Tracked but should not be: {', '.join(forbidden)}")
    data = [f for f in tracked if f.startswith("data/") and f.endswith(".txt")]
    check(len(data) == 3, "data/train.txt, val.txt and test.txt are tracked (the build needs them)",
          f"Only {len(data)} of the 3 data files are tracked")
    for needed in ("wsgi.py", "requirements.txt", ".github/workflows/tests.yml"):
        check(needed in tracked, f"{needed} is tracked", f"{needed} is NOT tracked by Git")
    check(not git("status", "--porcelain"), "Everything is committed",
          "You have uncommitted changes (git add . and git commit)", "WARN")
    email = git("config", "user.email")
    check(email and "12345678+" not in email, f"Git email: {email}", "Git email is missing or is the example placeholder")
    check(git("rev-parse", "--abbrev-ref", "HEAD") == "main", "Branch is main", "Branch is not main (git branch -M main)", "WARN")
    ignore = read(".gitignore")
    ignored = {line.strip() for line in ignore.splitlines()}
    check(not ({"data", "data/", "data/*", "*.txt"} & ignored), ".gitignore does not hide the data folder",
          ".gitignore hides data/ or *.txt, so the build would have no data")
    for entry in ("venv/", "app.db"):
        check(entry in ignored, f".gitignore contains {entry}", f".gitignore is missing {entry}")


# ------------------------------------------------------------------ 6
def check_requirements_and_docker():
    section("6. Deployment files")
    reqs = read("requirements.txt").lower()
    for package in ("flask", "scikit-learn", "gunicorn"):
        check(package in reqs, f"requirements.txt lists {package}", f"requirements.txt is missing {package}")
    check(len([l for l in reqs.splitlines() if l.strip()]) < 15, "requirements.txt is short and clean",
          "requirements.txt is long (use the short version)", "WARN")
    wsgi = read("wsgi.py")
    check("SECRET_KEY" in wsgi and "SESSION_COOKIE_SECURE" in wsgi, "wsgi.py enforces SECRET_KEY and secure cookies",
          "wsgi.py is missing the production checks")
    if Path("Dockerfile").is_file():
        docker = read("Dockerfile")
        check("DATABASE=/tmp/app.db" in docker, "Dockerfile keeps the database in /tmp",
              "Dockerfile does not set DATABASE=/tmp/app.db", "WARN")
        check(docker.rstrip().splitlines()[-1].startswith("CMD"), "Dockerfile ends with the CMD line",
              "Dockerfile has extra text after CMD")
    readme = read("README.md").splitlines()
    if readme and readme[0].strip() == "---":
        report("WARN", "README still starts with the Hugging Face header (---). You can delete it for Render")
    else:
        report("PASS", "README has no leftover Hugging Face header")


# ------------------------------------------------------------------ 7
def check_data():
    section("7. Dataset")
    sizes = {}
    for name in ("train", "val", "test"):
        path = Path(f"data/{name}.txt")
        if not path.is_file():
            report("FAIL", f"data/{name}.txt is missing")
            continue
        rows, bad, labels = 0, 0, set()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            rows += 1
            if line.count(";") < 1:
                bad += 1
            else:
                labels.add(line.rsplit(";", 1)[1].strip())
        sizes[name] = rows
        check(bad == 0, f"data/{name}.txt: {rows} rows, all in 'text;label' format",
              f"data/{name}.txt has {bad} lines without a ';'")
        check(labels <= EXPECTED_LABELS and len(labels) == 6, f"data/{name}.txt has the 6 expected labels",
              f"data/{name}.txt labels are unexpected: {sorted(labels)}", "WARN")
    if sizes:
        check(sizes.get("train", 0) >= 10000, "Training set looks like the real dataset (about 16,000 rows)",
              f"Training set has only {sizes.get('train', 0)} rows. Is this the real dataset?", "WARN")


# ------------------------------------------------------------------ 8
SAMPLES = [("i am so happy today", "joy"), ("i feel so lonely and sad", "sadness"),
           ("i am furious and so angry", "anger"), ("i am terrified and anxious about tomorrow", "fear"),
           ("i love my family so much", "love")]


def check_model():
    section("8. Saved model")
    path = Path("models/emotion_model.pkl")
    if not check(path.is_file(), f"Model file exists ({path.stat().st_size / 1e6:.1f} MB)" if path.is_file() else "",
                 "models/emotion_model.pkl is missing. Run: python -m ml.train"):
        return
    try:
        from ml.predict import EmotionClassifier
        start = time.time()
        clf = EmotionClassifier()
        report("PASS", f"Model loads in {time.time() - start:.1f}s ({clf.name})")
        hits = 0
        for text, expected in SAMPLES:
            got = clf.predict(text)
            hits += got["emotion"] == expected
            print(f"       {text!r} -> {got['emotion']} ({got['confidence']:.0%})")
        check(hits >= 4, f"Sanity check: {hits}/5 obvious sentences classified as expected",
              f"Only {hits}/5 obvious sentences classified as expected. Retrain the model", "WARN")
        for file in ("models/metrics.json", "models/confusion_matrix.png"):
            check(Path(file).is_file(), f"{file} exists (the README uses it)", f"{file} is missing", "WARN")
    except Exception as error:
        report("FAIL", f"Model could not be loaded or used: {str(error)[:150]}")


# ------------------------------------------------------------------ 9
def check_safety_rules():
    section("9. Crisis-safety rules")
    from core.safety import assess_risk
    must_flag = ["I want to end my life", "i want to kill myself", "I can't go on", "i want to die",
                 "i have been thinking about suicide", "there is no reason to live"]
    must_not = ["I'm stressed about my exam", "I killed it in my presentation", "i had a great day",
                "this exam is killing me"]
    missed = [t for t in must_flag if assess_risk(t) != "high"]
    false_alarm = [t for t in must_not if assess_risk(t) == "high"]
    check(not missed, f"All {len(must_flag)} crisis phrases are flagged as high risk", f"Missed crisis phrases: {missed}")
    check(not false_alarm, f"None of {len(must_not)} everyday phrases is wrongly flagged", f"False alarms: {false_alarm}")
    report("WARN", "Known limit: indirect phrasing such as 'everyone would be better off without me' is not caught")


# ------------------------------------------------------------------ 10
def check_tests():
    section("10. Test suite")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                            capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    last = output.splitlines()[-1] if output else ""
    if "No module named pytest" in output:
        report("WARN", "pytest is not installed here (pip install pytest)")
    else:
        check(result.returncode == 0, f"pytest: {last}", f"pytest failed: {last}")


# ------------------------------------------------------------------ 11
def check_production_run():
    section("11. Full run in production mode (real model, HTTPS, temporary database)")
    secret_free = subprocess.run([sys.executable, "-c", "import wsgi"], capture_output=True, text=True,
                                 env={**os.environ, "APP_ENV": "production", "SECRET_KEY": ""})
    check(secret_free.returncode != 0 and "SECRET_KEY" in secret_free.stderr,
          "The app refuses to start in production without SECRET_KEY",
          "The app started in production WITHOUT a SECRET_KEY")

    tmp = tempfile.mkdtemp()
    os.environ.update({"APP_ENV": "production", "SECRET_KEY": secrets.token_hex(16),
                       "DATABASE": os.path.join(tmp, "check.db")})
    try:
        import wsgi
        app = wsgi.app
        client = app.test_client()
        base = "https://localhost"
        check(not app.debug, "Debug mode is off", "Debug mode is ON in production")

        check(client.get("/", base_url=base).status_code == 200, "GET / returns 200", "GET / failed")
        check(client.get("/health", base_url=base).get_json() == {"status": "ok"}, "GET /health is ok", "/health failed")
        check(client.get("/dashboard", base_url=base).status_code == 302, "Dashboard redirects guests to login", "Dashboard is open to guests")
        check(client.get("/api/mood", base_url=base).status_code == 401, "Mood API rejects guests (401)", "Mood API is open to guests")

        bad = client.get("/no-such-page", base_url=base)
        leak = b"Traceback" in bad.data or b"Debugger" in bad.data
        check(bad.status_code == 404 and not leak, "Unknown pages give a clean 404", "404 page leaks debug information")
        check(client.post("/api/chat", data="not json", content_type="text/plain", base_url=base).status_code == 400,
              "Bad chat input gives 400, not a crash", "Bad chat input caused a server error")
        check(client.post("/api/chat", json={"message": "a" * 1001}, base_url=base).status_code == 400,
              "Over-long messages are rejected", "Over-long messages are accepted")

        chat = client.post("/api/chat", json={"message": "i am so happy today"}, base_url=base)
        data = chat.get_json() or {}
        check(chat.status_code == 200 and data.get("reply") and data.get("risk") == "none",
              f"Normal chat works (emotion: {data.get('emotion')}, confidence: {data.get('confidence')})", "Normal chat failed")
        flags = chat.headers.get("Set-Cookie", "")
        check("Secure" in flags and "HttpOnly" in flags and "SameSite=Lax" in flags,
              "Session cookie is Secure, HttpOnly and SameSite=Lax", f"Cookie flags are weak: {flags}")
        crisis = client.post("/api/chat", json={"message": "i want to end my life"}, base_url=base).get_json() or {}
        check(crisis.get("risk") == "high" and len(crisis.get("helplines") or []) >= 3,
              "Crisis message returns the fixed reply and helplines", "Crisis handling is broken")

        def csrf():
            client.get("/login", base_url=base)
            with client.session_transaction(base_url=base) as s:
                return s["csrf"]

        no_token = client.post("/register", data={"username": "checker_one", "password": "longpassword1"}, base_url=base)
        check(no_token.status_code == 400, "Sign-up without a CSRF token is rejected", "Sign-up works without a CSRF token")
        ok = client.post("/register", data={"username": "checker_one", "password": "longpassword1", "csrf": csrf()}, base_url=base)
        check(ok.status_code == 302, "Sign-up works", f"Sign-up failed ({ok.status_code})")
        client.post("/api/chat", json={"message": "i feel so lonely and sad"}, base_url=base)
        client.post("/api/chat", json={"message": "hello"}, base_url=base)
        mood = client.get("/api/mood?days=30&tz=330", base_url=base).get_json() or {}
        check(mood.get("total") == 1, "Mood is saved for check-ins and skipped for greetings", f"Mood total is {mood.get('total')}, expected 1")
        check(client.get("/dashboard", base_url=base).status_code == 200, "Dashboard opens when logged in", "Dashboard failed when logged in")
        no_csrf_delete = client.delete("/api/mood", base_url=base)
        check(no_csrf_delete.status_code == 400, "Deleting data needs a CSRF token", "Data can be deleted without a CSRF token")
        deleted = client.delete("/api/mood", headers={"X-CSRF-Token": csrf()}, base_url=base)
        total = (client.get("/api/mood", base_url=base).get_json() or {}).get("total")
        check(deleted.status_code == 200 and total == 0, "Delete my data works", "Delete my data failed")
        client.post("/logout", data={"csrf": csrf()}, base_url=base)
        check(client.get("/api/mood", base_url=base).status_code == 401, "Log out works", "Still logged in after logout")

        import sqlite3
        con = sqlite3.connect(os.path.join(tmp, "check.db"))
        columns = [row[1] for row in con.execute("PRAGMA table_info(mood_logs)")]
        stored = con.execute("SELECT pw_hash FROM users").fetchone()[0]
        con.close()
        check(not {"message", "text", "content"} & set(columns), "The database has no column for message text", "The database can store message text")
        check(stored != "longpassword1" and ":" in stored, "Passwords are stored hashed", "Passwords are NOT hashed")

        try:
            import psutil
            mb = psutil.Process().memory_info().rss / 1e6
            check(mb < 400, f"Memory after loading everything: {mb:.0f} MB", f"Memory is {mb:.0f} MB, close to a 512 MB limit", "WARN")
        except ImportError:
            report("WARN", "Memory not measured (pip install psutil to measure it)")
    except Exception as error:
        report("FAIL", f"Production run crashed: {type(error).__name__}: {str(error)[:200]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print(f"Pre-deployment check for {ROOT}")
    for step in (check_environment, check_files, check_leftovers, check_secrets, check_git,
                 check_requirements_and_docker, check_data, check_model, check_safety_rules,
                 check_tests, check_production_run):
        try:
            step()
        except Exception as error:
            report("FAIL", f"{step.__name__} crashed: {type(error).__name__}: {str(error)[:150]}")

    print("\n" + "=" * 60)
    print(f"RESULT: {counts['PASS']} passed, {counts['WARN']} warnings, {counts['FAIL']} FAILED")
    if counts["FAIL"]:
        print("Fix every [FAIL] line, then run this again before deploying.")
    else:
        print("No failures. Read the [WARN] lines, then you are ready to deploy.")
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()