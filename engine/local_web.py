"""Authenticated loopback UI. All content comes from the selected project."""
from __future__ import annotations

import hashlib
import hmac
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlencode, urlsplit

import knowledge
import workflow


def make_server(root, port=0):
    secret = secrets.token_urlsafe(32)
    cookie = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    token_used = False
    import threading
    token_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_page(self, status, content, headers=()):
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))

        def origin_ok(self):
            return (self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"
                    and self.headers.get("Sec-Fetch-Site") not in ("cross-site", "same-site")
                    and self.headers.get("Origin", self.server.origin) == self.server.origin)

        def authed(self):
            return any(hmac.compare_digest(pair.strip().encode(), ("sourcenest=" + cookie).encode())
                       for pair in self.headers.get("Cookie", "").split(";"))

        def do_GET(self):
            nonlocal token_used
            if not self.origin_ok() or len(self.path) > 2400:
                self.send_page(403, "Access denied")
                return
            url = urlsplit(self.path)
            query = parse_qs(url.query, max_num_fields=20)
            if url.path == "/open":
                with token_lock:
                    token = query.get("token", [""])[0]
                    if token_used or not hmac.compare_digest(token.encode(), secret.encode()):
                        self.send_page(403, "Start SourceNest again for a fresh access link.")
                        return
                    token_used = True
                self.send_page(303, "", [("Location", "/"),
                                         ("Set-Cookie", f"sourcenest={cookie}; HttpOnly; SameSite=Strict; Path=/")])
                return
            if not self.authed() or url.path != "/":
                self.send_page(403, "Open the local access link printed by SourceNest.")
                return
            try:
                content = page(root, query, csrf)
            except (ValueError, OSError, UnicodeError):
                self.send_page(400, "Could not read the selected project or source.")
                return
            self.send_page(200, content)

        def do_POST(self):
            if not self.origin_ok() or not self.authed() or self.path != "/capture":
                self.send_page(403, "Access denied")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 64000 or self.headers.get_content_type() != "application/x-www-form-urlencoded":
                    raise ValueError("Invalid form")
                data = {k: v[0] for k, v in parse_qs(self.rfile.read(size).decode(), max_num_fields=8).items()}
                if not hmac.compare_digest(data.get("csrf", "").encode(), csrf.encode()):
                    self.send_page(403, "Invalid form token")
                    return
                project = workflow.project(root, data.get("project", ""))["id"]
                created = capture(root, project, {"title": data.get("title"), "body": data.get("body")})
                self.send_page(303, "", [("Location", "/?" + urlencode({"project": project, "source": Path(created["created"]).name}))])
            except (ValueError, OSError, UnicodeError):
                self.send_page(400, "Capture failed. Check the title, text and project.")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.origin = f"http://127.0.0.1:{server.server_port}"
    return server, server.origin + "/open?token=" + secret


def capture(root, project, data):
    workflow.fields(data, "title body url")
    title = workflow.clean(data.get("title"), "capture title", 160)
    body = workflow.clean(data.get("body"), "capture text", 15000)
    if data.get("url"):
        url = workflow.clean(data["url"], "source URL", 2048)
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise ValueError("Expected a public-format HTTP(S) URL without credentials")
        body += "\n\nSource URL: " + url
    identifier = hashlib.sha256((title + "\n" + body).encode()).hexdigest()[:16]
    return knowledge.create(root, {"project": project, "title": title,
                                  "body": body, "slug": "inbox-" + identifier, "sensitivity": "sensitive"})


def page(root, query, csrf):
    esc = html.escape
    project = query.get("project", [""])[0]
    terms = query.get("q", [""])[0]
    selected = query.get("source", [""])[0]
    options = ['<option value="">Choose a project</option>']
    for row in workflow.workspaces(root):
        active = " selected" if row["id"] == project else ""
        options.append(f'<option value="{esc(row["id"])}"{active}>{esc(row["name"])}</option>')
    out = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>SourceNest</title><style>body{max-width:54rem;margin:2rem auto;padding:0 1rem;font:1rem system-ui;color:#182623;background:#f4f7f5}'
           'h1{color:#23564a}form,article{background:white;padding:1rem;margin:1rem 0;border:1px solid #baccc4;border-radius:.5rem}'
           'label{display:block;margin:.4rem 0}textarea,input,select,button{font:inherit;padding:.4rem;max-width:100%}'
           'textarea{display:block;width:95%}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}a{color:#145247}</style>',
           '<main><h1>SourceNest</h1><form method="get"><label>Project <select name="project">', *options,
           f'</select></label><label>Search notes <input name="q" value="{esc(terms)}" maxlength="500"></label><button>Search</button></form>']
    if project:
        project = workflow.project(root, project)["id"]
        if selected:
            source = selected if "/" in selected else "notes/" + selected
            note = workflow.read_note(root, project, source)
            out.append(f'<article><h2>{esc(note["source"])}</h2><pre>{esc(note["text"])}</pre></article>')
        for record in knowledge.lookup(root, project, terms, 8, 4800):
            link = "/?" + urlencode({"project": project, "q": terms, "source": record["source"]})
            out.append(f'<article><h2><a href="{esc(link)}">{esc(record["title"])}</a></h2><pre>{esc(record["body"])}</pre></article>')
        out.append(f'<form method="post" action="/capture"><h2>Capture a private note</h2>'
                   f'<input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="project" value="{esc(project)}">'
                   '<label>Title <input name="title" required maxlength="160"></label>'
                   '<label>Note <textarea name="body" required maxlength="15000" rows="5"></textarea></label><button>Save note</button></form>')
    return "".join(out) + "</main></html>"


def serve(root, port):
    server, url = make_server(root, port)
    with server:
        print(url, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
