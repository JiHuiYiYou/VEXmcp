# VEXmcp

VEX V5 C++ API 与竞赛规则 MCP 服务器，专为 Claude Code 设计。

让 Claude Code 在帮你写 VEX 机器人代码时，能够**自动查询准确的 API 文档**和**2026-27 赛季 OVERRIDE 竞赛规则**，写出正确、合规的代码。

## 工作原理

```
你："帮我写一个电机控制程序"
Claude Code → 自动调用 MCP 工具
  ├── search_vex_api("电机控制")  → 找到 motor::spin, motor::setVelocity
  ├── search_vex_rules("电机限制") → 查到 R10 电机限制、R11 子系统限制
  ├── get_vex_api_detail("spin")  → 确认参数类型和顺序
  └── 输出正确合规的代码
```

## 快速开始

### 前提条件

- 已安装 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- 已安装 Python 3.8+
- 已安装 Git

### 1. 克隆项目

```bash
git clone https://github.com/JiHuiYiYou/VEXmcp.git
cd VEXmcp
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 验证安装

```bash
python test_server.py
```

看到 `[DONE]` 且所有测试通过即可。

### 4. 重启 Claude Code

在项目目录下 `claude mcp list` ，你会看到类似提示：

```
vex-api: python server.py - ✓ Connected

```
只要你当前所在的工程项目根目录下存在 .mcp.json文件，它就会在**启动时自动读取**这个文件，并在后台静默拉起并连接里面配置好的 MCP 服务器。

之后你就可以直接问 Claude Code 写 VEX 代码了。

## 在多个项目中使用

如果你想在**另一个 VEX 编程目录**中也使用此 MCP（不需要重新安装），复制以下文件并修改路径：

**步骤 1：复制文件**

```bash
# 从 VEXmcp 目录
cp .mcp.json 你的VEX工作目录/
cp CLAUDE.md 你的VEX工作目录/
```

**步骤 2：修改 `.mcp.json` 中的路径**

复制后的 `.mcp.json` 里 `server.py` 是相对路径，在别的目录找不到。需要改成 `server.py` 的**绝对路径**：

```json
{
  "mcpServers": {
    "vex-api": {
      "command": "python",
      "args": ["C:\\Users\\你的用户名\\...\\VEXmcp\\server.py"]
    }
  }
}
```

> **提示**：在 VEXmcp 目录下运行 `pwd` 获取完整路径，然后拼接 `/server.py`。

## 可用工具

### API 参考

| 工具 | 何时使用 | 示例 |
|------|---------|------|
| `search_vex_api` | 查找某个功能的 API | `"电机转速"`, `"controller button"` |
| `get_vex_api_detail` | 确认确切的参数类型和顺序 | `"spin"`, `"setVelocity"` |
| `list_vex_classes` | 了解有哪些可用类 | — |
| `list_vex_class_methods` | 浏览一个类的全部功能 | `"motor"`, `"controller"` |

### 竞赛规则

| 工具 | 何时使用 | 示例 |
|------|---------|------|
| `search_vex_rules` | 检查编程相关的规则限制 | `"电机限制"`, `"AWP条件"`, `"R10"` |

Claude Code 会根据工具描述中的触发条件**自动判断何时调用**，无需你手动指定。

## 数据

| 类别 | 来源 | 数量 |
|------|------|------|
| API 参考 | `api.vex.com/v5/` 66 个 C++ 文档页面 | 184 个 API，58 个类 |
| 竞赛规则 | VEX 官方 OVERRIDE 2026-27 手册 (0.1 版) | 中英文双版本 |

## 项目结构

```
VEXmcp/
├── server.py              # MCP 服务器主程序
├── CLAUDE.md              # Claude Code 项目指令（自动加载）
├── README.md              # 本文件
├── requirements.txt       # Python 依赖
├── vex_cpp_api_v2.json    # API 数据 (184 APIs)
├── test_server.py         # 安装验证脚本
├── crawl_vex_api.py       # API 爬虫（维护用）
├── fix_data.py            # 数据后处理（维护用）
├── searchindex.js         # Sphinx 索引（爬虫依赖）
├── objects.inv            # Sphinx 对象清单（爬虫依赖）
├── .mcp.json              # MCP 配置
└── 赛季规则/               # OVERRIDE 2026-27 规则手册
    ├── override-0.1-game-manual.md      # 英文原版
    └── V5RC 26-27 OVERRIDE-0.1 CN.md   # 中文翻译
```

## 维护

### 更新 API 数据

```bash
python crawl_vex_api.py       # 重新爬取全部 66 页
python fix_data.py            # 后处理拆分成员函数
python test_server.py         # 验证
```

### 更新竞赛规则

将新版规则 `.md` 文件放入 `赛季规则/` 目录，重命名为当前文件名（或修改 `server.py` 中的文件路径）。

## 常见问题

**Q: 启动 Claude Code 后 MCP 没有加载？**
A: 确认当前目录是 VEXmcp，且 `.mcp.json` 存在。运行 `python test_server.py` 检查 Python 环境和依赖。

**Q: 我的 Python 命令是 `python3` 不是 `python`？**
A: 编辑 `.mcp.json`，将 `"command": "python"` 改为 `"command": "python3"`。

**Q: 如何确认 MCP 正在工作？**
A: 在 Claude Code 中问："列出 VEX 的 motor 类有哪些方法"。如果 Claude 给出了准确的 API 列表，说明 MCP 正常工作。
