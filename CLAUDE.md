# CLAUDE.md — VEXmcp 项目指南

## 项目定位
这是 VEX V5 C++ 编程的 MCP 服务器项目，旨在帮助 Claude Code 在帮助用户编写 VEX 机器人代码时，能够准确引用 API 文档和竞赛规则。

## 核心原则

### 编写 VEX 代码时必须参考规则
当用户请求编写任何 VEX V5 竞赛相关代码时，**必须主动查询规则**，即使用户未明确提及。关键规则检查点：
- 电机数量/型号是否超限（R10/R11）
- 是否使用了 Competition Template（R9）
- 自动时段行为是否符合 SG7/SG8/GG12
- 气动系统是否符合 R25/R26
- 传感器使用是否合规
- 机器人尺寸/硬件配置是否符合 Robot Rules 章节

### API 准确性
- 函数签名、参数类型、参数顺序以 `get_vex_api_detail` 返回结果为准
- 不确定 API 是否存在时先用 `search_vex_api` 搜索
- 了解某个类的全部功能时用 `list_vex_class_methods`

### 数据文件
- 主力数据：`vex_cpp_api_v2.json` (184 APIs, 58 classes)
- 规则来源：`赛季规则/` 目录（中英文双版本）
- 不可随意修改数据文件，需通过脚本更新

## 开发命令
- 测试服务器：`python test_server.py`
- 更新 API 数据：`python crawl_vex_api.py && python fix_data.py`
- 运行 MCP 服务器：`python server.py`
