#!/bin/bash

echo "=========================================="
echo "Transfer Google Sheets from Render.com"
echo "=========================================="
echo ""
echo "Open your Render.com dashboard and copy the environment variables"
echo ""
echo "1. Copy GOOGLE_SHEETS_CREDENTIALS_BASE64 or GOOGLE_APPLICATION_CREDENTIALS_BASE64"
echo "(It's a very long base64 string)"
echo ""
read -p "Paste the base64 credentials here: " CREDS_BASE64

if [ -z "$CREDS_BASE64" ]; then
    echo "❌ No credentials provided"
    exit 1
fi

echo ""
echo "2. Copy GOOGLE_SPREADSHEET_ID (optional)"
echo "(It looks like: 1ABC...xyz)"
echo ""
read -p "Paste Spreadsheet ID (or press Enter to skip): " SHEET_ID

# Save credentials to file
echo "$CREDS_BASE64" | base64 -d > /home/ubuntu/tiktok-transcriber/credentials.json

if [ $? -eq 0 ]; then
    echo "✅ Credentials decoded and saved to credentials.json"
    chmod 600 /home/ubuntu/tiktok-transcriber/credentials.json
else
    echo "❌ Failed to decode credentials. Make sure it's valid base64"
    exit 1
fi

# Set environment variables in PM2
pm2 set tiktok-transcriber:GOOGLE_SHEETS_CREDENTIALS_BASE64 "$CREDS_BASE64"

if [ ! -z "$SHEET_ID" ]; then
    pm2 set tiktok-transcriber:GOOGLE_SPREADSHEET_ID "$SHEET_ID"
    echo "✅ Spreadsheet ID saved: $SHEET_ID"
fi

# Restart application
echo ""
echo "Restarting application..."
pm2 restart tiktok-transcriber --update-env

echo ""
echo "✅ Transfer complete! Testing connection..."
sleep 3

# Test the connection
cd /home/ubuntu/tiktok-transcriber
source venv/bin/activate
python3 -c "
from google_sheets import init_google_sheets
import os

sheet_id = '$SHEET_ID' if '$SHEET_ID' else os.environ.get('GOOGLE_SPREADSHEET_ID')
manager = init_google_sheets(sheet_id)

if manager and manager.client:
    print('✅ Google Sheets connected successfully!')
    if manager.spreadsheet:
        print(f'✅ Connected to spreadsheet: {manager.spreadsheet.title}')
        print(f'📊 URL: {manager.spreadsheet.url}')
else:
    print('❌ Connection failed. Check credentials.')
"

echo ""
echo "Checking application status..."
curl -s http://localhost:10000/health | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Google Sheets Module: {data.get(\"google_sheets\")}')
print(f'Google Sheets Connected: {data.get(\"google_sheets_connected\")}')
"

echo ""
echo "=========================================="
echo "Done! Your transcriber now saves to Google Sheets"
echo "Access at: http://158.180.56.74"
echo "=========================================="

