#!/usr/bin/env python3
"""Keep one workflow service warm and run its unchanged CLI main() per HTTP request.

POST /run with form fields (multipart) sets the allowed workflow variables, runs main() and
returns its stdout (200) or its stderr (422). GET /healthz reports readiness.
Requests run strictly one after another, so per-request environment changes are
safe; concurrency comes from additional replicas behind the Kubernetes Service.
"""
import argparse
import contextlib
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib
import importlib.util
import io
import json
import os
import sys
import traceback

# Exactly the variables the workflow passes to services; anything else is rejected.
ALLOWED_ENV = frozenset({
    "WORKFLOW_EVALUATION_ID", "MODEL_KEY", "REFERENCE_KEY", "WORKFLOW_INPUT_PATH", "WORKFLOW_OUTPUT_PATH",
    "ANALYSIS_INPUT_PATH", "EVALUATION_INPUT_GZIP_BASE64", "TEXT_EVIDENCE", "GRAPH_MATCHING_DIAGNOSTICS",
})
MAX_BODY_BYTES = 16 * 1024 * 1024


def load_main(path):
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("service_main", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def parse_env(content_type, raw):
    """Read variables from multipart/form-data, which Dagu's http.request `form` sends with proper encoding."""
    if not content_type or not content_type.startswith("multipart/form-data"):
        raise ValueError("request must be multipart/form-data")
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\n\r\n".encode("latin-1") + raw)
    env = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name or name in env:
            raise ValueError("form fields need unique names")
        env[name] = part.get_payload(decode=True).decode("utf-8")
    unknown = set(env) - ALLOWED_ENV
    if unknown:
        raise ValueError(f"unsupported variables: {', '.join(sorted(unknown))}")
    return env


def run_main(main, env):
    for name in ALLOWED_ENV:
        os.environ.pop(name, None)
    os.environ.update(env)
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            sys.stdin = io.StringIO("")
            try:
                code = main()
            except SystemExit as error:
                code = error.code if isinstance(error.code, int) else 1
            except Exception:
                # A crashing CLI process would exit non-zero; report the same instead of dropping the connection.
                traceback.print_exc()
                code = 1
    finally:
        for name in env:
            os.environ.pop(name, None)
    return code, stdout.getvalue(), stderr.getvalue()


class Server(HTTPServer):
    # Waiting requests queue in the listen backlog; the default of 5 is too small for bursts.
    request_queue_size = 64


def handler(main, service):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type="application/json"):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/healthz":
                self._send(200, '{"status":"ok"}')
            else:
                self._send(404, '{"error":"not found"}')

        def do_POST(self):
            if self.path != "/run":
                return self._send(404, '{"error":"not found"}')
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY_BYTES:
                    raise ValueError("request body missing or too large")
                env = parse_env(self.headers.get("Content-Type"), self.rfile.read(length))
            except (ValueError, UnicodeDecodeError) as error:
                return self._send(400, json.dumps({"error": str(error)}))
            code, out, err = run_main(main, env)
            sys.stderr.write(err)
            if code == 0:
                self._send(200, out)
            else:
                self._send(422, err or f"[{service}] failed with exit code {code}\n", "text/plain; charset=utf-8")

        def log_message(self, format, *args):
            sys.stderr.write(f"[{service}] {self.address_string()} {format % args}\n")

    return Handler


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("main_path", help="Path to the service's main.py")
    cli.add_argument("--port", type=int, default=8080)
    cli.add_argument("--warmup", help="module:function to call once before accepting requests")
    args = cli.parse_args()
    service_main = load_main(args.main_path)
    # The service CLIs parse sys.argv; keep it free of the server's own arguments.
    sys.argv = [args.main_path]
    if args.warmup:
        module, function = args.warmup.split(":", 1)
        getattr(importlib.import_module(module), function)()
    server = Server(("0.0.0.0", args.port), handler(service_main, os.path.basename(os.path.dirname(args.main_path))))
    print(f"workflow server ready on :{args.port} for {args.main_path}", file=sys.stderr, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
