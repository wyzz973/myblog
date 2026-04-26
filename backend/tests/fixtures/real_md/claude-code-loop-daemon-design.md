# Claude Code Loop 守护进程设计方案

> 日期：2026-03-20
> 状态：v1 已实现，可用

## 核心问题

需要一个 Claude Code 长驻运营守护进程，让 `/loop` 永不中断。当前三个限制：

| 限制 | 原因 | 解决方案 |
|------|------|---------|
| Loop 3 天过期 | CronCreate 硬限制 | 守护进程每 2 天自动续命 |
| 上下文会满 | 长时间运行消息累积 | 每 2 小时自动 `/new` 轮转 |
| 进程可能挂 | Claude CLI 崩溃/网络断开/Mac 休眠 | 每 60s 健康检查，自动重建 |

## 最终架构：方向 B — 长驻会话 + 外部看门狗

选择方向 B 的原因：
- **Skill/MCP 热加载** — 避免每次冷启动的初始化开销
- **可随时 attach 交互** — `tmux attach -t claude-daemon` 即可手动介入

```
┌──────────────────────────────────────────────────────┐
│  daemon.py (Python 守护进程，后台运行)                   │
│                                                      │
│  三个定时器并行：                                       │
│                                                      │
│  [健康检查] 每 60s                                     │
│  ├─ tmux 会话存在？claude 进程活着？                     │
│  └─ 否 → 重建会话 + 启动 claude + 发 /loop             │
│                                                      │
│  [上下文轮转] 每 2 小时                                 │
│  └─ 发送 /new                                         │
│                                                      │
│  [Loop 续命] 每 2 天                                   │
│  └─ 停止当前 loop → /new → 重发 /loop 15m <prompt>     │
│                                                      │
└──────────────────────┬───────────────────────────────┘
                       │ tmux send-keys
                       ▼
┌──────────────────────────────────────────────────────┐
│  tmux session: "claude-daemon"                        │
│  └─ claude --dangerously-skip-permissions               │
│     -n xhs-daemon-{timestamp}                         │
│     └─ /loop 15m 读取并严格执行 loop-prompt.txt ...     │
│        ├─ 每 15 分钟自动执行一轮                        │
│        ├─ 读 strategy.json，判断当前时段任务             │
│        ├─ 执行 CLI 命令（check-login/互动/发布/...）     │
│        └─ 写日志到 logs/                               │
└──────────────────────────────────────────────────────┘
```

## 设计决策汇总

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 架构方向 | 方向 B：长驻会话 + 外部看门狗 | Skill/MCP 热加载；可随时 attach 交互 |
| 守护进程形态 | Python 单文件脚本 | 简单灵活，可靠性要求不高 |
| 上下文管理 | 每 2 小时 `/new` | 定时轮转，不需要检测上下文是否满 |
| Loop 续命 | 每 2 天 stop + `/new` + 重发 | 在 3 天过期前续命 |
| Loop prompt | 从文件读取（loop-prompt.txt） | 长 prompt 不适合放 JSON |
| 启动方式 | 后台 daemonize，start/stop/status | `python daemon.py start/stop/status` |
| Claude 启动参数 | `--dangerously-skip-permissions -n <name>` | 无人值守 + 会话可追溯 |
| Session 命名 | `xhs-daemon-{YYYYMMDD-HHMMSS}` | 记录在 state 中，可用 `--resume` 回看 |
| Prompt 传递 | 引用指令（非内联） | 避免 tmux send-keys 长文本 shell 解析问题 |
| 异常通知 | 先写日志，后续扩展飞书 | 简单优先 |
| 重建保护 | 5 分钟冷却期 | 防止 claude 启动失败导致无限重建 |

## 已实现功能

### daemon.py（~430 行，纯标准库）

**命令接口：**
```bash
python daemon.py start    # 后台启动（双 fork daemonize）
python daemon.py stop     # 发 SIGTERM 优雅停止
python daemon.py status   # 显示 PID、当前 session、历史 session、重建次数
```

**核心模块：**

| 模块 | 功能 |
|------|------|
| `load_config()` | 从 strategy.json 读 daemon 配置，支持 `loop_prompt_file` 从文件加载长 prompt |
| `daemonize()` | 经典双 fork，重定向 stdio 到 /dev/null |
| `read_pid() / write_pid()` | PID 文件管理，检测进程存活，清理 stale PID |
| `load_state() / save_state()` | 状态持久化到 daemon-state.json（原子写入，防 crash 损坏） |
| `tmux_*()` | tmux 会话管理（create/kill/send-keys/check session） |
| `claude_process_alive()` | 递归查进程树，处理 shell wrapper（nvm/fnm 等） |
| `ensure_session()` | 健康检查 + 自动重建，带 5 分钟冷却退避 |
| `maybe_rotate_context()` | 每 2 小时发 `/new` |
| `maybe_renew_loop()` | 每 2 天停 loop + `/new` + 重发 `/loop` |
| `run_loop()` | 主循环，1 秒粒度 sleep 响应 SIGTERM |

**日志：** `RotatingFileHandler`，5MB × 3 个备份

**Session 追溯：** 每次重建记录 session name 到 `daemon-state.json`，status 命令显示最近 3 个

### Prompt（loop-prompt.txt）

包含 A-G 七个执行阶段：

