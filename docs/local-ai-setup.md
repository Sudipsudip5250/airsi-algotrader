# Local AI Model Setup (VPS → PC)

Run Ollama on a VPS and connect your local trading bot to it.

## 1. Install Ollama on VPS

```bash
# SSH into your VPS
ssh user@your-vps-ip

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Verify
ollama --version
```

## 2. Pull a Model on VPS

```bash
# Lightweight (fast, ~4GB RAM)
ollama pull mistral

# Better reasoning (~7GB RAM)
ollama pull llama3.1

# Best quality (~10GB RAM)
ollama pull deepseek-r1:7b
```

Check available models: `ollama list`

## 3. Configure Ollama for Remote Access

By default Ollama listens only on `127.0.0.1`. Change it to listen on all interfaces:

```bash
# Stop Ollama
sudo systemctl stop ollama

# Edit service config
sudo systemctl edit ollama

# Add these lines:
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_KEEP_ALIVE=24h"

# Save and restart
sudo systemctl daemon-reload
sudo systemctl restart ollama

# Verify it's listening
ss -tlnp | grep 11434
```

## 4. Allow Through Firewall

```bash
# UFW
sudo ufw allow 11434/tcp

# Or iptables
sudo iptables -A INPUT -p tcp --dport 11434 -j ACCEPT
```

## 5. Get VPS IP

```bash
# Several ways to check your VPS public IP
curl -s ifconfig.me
curl -s icanhazip.com
curl -s ipinfo.io/ip
curl -s api.ipify.org

# Or if you just need the local IP (for internal network)
hostname -I
ip addr show | grep 'inet ' | awk '{print $2}'
```

## 6. Test Connection from Local PC

```bash
# Replace with your VPS IP
curl http://YOUR_VPS_IP:11434/api/tags

# Test a prompt
curl http://YOUR_VPS_IP:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Say hello in one word",
  "stream": false
}'
```

## 7. Configure `.env` on Your Local PC

```env
# Point to your VPS instead of localhost
OLLAMA_BASE_URL=http://YOUR_VPS_IP:11434
OLLAMA_MODEL=mistral

# Set higher timeout for network latency (in .env or before running)
# export OLLAMA_TIMEOUT=120
```

## 8. Security (Recommended)

For production, add a simple auth proxy instead of exposing Ollama publicly:

```bash
# On VPS — install nginx as a reverse proxy with password
sudo apt install nginx apache2-utils

# Create a password
sudo htpasswd -c /etc/nginx/.htpasswd ollama

# Create nginx config
sudo tee /etc/nginx/sites-available/ollama << 'EOF'
server {
    listen 11434 ssl;
    server_name _;

    # Optional: add SSL cert with Let's Encrypt
    # ssl_certificate /etc/letsencrypt/live/your-domain/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/your-domain/privkey.pem;

    location / {
        auth_basic "Ollama";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:11434;
        proxy_set_header Host $host;
    }
}
EOF

# Enable and restart
sudo ln -sf /etc/nginx/sites-available/ollama /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

Then from local PC:

```bash
curl -u ollama:yourpassword http://YOUR_VPS_IP:11434/api/tags
```

## Quick Test Script

```bash
#!/usr/bin/env bash
# test-ollama-remote.sh — Test connection to remote Ollama
VPS_IP="${1:-YOUR_VPS_IP}"
echo "Testing connection to $VPS_IP:11434..."
curl -s --max-time 5 "http://$VPS_IP:11434/api/tags" > /dev/null \
  && echo "✅ Connected!" \
  || echo "❌ Cannot reach Ollama at $VPS_IP:11434"
```
