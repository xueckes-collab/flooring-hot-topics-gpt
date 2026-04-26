# 在 ChatGPT 中配置这个 GPT

## 前置条件

1. ChatGPT Plus / Team / Enterprise 账号(才能创建 GPT)
2. 中间层 API 已经部署到一个 **HTTPS 公开 URL**(GPT Actions 不接受 http、不接受 localhost)。本地开发可用 `cloudflared tunnel` 或 `ngrok` 临时暴露 8000 端口。

## 步骤

### 1. 创建 GPT
- 打开 https://chatgpt.com/gpts/editor
- 点 **Configure** 标签

### 2. 基本信息
- **Name**: `Flooring Hotspot Scout`
- **Description**: `通过 Semrush 找出竞争对手 SPC/PVC/LVT/Vinyl/Commercial Flooring 网站的热点话题,直接产出 Blog / LinkedIn / 开发信选题。`
- **Instructions**: 复制 `gpt/system_prompt.md` 全文(去掉顶部那一行说明)粘进来。
- **Conversation starters**: 复制 `gpt/conversation_starters.md` 里的 4 条,每条占一行。

### 3. Capabilities
- ✅ Web Browsing — **关闭**(数据只走 Semrush)
- ✅ DALL·E — 关闭
- ✅ Code Interpreter — 关闭
- ✅ Canvas — 可选
- 关闭无关能力可以减少 GPT 走偏的概率。

### 4. Actions(关键步骤)
- 点 **Create new action**
- **Authentication**:
  - Type: `API Key`
  - Auth Type: `Bearer`
  - API Key: 填你 `.env` 里设置的 `API_BEARER_TOKEN` 完整字符串
- **Schema**: 把 `gpt/actions_openapi.yaml` 全文粘贴进去
  - 首先把第 9 行的 `https://your-public-host.example.com` 改成你部署后的真实 URL
- **Privacy policy**(如果要公开发布):填你的隐私政策 URL,内部使用可以填 `https://example.com/privacy`
- 点保存,GPT 编辑器会自动列出 3 个 actions: `analyzeHotTopics` / `exportTopics` / `getHealth`

### 5. 测试
- 在右侧预览框输入:
  ```
  分析 shaw.com 和 mohawkflooring.com 的 commercial flooring 话题
  ```
- 第一次调用时 ChatGPT 会问「Allow this action to run?」, 选 **Always Allow**(只对本 GPT 生效)
- 你应该看到一条带 ⚠️(mock 模式下)或不带前缀(real 模式下)的话题榜单。
- 接着发 `导出 xlsx`,GPT 应该返回一个 `https://你的域名/exports/...xlsx` 的下载链接。

### 6. 可见性

**如果是 BYOK 模式**(每个用户用自己的 Semrush key,推荐):
- 可以放心设为 **「知道链接的任何人」**,因为陌生人没有访问码就调不动你的 Semrush
- 用户拿到 GPT 链接后,你必须告诉他们也去 **`https://你的域名/setup`** 注册访问码
- 想上 GPT Store 也行,但要在 GPT description 里清楚写「需要 Semrush API key,请先访问 .../setup 注册」

**如果是共享 key 模式**(`DATA_SOURCE_MODE=real`,你给所有人付钱):
- 默认 **「只有我」**;给信任的同事开 **「知道链接的任何人」**
- **不要上 GPT Store** —— 陌生人会烧掉你的 Semrush 配额

### 7. BYOK 模式给最终用户的话术

如果你走 BYOK,把这段话连同 GPT 链接一起发给用户:

> 1. 打开这个 GPT:`https://chatgpt.com/g/g-xxxx`
> 2. 第一次用之前先去 `https://你的域名/setup` 注册:粘贴你的 Semrush API Key,得到一串「访问码」(格式 `floor-XXXX-XXXX`)
> 3. 在 GPT 里和它说:「我的访问码是 floor-XXXX-XXXX,接下来分析 shaw.com 的热点话题」
> 4. 后续在同一段对话里直接问就行,不用每次重报访问码;**新开对话需要再报一次**
> 5. 默认每天上限 50 次调用,不够可以在 setup 页改

## 常见坑

| 现象 | 原因 | 修法 |
|---|---|---|
| `Could not parse OpenAPI spec` | YAML 缩进 / `servers.url` 用了 http | 检查 url 是 https,粘贴前用 `python -c "import yaml,sys;yaml.safe_load(open(sys.argv[1]))" actions_openapi.yaml` 验证 |
| GPT 总说「我无法访问外部数据」 | 没保存 action,或 GPT 没选用 action | 在 Configure 里确认 action 出现在 Actions 区块,清掉对话重试 |
| `401 Unauthorized` | Bearer token 没匹配 | 把 GPT 编辑器里的 API Key 和 .env 里的 `API_BEARER_TOKEN` 完全对齐 |
| 返回都是 mock | `DATA_SOURCE_MODE` 没切到 `real`,或 `SEMRUSH_API_KEY` 空 | 改 .env 后重启 uvicorn |
| 下载链接 404 | `PUBLIC_BASE_URL` 没设对 | 把 .env 里的 `PUBLIC_BASE_URL` 改成 GPT 实际访问的那个 https 地址 |
