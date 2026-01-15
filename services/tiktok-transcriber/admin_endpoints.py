
# Admin endpoints
@app.route('/admin/restart', methods=['POST'])
def restart_service():
    """Restart the PM2 service"""
    try:
        import subprocess
        result = subprocess.run(
            ['pm2', 'restart', 'tiktok-transcriber'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return jsonify({
                "status": "success",
                "message": "Сервис успешно перезапущен"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Ошибка при перезапуске"
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/admin/status', methods=['GET'])
def service_status():
    """Get PM2 service status"""
    try:
        import subprocess
        result = subprocess.run(
            ['pm2', 'info', 'tiktok-transcriber'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Simple parsing
        status = "online" if "online" in result.stdout else "offline"
        
        return jsonify({
            "status": "success",
            "service": {
                "status": status,
                "info": "Service is running"
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

