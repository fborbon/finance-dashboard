#!/usr/bin/env bash
# Deploy the personal finance dashboard to banking.forwardforecasting.eu
set -euo pipefail

SERVER="ubuntu@54.78.82.101"
KEY="$HOME/.ssh/forwardforecasting.pem"
REMOTE_DIR="/home/ubuntu/finance-dashboard"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSH="ssh -i $KEY"
RSYNC="rsync -az --progress -e \"ssh -i $KEY\""

step() { echo -e "\n\033[1;34m▶ $1\033[0m"; }
ok()   { echo -e "\033[1;32m✓ $1\033[0m"; }
warn() { echo -e "\033[1;33m⚠ $1\033[0m"; }
die()  { echo -e "\033[1;31m✗ $1\033[0m" >&2; exit 1; }

# ── Pre-flight ────────────────────────────────────────────────────────────────

step "Checking DNS for banking.forwardforecasting.eu"
RESOLVED=$(dig +short banking.forwardforecasting.eu 2>/dev/null | head -1)
if [[ "$RESOLVED" != "54.78.82.101" ]]; then
    warn "DNS not yet set (resolved: '${RESOLVED:-none}')"
    warn "Add this A record BEFORE running deploy with --ssl:"
    warn "  banking.forwardforecasting.eu → 54.78.82.101"
fi

# ── Snapshot overrides before any sync ───────────────────────────────────────

step "Snapshotting category_overrides.json before deploy"
$SSH -i "$KEY" "$SERVER" /home/ubuntu/finance-dashboard/backups/backup_overrides.sh
ok "Snapshot saved to ~/finance-dashboard/backups/overrides/"

# ── Sync code to server ───────────────────────────────────────────────────────

step "Syncing code to server"
eval "$RSYNC" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude "venv/" \
    --exclude ".venv/" \
    --exclude "*.egg-info/" \
    --exclude "category_overrides.json" \
    --exclude "categories.json" \
    --exclude "docs/" \
    --exclude "deploy/" \
    "$LOCAL_DIR/" "$SERVER:$REMOTE_DIR/"
ok "Code synced to $REMOTE_DIR"

# ── Install deps on server ────────────────────────────────────────────────────

step "Setting up Python virtual environment and dependencies"
$SSH -i "$KEY" "$SERVER" bash <<'REMOTE'
    cd ~/finance-dashboard
    if [[ ! -d venv ]]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet streamlit pandas plotly openpyxl xlrd numpy pymupdf
REMOTE
ok "Dependencies installed"

# ── systemd service ───────────────────────────────────────────────────────────

step "Installing systemd service"
rsync -az -e "ssh -i $KEY" \
    "$LOCAL_DIR/deploy/finance-dashboard.service" \
    "$SERVER:/tmp/finance-dashboard.service"

$SSH -i "$KEY" "$SERVER" bash <<'REMOTE'
    sudo cp /tmp/finance-dashboard.service /etc/systemd/system/finance-dashboard.service
    sudo systemctl daemon-reload
    sudo systemctl enable finance-dashboard
    sudo systemctl restart finance-dashboard
    sleep 2
    sudo systemctl is-active finance-dashboard
REMOTE
ok "Service running on port 8502"

# ── Basic auth password ───────────────────────────────────────────────────────

step "Setting up HTTP Basic Auth"
if $SSH -i "$KEY" "$SERVER" test -f /etc/nginx/.htpasswd_banking; then
    warn "htpasswd already exists — skipping (run with --reset-pw to regenerate)"
else
    echo -n "Choose a password for the finance dashboard: "
    read -rs PASS
    echo
    $SSH -i "$KEY" "$SERVER" bash -c "
        sudo apt-get install -y -q apache2-utils 2>/dev/null
        echo '$PASS' | sudo htpasswd -ic /etc/nginx/.htpasswd_banking admin
        sudo chmod 640 /etc/nginx/.htpasswd_banking
        sudo chown root:www-data /etc/nginx/.htpasswd_banking
    "
    ok "htpasswd set for user 'admin'"
fi

# ── nginx config — only touch if banking.conf does not yet exist on server ────
# Once SSL is provisioned the config lives on the server; never overwrite it.

if $SSH -i "$KEY" "$SERVER" test -f /etc/nginx/sites-available/banking.conf; then
    ok "nginx banking.conf already present on server — skipping (use --reset-nginx to force)"
elif [[ "${1:-}" == "--ssl" ]]; then
    step "Provisioning SSL certificate with Let's Encrypt"
    $SSH -i "$KEY" "$SERVER" bash <<'REMOTE'
        sudo certbot certonly --nginx \
            -d banking.forwardforecasting.eu \
            --non-interactive \
            --agree-tos \
            --email correoprincipal2021@hotmail.com \
            --expand
REMOTE
    ok "SSL certificate issued"

    step "Installing nginx config (with SSL)"
    rsync -az -e "ssh -i $KEY" \
        "$LOCAL_DIR/deploy/nginx-banking.conf" \
        "$SERVER:/tmp/nginx-banking.conf"

    $SSH -i "$KEY" "$SERVER" bash <<'REMOTE'
        sudo cp /tmp/nginx-banking.conf /etc/nginx/sites-available/banking.conf
        sudo ln -sf /etc/nginx/sites-available/banking.conf /etc/nginx/sites-enabled/banking.conf
        sudo nginx -t
        sudo systemctl reload nginx
REMOTE
    ok "nginx config active with SSL"

else
    step "Installing nginx config (HTTP, first-time only)"
    $SSH -i "$KEY" "$SERVER" bash <<'REMOTE'
        cat > /tmp/nginx-banking-http.conf <<'EOF'
server {
    listen 80;
    server_name banking.forwardforecasting.eu;

    auth_basic           "Finance Dashboard";
    auth_basic_user_file /etc/nginx/.htpasswd_banking;

    location = / {
        return 302 http://$host/app/;
    }

    location /app/ {
        proxy_pass         http://127.0.0.1:8502;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
EOF
        sudo cp /tmp/nginx-banking-http.conf /etc/nginx/sites-available/banking.conf
        sudo ln -sf /etc/nginx/sites-available/banking.conf /etc/nginx/sites-enabled/banking.conf
        sudo nginx -t
        sudo systemctl reload nginx
REMOTE
    ok "HTTP nginx config active"
    warn "Run with --ssl once DNS is pointing to 54.78.82.101 to enable HTTPS"
fi  # end first-time nginx block

# ── Final status ──────────────────────────────────────────────────────────────

echo ""
echo "────────────────────────────────────────────────────────"
$SSH -i "$KEY" "$SERVER" bash -c "
    echo 'Streamlit:' \$(systemctl is-active finance-dashboard)
    curl -sf http://localhost:8502/app/_stcore/health && echo 'Health: OK' || echo 'Health: not ready yet'
"
if [[ "${1:-}" == "--ssl" ]]; then
    ok "Dashboard live at → https://banking.forwardforecasting.eu/app/"
else
    ok "Dashboard live at → http://banking.forwardforecasting.eu/app/ (HTTP only)"
fi
