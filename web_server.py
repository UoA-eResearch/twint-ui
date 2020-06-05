#!/usr/bin/env python3
from gevent import monkey
monkey.patch_all()

import twint
from bottle import Bottle, request, response, static_file, run, abort
import os
import csv
import datetime
import subprocess
from pathvalidate import sanitize_filename
import json
import urllib

from gevent.pywsgi import WSGIServer
from geventwebsocket import WebSocketError
from geventwebsocket.handler import WebSocketHandler

app = Bottle()

os.makedirs("csvs", exist_ok=True)
os.makedirs("logs", exist_ok=True)

@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'PUT, GET, POST, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

@app.get('/')
def index():
    return static_file("index.html", root='.')

@app.get("/csvs/<filename>")
def get_csv(filename):
    filename = urllib.parse.unquote_plus(filename)
    return static_file(filename, root='csvs')

@app.post("/")
def run_twint():
    query = request.params.get("query")
    bd = request.params.get("bd", None)
    ed = request.params.get("ed", None)
    c = twint.Config()
    c.Search = query
    if bd:
        c.Since = bd
    if ed:
        c.Until = ed
    c.Store_csv = True
    c.Output = f"csvs/{query}_{bd}_{ed}.csv"
    twint.run.Search(c)
    return c.Output

@app.get("/health")
def health():
    return "OK"

@app.get("/list")
def list_csvs():
    return subprocess.run("wc -l logs/*", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout

@app.route("/ws")
def handle_ws():
    wsock = request.environ.get('wsgi.websocket')
    if not wsock:
        abort(400, 'Expected WebSocket request.')
    while True:
        message = wsock.receive()
        if not message:
            return
        try:
            params = json.loads(message)
            assert type(params) == dict
        except:
            wsock.send('{"error": "unable to parse JSON"}')
            continue
        request_type = params.get("request_type")
        try:
            if request_type == "run_twint":
                query = params.get("query")
                filename = sanitize_filename(query)
                args = ["twint", "-s", query, "--csv", "--output", f"csvs/{filename}.csv", "--proxy-type", "tor"]
                if params.get("limit"):
                    args.extend(["--limit", str(int(params.get("limit")))])
                with open(f"logs/{filename}.txt", "w") as logfile:
                    print(args)
                    subprocess.Popen(args, stdout=logfile)
                wsock.send(json.dumps({"request_type": request_type, "filename": filename}))
            elif request_type == "list":
                proc = subprocess.run("cd logs && wc -l *", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                if proc.stderr:
                    wsock.send(json.dumps({
                        "request_type": request_type,
                        "error": proc.stderr
                    }))
                    continue
                output = proc.stdout.strip().split("\n")
                results = {
                    "request_type": request_type
                }
                for line in output:
                    bits = line.split(maxsplit=1)
                    filename = os.path.splitext(bits[1])[0]
                    results[filename] = int(bits[0])
                wsock.send(json.dumps(results))
            elif request_type == "wc":
                filename = sanitize_filename(params.get("filename"))
                wsock.send(subprocess.run(["wc", "-l", f"logs/{filename}"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout)
            elif request_type == "tail":
                filename = sanitize_filename(params.get("tail"))
                wsock.send(subprocess.run(["tail", f"logs/{filename}"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout)
            else:
                wsock.send('{"error": "Unknown request type"}')
        except WebSocketError as e:
            print(e)
        except Exception as e:
            wsock.send(e.message)


if __name__ == "__main__":
    app.run(
        host='localhost',
        port=8081,
        server='gunicorn',
        workers=8,
        worker_class="geventwebsocket.gunicorn.workers.GeventWebSocketWorker",
        timeout=86400
    )
