# Deploy Guide — 把代码变成一个真实链接(5 分钟)

> ⚠️ 重要前提:**部署这一步必须你自己点**(GitHub / Railway 不接受第三方代操作)。下面这套流程把所有「你需要思考」的环节降到最低 —— 你做的事是按按钮、复制粘贴。
>
> **总耗时**:已有 GitHub 账号的情况下,~5 分钟到拿到公网 URL。
>
> **零免费**:Railway 从 $5/月起算计费(它给 $5 免费额度,够测试)。Render 起步 $7/月。Fly.io 有真免费档。

---

## 推荐路径:Railway

### 0. 准备(一次性)

打开 3 个浏览器 tab:
1. https://github.com/new — 新建一个空仓库,起名 `flooring-hot-topics-gpt`(public 或 private 都行)
2. https://railway.app/login — 用 GitHub 登录
3. 你的本地终端

### 1. 推代码到 GitHub

在项目目录里:

```bash
cd flooring-hot-topics-gpt
git init
git add .
git commit -m "initial: BYOK middleware for Flooring Hotspot GPT"
git branch -M main
git remote add origin https://github.com/<你的账号>/flooring-hot-topics-gpt.git
git push -u origin main
```

### 2. 在 Railway 一键部署

1. 在 Railway:**+ New → Deploy from GitHub repo → 选刚推的仓库**
2. Railway 自动识别 `Dockerfile` + `railway.json` → 开始 build
3. Build 完成前(~2 分钟),把环境变量配好(下一节)

### 3. 配置环境变量(Railway → Variables → Raw Editor)

把下面整块粘进去,**按里面的注释把 4 个值改成你自己的**:

```env
# === 必填:把下面 4 行替换成你的值 ===
API_BEARER_TOKEN=粘一段长的随机字符串(32 位以上,见下方生成命令)
KEY_ENCRYPTION_SECRET=粘 Fernet key(见下方生成命令)
PUBLIC_BASE_URL=https://你的-railway-app.up.railway.app

# === 默认就好,无需改 ===
DATA_SOURCE_MODE=byok
DATABASE_PATH=/data/byok.db
EXPORT_DIR=/data/exports
DEFAULT_DAILY_QUOTA=50
DEFAULT_MONTHLY_QUOTA=800
VALIDATE_SEMRUSH_ON_REGISTER=true
SEMRUSH_BASE_URL=https://api.semrush.com/
DEFAULT_DATABASE=us
SEMRUSH_PAGES_LIMIT=50
SEMRUSH_KEYWORDS_LIMIT=200
```

**生成 `API_BEARER_TOKEN`**(终端):
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**生成 `KEY_ENCRYPTION_SECRET`**(终端):
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> ⚠️ `KEY_ENCRYPTION_SECRET` 一旦生成,**永远不要换**,换了所有用户的访问码会作废。

### 4. 给 SQLite 加持久化磁盘(关键,否则重启数据全丢)

Railway → 你的 service → **Settings → Volumes → + New Volume**
- Mount path: `/data`
- Size: 1 GB(够用很久)

### 5. 拿到公网域名

