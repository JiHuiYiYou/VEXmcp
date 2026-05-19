# CLAUDE.md — VEXmcp 项目指南

## 项目定位
这是 VEX V5 C++ 编程的 MCP 服务器项目，旨在帮助 Claude Code 在帮助用户编写 VEX 机器人代码时，能够准确引用 API 文档、获取标准 C++ 模板、查阅赛局数据与竞赛规则。

## 核心原则

### 编写 VEX 代码时必须参考规则
当用户请求编写任何 VEX V5 竞赛相关代码时，**必须主动查询规则**，即使用户未明确提及。关键规则检查点：
- 电机数量/型号是否超限（R10/R11）
- 是否使用了 Competition Template（R9）
- 自动时段行为是否符合 SG7/SG8/GG12
- 气动系统是否符合 R25/R26
- 传感器使用是否合规
- 机器人尺寸/硬件配置是否符合 Robot Rules 章节

### 编写 VEX 代码时的工具调用链
1. **先获取赛局上下文**：调用 `get_vex_game_context()` 了解场地、时间、计分规则
2. **再获取代码模板**：调用 `get_vex_code_template(template_name)` 获取标准 C++ 骨架
3. **在模板基础上填充业务逻辑**，同时用 `search_vex_rules` 检查规则合规性
4. **API 调用以 `get_vex_api_detail` 为准**：函数签名、参数类型、参数顺序严格按返回结果
5. 不确定 API 是否存在时先用 `search_vex_api` 搜索
6. 了解某个类的全部功能时用 `list_vex_class_methods`

### VEXcode Pro V5 C++ 编码规范

**头文件与命名空间**
- 必须以 `#include "vex.h"` 开头
- 使用 `using namespace vex;`（省略 `vex::` 前缀）

**初始化**
- `vexcodeInit()` 必须在 `pre_auton()` 中调用
- 传感器校准在 `autonomous()` 首行，**不在** `pre_auton()` 中（避坑：赛前搬动机器人会致基准漂移）

**运动控制**
- 相对旋转：`motor.spinFor(forward, 500, degrees);`
- 持续旋转：`motor.spin(forward, 50, percent);`
- 停止必须指定制动模式：`motor.stop(brake);`
- **禁止**使用 `spinFor(inches)` 等不存在的 API

**制动模式**
- `brake`：急停，适合底盘
- `hold`：锁死位置，适合机械臂/升降机构
- `coast`：惯性滑行，适合滚轮/吸球器

**手动控制**
- Arcade Drive：Axis3（左摇杆 Y）+ Axis1（右摇杆 X），值域 [-100, 100]
- 按钮检测：`Controller1.ButtonL1.pressing()`
- 松手即停：`else { Motor.stop(hold); }`

**定时与等待**
- 使用 `wait(20, msec);` 或 `wait(1, seconds);`
- 禁止 `sleep()` 或 `delay()`

**其他**
- 不假设 `Drivetrain` 类，使用 `motor` 和 `motor_group`
- 竞赛生命周期：`Competition.autonomous()` + `Competition.drivercontrol()`

### 数据文件
- API 数据：`vex_cpp_api_v2.json` (184 APIs, 58 classes)
- C++ 模板：`templates/override_cpp.json` (6 个标准模板)
- 赛局数据：`config/game_rules.json`（结构化场地/计分/规则数据）
- 规则来源：`赛季规则/` 目录（中英文双版本）
- 不可随意修改数据文件，需通过脚本更新

## 开发命令
- 测试服务器：`python test_server.py`
- 更新 API 数据：`python crawl_vex_api.py`
- 运行 MCP 服务器：`python server.py`
