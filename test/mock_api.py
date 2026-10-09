"""A stand-in for the Excalibase deploy API, one scenario per run.

Usage: mock_api.py <scenario> <port file> <request log>
It writes the port it listens on to <port file> and each request to <request log>.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

SCENARIO, PORT_FILE, LOG = sys.argv[1], sys.argv[2], sys.argv[3]
APP = "/api/projects/proj-1/apps/app-1"
COMMIT = "9fceb02d0ae598e95dc970b74767f19372d61af8"
IMAGE = "ghcr.io/acme/web@sha256:" + "ab" * 32
URL = "https://web.apps.test"
polls = 0


def deploy(status, **extra):
    return {"id": "dep-1", "appId": "app-1", "status": status, "url": URL, **extra}


FAILED = {"failureReason": "the container never became ready"}

# What POST .../deploy answers, per scenario: (code, body); None is a non-JSON edge answer.
POSTS = {
    "wait-live": (200, deploy("succeeded")),
    "wait-failed": (422, deploy("failed", error="deploy dep-1 failed: the container never became ready", **FAILED)),
    "wait-superseded": (409, deploy("superseded", error="deploy dep-1 was superseded")),
    "legacy-live": (202, deploy("pending")),
    "legacy-failed": (202, deploy("pending")),
    "wait-ran-out": (504, deploy("rolling", error="deploy dep-1 is still rolling")),
    "edge-cut": (504, None),
    "edge-cut-old-deploy": (504, None),
    "refused": (422, {"error": "the registry has no such image", "status": 422}),
    "api-down": (202, deploy("pending")),
    "never-live": (202, deploy("pending")),
}

# What GET .../deploys/dep-1 answers on each poll, the last repeating.
POLLS = {
    "legacy-live": ["rolling", "succeeded"],
    "legacy-failed": ["rolling", "failed"],
    "wait-ran-out": ["succeeded"],
    "edge-cut": ["rolling", "succeeded"],
    "api-down": ["down"],
    "never-live": ["rolling"],
}


def created(minutes_ago):
    at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return at.strftime("%Y-%m-%dT%H:%M:%S.123456Z")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, body):
        raw = json.dumps(body).encode() if body is not None else b"<html>504 Gateway Time-out</html>"
        self.send_response(code)
        self.send_header("Content-Type", "application/json" if body is not None else "text/html")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def record(self, body=""):
        with open(LOG, "a") as log:
            log.write(json.dumps({"method": self.command, "path": self.path, "body": body,
                                  "auth": self.headers.get("Authorization")}) + "\n")

    def authorized(self):
        if self.headers.get("Authorization") == "Bearer excali_test_token":
            return True
        self.reply(401, {"error": "unauthenticated", "status": 401})
        return False

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        self.record(body)
        if not self.authorized():
            return
        if self.path.split("?")[0] != APP + "/deploy":
            return self.reply(404, {"error": "not found"})
        self.reply(*POSTS[SCENARIO])

    def do_GET(self):
        global polls
        self.record()
        if not self.authorized():
            return
        if self.path == APP + "/deploys?limit=20":
            minutes = 60 if SCENARIO == "edge-cut-old-deploy" else 0
            return self.reply(200, [deploy("rolling", commitSha=COMMIT, imageRef=IMAGE, image=IMAGE, createdAt=created(minutes))])
        if self.path != APP + "/deploys/dep-1":
            return self.reply(404, {"error": "not found"})
        statuses = POLLS[SCENARIO]
        status = statuses[min(polls, len(statuses) - 1)]
        polls += 1
        if status == "down":
            return self.reply(503, None)
        self.reply(200, deploy(status, **(FAILED if status == "failed" else {})))


server = HTTPServer(("127.0.0.1", 0), Handler)
with open(PORT_FILE, "w") as port_file:
    port_file.write(str(server.server_address[1]))
server.serve_forever()
