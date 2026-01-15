#!/usr/bin/env python3
import http.server
import socketserver
import subprocess
import json
import urllib.parse
import signal
import sys

def signal_handler(sig, frame):
    print('Shutting down...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

PORT = 4500

class TerminalHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Oracle VM Terminal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            color: #fff;
        }
        .header {
            background: rgba(0,0,0,0.3);
            padding: 15px 20px;
            backdrop-filter: blur(10px);
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .header h1 {
            font-size: 24px;
            font-weight: 300;
        }
        .status {
            background: #4CAF50;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 13px;
        }
        .container {
            flex: 1;
            padding: 20px;
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
        }
        .controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }
        .btn {
            padding: 10px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.3);
            color: #fff;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.3s;
            backdrop-filter: blur(5px);
        }
        .btn:hover {
            background: rgba(255,255,255,0.2);
            transform: translateY(-2px);
        }
        .terminal {
            background: rgba(0,0,0,0.7);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 14px;
            height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
            backdrop-filter: blur(10px);
            line-height: 1.5;
        }
        .input-box {
            display: flex;
            margin-top: 20px;
            background: rgba(0,0,0,0.5);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            overflow: hidden;
        }
        #cmd {
            flex: 1;
            padding: 15px;
            background: transparent;
            border: none;
            color: #fff;
            font-family: 'Consolas', monospace;
            font-size: 14px;
            outline: none;
        }
        #cmd::placeholder {
            color: rgba(255,255,255,0.5);
        }
        .btn-run {
            padding: 15px 30px;
            background: #4CAF50;
            color: #fff;
            border: none;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: background 0.3s;
        }
        .btn-run:hover {
            background: #45a049;
        }
        .cmd-line { color: #4CAF50; }
        .output { color: #fff; display: block; margin: 5px 0 15px 20px; }
        .error { color: #ff6b6b; }
        .loading {
            display: none;
            color: #4CAF50;
            margin: 10px 0;
        }
        .loading.active {
            display: block;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🖥️ Oracle VM Terminal</h1>
        <div class="status">● Connected 158.180.56.74</div>
    </div>
    
    <div class="container">
        <div class="controls">
            <button class="btn" onclick="run('pwd')">📁 PWD</button>
            <button class="btn" onclick="run('ls -la')">📄 List</button>
            <button class="btn" onclick="run('free -h')">💾 RAM</button>
            <button class="btn" onclick="run('df -h')">💿 Disk</button>
            <button class="btn" onclick="run('docker ps')">🐳 Docker</button>
            <button class="btn" onclick="run('pm2 list')">⚙️ PM2</button>
            <button class="btn" onclick="run('ps aux | head -20')">📊 Process</button>
            <button class="btn" onclick="run('systemctl status vm-server')">🔧 Service</button>
            <button class="btn" onclick="run('uptime')">⏰ Uptime</button>
            <button class="btn" onclick="run('date')">📅 Date</button>
            <button class="btn" onclick="run('whoami')">👤 User</button>
            <button class="btn" onclick="clearTerm()">🗑️ Clear</button>
        </div>
        
        <div class="terminal" id="term">Welcome to Oracle VM Terminal
Ready to execute commands...

$ </div>
        
        <div class="loading">Executing command...</div>
        
        <div class="input-box">
            <input type="text" id="cmd" placeholder="Enter command and press Enter" autocomplete="off">
            <button class="btn-run" onclick="execute()">Execute</button>
        </div>
    </div>
    
    <script>
        const term = document.getElementById('term');
        const input = document.getElementById('cmd');
        const loading = document.querySelector('.loading');
        let history = [];
        let histIdx = -1;
        
        input.focus();
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                execute();
            } else if (e.key === 'ArrowUp' && history.length > 0) {
                e.preventDefault();
                histIdx = Math.min(histIdx + 1, history.length - 1);
                input.value = history[history.length - 1 - histIdx];
            } else if (e.key === 'ArrowDown' && histIdx > 0) {
                e.preventDefault();
                histIdx--;
                input.value = history[history.length - 1 - histIdx];
            } else if (e.key === 'ArrowDown' && histIdx === 0) {
                e.preventDefault();
                histIdx = -1;
                input.value = '';
            }
        });
        
        async function execute() {
            const cmd = input.value.trim();
            if (!cmd) return;
            
            history.push(cmd);
            if (history.length > 100) history.shift();
            histIdx = -1;
            
            term.innerHTML += '<span class="cmd-line">$ ' + escapeHtml(cmd) + '</span>\n';
            input.value = '';
            loading.classList.add('active');
            
            try {
                const res = await fetch('/exec', {
                    method: 'POST',
                    body: 'cmd=' + encodeURIComponent(cmd),
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'}
                });
                const text = await res.text();
                term.innerHTML += '<span class="output">' + escapeHtml(text) + '</span>\n$ ';
            } catch(e) {
                term.innerHTML += '<span class="error">Error: ' + e.message + '</span>\n$ ';
            }
            
            loading.classList.remove('active');
            term.scrollTop = term.scrollHeight;
            input.focus();
        }
        
        function run(cmd) {
            input.value = cmd;
            execute();
        }
        
        function clearTerm() {
            term.innerHTML = 'Terminal cleared\n$ ';
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>'''
        self.wfile.write(html.encode('utf-8'))
    
    def do_POST(self):
        if self.path == '/exec':
            length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(length).decode('utf-8')
            params = urllib.parse.parse_qs(data)
            cmd = params.get('cmd', [''])[0]
            
            if not cmd:
                self.send_response(400)
                self.end_headers()
                return
            
            # Security: limit dangerous commands
            dangerous = ['rm -rf /', 'dd if=', 'mkfs', 'format']
            if any(d in cmd for d in dangerous):
                output = "Command blocked for safety"
            else:
                try:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd='/home/ubuntu'
                    )
                    output = result.stdout if result.stdout else (result.stderr if result.stderr else "Command executed")
                except subprocess.TimeoutExpired:
                    output = "Command timed out after 30 seconds"
                except Exception as e:
                    output = f"Error: {str(e)}"
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(output.encode('utf-8'))
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        return  # Suppress logs

print(f"Enhanced Terminal Server starting on port {PORT}")
with socketserver.TCPServer(("0.0.0.0", PORT), TerminalHandler) as httpd:
    httpd.serve_forever()

