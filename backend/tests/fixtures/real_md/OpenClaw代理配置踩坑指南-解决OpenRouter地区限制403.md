# OpenClaw 代理配置踩坑指南 — 解决 OpenRouter 地区限制 403

## 问题背景

在 macOS 上使用 OpenClaw 接入 OpenRouter 模型（如 `openrouter/anthropic/claude-sonnet-4.6`）时，由于地区限制，API 请求会返回：

```
HTTP 403: This model is not available in your region.
```

即使本机已有 HTTP 代理（如 Clash 运行在 `127.0.0.1:7890`），OpenClaw Gateway 作为 LaunchAgent 服务运行时**不会自动使用代理**。

## 核心原因

这个问题涉及 **三层坑**，每层都不一样：

### 坑 1：LaunchAgent 不继承终端环境变量

macOS 的 LaunchAgent 启动的服务**不会继承** Shell 中 `export` 的环境变量。即使终端里设了 `HTTP_PROXY`，Gateway 进程也读不到。

### 坑 2：Node.js 原生 fetch 不走 HTTP_PROXY

即使在 plist 里设了 `HTTP_PROXY` / `HTTPS_PROXY`，Node.js（v18+）内置的 `fetch`（基于 undici）**不会自动读取这些环境变量**。这是 Node.js 的已知行为，和传统的 `curl` / Python `requests` 不同。

### 坑 3：OpenClaw 内部有特殊的 Dispatcher 检测逻辑

OpenClaw 内部使用 undici 的 `EnvHttpProxyAgent` 来处理代理。它在每次模型请求前会检查全局 Dispatcher 的类型：

- 如果是 `EnvHttpProxyAgent` → 走代理分支 ✅
- 如果是普通 `ProxyAgent` → 被标记为 `"unsupported"` 跳过 ❌
- 如果是普通 `Agent` → 不走代理 ❌

所以用 `global-agent` 这类第三方库注入的 `ProxyAgent` **会被 OpenClaw 忽略**。

## 解决方案

需要两步配合：**plist 注入环境变量** + **bootstrap 脚本设置正确的 Dispatcher**。

### 第一步：创建 Proxy Bootstrap 脚本

创建文件 `~/.openclaw/proxy-bootstrap.js`：

```javascript
// 使用 EnvHttpProxyAgent，OpenClaw 才会识别为代理 dispatcher
try {
  const undici = require('/opt/homebrew/lib/node_modules/openclaw/node_modules/undici');
  const proxy = process.env.HTTPS_PROXY || process.env.HTTP_PROXY || process.env.https_proxy || process.env.http_proxy;
  if (proxy && undici.EnvHttpProxyAgent && undici.setGlobalDispatcher) {
    undici.setGlobalDispatcher(new undici.EnvHttpProxyAgent());
  }
} catch (e) {}
```

> **关键点**：必须用 OpenClaw 自带的 undici（路径 `/opt/homebrew/lib/node_modules/openclaw/node_modules/undici`），因为 Node.js 25 中 `require('node:undici')` 在 CJS 模式下不可用。

### 第二步：修改 LaunchAgent plist

编辑 `~/Library/LaunchAgents/ai.openclaw.gateway.plist`，在 `<dict>` 的 `EnvironmentVariables` 段中添加：

```xml
<key>HTTP_PROXY</key>
<string>http://127.0.0.1:7890</string>
<key>HTTPS_PROXY</key>
<string>http://127.0.0.1:7890</string>
<key>NO_PROXY</key>
<string>localhost,127.0.0.1,::1</string>
<key>NODE_OPTIONS</key>
<string>-r /Users/你的用户名/.openclaw/proxy-bootstrap.js</string>
```

> 把 `127.0.0.1:7890` 替换为你的实际代理地址。

### 第三步：重启 Gateway

```bash
# 停止
openclaw gateway stop

# 卸载旧的 LaunchAgent
launchctl bootout gui/$UID/ai.openclaw.gateway

# 加载新配置
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/ai.openclaw.gateway.plist

# 验证
openclaw health
```

## 验证方法

### 验证 Bootstrap 脚本

```bash
HTTP_PROXY=http://127.0.0.1:7890 \
HTTPS_PROXY=http://127.0.0.1:7890 \
NO_PROXY=localhost,127.0.0.1,::1 \
node -r ~/.openclaw/proxy-bootstrap.js -e "
const undici = require('/opt/homebrew/lib/node_modules/openclaw/node_modules/undici');
console.log('Dispatcher:', undici.getGlobalDispatcher().constructor.name);
fetch('https://openrouter.ai/api/v1/models')
  .then(r => r.json())
  .then(d => console.log('OK, models:', d.data.length))
  .catch(e => console.error('FAIL:', e.message))
"
```

期望输出：

```
Dispatcher: EnvHttpProxyAgent
OK, models: 342
```

### 验证 Gateway 运行状态

```bash
openclaw health
openclaw models status
```

## 踩过的坑汇总

| 尝试方案 | 结果 | 原因 |
|---------|------|------|
| plist 里只设 `HTTPS_PROXY` | ❌ 403 | Node.js fetch 不读环境变量 |
| plist 里设 `HTTP_PROXY` + `HTTPS_PROXY` | ❌ WebSocket 断连 | 本地 `ws://` 连接也被代理了 |
| 只设 `HTTPS_PROXY`（不设 `HTTP_PROXY`） | ❌ 403 | undici 内部需要 HTTP_PROXY |
| npm `global-agent` + `NODE_OPTIONS=-r global-agent/bootstrap` | ❌ 403 | global-agent 只 patch http/https 模块，不影响 undici fetch |
| 自写 bootstrap 用 `undici.ProxyAgent` | ❌ 403 | OpenClaw 检测到 ProxyAgent 标记为 unsupported |
| 自写 bootstrap 用 `require('node:undici')` | ❌ 启动报错 | Node.js 25 CJS 模式不支持 `require('node:undici')` |
| **自写 bootstrap 用 openclaw 自带 undici 的 `EnvHttpProxyAgent`** | **✅ 成功** | OpenClaw 识别 EnvHttpProxyAgent，走代理分支 |

## 注意事项

1. **OpenClaw 更新后**：如果 `npm update -g openclaw`，undici 路径不会变，bootstrap 脚本无需修改。但如果完全卸载重装，需确认 undici 路径。
2. **`openclaw gateway install --force`**：此命令会重新生成 plist 文件，**会覆盖你添加的环境变量和 NODE_OPTIONS**，需要重新添加。
3. **NO_PROXY 很重要**：必须包含 `localhost,127.0.0.1,::1`，否则 Gateway 的本地 WebSocket 连接会被代理导致异常断连。
4. **代理端口**：文中 `7890` 是 Clash 默认端口，请根据实际情况修改。

## 环境信息

- macOS Darwin 24.0.0（Apple Silicon）
- Node.js v25.2.1
- OpenClaw 2026.3.8
- 代理：Clash（HTTP 代理 127.0.0.1:7890）

---

*最后更新：2026-03-12*
