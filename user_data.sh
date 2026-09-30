#!/bin/bash
set -ex

dnf install -y python3-pip
pip3 install flask boto3 gunicorn

mkdir -p /opt/photovault
cat > /opt/photovault/app.py <<'PYEOF'
${app_py}
PYEOF

cat > /etc/systemd/system/photovault.service <<'EOF'
[Unit]
Description=PhotoVault
After=network-online.target

[Service]
Environment=BUCKET=${bucket}
Environment=AWS_REGION=${region}
WorkingDirectory=/opt/photovault
ExecStart=/usr/local/bin/gunicorn -w 2 -b 0.0.0.0:80 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now photovault
