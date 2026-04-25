# cmux 终端操作手册 - AI 编程终端配置指南

> cmux 是一款基于 Ghostty 的原生 macOS 终端应用，专为运行多个 AI 编码代理而设计，具备垂直标签页、分割窗格、内嵌浏览器和通知系统。

## 1. 基本信息

| 项目 | 说明 |
|------|------|
| 官网 | https://cmux.com |
| GitHub | https://github.com/manaflow-ai/cmux |
| 许可证 | GPL-3.0-or-later |
| 平台 | macOS |
| 底层技术 | Swift + AppKit + libghostty |
| 当前版本 | 0.63.2 |

## 2. 安装方法

### 方式一：Homebrew 安装（推荐）

```bash
# 添加 tap
brew tap manaflow-ai/cmux

# 安装 cmux
brew install --cask cmux

# 更新 cmux
brew upgrade --cask cmux
```

### 方式二：DMG 安装

1. 前往 [cmux.app](https://cmux.app) 下载 `.dmg` 文件
2. 打开 `.dmg`，将 cmux 拖入 Applications 文件夹
3. 从 Applications 启动 cmux
4. 支持通过 Sparkle 自动更新

### 验证安装

```bash
cmux --version
# 输出示例: cmux 0.63.2 (79) [179b16ce6]
```

> 首次启动 cmux 会自动安装命令行工具，使 `cmux` 命令在应用内的所有 shell 中可用。

## 3. 核心功能

### 3.1 通知系统
- 窗格在代理需要关注时显示蓝色光晕
- 标签页在侧边栏中高亮显示
- 专用通知面板显示待处理通知
- 使用 `⌘⇧U` 跳转到最新未读通知

### 3.2 内嵌浏览器
- 终端旁边分屏显示浏览器
- 可编程 API（从 agent-browser 移植）
- 支持：无障碍树快照、元素引用、点击、表单填写、JavaScript 执行
- 支持从 Chrome、Firefox、Arc 等 20+ 浏览器导入数据

### 3.3 标签页与窗格管理
- 垂直侧边栏显示：git 分支信息、PR 状态/编号、工作目录、监听端口、最新通知
- 支持水平和垂直分屏
- 多工作区支持

### 3.4 SSH 支持

```bash
cmux ssh user@remote
```

- 为远程机器创建工作区
- 浏览器窗格通过远程网络路由
- 支持拖拽上传图片（通过 scp）

### 3.5 Claude Code Teams

```bash
cmux claude-teams
```

- 运行 Claude Code teammate 模式，使用原生分屏
- 侧边栏显示元数据和通知

### 3.6 其他特性
- GPU 加速渲染
- Ghostty 配置兼容（主题、字体、颜色）
- 会话恢复（布局、工作目录、浏览器历史）
- 自定义命令（通过 `cmux.json`）
- 可编程 CLI 和 Socket API

## 4. 快捷键速查表

### 工作区 (Workspace)

| 快捷键 | 功能 |
|--------|------|
| `⌘N` | 新建工作区 |
| `⌘1` ~ `⌘8` | 跳转到对应工作区 |
| `⌘⇧W` | 关闭工作区 |
| `⌘⇧R` | 重命名工作区 |
| `⌘B` | 切换侧边栏 |

### 窗格 (Pane)

| 快捷键 | 功能 |
|--------|------|
| `⌘D` | 向右分屏 |
| `⌘⇧D` | 向下分屏 |
| `⌥⌘←→↑↓` | 切换焦点 |

### 浏览器 (Browser)

| 快捷键 | 功能 |
|--------|------|
| `⌘⇧L` | 打开浏览器分屏 |
| `⌘L` | 聚焦地址栏 |
| `⌘R` | 刷新页面 |
| `⌥⌘I` | 切换开发者工具 |
| `⌥⌘C` | JavaScript 控制台 |

### 通知 (Notifications)

| 快捷键 | 功能 |
|--------|------|
| `⌘I` | 显示通知面板 |
| `⌘⇧U` | 跳转到最新未读通知 |

### 终端 (Terminal)

| 快捷键 | 功能 |
|--------|------|
| `⌘K` | 清除滚动缓冲区 |
| `⌘+` / `⌘-` | 调整字体大小 |
| `⌘F` | 查找 |

### 通用 (General)

| 快捷键 | 功能 |
|--------|------|
| `⌘,` | 打开设置 |
| `⌘⇧,` | 重新加载配置 |
| `⌘Q` | 退出 |

## 5. 配置说明

### 5.1 终端配置

cmux 从 Ghostty 配置文件读取终端按键绑定：

```
~/.config/ghostty/config
```

可在此文件中配置主题、字体、颜色等终端外观。

### 5.2 自定义命令 (cmux.json)

在项目根目录创建 `cmux.json`，定义自定义命令，可通过命令面板启动：

```json
{
  "commands": [
    {
      "name": "启动开发服务器",
      "command": "npm run dev"
    },
    {
      "name": "运行测试",
      "command": "npm test"
    }
  ]
}
```

### 5.3 cmux 特定设置

cmux 特定的快捷键（工作区、分割、浏览器、通知）可在 **设置** (`⌘,`) 中自定义。

## 6. CLI 命令参考

### 工作区管理

```bash
cmux list-workspaces    # 列出所有工作区
cmux new-workspace      # 新建工作区
cmux rename-workspace   # 重命名工作区
```

### 窗格控制

```bash
cmux new-split          # 新建分屏
cmux new-pane           # 新建窗格
cmux close-surface      # 关闭当前表面
```

### 代理交互

```bash
cmux send               # 发送文本到窗格
cmux send-key           # 发送按键到窗格
```

### 浏览器操作

```bash
# 完整的浏览器子命令套件，用于导航和交互
```

### 反馈与状态

```bash
cmux notify             # 发送通知
cmux set-status         # 设置工作区状态
cmux set-progress       # 设置进度
```

### Socket API

cmux 通过 Unix 域套接字通信：

```
/tmp/cmux.sock
```

## 7. 典型使用场景

### 场景一：AI 多代理开发

1. 启动 cmux
2. `⌘D` 分屏，左侧运行 Claude Code，右侧运行开发服务器
3. `⌘⇧L` 打开浏览器预览应用
4. 通知系统自动提醒代理状态变化

### 场景二：Claude Code Teams

```bash
cmux claude-teams
```

自动创建多个分屏，每个运行一个 Claude Code teammate，侧边栏统一管理。

### 场景三：远程开发

```bash
cmux ssh user@server
```

创建远程工作区，内嵌浏览器通过远程网络访问服务。

## 8. 常见问题

**Q: cmux 命令找不到？**
A: 确保 cmux 应用已启动过一次（首次启动会自动安装 CLI 工具），或检查 `/opt/homebrew/bin/cmux` 是否在 PATH 中。

**Q: 如何自定义主题和字体？**
A: 编辑 `~/.config/ghostty/config` 文件，cmux 会自动读取 Ghostty 的配置。

**Q: 如何导入浏览器数据？**
A: 在设置中选择浏览器导入，支持 Chrome、Firefox、Arc 等 20+ 浏览器。

---

*文档更新日期：2026-04-14*
*cmux 版本：0.63.2*
*官方文档：https://cmux.com/docs/getting-started*
