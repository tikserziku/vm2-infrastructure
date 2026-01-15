from flask import Flask, request, jsonify
import subprocess
import os
from datetime import datetime

app = Flask(__name__)
API_KEY = "oracle-vm-key-2025"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'vm': 'oracle-free',
        'ip': '158.180.56.74',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/execute', methods=['POST'])
def execute():
    key = request.headers.get('X-API-Key')
    if key != API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    if not data or 'command' not in data:
        return jsonify({'error': 'No command provided'}), 400
    
    command = data.get('command')
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return jsonify({
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'code': result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Command timeout'}), 408
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting Oracle VM Agent on port 8888...")
    app.run(host='0.0.0.0', port=8888, debug=False)
