#!/usr/bin/env python3
"""
VM Controller for VM2
=====================
Позволяет с VM2 управлять VM1 через OCI CLI и SSH.
Запускать на VM2 (158.180.56.74)

Установка:
    pip3 install flask requests --break-system-packages
    
Запуск:
    python3 vm_controller.py
    
Или как сервис:
    sudo cp vm-controller.service /etc/systemd/system/
    sudo systemctl enable --now vm-controller
"""

from flask import Flask, request, jsonify
import subprocess
import os
import json
from datetime import datetime

app = Flask(__name__)

# === КОНФИГУРАЦИЯ ===
PORT = 5100
API_KEY = os.environ.get('VM_CONTROLLER_KEY', 'vm-controller-2026')

# VM1 Configuration
VM1_IP = "92.5.72.169"
VM1_SSH_KEY = "/home/ubuntu/.ssh/id_rsa"  # или vm1_key
VM1_USER = "ubuntu"

# OCI Configuration (заполнить после получения OCID)
OCI_CLI = "/home/ubuntu/.local/bin/oci"
VM1_INSTANCE_OCID = os.environ.get('VM1_INSTANCE_OCID', '')  # Нужно заполнить!

# === HELPERS ===

def auth_required(f):
    def wrapper(*args, **kwargs):
        key = request.headers.get('X-API-Key') or request.args.get('key')
        if key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def run_local(cmd, timeout=30):
    """Выполнить команду локально на VM2"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, 
            text=True, timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def run_on_vm1(cmd, timeout=30):
    """Выполнить команду на VM1 через SSH"""
    ssh_cmd = f'ssh -i {VM1_SSH_KEY} -o StrictHostKeyChecking=no -o ConnectTimeout=10 {VM1_USER}@{VM1_IP} "{cmd}"'
    return run_local(ssh_cmd, timeout)

def check_vm1_alive():
    """Проверить доступность VM1"""
    result = run_local(f"ping -c 1 -W 3 {VM1_IP}")
    return result["success"]

def check_oci_cli():
    """Проверить наличие OCI CLI"""
    return os.path.exists(OCI_CLI)

# === API ENDPOINTS ===

@app.route('/')
def index():
    return jsonify({
        "service": "VM Controller",
        "purpose": "Manage VM1 from VM2",
        "vm1_ip": VM1_IP,
        "vm1_ocid_configured": bool(VM1_INSTANCE_OCID),
        "oci_cli_available": check_oci_cli(),
        "endpoints": {
            "GET /health": "Health check",
            "GET /vm1/ping": "Check if VM1 is alive",
            "GET /vm1/status": "Get VM1 services status",
            "POST /vm1/ssh": "Execute command on VM1 via SSH",
            "POST /vm1/reboot/soft": "Soft reboot VM1 via SSH",
            "POST /vm1/reboot/hard": "Hard reboot VM1 via OCI CLI",
            "POST /vm1/oci-action": "OCI instance action (STOP/START/RESET)"
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "vm1_reachable": check_vm1_alive(),
        "oci_cli": check_oci_cli()
    })

@app.route('/vm1/ping')
def vm1_ping():
    alive = check_vm1_alive()
    return jsonify({
        "vm1_ip": VM1_IP,
        "reachable": alive,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/vm1/status')
@auth_required
def vm1_status():
    """Получить статус сервисов на VM1"""
    if not check_vm1_alive():
        return jsonify({
            "error": "VM1 is not reachable",
            "reachable": False
        }), 503
    
    # Проверяем сервисы
    result = run_on_vm1("systemctl list-units 'grok-*' --no-pager --no-legend | head -30")
    
    return jsonify({
        "reachable": True,
        "services": result.get("stdout", ""),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/vm1/ssh', methods=['POST'])
@auth_required
def vm1_ssh():
    """Выполнить команду на VM1 через SSH"""
    data = request.get_json() or {}
    cmd = data.get('command') or request.form.get('command')
    
    if not cmd:
        return jsonify({"error": "command required"}), 400
    
    # Безопасность - блокируем опасные команды
    dangerous = ['rm -rf /', 'dd if=', 'mkfs', '> /dev/sda']
    if any(d in cmd for d in dangerous):
        return jsonify({"error": "Command blocked"}), 403
    
    if not check_vm1_alive():
        return jsonify({"error": "VM1 not reachable"}), 503
    
    result = run_on_vm1(cmd)
    return jsonify(result)

@app.route('/vm1/reboot/soft', methods=['POST'])
@auth_required
def vm1_reboot_soft():
    """Мягкая перезагрузка через SSH"""
    if not check_vm1_alive():
        return jsonify({
            "error": "VM1 not reachable, try hard reboot via OCI",
            "suggestion": "POST /vm1/reboot/hard"
        }), 503
    
    result = run_on_vm1("sudo reboot", timeout=10)
    return jsonify({
        "action": "soft_reboot",
        "initiated": True,
        "note": "VM1 will be unavailable for 1-2 minutes",
        "result": result
    })

@app.route('/vm1/reboot/hard', methods=['POST'])
@auth_required
def vm1_reboot_hard():
    """Жёсткая перезагрузка через OCI CLI"""
    if not check_oci_cli():
        return jsonify({
            "error": "OCI CLI not installed",
            "install": "pip3 install oci-cli --break-system-packages"
        }), 500
    
    if not VM1_INSTANCE_OCID:
        return jsonify({
            "error": "VM1_INSTANCE_OCID not configured",
            "hint": "Set environment variable VM1_INSTANCE_OCID"
        }), 500
    
    # OCI CLI reboot
    cmd = f"{OCI_CLI} compute instance action --action RESET --instance-id {VM1_INSTANCE_OCID}"
    result = run_local(cmd, timeout=60)
    
    return jsonify({
        "action": "hard_reboot_oci",
        "initiated": result["success"],
        "result": result,
        "note": "VM1 will be unavailable for 2-5 minutes"
    })

@app.route('/vm1/oci-action', methods=['POST'])
@auth_required
def vm1_oci_action():
    """Выполнить OCI action (STOP, START, RESET, SOFTRESET)"""
    data = request.get_json() or {}
    action = data.get('action', 'RESET').upper()
    
    allowed_actions = ['STOP', 'START', 'RESET', 'SOFTRESET', 'SOFTSTOP']
    if action not in allowed_actions:
        return jsonify({
            "error": f"Invalid action. Allowed: {allowed_actions}"
        }), 400
    
    if not check_oci_cli():
        return jsonify({"error": "OCI CLI not installed"}), 500
    
    if not VM1_INSTANCE_OCID:
        return jsonify({"error": "VM1_INSTANCE_OCID not configured"}), 500
    
    cmd = f"{OCI_CLI} compute instance action --action {action} --instance-id {VM1_INSTANCE_OCID}"
    result = run_local(cmd, timeout=60)
    
    return jsonify({
        "action": action,
        "instance_id": VM1_INSTANCE_OCID,
        "success": result["success"],
        "result": result
    })

@app.route('/vm1/services/restart/<service>', methods=['POST'])
@auth_required
def vm1_restart_service(service):
    """Перезапустить сервис на VM1"""
    if not check_vm1_alive():
        return jsonify({"error": "VM1 not reachable"}), 503
    
    # Только grok-* сервисы
    if not service.startswith('grok-'):
        return jsonify({"error": "Only grok-* services allowed"}), 403
    
    result = run_on_vm1(f"sudo systemctl restart {service}")
    
    # Проверяем статус
    status = run_on_vm1(f"systemctl is-active {service}")
    
    return jsonify({
        "service": service,
        "restarted": result["success"],
        "status": status.get("stdout", "unknown")
    })

@app.route('/setup/oci', methods=['POST'])
@auth_required
def setup_oci():
    """Инструкции по настройке OCI CLI"""
    return jsonify({
        "steps": [
            "1. pip3 install oci-cli --break-system-packages",
            "2. oci setup config",
            "3. Добавить API key в Oracle Console",
            "4. Найти Instance OCID в Oracle Console",
            "5. export VM1_INSTANCE_OCID=ocid1.instance.oc1..."
        ],
        "oci_installed": check_oci_cli(),
        "ocid_configured": bool(VM1_INSTANCE_OCID)
    })

if __name__ == '__main__':
    print("🎮 VM Controller starting...")
    print(f"   Port: {PORT}")
    print(f"   VM1 IP: {VM1_IP}")
    print(f"   OCI CLI: {'✅' if check_oci_cli() else '❌'}")
    print(f"   VM1 OCID: {'✅' if VM1_INSTANCE_OCID else '❌ NOT SET'}")
    print(f"   VM1 Alive: {'✅' if check_vm1_alive() else '❌'}")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
