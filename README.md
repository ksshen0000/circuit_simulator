# 电路仿真器

React 电路编辑器 + FastAPI / NumPy 改进节点分析（MNA）求解器。支持 DC 工作点、AC 扫频、瞬态，以及可接线的非理想运算放大器。

## 导航

- [快速启动](#运行)
- [标准电路与数据格式](#标准电路与文件格式)
- [SPICE 文字设计](#用文字设计电路spice-子集)
- [Python 独立运行与 CLI](#python-独立后端与命令行)
- [HTTP API](#http-api)
- [运放模型](#运放)
- [配置与数据保存](#配置与数据保存)
- [常见问题](#常见问题)
- [开发验证](#验证)

## 运行

在项目根目录执行：

```sh
./dev.sh
```

一键脚本面向 Linux/macOS 等 POSIX 环境，Windows 建议通过 WSL 使用。后端要求 Python 3.10+；当前开发验证环境为 Python 3.12、Node.js 24。完整界面需要 uv、Node.js/npm，独立后端只需要 Python 和 uv。首次运行使用 `uv venv` 创建 `backend/.venv`，每次启动使用 `uv pip install` 检查和安装后端依赖；前端缺少依赖时自动执行 `npm ci`。不依赖系统的 `ensurepip` 或 `python3-venv` 包，首次下载依赖需要网络。前端地址为 http://localhost:5173，后端为 http://localhost:8000，交互式 API 文档为 http://localhost:8000/docs。按 **Ctrl+C** 同时关闭前后端及其子进程；任意服务退出时也会关闭另一个。端口被占用时会报错，不会结束其他程序。也可从任意目录通过脚本的绝对路径启动。

如需分别启动：

```sh
cd backend
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

另一个终端：

```sh
cd frontend
npm ci
npm run dev
```

## 标准电路与文件格式

运放是默认元件，工具栏点击「▷ 运算放大器」即可放置。也可在「标准电路」中选择同相放大器 ×10、反相放大器 ×10 或电压跟随器，然后点击「载入模板」。模板包含信号源、通用运放、负载、反馈连线和接地，载入后默认使用 DC 分析，输入为 0.1 V。可继续编辑并保存为自己的电路；当前画布非空时会先提示替换。

项目使用 JSON 表达电路：

- **画布数据**：`elements`、`wires`、`ground_element_id`，包含元件坐标、旋转、参数和导线折点；保存到后端 SQLite 数据库，加载时恢复可编辑画布。内置模板也生成同样的画布数据。
- **仿真网表**：`elements`、`ground_node`、`settings`，使用节点名称表达电气连接，不包含画布坐标。运放的 `node_a` 为同相输入，`node_b` 为反相输入，`node_out` 为输出。[示例 JSON](examples/opamp-noninverting.json) 属于这种格式，提交给 `/simulate` 使用。

画布/API 内部仍用这两种 JSON 结构。文字设计入口采用下面的 SPICE 子集，支持本地 `.cir` / `.sp` 文件；厂商 `.lib` / 任意 `.subckt` 模型暂不支持。

## 用文字设计电路（SPICE 子集）

工具栏点击「文本电路 / SPICE」，可以粘贴文本、打开文件、校验、应用到画布、直接仿真或下载 `.cir`。点击「从画布读取」可把画布上的电路转回文本。文本草稿关闭窗口后仍保留在当前页面内，刷新页面前请下载文件。

```spice
* Non-inverting amplifier, gain 10
V1 in 0 DC 0.1 AC 1
XU1 in feedback out CS_OPAMP A0=100k GBW=1meg
R1 out feedback 9k
R2 feedback 0 1k
RL out 0 10k
.op
.end
```

这采用公开的 [SPICE 网表语法](https://ngspice.sourceforge.io/docs.html)，不是完整的 ngspice/LTspice 实现。当前范围：

| 内容 | 支持格式 |
| --- | --- |
| 电阻、电容、电感 | `R/C/L名称 节点A 节点B 数值`，数值必须为正 |
| 电压源、电流源 | `V/I名称 节点A 节点B [DC 值] [AC 幅值 [相位]]`，也可直接写一个 DC 数值 |
| 运放 | `X名称 同相节点 反相节点 输出节点 CS_OPAMP [参数=值 …]` |
| DC 工作点 | `.op` |
| AC 扫频 | `.ac dec 每十倍频点数 起始频率 结束频率`，或 `.ac lin 总点数 起始频率 结束频率` |
| 瞬态 | `.tran 步长 结束时间 [0]`；目前只支持开始时间 0、梯形积分 |
| 注释、续行、标题 | `*` 整行注释，`;` / `$` 行尾注释，`+` 续行，`.title 名称` |

每个文件只支持一种分析，未写分析命令时默认 `.op`。请用 `* 标题` 或 `.title 标题` 开头；不解析裸标题行。支持的数值后缀为 `t/g/meg/k/m/u/n/p/f/mil`，按 SPICE 规则不区分大小写：**`M` 也是毫，兆必须写 `meg`**。支持科学记数法，`0` 和 `GND` 均视为接地，名称不区分大小写。未指定 AC 的文字电源默认 AC 幅值为零。

`CS_OPAMP` 是本项目提供的模型名称，子电路调用形式 `X...` 来自 SPICE，但该模型不是 SPICE 标准内置器件。其参数是 `A0/GBW/RIN/ROUT/VMIN/VMAX/SR/VOS`，对应属性面板的增益、带宽、输入/输出电阻、输出上下限、压摆率、失调。**导出到外部 SPICE 时需要另行提供对应 `.SUBCKT` 模型库**，当前导出文件不会包含该库。

`.param`、表达式、任意 `.subckt` / `.model`、`.include` / `.lib`、控制脚本和 `SIN/PULSE` 源目前会明确报错，不会忽略。包含不支持的波形或设置的画布也会拒绝导出，避免悄悄改变电路行为。当前求解引擎仍是项目自身的 NumPy 求解器。

SPICE 描述电气连接，不包含画布布局。应用文本时将替换画布并自动排布，以**同名节点标签**连接各端子，不自动拉线；这些标签保存后仍有效，移动/旋转元件不会断开命名连接。之后可继续用画布接线；物理导线连接的节点会合并。导出再导入会改变布局，保留原布局请使用原有保存功能。若要交换完整原理图布局，可以使用公开的 [KiCad `.kicad_sch` 格式](https://dev-docs.kicad.org/en/file-formats/sexpr-schematic/)，本项目尚未接入。

### Python 独立后端与命令行

解析、SPICE 导出和仿真核心全部由 Python 实现。前端只负责编辑和画布转换，文本校验需要后端在线。CLI 直接调用本地核心，无需浏览器、Node.js、HTTP 服务或数据库。

从项目根目录安装依赖：

```sh
uv venv backend/.venv
uv pip install --python backend/.venv/bin/python -r backend/requirements.txt
```

以下命令从后端目录执行；已有 `.venv` 时无需重新创建：

```sh
cd backend
.venv/bin/python -m app.cli ../examples/noninverting.cir
.venv/bin/python -m app.cli ../examples/rc-lowpass.cir --format csv -o /tmp/response.csv
.venv/bin/python -m app.cli ../examples/noninverting.cir --parse-only -o /tmp/request.json
.venv/bin/python -m app.cli /tmp/request.json
.venv/bin/python -m app.cli /tmp/request.json --export-spice
```

输入 `-` 从标准输入读取；错误写入 stderr 并返回非零退出码。回到项目根目录后，也可以用 `uv pip install --python backend/.venv/bin/python -e backend` 安装项目，获得 `backend/.venv/bin/circuit-sim` 命令。原有 Node 脚本保留为调用 Python 的兼容入口。

Python 代码可直接调用：

```python
from app.spice import parse_spice, export_spice
from app.simulation.engine import run_simulation

parsed = parse_spice(open("circuit.cir", encoding="utf-8").read())
result = run_simulation(parsed.request)
print(result.node_voltages)
```

### HTTP API

先启动后端服务；以下请求从项目根目录执行。接口详情、字段类型和响应结构可在 http://localhost:8000/docs 查看。

HTTP 接口：

- `POST /simulate`：原有 JSON 网表仿真。
- `POST /spice/parse`：请求 `{"text": "SPICE 内容"}`，返回 `title` 和 `request` 网表。
- `POST /simulate/spice`：同样接收 `text`，直接返回仿真结果。
- `POST /spice/export`：请求 `{"request": 网表对象, "title": "名称"}`，返回 `{"text": "SPICE 内容"}`。

直接提交 SPICE 文件（`text` 字段应为 JSON 字符串，不能把裸网表直接作为请求体）：

```sh
backend/.venv/bin/python -c 'import json,pathlib; print(json.dumps({"text": pathlib.Path("examples/noninverting.cir").read_text()}))' | \
  curl --fail-with-body -sS http://localhost:8000/simulate/spice \
    -H 'Content-Type: application/json' --data-binary @-
```

结果中 `x_values` 在 DC 模式为 `[0]`，在 AC 模式为频率（Hz），在瞬态模式为时间（s）。`node_voltages` 和 `branch_currents` 按节点/元件名给出等长数组；AC 还返回 `*_mag` 与 `*_phase`，相位单位为度，幅值为线性幅值而非 dB。CSV 的 AC 输出同时包含幅值和相位列。

语法、模型或电路求解错误返回 HTTP 400；请求结构校验失败返回 HTTP 422。CLI 对应错误写入 stderr，退出码非零。校验文本仅检查语法和参数；电路是否存在悬浮节点或收敛问题，要在仿真时判断。

示例：[运放放大器](examples/noninverting.cir)、[RC 低通扫频](examples/rc-lowpass.cir)。支持的 SPICE 子集范围与上表一致。

## 运放

工具栏选择「运算放大器」后放置。未旋转时左上是同相输入 `+`，左下是反相输入 `−`，右侧是输出；三个端子均可接导线。选中后在属性面板设置参数。电源通过相对于 GND 的输出上下限表示，不需要额外连接电源引脚。

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| 开环增益 | 100000 V/V | 有限 DC 增益 |
| 增益带宽积 | 1 MHz | 单主极点，极点频率 = GBW / 开环增益 |
| 差分输入电阻 | 1 GΩ | 跨接两个输入端 |
| 输出电阻 | 75 Ω | 内部驱动源与输出端串联，负载会引起压降 |
| 输出上下限 | −13.5 / +13.5 V | 内部驱动电压的饱和限值 |
| 压摆率 | 500000 V/s | 即 0.5 V/μs，限制内部驱动电压变化 |
| 输入失调 | 0 V | 加在差分输入上的偏置 |

DC 使用带阻尼的分段线性 Newton 求解处理饱和；AC 使用 `A(s) = A0 / (1 + s A0 / (2π GBW))`。AC 开始前检查 DC 工作点，饱和时返回错误，要求先调整偏置。源属性中的 AC 小信号幅值独立于 DC 值，允许明确设置为零；未指定时沿用源的值。

瞬态的 RLC 元件可选隐式 Euler 或梯形积分，运放主极点采用隐式 Euler，并叠加压摆率和饱和限制。第一个样本是开始时刻之前的工作点（因此阶跃源在 t=0 的初值为零），最后一个样本精确到达结束时间。步长应充分小于关注的最快变化时间；目前不支持自适应步长。

这是行为模型，尚未包含输出限流、输入共模范围、输入偏置电流、噪声、温漂、多极点或特定芯片宏模型，默认参数不代表某个真实型号。正反馈或多稳态电路可能无法收敛，会明确报错。

## 示例：10 倍同相放大器

[examples/opamp-noninverting.json](examples/opamp-noninverting.json) 是可直接提交的仿真请求：输入 0.1 V，反馈电阻 9 kΩ / 1 kΩ，输出约 1 V。

```sh
curl -s http://localhost:8000/simulate \
  -H 'Content-Type: application/json' \
  --data-binary @examples/opamp-noninverting.json
```

将 `settings` 改成以下内容可查看闭环带宽，示例电压源已设置 AC 幅值为 1 V：

```json
{"mode": "ac", "f_start": 10, "f_stop": 1000000, "points_per_decade": 20}
```

把电压源的 `source_waveform` 改成 `step`，并设置以下参数，可观察阶跃响应：

```json
{"mode": "transient", "t_stop": 0.0001, "t_step": 0.0000001, "method": "trapezoidal"}
```

## 求解约定与错误

- 电阻、电容、电感和独立源的电流正方向均为端子 A → B，与电流源箭头一致。当前方向已修正旧版电流源方向相反的问题，旧电路若依赖旧方向，需要交换引脚或改变源值符号。
- 运放电流是流入输出端的电流；向负载供电时通常为负，不包含电源或输入端电流。
- 所有接地符号共用 GND。悬浮节点、矛盾的理想源、非收敛电路返回错误，不再输出全零 AC 数据或不完整的瞬态曲线。
- R/L/C 必须为正，频率、时间范围、步长和运放参数经过校验。单次瞬态最多 200000 步。

## 配置与数据保存

| 配置 | 默认值 | 用途 |
| --- | --- | --- |
| `VITE_API_URL` | `http://localhost:8000` | 前端访问后端的地址；通过 Vite 环境变量设置，修改后重启开发服务或重新构建 |
| `DB_PATH` | `./circuit.db` | HTTP 服务保存画布的 SQLite 文件路径，相对于后端启动工作目录 |
| `CORS_ORIGINS` | `*` | 后端允许的跨域来源；多个来源用逗号分隔 |

`./dev.sh` 从 `backend` 目录启动后端，所以默认数据库是 `backend/circuit.db`。画布保存/加载需要后端在线；CLI 仿真不会访问数据库。SPICE 文本下载保存电气设计，画布保存功能还保留布局；文本导入后的自动排布不等于原图布局。

前端开发端口固定为 5173，一键脚本的后端端口为 8000。需要不同端口时，请分别启动服务并同步调整 `VITE_API_URL`。

## 项目结构

```text
backend/
  app/spice.py             SPICE 解析与导出
  app/cli.py               独立命令行入口
  app/models/              请求、网表与结果的数据模型
  app/simulation/engine.py 可直接调用的 Python 仿真入口
  app/simulation/         MNA、DC、AC、瞬态及运放求解
  app/routers/            HTTP API 与电路保存接口
  tests/                  解析、CLI 与数值回归测试
frontend/
  src/components/         画布、文本编辑器、属性和波形界面
  src/utils/spice.ts      Python API 客户端与画布转换
  tests/                  前端连接关系与 API 委托测试
examples/                 可运行的 SPICE / JSON 示例
scripts/dev.py            前后端进程启动与退出管理
scripts/spice.cjs         旧 Node CLI 的 Python 转发兼容入口
dev.sh                    一键启动入口
```

仓库还包含 Tauri/PyInstaller 桌面构建相关文件，主文档的启动与验证流程针对 Web 界面和 Python 后端。桌面打包另需 Rust 和平台系统依赖，不属于 `./dev.sh` 的启动步骤。

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 根目录 `npm run dev` 提示没有 `package.json` | 使用 `./dev.sh`，或 `npm --prefix frontend run dev` |
| `ensurepip is not available` | 使用 uv 创建和安装环境；当前一键脚本不依赖系统 `ensurepip` |
| `uv: command not found` | 安装 uv 并确认在 PATH 中，然后重新运行脚本 |
| 端口 8000 / 5173 被占用 | 关闭之前启动的服务，或分别启动并配置其他端口；脚本不会替你结束其他进程 |
| 文本编辑器提示无法连接 Python 后端 | 确认后端已启动，并检查 `VITE_API_URL` 与后端端口 |
| `Singular circuit` | 检查接地、悬浮节点、短接或互相矛盾的理想源 |
| 运放 AC 分析提示饱和 | 调整 DC 偏置或输出限值，让工作点处于线性区 |
| SPICE 中 `1M` 得到 0.001 | SPICE 的 M/m 都表示毫，兆应写 `1meg` |
| `SIN`、`.include` 或厂商模型被拒绝 | 当前文字入口只实现文档列出的子集；画布/JSON 源波形支持范围更大 |
| 关闭文本窗口后找不到文件 | 草稿仅保存在当前页面内，持久保存需下载 `.cir`；刷新前先下载 |

## 验证

以下命令从项目根目录开始：

```sh
cd backend
uv pip install --python .venv/bin/python pytest
.venv/bin/python -m pytest tests -q
cd ../frontend
npm run build
node tests/circuitTemplates.test.cjs
node tests/spice.test.cjs
```

测试覆盖解析/导出、Python CLI、API 处理、前端连接关系，以及解析解对照：闭环增益、输出负载、失调、正负饱和、带宽与相位、压摆率、RC/RL 阶跃和电流方向。构建通过不代表任意 SPICE 文件兼容，支持范围以本文的 SPICE 子集和模型说明为准。
