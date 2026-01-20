#!/usr/bin/env python3
"""
Oracle Admin API v2.0 for VM2
Backend for MCP Hub with all vm_* tools support

Port: 5001
Runs on VM2 (158.180.56.74)
"""

from flask import Flask, request, jsonify
import subprocess
import os
import json
import re
from datetime import datetime
from functools import wraps

app = Flask(__name__)

PORT = int(os.environ.get('ADMIN_PORT', 5001))
WORK_DIR = '/home/ubuntu'
SERVICES_DIR = '/home/ubuntu/services'

def run_cmd(cmd, timeout=30, cwd=None):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd or WORK_DIR
        )
        return {
            'success': result.returncode == 0,
            'output': result.stdout.strip(),
            'error': result.stderr.strip(),
            'code': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': f'Timeout {timeout}s'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '2.0.0', 'vm': 'vm2', 'ip': '158.180.56.74'})

# ============== FILES ==============
@app.route('/files/list', methods=['POST'])
def files_list():
    path = (request.json or {}).get('path', WORK_DIR)
    if '..' in path: return jsonify({'error': 'Invalid path'})
    result = run_cmd(f'ls -la "{path}" 2>/dev/null')
    files = []
    for line in result['output'].split('\n')[1:]:
        if not line.strip(): continue
        parts = line.split()
        if len(parts) >= 9:
            name = ' '.join(parts[8:])
            if name not in ['.', '..']:
                files.append({'name': name, 'isDir': line.startswith('d'), 'size': parts[4]})
    return jsonify({'files': files, 'path': path})

@app.route('/files/read', methods=['POST'])
def files_read():
    path = (request.json or {}).get('path')
    if not path: return jsonify({'error': 'path required'})
    if '..' in path: return jsonify({'error': 'Invalid path'})
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return jsonify({'content': f.read(), 'path': path})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/files/write', methods=['POST'])
def files_write():
    data = request.json or {}
    path, content = data.get('path'), data.get('content')
    if not path or content is None: return jsonify({'error': 'path and content required'})
    if '..' in path: return jsonify({'error': 'Invalid path'})
    try:
        if os.path.exists(path): run_cmd(f'cp "{path}" "{path}.bak"')
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w') as f: f.write(content)
        return jsonify({'success': True, 'path': path})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/files/delete', methods=['POST'])
def files_delete():
    path = (request.json or {}).get('path')
    if not path or '..' in path or path in ['/', '/home']: return jsonify({'error': 'Invalid path'})
    run_cmd(f'rm -rf "{path}"')
    return jsonify({'success': True})

# ============== SERVICES ==============
@app.route('/services/list', methods=['GET'])
def services_list():
    result = run_cmd('pm2 jlist 2>/dev/null || echo "[]"')
    services = []
    try:
        for svc in json.loads(result['output'] or '[]'):
            services.append({
                'name': svc.get('name'),
                'active': svc.get('pm2_env', {}).get('status') == 'online',
                'description': 'PM2 service'
            })
    except: pass
    return jsonify({'services': services})

@app.route('/services/status', methods=['POST'])
def services_status():
    service = (request.json or {}).get('service')
    if not service: return jsonify({'error': 'service required'})
    result = run_cmd(f'pm2 show {service} 2>/dev/null')
    active = 'online' in result['output'].lower()
    return jsonify({'service': service, 'active': active, 'status': result['output'][:500]})

@app.route('/services/logs', methods=['POST'])
def services_logs():
    data = request.json or {}
    service, lines = data.get('service'), data.get('lines', 50)
    if not service: return jsonify({'error': 'service required'})
    result = run_cmd(f'pm2 logs {service} --nostream --lines {lines} 2>&1')
    return jsonify({'logs': result['output'], 'service': service})

@app.route('/services/restart', methods=['POST'])
def services_restart():
    service = (request.json or {}).get('service')
    if not service: return jsonify({'error': 'service required'})
    result = run_cmd(f'pm2 restart {service} 2>&1')
    return jsonify({'success': result['success'], 'service': service})

@app.route('/services/stop', methods=['POST'])
def services_stop():
    service = (request.json or {}).get('service')
    run_cmd(f'pm2 stop {service} 2>&1')
    return jsonify({'success': True})

@app.route('/services/start', methods=['POST'])
def services_start():
    service = (request.json or {}).get('service')
    run_cmd(f'pm2 start {service} 2>&1')
    return jsonify({'success': True})

@app.route('/services/mapping', methods=['GET'])
def services_mapping():
    result = run_cmd('pm2 jlist 2>/dev/null || echo "[]"')
    services = []
    try:
        for svc in json.loads(result['output'] or '[]'):
            env = svc.get('pm2_env', {})
            services.append({
                'service': svc.get('name'),
                'python_filename': os.path.basename(env.get('pm_exec_path', '')),
                'active': env.get('status') == 'online'
            })
    except: pass
    return jsonify({'services': services})

# ============== CODE ==============
@app.route('/code/run', methods=['POST'])
def code_run():
    data = request.json or {}
    code, timeout = data.get('code'), min(data.get('timeout', 30), 60)
    if not code: return jsonify({'error': 'code required'})
    with open('/tmp/claude_code.py', 'w') as f: f.write(code)
    result = run_cmd('python3 /tmp/claude_code.py', timeout=timeout)
    return jsonify({'output': result['output'], 'error': result['error'], 'code': result['code']})

@app.route('/code/check', methods=['POST'])
def code_check():
    code = (request.json or {}).get('code')
    if not code: return jsonify({'error': 'code required'})
    with open('/tmp/check.py', 'w') as f: f.write(code)
    result = run_cmd('python3 -m py_compile /tmp/check.py')
    return jsonify({'valid': result['success'], 'error': result['error'] if not result['success'] else None})

# ============== SYSTEM ==============
@app.route('/system/stats', methods=['GET'])
def system_stats():
    cpu = run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    mem = run_cmd("free -m | awk 'NR==2{printf \"%.1f%% (%dMB/%dMB)\", $3*100/$2, $3, $2}'")
    disk = run_cmd("df -h / | awk 'NR==2{print $5}'")
    uptime = run_cmd("uptime -p")
    return jsonify({'cpu': cpu['output'], 'memory': mem['output'], 'disk': disk['output'], 'uptime': uptime['output']})

@app.route('/system/processes', methods=['POST'])
def system_processes():
    data = request.json or {}
    sort_by, limit = data.get('sort_by', 'cpu'), data.get('limit', 15)
    cmd = f'ps aux --sort=-{"mem" if sort_by == "mem" else "cpu"} | head -{limit + 1}'
    return jsonify({'processes': run_cmd(cmd)['output']})

@app.route('/system/uptime', methods=['GET'])
def system_uptime():
    return jsonify({'uptime': run_cmd('uptime')['output']})

# ============== NETWORK ==============
@app.route('/network/curl', methods=['POST'])
def network_curl():
    data = request.json or {}
    url, method = data.get('url'), data.get('method', 'GET')
    if not url: return jsonify({'error': 'url required'})
    result = run_cmd(f'curl -s -X {method} "{url}"', timeout=30)
    return jsonify({'response': result['output']})

@app.route('/network/ping', methods=['POST'])
def network_ping():
    data = request.json or {}
    host, count = data.get('host'), data.get('count', 3)
    if not host: return jsonify({'error': 'host required'})
    host = re.sub(r'[^a-zA-Z0-9.-]', '', host)
    return jsonify({'result': run_cmd(f'ping -c {count} {host}', timeout=30)['output']})

@app.route('/network/ports', methods=['GET'])
def network_ports():
    return jsonify({'ports': run_cmd('ss -tuln | grep LISTEN')['output']})

# ============== LOGS ==============
@app.route('/logs/search', methods=['POST'])
def logs_search():
    data = request.json or {}
    query, service, lines = data.get('query'), data.get('service'), data.get('lines', 50)
    if not query: return jsonify({'error': 'query required'})
    if service:
        result = run_cmd(f'pm2 logs {service} --nostream --lines 200 2>&1 | grep -i "{query}" | tail -{lines}')
    else:
        result = run_cmd(f'journalctl --no-pager | grep -i "{query}" | tail -{lines}')
    return jsonify({'results': result['output']})

@app.route('/logs/errors', methods=['POST'])
def logs_errors():
    data = request.json or {}
    hours = data.get('hours', 24)
    result = run_cmd(f'journalctl --since "{hours} hours ago" --no-pager | grep -iE "(error|exception|failed)" | tail -100')
    return jsonify({'errors': result['output']})

# ============== DIAGNOSE ==============
@app.route('/diagnose/service', methods=['POST'])
def diagnose_service():
    service = (request.json or {}).get('service')
    if not service: return jsonify({'error': 'service required'})
    status = run_cmd(f'pm2 show {service} 2>/dev/null')
    is_active = 'online' in status['output'].lower()
    errors = run_cmd(f'pm2 logs {service} --nostream --lines 20 2>&1 | grep -iE "(error|exception)" || true')
    issues = []
    if not is_active: issues.append('Service is not running')
    if 'error' in errors['output'].lower(): issues.append('Errors found')
    return jsonify({'service': service, 'healthy': is_active and not issues, 'is_active': is_active, 'issues': issues, 'recent_errors': errors['output'][:500]})

@app.route('/diagnose/all', methods=['GET'])
def diagnose_all():
    result = run_cmd('pm2 jlist 2>/dev/null || echo "[]"')
    services, healthy, total = [], 0, 0
    try:
        for svc in json.loads(result['output'] or '[]'):
            is_online = svc.get('pm2_env', {}).get('status') == 'online'
            total += 1
            if is_online: healthy += 1
            services.append({'name': svc.get('name'), 'healthy': is_online})
    except: pass
    return jsonify({'healthy': healthy, 'total': total, 'services': services})

# ============== CRON ==============
@app.route('/cron/list', methods=['GET'])
def cron_list():
    cron = run_cmd('crontab -l 2>/dev/null || echo "No crontab"')
    timers = run_cmd('systemctl list-timers --no-pager 2>/dev/null | head -15')
    return jsonify({'tasks': f"=== Crontab ===\n{cron['output']}\n\n=== Timers ===\n{timers['output']}"})

# ============== GIT ==============
@app.route('/git/status', methods=['POST'])
def git_status():
    path = (request.json or {}).get('path', WORK_DIR)
    return jsonify({'status': run_cmd('git status', cwd=path)['output']})

@app.route('/git/pull', methods=['POST'])
def git_pull():
    path = (request.json or {}).get('path')
    if not path: return jsonify({'error': 'path required'})
    return jsonify({'result': run_cmd('git pull', cwd=path)['output']})

# ============== DEPLOY HTML ==============
@app.route('/deploy/html', methods=['POST'])
def deploy_html():
    data = request.json or {}
    filename, content = data.get('filename', 'index.html'), data.get('content')
    if not content: return jsonify({'error': 'content required'})
    run_cmd('sudo mkdir -p /var/www/html')
    with open(f'/tmp/{filename}', 'w') as f: f.write(content)
    run_cmd(f'sudo cp /tmp/{filename} /var/www/html/{filename}')
    return jsonify({'success': True, 'url': f'http://158.180.56.74/{filename}'})

if __name__ == '__main__':
    print(f"🚀 Oracle Admin API v2.0 on port {PORT}")
    app.run(host='0.0.0.0', port=PORT)
