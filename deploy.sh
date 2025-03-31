#!/bin/bash

# Clean up existing files
rm -rf /opt/telegrambot/*

# Create directory structure
mkdir -p /opt/telegrambot
cd /opt/telegrambot

# Clone the repository
git clone https://github.com/chamika1/social_media_downloader_bot.git
cd social_media_downloader_bot

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment and install requirements
source venv/bin/activate
pip install python-telegram-bot yt-dlp

# Create systemd service file
cat > /etc/systemd/system/telegrambot.service << 'EOL'
[Unit]
Description=Telegram YouTube Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegrambot/social_media_downloader_bot
Environment=PATH=/opt/telegrambot/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/opt/telegrambot/venv/bin/python youtubebot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

# Set proper permissions
chmod 644 youtubebot.py
chmod 644 cookies.txt

# Reload systemd and start service
systemctl daemon-reload
systemctl enable telegrambot
systemctl restart telegrambot

# Show status
systemctl status telegrambot