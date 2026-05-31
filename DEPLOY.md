# 🚀 股票资讯聚合网站 — 部署上线指南

## 一、本地运行

```bash
cd stocknews
pip install -r requirements.txt

# 手动爬取一次测试
python run.py --crawl

# 启动网站（含定时爬取）
python run.py --port 8000
```

访问: http://localhost:8000

---

## 二、部署到云服务器

### 2.1 买服务器（最低配置即可）

| 云厂商 | 推荐型号 | 月费 | 链接 |
|--------|---------|:---:|------|
| **阿里云** | 轻量应用服务器 2C2G | ¥34/月 | aliyun.com |
| **腾讯云** | 轻量应用服务器 2C2G | ¥38/月 | cloud.tencent.com |
| **华为云** | HECS 2C2G | ¥40/月 | huaweicloud.com |

> 💰 **月费总计: ¥34-40 + ¥50/年域名 ≈ ¥38/月**

### 2.2 选操作系统

选 **Ubuntu 22.04 LTS**（最通用，教程最多）

### 2.3 连接到服务器

```bash
ssh root@你的服务器IP
```

### 2.4 一键部署脚本

在服务器上执行：

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Python 和 git
apt install -y python3 python3-pip python3-venv git nginx

# 创建项目目录
mkdir -p /opt/stocknews
cd /opt/stocknews

# 把本地代码上传到服务器（二选一）
# 方案A: git clone（如果你的代码在 GitHub）
git clone https://github.com/你的用户名/stocknews.git .

# 方案B: 从本地上传（在本地电脑执行）
# scp -r stocknews/* root@服务器IP:/opt/stocknews/

# 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
nano .env   # 填入你的 API Key
```

### 2.5 配置 Systemd（开机自启）

```bash
cat > /etc/systemd/system/stocknews.service << 'EOF'
[Unit]
Description=Stock News Aggregator
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/stocknews
ExecStart=/opt/stocknews/venv/bin/python run.py --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable stocknews
systemctl start stocknews

# 查看状态
systemctl status stocknews

# 查看日志
journalctl -u stocknews -f
```

### 2.6 配置 Nginx 反向代理

```bash
cat > /etc/nginx/sites-available/stocknews << 'EOF'
server {
    listen 80;
    server_name 你的域名.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket 支持
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # 静态文件缓存
    location /static {
        alias /opt/stocknews/static;
        expires 30d;
    }
}
EOF

ln -s /etc/nginx/sites-available/stocknews /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 2.7 配置 HTTPS 免费证书

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d 你的域名.com
```

---

## 三、费用清单

| 项目 | 费用 | 必须？ |
|------|:---:|:---:|
| 服务器 (2C2G) | ¥34-40/月 | ✅ 必须 |
| 域名 | ¥50-80/年 | ✅ 必须 |
| HTTPS 证书 | ¥0 (Let's Encrypt) | ✅ 推荐 |
| DeepSeek API (AI摘要) | ¥1/百万token ≈ ¥5-20/月 | ❌ 可选 |
| Yahoo Finance API | ¥0 (免费额度) | ❌ 可选 |
| Finnhub API | ¥0 (免费额度) | ❌ 可选 |
| CDN (Cloudflare) | ¥0 (免费套餐) | ❌ 可选 |

> 💰 **最低月费: ¥38**（服务器+域名均摊）/ **全功能: ¥50-60/月**

---

## 四、维护操作

```bash
# 重启服务
systemctl restart stocknews

# 手动爬取
cd /opt/stocknews && source venv/bin/activate && python run.py --crawl

# AI 批量摘要（需要 DeepSeek Key）
cd /opt/stocknews && source venv/bin/activate && python run.py --ai

# 重置数据库
cd /opt/stocknews && source venv/bin/activate && python run.py --reset

# 查看数据库
sqlite3 /opt/stocknews/stocknews.db "SELECT COUNT(*) FROM articles;"
```

---

## 五、可选增强

### 5.1 接入 Cloudflare CDN（免费提速）
在 Cloudflare 添加域名 → 把 DNS 指向 Cloudflare → 开启 CDN + DDoS 防护

### 5.2 Docker 部署（隔离环境）
项目根目录已包含 `Dockerfile`，可一键 `docker compose up -d`

### 5.3 监控 & 告警
可使用 UptimeRobot（免费）监控网站可用性
