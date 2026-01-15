#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import json
from datetime import datetime

PORT = 4501

class MonitorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            # Check services
            vm_active = subprocess.run(['systemctl', 'is-active', 'vm-server'], 
                                      capture_output=True, text=True).stdout.strip() == 'active'
            tunnel_active = subprocess.run(['pgrep', '-f', 'cloudflared'], 
                                         capture_output=True).returncode == 0
            
            # Get main URL
            try:
                result = subprocess.run('grep -o "https://[^[:space:]]*\\.trycloudflare\\.com" /home/ubuntu/tunnel.log 2>/dev/null | tail -1',
                                      shell=True, capture_output=True, text=True, timeout=5)
                main_url = result.stdout.strip()
            except:
                main_url = ""
            
            html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>VM Monitor</title>
<meta http-equiv="refresh" content="30">
<style>
body {
    font-family: Arial, sans-serif;
    background: linear-gradient(135deg, #667eea, #764ba2);
    margin: 0;
    padding: 20px;
    min-height: 100vh;
}
.container {
    max-width: 900px;
    margin: 0 auto;
    background: white;
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
h1 {
    text-align: center;
    color: #333;
    margin-bottom: 30px;
}
.status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}
.status-card {
    background: #f5f5f5;
    padding: 20px;
    border-radius: 10px;
    border-left: 4px solid #ddd;
}
.status-card.online { border-left-color: #4CAF50; }
.status-card.offline { border-left-color: #f44336; }
.status-card h3 {
    color: #666;
    font-size: 14px;
    margin: 0 0 10px 0;
}
.status-value {
    font-size: 20px;
    font-weight: bold;
}
.online .status-value { color: #4CAF50; }
.offline .status-value { color: #f44336; }
.actions {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 15px;
    margin: 30px 0;
}
.btn {
    padding: 15px;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: bold;
    cursor: pointer;
    color: white;
    transition: all 0.3s;
}
.btn-check { background: #2196F3; }
.btn-restart { background: #4CAF50; }
.btn-full { background: #ff9800; }
.btn-danger { background: #f44336; }
.btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
}
.main-link {
    display: """ + ('block' if main_url else 'none') + """;
    text-align: center;
    margin: 30px 0;
}
.main-link a {
    display: inline-block;
    padding: 20px 40px;
    background: #4CAF50;
    color: white;
    text-decoration: none;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
}
.main-link a:hover {
    background: #45a049;
}
#output {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 20px;
    border-radius: 10px;
    font-family: monospace;
    font-size: 13px;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    margin-top: 20px;
    display: none;
}
#output.active { display: block; }
.loading {
    display: none;
    text-align: center;
    padding: 20px;
    color: #667eea;
}
.loading.active { display: block; }
</style>
</head>
<body>
<div class="container">
<h1>🛡️ VM Monitor & Recovery</h1>

<div class="status-grid">
    <div class="status-card """ + ('online' if vm_active else 'offline') + """">
        <h3>MAIN SERVER</h3>
        <div class="status-value">""" + ('● ONLINE' if vm_active else '○ OFFLINE') + """</div>
    </div>
    
    <div class="status-card """ + ('online' if tunnel_active else 'offline') + """">
        <h3>CLOUDFLARE TUNNEL</h3>
        <div class="status-value">""" + ('● CONNECTED' if tunnel_active else '○ DISCONNECTED') + """</div>
    </div>
    
    <div class="status-card online">
        <h3>MONITOR SERVICE</h3>
        <div class="status-value">● ACTIVE</div>
    </div>
    
    <div class="status-card online">
        <h3>VM HOST</h3>
        <div class="status-value">158.180.56.74</div>
    </div>
</div>

""" + (f'<div class="main-link"><a href="{main_url}" target="_blank">🚀 Open Main Terminal</a></div>' if main_url else '') + """

<h2 style="text-align: center; color: #333; margin: 30px 0 20px;">Recovery Actions</h2>

<div class="actions">
    <button class="btn btn-check" id="btnCheck">🔍 Check Status</button>
    <button class="btn btn-restart" id="btnServer">🔄 Restart Server</button>
    <button class="btn btn-restart" id="btnTunnel">🔄 Restart Tunnel</button>
    <button class="btn btn-full" id="btnFull">🔥 Full Restart</button>
    <button class="btn btn-check" id="btnUrl">🔗 Get URLs</button>
    <button class="btn btn-check" id="btnLogs">📝 View Logs</button>
</div>

<div class="loading" id="loading">Executing command...</div>
<div id="output"></div>

</div>

<script>
const output = document.getElementById('output');
const loading = document.getElementById('loading');

// Simple direct implementation
document.getElementById('btnCheck').onclick = function() { runAction('check'); };
document.getElementById('btnServer').onclick = function() { runAction('restart-server'); };
document.getElementById('btnTunnel').onclick = function() { runAction('restart-tunnel'); };
document.getElementById('btnFull').onclick = function() { runAction('full-restart'); };
document.getElementById('btnUrl').onclick = function() { runAction('get-url'); };
document.getElementById('btnLogs').onclick = function() { runAction('view-logs'); };

async function runAction(action) {
    loading.classList.add('active');
    output.classList.add('active');
    output.textContent = 'Executing ' + action + '...\n';
    
    try {
        const response = await fetch('/action?cmd=' + action);
        const data = await response.json();
        output.textContent = data.output || 'Command executed';
        
        if (data.success && action.includes('restart')) {
            output.textContent += '\n\nPage will reload in 5 seconds...';
            setTimeout(() => location.reload(), 5000);
        }
    } catch(error) {
        output.textContent = 'Error: ' + error.message;
    }
    
    loading.classList.remove('active');
}
</script>
</body>
</html>"""
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        
        elif self.path.startswith('/action'):
            # Extract command
            cmd_name = self.path.split('=')[1] if '=' in self.path else ''
            
            # Command mapping
            commands = {
                'check': 'echo "=== VM Server Status ==="; systemctl status vm-server --no-pager | head -5; echo "\n=== Cloudflare Tunnels ==="; ps aux | grep cloudflared | grep -v grep',
                'restart-server': 'sudo systemctl restart vm-server && echo "✅ Server restarted successfully"',
                'restart-tunnel': 'pkill -f cloudflared; sleep 1; nohup /home/ubuntu/start_tunnel.sh > /dev/null 2>&1 & echo "✅ Tunnel restarted"',
                'full-restart': 'sudo systemctl restart vm-server vm-monitor; pkill -f cloudflared; sleep 1; nohup /home/ubuntu/start_tunnel.sh > /dev/null 2>&1 & nohup /home/ubuntu/start_monitor_tunnel.sh > /dev/null 2>&1 & echo "✅ Full restart completed"',
                'get-url': 'echo "=== Current URLs ==="; grep -o "https://[^[:space:]]*\\.trycloudflare\\.com" /home/ubuntu/tunnel.log /home/ubuntu/monitor_tunnel.log /home/ubuntu/tunnel_new.log /home/ubuntu/monitor_new.log 2>/dev/null | tail -5',
                'view-logs': 'echo "=== Recent Tunnel Logs ==="; tail -20 /home/ubuntu/tunnel.log 2>/dev/null'
            }
            
            cmd = commands.get(cmd_name, 'echo "Unknown command: ' + cmd_name + '"')
            
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                output = {
                    'success': result.returncode == 0,
                    'output': result.stdout + result.stderr
                }
            except subprocess.TimeoutExpired:
                output = {'success': False, 'output': 'Command timed out after 30 seconds'}
            except Exception as e:
                output = {'success': False, 'output': f'Error: {str(e)}'}
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(output).encode('utf-8'))
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        return  # Suppress logs

print(f"Monitor server starting on port {PORT}")
httpd = HTTPServer(('0.0.0.0', PORT), MonitorHandler)
httpd.serve_forever()

