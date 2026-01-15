#!/bin/bash

# Setup Google Sheets Credentials for TikTok Transcriber
# This script helps you configure Google Sheets integration

echo "=========================================="
echo "Google Sheets Integration Setup"
echo "=========================================="
echo ""

# Check if running as ubuntu user
if [ "$USER" != "ubuntu" ]; then
    echo "Warning: Running as $USER, should be ubuntu"
fi

# Navigate to app directory
cd /home/ubuntu/tiktok-transcriber

echo "Choose setup method:"
echo "1. Upload credentials.json file"
echo "2. Use base64 encoded credentials (environment variable)"
echo "3. Skip Google Sheets setup"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo "Please upload your credentials.json file to the server."
        echo "You can use SCP or SFTP to upload it to: /home/ubuntu/tiktok-transcriber/credentials.json"
        echo ""
        echo "Example SCP command from your local machine:"
        echo "scp /path/to/credentials.json ubuntu@158.180.56.74:/home/ubuntu/tiktok-transcriber/"
        echo ""
        read -p "Press Enter when file is uploaded..."
        
        if [ -f "credentials.json" ]; then
            echo "✅ credentials.json found!"
            chmod 600 credentials.json
            echo "File permissions set."
        else
            echo "❌ credentials.json not found in current directory"
            exit 1
        fi
        ;;
        
    2)
        echo ""
        echo "Please provide the base64 encoded credentials string."
        echo "You can create it with: cat credentials.json | base64 -w 0"
        echo ""
        read -p "Enter base64 string: " base64_creds
        
        if [ -z "$base64_creds" ]; then
            echo "❌ No credentials provided"
            exit 1
        fi
        
        # Save to environment file
        echo "GOOGLE_SHEETS_CREDENTIALS_BASE64='$base64_creds'" > .env_sheets
        chmod 600 .env_sheets
        
        # Add to PM2 environment
        pm2 set tiktok-transcriber:GOOGLE_SHEETS_CREDENTIALS_BASE64 "$base64_creds"
        
        echo "✅ Base64 credentials saved to environment"
        ;;
        
    3)
        echo "Skipping Google Sheets setup..."
        echo "You can configure it later if needed."
        ;;
        
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Optional: Enter Google Spreadsheet ID (or press Enter to skip):"
read -p "Spreadsheet ID: " spreadsheet_id

if [ ! -z "$spreadsheet_id" ]; then
    pm2 set tiktok-transcriber:GOOGLE_SPREADSHEET_ID "$spreadsheet_id"
    echo "✅ Default spreadsheet ID saved"
fi

echo ""
echo "=========================================="
echo "Testing Google Sheets connection..."
echo "=========================================="

# Test the connection
source venv/bin/activate
python3 -c "
from google_sheets import init_google_sheets
manager = init_google_sheets('$spreadsheet_id' if '$spreadsheet_id' else None)
if manager and manager.client:
    print('✅ Google Sheets connection successful!')
else:
    print('⚠️ Google Sheets connection failed or no credentials')
"

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Replace current app.py with the new version:"
echo "   mv app.py app_old.py"
echo "   mv app_with_sheets.py app.py"
echo ""
echo "2. Restart the application:"
echo "   pm2 restart tiktok-transcriber"
echo ""
echo "3. Check logs:"
echo "   pm2 logs tiktok-transcriber"
echo ""

