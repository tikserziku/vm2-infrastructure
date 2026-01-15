#!/bin/bash
# Quick setup for Google Sheets credentials via base64

echo "Paste your base64 encoded credentials (one line):"
read BASE64_CREDS

if [ -z "$BASE64_CREDS" ]; then
    echo "No credentials provided"
    exit 1
fi

# Set in PM2 environment
pm2 set tiktok-transcriber:GOOGLE_SHEETS_CREDENTIALS_BASE64 "$BASE64_CREDS"

# Restart application
pm2 restart tiktok-transcriber --update-env

echo "Credentials set. Checking status..."
sleep 3
pm2 logs tiktok-transcriber --lines 10

