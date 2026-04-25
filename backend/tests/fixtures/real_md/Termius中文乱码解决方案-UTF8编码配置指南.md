# Termius 中文乱码问题解决方案：UTF-8 编码配置指南

> 来源：[文心快码](https://comate.baidu.com/zh/page/qk19ea2iu69) | 2025-11-14

---

## 问题概述

在 Mac 或 Windows 系统使用 Termius 时，用户常遇到中文显示乱码问题。本文将系统梳理不同场景下的 UTF-8 编码配置方案，帮助用户彻底解决字符解析异常问题。

---

## 系统 Shell 环境变量配置

### 1. 确认 Shell 类型

执行以下命令确认当前 Shell 类型：

```bash
echo $SHELL
```

| 输出内容 | 需修改的文件 |
|---------|-------------|
| 包含 `zsh` | `~/.zshrc` |
| 包含 `bash` | `~/.bash_profile` |

---

### 2. 修改环境变量

#### 对于 zsh 用户

```bash
vi ~/.zshrc
```

操作步骤：
1. 按 `i` 进入编辑模式
2. 在文件末尾添加：

```bash
export LANG=en_US.UTF-8
```

3. 按 `Esc` 退出编辑
4. 输入 `:wq` 保存退出

#### 对于 bash 用户

```bash
vi ~/.bash_profile
```

操作与 zsh 相同，添加相同内容后保存。

---

### 3. 生效配置

执行以下命令使修改立即生效：

```bash
# zsh 用户
source ~/.zshrc

# bash 用户
source ~/.bash_profile
```

---

## 跨平台特殊场景处理

### Windows 连接树莓派乱码

树莓派默认使用 GB-18030 编码，需修改为 UTF-8：

```bash
sudo nano /etc/default/locale
```

将配置项中的 `GB-18030` 更改为 `UTF-8` 后保存。

---

### Termius CLI 中文乱码

在终端中配置 UTF-8 环境变量（方法同系统 Shell 配置）。

---

## 配置文件示例

### zsh 配置文件 (~/.zshrc)

```bash
# 末尾添加以下内容
export LANG=en_US.UTF-8
```

### bash 配置文件 (~/.bash_profile)

```bash
# 末尾添加以下内容
export LANG=en_US.UTF-8
```

---

## 验证与注意事项

- 修改配置后需执行 `source` 命令使配置生效
- 建议备份原始配置文件
- 确保系统已安装 UTF-8 语言包

### Shell 类型与配置文件对照表

| Shell 类型 | 配置文件 |
|-----------|---------|
| zsh | `~/.zshrc` |
| bash | `~/.bash_profile` |

---

## 参考资料

| 来源 | 链接 |
|------|------|
| 百度智能云 | [Mac中Termius中文显示乱码的解决方案](https://cloud.baidu.com/article/3294579) |
| CSDN博客 | [如何解决mac中Termius中文显示乱码](https://blog.csdn.net/qq_34041723/article/details/133985318) |
| CSDN博客 | [termius链接树莓派显示乱码](https://blog.csdn.net/KeeYNgveKOn/article/details/127720639) |
| CSDN博客 | [Termius CLI项目常见问题解决方案](https://blog.csdn.net/gitblog_00990/article/details/143561854) |

---

> 页面内容由人工智能模型生成，请仔细甄别准确性
