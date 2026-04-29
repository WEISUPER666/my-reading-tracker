# 🚀 部署说明

> 本文档详细说明个人阅读档案系统的部署方式、配置选项、生产环境最佳实践及故障排查方法。

---

## 📋 目录

- [1. 本地部署](#1-本地部署)
- [2. Docker 部署](#2-docker-部署)
- [3. 环境变量参考](#3-环境变量参考)
- [4. API 接口列表](#4-api-接口列表)
- [5. 生产环境部署建议](#5-生产环境部署建议)
- [6. 安全最佳实践](#6-安全最佳实践)
- [7. 数据备份与恢复](#7-数据备份与恢复)
- [8. 性能优化](#8-性能优化)
- [9. 监控与日志](#9-监控与日志)
- [10. 故障排查](#10-故障排查)
- [11. 版本更新](#11-版本更新)

---

## 1. 本地部署

### 1.1 环境要求

| 依赖 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.7 | 3.9+ |
| pip | 19.0 | 最新 |
| 磁盘空间 | 100MB | 500MB+（含数据存储） |

### 1.2 部署步骤

1. **克隆项目**
   ```bash
   git clone <项目仓库地址>
   cd my-reading-tracker
   ```

2. **创建虚拟环境（推荐）**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **（可选）配置环境变量**
   创建 `.env` 文件（与 [`main.py`](main.py) 同级），参考以下格式：
   ```env
   # 允许跨域访问的域名列表（逗号分隔）
   ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
   ```
   系统会自动通过 `python-dotenv` 加载 `.env` 文件中的配置。

5. **启动服务**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

6. **访问应用**
   打开浏览器，访问 `http://localhost:8000`，在密码锁页面输入访问密码后即可使用。

### 1.3 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| **访问密码** | 首次启动时自动初始化，默认密码 `123456`，可通过应用内「修改访问密码」功能更改 | `123456` |
| **跨域来源** | 通过环境变量 `ALLOWED_ORIGINS` 配置允许的跨域域名（逗号分隔） | `http://localhost:8000,http://127.0.0.1:8000` |
| **数据库** | 默认使用 SQLite 数据库，数据文件存储在 [`data/books.db`](data/books.db) | SQLite |
| **封面图片** | 上传的封面图片存储在 [`data/covers/`](data/covers/) 目录 | - |
| **服务端口** | 默认运行在 `8000` 端口 | 8000 |
| **系统名称/欢迎语** | 可在应用内「系统设置」中自定义，持久化到数据库 | 个人阅读档案 |

> 可以通过修改 [`main.py`](main.py) 文件中的配置来更改数据库连接或端口。

### 1.4 数据目录说明

启动服务后，会自动创建以下目录结构：

```
my-reading-tracker/
├── data/
│   ├── books.db      # SQLite 数据库文件
│   └── covers/       # 上传的封面图片存储目录
├── plans/            # 项目规划文档
│   └── ux-upgrade-plan.md
└── test_export.json  # 导出备份示例文件
```

> **注意**：[`data/`](data/) 目录及其子目录会在首次启动时自动创建，无需手动创建。

### 1.5 数据库自动迁移

系统在启动时会自动执行以下数据库维护操作：

1. **自动建表**：首次启动时自动创建 `books`、`reading_logs`、`categories`、`platforms`、`system_config` 五张表
2. **自动迁移**：检测旧表结构，自动添加缺失的列（如 `category`、`rating`、`read_url`、`progress`、`notes`、`icon` 等）
3. **默认分类初始化**：首次运行时自动创建默认分类（小说、历史、科技、哲学、心理学、经济管理、个人成长、其他），每个分类带有对应的 Emoji 图标
4. **默认平台初始化**：首次运行时自动创建默认平台（微信读书、喜马拉雅、本地文件、实体书）
5. **密码初始化**：首次运行时自动创建默认管理员密码（SHA-256 哈希存储）

迁移日志会在服务启动时打印到控制台，无需手动干预。

---

## 2. Docker 部署

### 2.1 环境要求

| 依赖 | 版本要求 |
|------|----------|
| Docker | 20.10+ |
| Docker Compose | 1.29+ 或 v2 |

### 2.2 部署步骤

1. **克隆项目**
   ```bash
   git clone <项目仓库地址>
   cd my-reading-tracker
   ```

2. **（可选）修改访问密码**
   部署后通过应用内「修改访问密码」功能更改默认密码。

3. **构建并启动容器**
   ```bash
   docker-compose up -d
   ```

4. **访问应用**
   打开浏览器，访问 `http://localhost:8000`，在密码锁页面输入访问密码后即可使用。

### 2.3 Docker 配置详解

[`docker-compose.yml`](docker-compose.yml) 配置文件说明：

```yaml
version: '3.8'

services:
  reading-tracker:
    build: .                    # 使用当前目录的 Dockerfile 构建镜像
    ports:
      - "8000:8000"             # 宿主机端口映射到容器 8000 端口
    volumes:
      - ./data:/app/data        # 数据持久化：宿主机 ./data 挂载到容器 /app/data
    environment:
      - TZ=Asia/Shanghai        # 设置时区为亚洲/上海
    restart: unless-stopped     # 容器退出时自动重启（除非手动停止）

volumes:
  data:
    driver: local
```

| 配置项 | 说明 |
|--------|------|
| **端口映射** | 容器暴露 `8000` 端口，默认映射到主机的 `8000` 端口 |
| **数据持久化** | `./data` 目录挂载到容器的 `/app/data` 目录，确保数据不丢失 |
| **封面图片** | 上传后存储在 `./data/covers/` 目录，通过卷挂载持久化 |
| **时区** | 环境变量 `TZ=Asia/Shanghai` 设置容器时区 |
| **重启策略** | `restart: unless-stopped` 确保容器在重启后自动启动 |

### 2.4 常用 Docker 命令

| 命令 | 说明 |
|------|------|
| `docker-compose up -d` | 后台启动服务 |
| `docker-compose down` | 停止并移除容器 |
| `docker-compose restart` | 重启服务 |
| `docker-compose ps` | 查看容器状态 |
| `docker-compose logs -f` | 查看实时日志 |
| `docker-compose up -d --build` | 重新构建镜像并启动（代码更新后使用） |
| `docker-compose exec reading-tracker bash` | 进入容器内部 |
| `docker system prune` | 清理未使用的 Docker 资源（镜像、容器、卷） |

---

## 3. 环境变量参考

| 环境变量 | 说明 | 默认值 | 示例 |
|----------|------|--------|------|
| `ALLOWED_ORIGINS` | 允许跨域访问的域名列表（逗号分隔） | `http://localhost:8000,http://127.0.0.1:8000` | `https://books.example.com,https://admin.example.com` |
| `TZ` | 容器时区（仅 Docker 部署） | `Asia/Shanghai` | `America/New_York` |

### 设置环境变量

**本地部署（Windows）**：
```cmd
set ALLOWED_ORIGINS=https://books.example.com
```

**本地部署（Linux/Mac）**：
```bash
export ALLOWED_ORIGINS=https://books.example.com
```

**使用 `.env` 文件（所有平台）**：
在项目根目录创建 `.env` 文件：
```env
ALLOWED_ORIGINS=https://books.example.com
```
系统启动时会自动通过 `python-dotenv` 加载该文件。

**Docker 部署**：
在 [`docker-compose.yml`](docker-compose.yml) 的 `environment` 中添加：
```yaml
environment:
  - ALLOWED_ORIGINS=https://books.example.com
  - TZ=Asia/Shanghai
```

---

## 4. API 接口列表

### 4.1 书籍接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 返回前端主页 [`index.html`](index.html) |
| `GET` | `/api/books/` | 获取所有书籍列表，包含阅读统计信息 |
| `GET` | `/api/books/check?title=书名` | 检查书籍是否已存在（智能查重） |
| `POST` | `/api/books/` | 录入新书（同时创建第一条阅读记录） |
| `PUT` | `/api/books/{book_id}` | 更新指定书籍的信息（书名、封面、分类、评分、阅读链接） |
| `GET` | `/api/books/{book_id}/logs` | 获取指定书籍的所有阅读记录 |
| `POST` | `/api/books/{book_id}/logs` | 为已有书籍添加新的阅读记录 |

### 4.2 阅读记录接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `PUT` | `/api/logs/{log_id}` | 更新指定阅读记录（平台、状态、日期、进度、备注） |
| `PATCH` | `/api/logs/{log_id}/progress` | 快速更新阅读进度（仅需 progress 字段） |
| `DELETE` | `/api/logs/{log_id}` | 删除指定阅读记录（若书籍无其他记录则自动删除书籍） |

### 4.3 分类管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/categories/` | 获取所有分类列表 |
| `POST` | `/api/categories/` | 创建新分类 |
| `PUT` | `/api/categories/{category_id}` | 更新分类（名称、图标） |
| `DELETE` | `/api/categories/{category_id}` | 删除指定分类 |

### 4.4 平台管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/platforms/` | 获取所有平台列表 |
| `POST` | `/api/platforms/` | 创建新平台 |
| `DELETE` | `/api/platforms/{platform_id}` | 删除指定平台 |

### 4.5 封面上传接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/upload/cover` | 上传封面图片，返回可访问的 URL |

### 4.6 数据备份接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/export` | 导出所有书籍和阅读记录为 JSON |
| `POST` | `/api/import` | 导入 JSON 格式的备份数据 |

### 4.7 系统设置接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/settings/` | 获取所有系统设置（站点名称、欢迎语、图标等） |
| `POST` | `/api/settings/` | 更新系统设置 |
| `POST` | `/api/settings/change-password` | 修改管理员访问密码 |

### 4.8 接口详细说明

#### `POST /api/books/` - 录入新书

**请求体**：
```json
{
  "title": "书名",
  "cover": "封面URL（可选）",
  "category": "分类（可选，默认'未分类'）",
  "rating": 4,
  "read_url": "阅读链接（可选）",
  "log": {
    "platform": "微信读书",
    "status": "阅读中",
    "start_date": "2024-01-15",
    "progress": "第823章（可选）",
    "notes": "随手记内容（可选）"
  }
}
```

**响应**：
```json
{
  "message": "新书录入成功！",
  "book_id": 1
}
```

#### `PUT /api/books/{book_id}` - 编辑书籍信息

**请求体**：
```json
{
  "title": "新书名（可选）",
  "cover": "新封面URL（可选）",
  "category": "新分类（可选）",
  "rating": 4,
  "read_url": "新阅读链接（可选）"
}
```

**响应**：
```json
{
  "message": "书籍信息更新成功！",
  "book_id": 1
}
```

#### `PUT /api/logs/{log_id}` - 更新阅读记录

**请求体**：
```json
{
  "platform": "微信读书（可选）",
  "status": "已读完（可选）",
  "start_date": "2024-06-01（可选）",
  "progress": "第900章（可选）",
  "notes": "新的备注（可选）"
}
```

**响应**：
```json
{
  "message": "阅读记录更新成功！"
}
```

#### `PATCH /api/logs/{log_id}/progress` - 快速更新阅读进度

**请求体**：
```json
{
  "progress": "第900章"
}
```

**响应**：
```json
{
  "message": "进度更新成功！",
  "log_id": 1,
  "progress": "第900章"
}
```

#### `POST /api/upload/cover` - 上传封面图片

- 请求类型：`multipart/form-data`
- 参数：`file`（图片文件）
- 限制：仅支持图片格式，大小不超过 5MB
- 响应：
  ```json
  {
    "url": "/covers/abc123def456.jpg"
  }
  ```

#### `DELETE /api/logs/{log_id}` - 删除阅读记录

- 删除指定阅读记录
- 如果该书籍没有其他阅读记录，书籍也会被自动删除（同时清理孤儿封面图片）
- 响应：
  ```json
  {
    "message": "阅读记录删除成功"
  }
  ```
  或（书籍同时被删除时）：
  ```json
  {
    "message": "阅读记录删除成功，由于该书已无其他阅读记录，书籍也已删除"
  }
  ```

#### `GET /api/export` - 导出备份数据

- 导出所有书籍和对应的阅读记录为完整的 JSON 结构
- 响应：
  ```json
  {
    "export_time": "2024-01-15 10:30:00",
    "total_books": 10,
    "books": [
      {
        "id": 1,
        "title": "三体",
        "cover": "/covers/abc.jpg",
        "category": "小说",
        "rating": 5,
        "read_url": "https://weread.qq.com/web/...",
        "created_at": "2024-01-01 12:00:00",
        "reading_logs": [
          {
            "id": 1,
            "platform": "微信读书",
            "status": "已读完",
            "start_date": "2024-01-01",
            "progress": "全本",
            "notes": "经典之作"
          }
        ]
      }
    ]
  }
  ```

#### `POST /api/import` - 导入备份数据

- 导入 JSON 格式的备份数据
- 自动跳过书名已存在的书籍（去重）
- 自动创建备份数据中缺失的分类
- 请求体：与 `/api/export` 返回格式相同
- 响应：
  ```json
  {
    "message": "导入完成！成功导入 5 本书",
    "imported_count": 5,
    "skipped_count": 2
  }
  ```

#### `POST /api/categories/` - 创建新分类

**请求体**：
```json
{
  "name": "科幻",
  "icon": "🚀"
}
```

**响应**：
```json
{
  "message": "分类创建成功",
  "id": 1,
  "name": "科幻",
  "icon": "🚀"
}
```

#### `PUT /api/categories/{category_id}` - 更新分类

**请求体**：
```json
{
  "name": "科幻小说（可选）",
  "icon": "🌌（可选）"
}
```

**响应**：
```json
{
  "message": "分类更新成功",
  "id": 1,
  "name": "科幻小说",
  "icon": "🌌"
}
```

#### `POST /api/platforms/` - 创建新平台

**请求体**：
```json
{
  "name": "Kindle"
}
```

**响应**：
```json
{
  "message": "平台创建成功",
  "id": 1,
  "name": "Kindle"
}
```

#### `GET /api/settings/` - 获取系统设置

**响应**：
```json
{
  "site_name": "个人阅读档案",
  "welcome_title": "欢迎回来，阅读者 👋",
  "welcome_subtitle": "今天又读了什么好书？赶快记录下你的阅读进度或听书历程吧。每一次记录都是灵魂的脚印。",
  "site_icon": ""
}
```

#### `POST /api/settings/` - 更新系统设置

**请求体**：
```json
{
  "site_name": "我的书阁（可选）",
  "welcome_title": "欢迎回来（可选）",
  "welcome_subtitle": "新的欢迎语（可选）",
  "site_icon": "/covers/icon.jpg（可选）"
}
```

**响应**：
```json
{
  "message": "系统设置更新成功"
}
```

#### `POST /api/settings/change-password` - 修改访问密码

**请求体**：
```json
{
  "old_password": "当前密码",
  "new_password": "新密码（至少4位）",
  "confirm_password": "确认新密码"
}
```

**响应**：
```json
{
  "message": "密码修改成功"
}
```

### 4.9 认证说明

所有 `/api/` 开头的请求需要在请求头中携带 `X-Auth-Token` 字段，值为后端配置的访问密码。未携带或密码错误将返回 401 状态码：

```json
{
  "detail": "未授权访问，请提供正确的访问密码"
}
```

前端在密码锁页面验证成功后，会自动将密码保存到 `localStorage`，并在后续请求中自动添加 `X-Auth-Token` 请求头。如果后端返回 401 状态码，前端会自动清除本地保存的密码并跳转到密码锁页面。

---

## 5. 生产环境部署建议

### 5.1 本地部署生产方案

#### 使用 Supervisor 管理进程（Linux）

安装 Supervisor：
```bash
sudo apt-get install supervisor  # Ubuntu/Debian
sudo yum install supervisor      # CentOS/RHEL
```

创建 Supervisor 配置文件 `/etc/supervisor/conf.d/reading-tracker.conf`：
```ini
[program:reading-tracker]
command=/path/to/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
directory=/path/to/my-reading-tracker
user=www-data
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/reading-tracker.err.log
stdout_logfile=/var/log/reading-tracker.out.log
environment=ALLOWED_ORIGINS="https://books.example.com"
```

启动管理：
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start reading-tracker
```

#### 使用 Nginx 反向代理（推荐）

安装 Nginx 后，创建配置文件 `/etc/nginx/sites-available/reading-tracker`：

```nginx
server {
    listen 80;
    server_name books.example.com;

    # 启用 HTTPS 重定向（如果配置了 SSL）
    # return 301 https://$host$request_uri;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（如需）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 文件上传大小限制
        client_max_body_size 10M;
    }

    # 静态文件缓存
    location /covers/ {
        alias /path/to/my-reading-tracker/data/covers/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

启用站点并重启 Nginx：
```bash
sudo ln -s /etc/nginx/sites-available/reading-tracker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 配置 HTTPS（使用 Let's Encrypt）

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d books.example.com
```

### 5.2 Docker 部署生产方案

#### 使用 Docker Swarm

```bash
# 初始化 Swarm
docker swarm init

# 部署服务
docker stack deploy -c docker-compose.yml reading-tracker
```

#### 使用命名卷替代绑定挂载

修改 [`docker-compose.yml`](docker-compose.yml) 以获得更好的跨平台兼容性：

```yaml
version: '3.8'

services:
  reading-tracker:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - reading-data:/app/data
    environment:
      - TZ=Asia/Shanghai
      - ALLOWED_ORIGINS=https://books.example.com
    restart: unless-stopped

volumes:
  reading-data:
    driver: local
```

#### 使用 Nginx 反向代理 Docker 容器

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl
      - ./data/covers:/app/covers:ro
    depends_on:
      - reading-tracker
    restart: unless-stopped

  reading-tracker:
    build: .
    expose:
      - "8000"
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai
      - ALLOWED_ORIGINS=https://books.example.com
    restart: unless-stopped

volumes:
  data:
    driver: local
```

---

## 6. 安全最佳实践

### 6.1 密码安全

| 措施 | 说明 |
|------|------|
| **修改默认密码** | 部署后立即修改默认密码 `123456` |
| **使用强密码** | 建议使用 8 位以上，包含字母、数字和特殊字符的密码 |
| **密码哈希存储** | 系统使用 SHA-256 哈希存储密码，数据库泄露也无法直接获取明文密码 |
| **定期更换密码** | 建议每 3-6 个月更换一次访问密码 |

### 6.2 网络安全

| 措施 | 说明 |
|------|------|
| **配置 HTTPS** | 使用 Nginx + Let's Encrypt 配置 HTTPS 加密传输 |
| **限制跨域来源** | 通过 `ALLOWED_ORIGINS` 环境变量限制允许的跨域域名 |
| **使用反向代理** | 不要直接将 Uvicorn 暴露到公网，使用 Nginx 作为反向代理 |
| **防火墙配置** | 仅开放必要的端口（如 80/443） |

### 6.3 数据安全

| 措施 | 说明 |
|------|------|
| **定期备份** | 定期备份 `data/` 目录和导出 JSON 备份 |
| **访问控制** | 确保 `data/` 目录权限正确，避免未授权访问 |
| **安全传输** | 使用 HTTPS 传输备份文件 |

---

## 7. 数据备份与恢复

### 7.1 本地部署

**备份**：复制整个 `data/` 目录到安全位置
```bash
# Linux/Mac
cp -r data/ data_backup_$(date +%Y%m%d)/

# Windows (PowerShell)
Copy-Item -Path data -Destination "data_backup_$(Get-Date -Format 'yyyyMMdd')" -Recurse
```

**恢复**：将备份的 `data/` 目录复制回项目根目录

### 7.2 Docker 部署

**备份**：
```bash
# 先停止容器以确保数据一致性
docker-compose down
cp -r ./data/ ./data_backup_$(date +%Y%m%d)/
docker-compose up -d
```

**恢复**：
```bash
docker-compose down
cp -r ./data_backup_20240101/* ./data/
docker-compose up -d
```

### 7.3 应用内备份（推荐）

除了文件级别的备份，系统还提供了应用内备份功能：

- **导出备份**：在应用界面中点击「⚙️ 设置 / 更多 → 导出备份」，一键下载 JSON 格式的备份文件
- **导入备份**：在应用界面中点击「⚙️ 设置 / 更多 → 导入备份」，选择之前导出的 JSON 文件即可恢复数据
- 导入时会自动跳过书名重复的书籍，避免数据冲突
- 导入时会自动创建备份数据中缺失的分类

### 7.4 自动化备份脚本

创建一个定时任务自动备份数据：

**Linux (crontab)**：
```bash
# 每天凌晨 2 点备份
0 2 * * * /path/to/backup-script.sh
```

**`backup-script.sh`**：
```bash
#!/bin/bash
BACKUP_DIR="/path/to/backups"
PROJECT_DIR="/path/to/my-reading-tracker"
DATE=$(date +%Y%m%d_%H%M%S)

# 备份 data 目录
cp -r "$PROJECT_DIR/data" "$BACKUP_DIR/data_$DATE"

# 保留最近 30 天的备份，删除更早的
find "$BACKUP_DIR" -name "data_*" -mtime +30 -exec rm -rf {} \;

# 输出日志
echo "[$(date)] 备份完成: $BACKUP_DIR/data_$DATE" >> "$BACKUP_DIR/backup.log"
```

**Windows (任务计划程序)**：
```powershell
# PowerShell 备份脚本 backup-script.ps1
$backupDir = "C:\backups"
$projectDir = "C:\Users\wcrwin\Desktop\my-reading-tracker"
$date = Get-Date -Format "yyyyMMdd_HHmmss"

# 备份 data 目录
Copy-Item -Path "$projectDir\data" -Destination "$backupDir\data_$date" -Recurse

# 保留最近 30 天的备份
Get-ChildItem "$backupDir" -Directory | Where-Object {
    $_.Name -like "data_*" -and $_.LastWriteTime -lt (Get-Date).AddDays(-30)
} | Remove-Item -Recurse -Force

# 输出日志
"[$([DateTime]::Now)] 备份完成: $backupDir\data_$date" | Out-File -FilePath "$backupDir\backup.log" -Append
```

---

## 8. 性能优化

### 8.1 数据库优化

| 场景 | 建议 |
|------|------|
| **大量书籍（1000+）** | 考虑迁移到 PostgreSQL 以获得更好的查询性能 |
| **大量阅读记录（10000+）** | 添加数据库索引优化查询速度 |
| **频繁读写** | SQLite 适合单用户场景，多用户并发建议使用 PostgreSQL |

### 8.2 前端优化

| 场景 | 建议 |
|------|------|
| **大量书籍卡片** | 考虑添加分页或虚拟滚动 |
| **图片加载** | 封面图片建议压缩后再上传，控制文件大小 |
| **首次加载** | 前端资源已通过 CDN 加载，无需额外优化 |

### 8.3 Docker 优化

| 措施 | 说明 |
|------|------|
| **限制资源使用** | 在 `docker-compose.yml` 中添加资源限制 |
| **使用 Alpine 镜像** | 减小镜像体积，加快构建速度 |
| **多阶段构建** | 分离构建环境和运行环境 |

**资源限制示例**：
```yaml
services:
  reading-tracker:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M
```

---

## 9. 监控与日志

### 9.1 查看应用日志

**本地部署**：
```bash
# 启动时日志直接输出到控制台
uvicorn main:app --host 0.0.0.0 --port 8000

# 如需保存日志到文件
uvicorn main:app --host 0.0.0.0 --port 8000 > app.log 2>&1
```

**Docker 部署**：
```bash
# 查看实时日志
docker-compose logs -f

# 查看最近 100 行日志
docker-compose logs --tail=100

# 将日志保存到文件
docker-compose logs > app.log
```

### 9.2 健康检查

可以通过以下方式检查应用是否正常运行：

```bash
# 检查 HTTP 响应
curl -I http://localhost:8000

# 检查 API 是否响应（需要携带认证头）
curl -H "X-Auth-Token: 123456" http://localhost:8000/api/books/

# Docker 容器健康检查
docker-compose ps
```

### 9.3 Docker 健康检查配置

在 [`docker-compose.yml`](docker-compose.yml) 中添加健康检查：

```yaml
services:
  reading-tracker:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

---

## 10. 故障排查

### 10.1 服务无法启动

| 问题 | 排查方法 | 解决方案 |
|------|----------|----------|
| **端口被占用** | `netstat -ano \| findstr :8000`（Windows）<br>`lsof -i :8000`（Linux/Mac） | 修改端口或停止占用端口的进程 |
| **依赖未安装** | `pip list` | 重新运行 `pip install -r requirements.txt` |
| **Python 版本过低** | `python --version` | 升级到 Python 3.7+ |
| **Docker 构建失败** | `docker-compose logs --tail=50` | 检查 Dockerfile 和依赖配置 |

### 10.2 封面上传失败

| 问题 | 排查方法 | 解决方案 |
|------|----------|----------|
| **目录权限** | 检查 `data/covers/` 是否存在且可写 | 确保目录存在且有写入权限 |
| **文件格式** | 检查上传文件类型 | 仅支持图片格式（JPG、PNG、GIF 等） |
| **文件大小** | 检查文件大小 | 上传文件不能超过 5MB |
| **磁盘空间** | 检查磁盘剩余空间 | 清理磁盘或扩展存储 |

### 10.3 密码验证失败

| 问题 | 排查方法 | 解决方案 |
|------|----------|----------|
| **请求头缺失** | 检查请求是否携带 `X-Auth-Token` | 确保前端正确配置了认证头 |
| **密码被修改** | 检查数据库中的密码哈希 | 通过应用内「修改密码」功能重置 |
| **忘记密码** | 查看 `main.py` 中的默认密码 | 删除 `data/books.db` 后重启可重置为默认密码 |

### 10.4 数据丢失

| 问题 | 排查方法 | 解决方案 |
|------|----------|----------|
| **Docker 数据卷未挂载** | 检查 `docker-compose.yml` 的 volumes 配置 | 确保 `./data:/app/data` 正确配置 |
| **数据库文件损坏** | 检查 `data/books.db` 文件大小 | 从备份恢复数据 |
| **误删除数据** | 检查是否有备份 | 使用应用内「导入备份」功能恢复 |

### 10.5 数据库字段错误

| 问题 | 排查方法 | 解决方案 |
|------|----------|----------|
| **字段不存在** | 查看启动日志中的迁移信息 | 重启服务即可自动执行数据库迁移 |
| **数据类型不匹配** | 检查 API 请求数据格式 | 确保请求数据符合 Pydantic 模型定义 |

### 10.6 跨域问题（CORS）

| 问题 | 排查方法 | 解决方案 |
|------|----------|----------|
| **前端无法访问 API** | 查看浏览器控制台 CORS 错误 | 在 `ALLOWED_ORIGINS` 中添加前端域名 |
| **自定义域名** | 确认域名已正确配置 | 设置环境变量 `ALLOWED_ORIGINS=https://your-domain.com` |

### 10.7 性能问题

| 问题 | 排查方法 | 解决方案 |
|------|----------|----------|
| **页面加载缓慢** | 检查网络请求耗时 | 优化封面图片大小，考虑使用 CDN |
| **大量书籍卡顿** | 检查书籍数量 | 考虑分页加载或迁移到 PostgreSQL |
| **Docker 容器内存不足** | `docker stats` | 增加容器内存限制 |

### 10.8 系统设置不生效

| 问题 | 排查方法 | 解决方案 |
|------|----------|----------|
| **设置未保存** | 检查 API 响应是否成功 | 重新保存设置，确认提示「保存成功」 |
| **页面标题未更新** | 检查 `document.title` | 刷新页面或重新登录 |
| **图标不显示** | 检查图片 URL 是否可访问 | 确保图标图片路径正确且可访问 |

---

## 11. 版本更新

### 11.1 本地部署

1. **停止服务**（按 `Ctrl+C`）
2. **备份数据**
   ```bash
   cp -r data/ data_backup_$(date +%Y%m%d)/
   ```
3. **拉取最新代码**
   ```bash
   git pull
   ```
4. **重新构建并启动容器**
   ```bash
   docker-compose up -d --build
   ```
5. **验证更新**
   ```bash
   docker-compose logs --tail=50
   ```

### 11.3 更新注意事项

- **数据库迁移**：系统启动时自动执行，无需手动操作
- **数据兼容性**：更新前建议先导出 JSON 备份
- **配置变更**：检查是否有新的环境变量或配置项需要设置
- **回滚方案**：保留旧版本的代码和数据库备份，以便需要时回滚

---

> **提示**：如有其他部署相关问题，请查看 [`README.md`](README.md) 中的常见问题部分或提交 Issue。
   ```bash
   git pull
   ```
4. **安装新的依赖（如果有）**
   ```bash
   pip install -r requirements.txt
   ```
5. **启动服务**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
6. **验证更新**
   - 检查启动日志中的数据库迁移信息
   - 访问应用确认功能正常

### 11.2 Docker 部署

1. **备份数据**
   ```bash
   cp -r ./data/ ./data_backup_$(date +%Y%m%d)/
   ```
2. **停止并移除旧容器**
   ```bash
   docker-compose down
   ```
3. **拉取最新代码**
   ```bash
   git pull
   ```
4. **重新构建并启动容器**
   ```bash
   docker-compose up -d --build
   ```
5. **验证更新**
   ```bash
   docker-compose logs --tail=50
   ```

### 11.3 更新注意事项

- **数据库迁移**：系统启动时自动执行，无需手动操作
- **数据兼容性**：更新前建议先导出 JSON 备份
- **配置变更**：检查是否有新的环境变量或配置项需要设置
- **回滚方案**：保留旧版本的代码和数据库备份，以便需要时回滚

---

> **提示**：如有其他部署相关问题，请查看 [`README.md`](README.md) 中的常见问题部分或提交 Issue。