| 阶段 | 内容 |
|------|------|
| A | 基础检查（登录、策略、今日状态） |
| B | 选题雷达（推荐页 + 搜索 + 网络调研） |
| C | 主稿引擎（竞品学习 + 写稿 + 三层校验） |
| D | 发布守门（时间窗口 + 风控检查） |
| E | 实时运营巡航（通知、评论、互动） |
| F | 夜间调参（数据复盘 + 策略微调） |
| **G** | **自我进化机制（新增）** |

### 自我进化机制（G 阶段）

| 子模块 | 作用 | 数据载体 |
|--------|------|---------|
| G1 知识沉淀 | 累积 winning/losing patterns、受众洞察、趋势话题、评论模板 | `logs/evolution.json` |
| G2 策略自动迭代 | 数据驱动 strategy.json 参数调整（权重、关键词、时段） | strategy.json + 变更日志 |
| G3 写稿进化 | 写稿前读历史 pattern，融入有效模式，回避失败做法 | 草稿 metadata |
| G4 互动进化 | 追踪评论反馈，学习高回复率风格和帖子类型 | evolution.json |
| G5 选题进化 | 追踪选题预测准确度，修正选题判断逻辑 | evolution.json |
| G6 Prompt 自优化 | 每周生成进化报告，反思规则合理性 | `logs/weekly-evolution-report-{date}.json` |

## 文件结构

```
~/xhs-workspace/
├── daemon.py                         # 守护进程主程序
├── loop-prompt.txt                   # /loop 的完整 prompt（从文件加载）
├── strategy.json                     # 运营策略（含 daemon 配置节）
├── docs/plans/
│   ├── 2026-03-20-loop-daemon-design.md   # 设计文档
│   └── 2026-03-20-loop-daemon-plan.md     # 实现计划
└── logs/
    ├── daemon.pid                    # PID 文件
    ├── daemon.log                    # 守护进程日志（5MB × 3 轮转）
    ├── daemon-state.json             # 运行状态 + session 历史
    └── evolution.json                # 自我进化知识库（由 Claude 维护）
```

## 配置（strategy.json 的 daemon 节）

```json
{
  "daemon": {
    "loop_interval_minutes": 15,
    "loop_prompt": "/xhs-autopilot",
    "loop_prompt_file": "loop-prompt.txt",
    "health_check_interval_seconds": 60,
    "context_rotate_hours": 2,
    "loop_renew_days": 2,
    "tmux_session_name": "claude-daemon",
    "log_level": "INFO"
  }
}
```

- `loop_prompt_file` 优先于 `loop_prompt`，支持相对路径（相对 workspace）、绝对路径、`~` 展开
- 指定 `loop_prompt_file` 后，实际发送的是 `"读取并严格执行 <绝对路径> 中的完整指令"`，由 Claude 自己读文件（避免 tmux send-keys 长文本解析问题）
- 修改 `loop-prompt.txt` 后不需要重启守护进程，下次 loop 续命时自动生效

## 使用方法

```bash
cd ~/xhs-workspace

# 启动
python daemon.py start

# 查看状态
python daemon.py status
# 输出示例：
# 守护进程运行中 (PID 12345)
#   当前 session: xhs-daemon-20260320-143000
#   上次 /loop:   2026-03-20 14:30:10
#   上次 /new:    2026-03-20 16:30:05
#   重建次数:     1
#   历史 session: 1 个
#     - xhs-daemon-20260320-143000 (2026-03-20 14:30:00, rebuild)

# 看日志
tail -f ~/xhs-workspace/logs/daemon.log

# 手动进入 Claude 会话交互
tmux attach -t claude-daemon
# Ctrl+B D 退出 tmux（不中断 Claude）

# 回看历史会话
claude -r xhs-daemon-20260320-143000

# 停止
python daemon.py stop
```

## 踩坑记录

### 已修复的问题

| 问题 | 原因 | 修复 |
|------|------|------|
| `--session-name` 报错 | claude CLI 正确 flag 是 `-n` / `--name` | 改为 `-n` |
| 长 prompt 被 shell 解析 | tmux send-keys 发 2800 字符，反引号等被 zsh 解析 | 改为发引用指令，Claude 自己读 `loop-prompt.txt` |
| `claude_process_alive` 永远 False | macOS `pgrep -a` 只输出 PID 不带命令名 | 改用 `ps -p <pid> -o comm=` 获取进程名 |
| 无限重建 208 次 | 上述两个 bug 叠加 | 修复检测 + 重置 state |
| `pgrep -P` 只查直接子进程 | nvm/fnm 等 wrapper 导致 claude 是孙进程 | 递归查两层（子+孙） |
| 无重建退避 | claude 启动失败时每 60s 重建 | 5 分钟冷却期 |
| 状态文件 crash 损坏 | 直接写文件 mid-write 被 kill | 先写 `.tmp` 再 `rename` 原子操作 |
| 时间戳不可读 | status 显示 epoch 浮点数 | `datetime.fromtimestamp` 格式化 |
| 日志无轮转 | FileHandler 无限追加 | `RotatingFileHandler` 5MB × 3 |

## 后续扩展（不在 v1 范围）

- 飞书通知异常和日报
- Web 监控面板
- 多账号支持
- launchd 开机自启
- 配置热重载（SIGHUP）