Railway → service → **Settings → Networking → Generate Domain**
- 你会拿到形如 `flooring-hot-topics-gpt-production.up.railway.app`
- **回到 Variables**,把 `PUBLIC_BASE_URL` 改成 `https://<刚生成的域名>`(注意 https://)
- service 自动重启

### 6. 验证部署

```bash
BASE_URL=https://你的-railway-app.up.railway.app \
BEARER=你刚生成的-API_BEARER_TOKEN \
./scripts/post_deploy_smoke_test.sh
```

期待输出:8 项检查全部 ✓ PASS。失败的话往下看「常见坑」。

如果你**已经有真实的 Semrush API key**,加上 `SEMRUSH_KEY=sm_xxx` 让它跑一次真调用:
```bash
BASE_URL=... BEARER=... SEMRUSH_KEY=sm_xxx ./scripts/post_deploy_smoke_test.sh
```

### 7. 把 GPT 配起来

在 ChatGPT GPT Editor:
- 把 `gpt/system_prompt.md` 全文粘进 Instructions
  - **替换**里面的 `https://your-public-host.example.com` → 你的 Railway 域名
- 把 `gpt/actions_openapi.yaml` 全文粘进 Actions Schema
  - **替换** `servers.url` → 你的 Railway 域名
- Actions Authentication:
  - Type: API Key
  - Auth Type: Bearer
  - API Key: 粘你设的 `API_BEARER_TOKEN`
- 可见性:**知道链接的任何人**
- 保存,记下 GPT URL,长这样:`https://chatgpt.com/g/g-XXXXX-flooring-hotspot-scout`

### 8. 你给用户的两条链接 + 一段说明

```
> 用我的 Flooring Hotspot Scout 找竞争对手热点话题:
>
> 1. 注册访问码(只需做一次):
>    https://你的-railway-app.up.railway.app/setup
>    粘你的 Semrush API Key,拿一串 floor-XXXX-XXXX 访问码
>
> 2. 打开机器人:
>    https://chatgpt.com/g/g-XXXXX-flooring-hotspot-scout
>    第一句对它说:「我的访问码是 floor-XXXX-XXXX,分析 shaw.com 的 commercial flooring 热点」
>
> 需要 ChatGPT Plus($20/月)+ Semrush API 套餐(Business $449/月起)
> 默认配额:每天 50 次调用 / 每月 800 次
```

---

## 备选路径:Render

```bash
# 同样先 git push 到 GitHub,然后:
# 1. 登录 https://render.com → New + → Blueprint
# 2. 选你刚推的 repo,Render 自动识别 render.yaml
# 3. 在 KEY_ENCRYPTION_SECRET 那一栏粘 Fernet key
# 4. 部署完,在 service Settings 把 PUBLIC_BASE_URL 改成 https://<service>.onrender.com
```

## 备选路径:Fly.io(免费档可用)

```bash
brew install flyctl     # macOS
fly auth login

cd flooring-hot-topics-gpt
fly launch --no-deploy --copy-config

# 设置 secrets(不会暴露到 fly.toml)
fly secrets set API_BEARER_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fly secrets set KEY_ENCRYPTION_SECRET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Volumes — 持久化数据
fly volumes create byok_data --size 1

fly deploy

# 设置公网 URL(部署后)
fly secrets set PUBLIC_BASE_URL=https://flooring-hotspot-gpt.fly.dev
```

---

## 常见坑

| 现象 | 原因 | 解决 |
|---|---|---|
| `503 Server misconfigured: API_BEARER_TOKEN is still the default` | `.env` 里没改 token | Railway → Variables 配上 |
| `/setup` 打不开,显示 404 | service 没起来 | Railway → Deployments 看日志 |
| `/register` 一直报 `Could not validate this Semrush key` | 你的 Semrush 套餐没开 API,或 units 用完 | 临时把 `VALIDATE_SEMRUSH_ON_REGISTER=false`,但**生产强烈建议保持 true** |
| GPT 一直说「我无法访问数据」 | OpenAPI schema 里的 `servers.url` 没改成你的真实域名 | 改完保存 GPT,清空对话重试 |
| 调 GPT 后 200 但 `data_source: mock` | 服务器 `DATA_SOURCE_MODE` 不是 `byok` 或 `real` | Railway Variables 改一下 |
| 重启后所有访问码失效 | `KEY_ENCRYPTION_SECRET` 被换了 / volume 没挂上 | 检查 secret 没变 + `/data` 挂载 |
| 看不到自己的 SQLite | Railway 的 shell 工具:`Variables → Connect → Shell`,然后 `sqlite3 /data/byok.db ".tables"` | |

---

## 跑通后的日常运维

- **看用量**:`/usage/<访问码>` 返回 JSON,任何人都能查自己的
- **某用户跑超了**:Railway shell 进去 `sqlite3 /data/byok.db "UPDATE user_keys SET daily_quota=200 WHERE user_token='floor-XXXX-XXXX'"`
- **黑名单某访问码**:调 `/revoke` 接口,或 SQL `UPDATE user_keys SET status='revoked' WHERE ...`
- **导出文件清理**:`exports/` 会一直长大。每月手动清理或加个 cron
- **滚动 KEY_ENCRYPTION_SECRET**:别滚,会废掉所有用户。如果非要,得做迁移脚本(我可以帮写)
