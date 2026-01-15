#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Admin endpoints for TikTok Transcriber
"""

import subprocess
import os
from flask import jsonify

def add_admin_routes(app):
    """Add admin routes to Flask app"""
    
    @app.route('/admin/restart', methods=['POST'])
    def restart_service():
        """Restart the PM2 service"""
        try:
            # Restart PM2 service
            result = subprocess.run(
                ['pm2', 'restart', 'tiktok-transcriber'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return jsonify({
                    "status": "success",
                    "message": "Сервис успешно перезапущен",
                    "details": result.stdout
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": "Ошибка при перезапуске",
                    "details": result.stderr
                }), 500
                
        except subprocess.TimeoutExpired:
            return jsonify({
                "status": "error",
                "message": "Превышено время ожидания"
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
            result = subprocess.run(
                ['pm2', 'info', 'tiktok-transcriber'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Parse uptime and restarts from output
            lines = result.stdout.split('\n')
            status_info = {}
            
            for line in lines:
                if 'status' in line.lower():
                    status_info['status'] = line.split('│')[2].strip() if '│' in line else 'unknown'
                elif 'uptime' in line.lower():
                    status_info['uptime'] = line.split('│')[2].strip() if '│' in line else 'unknown'
                elif 'restarts' in line.lower():
                    status_info['restarts'] = line.split('│')[2].strip() if '│' in line else '0'
            
            return jsonify({
                "status": "success",
                "service": status_info
            })
            
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    
    @app.route('/admin/logs', methods=['GET'])
    def get_logs():
        """Get recent logs"""
        try:
            result = subprocess.run(
                ['pm2', 'logs', 'tiktok-transcriber', '--lines', '20', '--nostream'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return jsonify({
                "status": "success",
                "logs": result.stdout
            })
            
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

