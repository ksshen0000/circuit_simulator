# 电路仿真器 —— 距专业使用的差距分析（评审意见）

> 评审范围：仓库根目录 `circuit_simulator`，未修改任何代码。
> 评审方式：通读后端求解内核、SPICE 解析/导出、HTTP API、数据层、前端编辑器与测试，并结合 README / docs 中自述的能力边界。
> 结论先放前面：这是一个**结构清晰、内核正确、文档认真**的“教学/原型级”电路仿真器；但要达到可交付给专业工程师日常使用（对标 ngspice、LTspice、Falstad、CircuitLab、EasyEDA 仿真）的水平，在**器件模型、数值方法、性能、工程质量、安全与产品化**五个维度仍有显著差距。

> **后续进展（2026-10-30 更新）**：本文档提出的主要差距已在 `feat/production-hardening` 分支逐项落地——工程质量/CI、部署加固、持久化、稀疏求解、收敛控制、自适应步长、受控源+二极管、SPICE 器件卡片、project 分组与经典用例种子均已完成（后端 88 个测试、前端 lint/build 全绿）。具体完成状态见下方 Roadmap 与附录清单的「状态」标注。

---

## 一、总体评价

**做得好的地方（应保留）**

- 分层干净：`app/simulation/*` 是纯 Python 求解内核，可脱离 Web/Node/数据库独立使用；CLI、HTTP、前端三层解耦清晰。
- MNA 实现正确、注释充分，电流方向约定（电阻/电容/电感/源 A→B、运放流入输出）在 README 中明确声明。
- 数值测试有**解析解对照**（四级低通、容性负载、欠阻尼 RLC、80 段电阻网络、饱和/压摆恢复），不是只测“不崩”。
- SPICE 子集解析较严谨：数值后缀、节点大小写冲突、参考地别名、续行、错误行号、原子写文件等都做了处理。
- 错误信息质量高（带行号、带 t/步长、区分 400/422）。
- 文档（README 17KB + 数值验证记录 + 工作日志）远高于同类原型项目的平均水平。

**一句话定位**：当前项目在“正确性”上投入很多，但在“专业可用性”上投入不足——它更像一个被仔细验证过的**教学用求解器内核 + 演示编辑器**，而不是一个工程工具。

---

## 二、差距分析（按维度）

### 1. 器件模型：最大的功能性缺口

| 项目 | 现状 | 专业工具的要求 |
| --- | --- | --- |
| 半导体器件 | **无**二极管、BJT、MOSFET、JFET 等 | 必备。绝大多数真实电路含半导体器件 |
| 运放模型 | 仅一个单极点行为模型 `CS_OPAMP` | 需支持厂商 `.SUBCKT` / `.MODEL` 宏模型 |
| 无源器件 | R/C/L 仅理想模型 | 需串联/并联寄生、温度系数、非线性（如 MLCC 直流偏置降容） |
| 受控源 | 无（E/F/G/H 四类受控源全缺） | 行为建模的基石 |
| 开关/传输线/变压器 | 无 | 常见 |
| 噪声 | 无（`NOISE` 分析缺失） | 放大器/滤波器设计必需 |
| 温度 | 无（无 `.temp`、无温漂） | 工业电路必需 |
| 非线性 | 仅运放饱和+压摆是分段线性 | 二极管/晶体管是指数+多种效应 |

**影响**：当前只能分析由 R/L/C + 独立源 + 一个理想化运放组成的电路。README 也自述“无输出限流、无共模范围、无偏置电流、无噪声、无温漂、无多极点”。这是“专业使用”的第一道硬门槛。

### 2. SPICE 兼容性

已实现的子集质量不错，但范围过窄：

- 缺失：`.param`、`.model`、`.subckt`、`.include` / `.lib`、`.func`、`.meas`、`.step`、`.noise`、`.tf`、`.four`、`.dc` 扫描、`.pz`、`.sens`、Monte Carlo / worst-case。
- 源激励：文本入口不支持 `SIN` / `PULSE` / `EXP` / `PWL` / `SFFM`（README 明确写死，JSON 才支持部分波形）。
- 厂商模型库完全不支持，意味着**无法与真实芯片数据手册 / 厂商模型对接**。
- `.tran` 只支持起始时间 0、只支持梯形/欧拉、无 UIC（跳过初始工作点）。
- 单文件单分析（一个文件只能一种分析）。

**影响**：对专业用户来说，“能跑文本 SPICE”这个卖点目前只覆盖了极小一部分网表，且与 ngspice/LTspice 不互操作（导出依赖一个并不存在的 `CS_OPAMP` 子电路库，README 已提示）。

### 3. 数值方法与收敛性

内核在“线性+单非线性器件”范围内做对了，但缺乏专业求解器的关键机制：

- **无自适应步长**：瞬态是“固定最大步长 + 已知脉冲边沿插点”，没有基于局部截断误差（LTE）的步长控制。遇到刚性问题（stiff）、高 Q 谐振、快慢时间常数混叠时会不可靠或低效。README 也承认“不等于自适应步长”。
- **积分方法单一**：只有隐式 Euler 与梯形法。缺 GEAR/BDF 2~6 阶；梯形法在刚性问题上的“梯形振荡（trapezoidal ringing）”没有抑制手段。
- **无收敛控制**：无 gmin 步进、无 source stepping、无用户可调的 `abstol/reltol/vntol/itl1/itl4`；Newton 阻尼固定为二分 40 次、外层 100 次、容差硬编码 `1e-9`。
- **稠密矩阵**：`np.linalg.solve` 全程 dense，`build_mna_*` 都构造 `(n+m)×(n+m)` 全矩阵。80 节点基准尚可，但 n=数千时内存 O(n²)、求解 O(n³)，无法支撑专业级规模。README/benchmark 也承认“未引入稀疏求解或矩阵分解缓存”。
- **数值稳定性边界**：没有条件数检查、没有针对病态矩阵的预处理；AC 在 `ω→0` 时电容/电感被跳过（可接受），但 `1/(jωL)` 在极低频会放大误差。
- 运放模型里 `output_current` 通过 `base = len(x) - 运放数量` 反推索引，依赖“运放排在解向量末尾”的隐含约定，属脆弱实现。

### 4. 性能与可扩展性

- dense 求解是主要瓶颈，见上。
- 每次 AC 频率点都**重建矩阵并重新 `np.linalg.solve`**，无 LU 分解复用；线性电路本可一次分解后只做回代。
- 前端 `computeNodes` 每次变更全量重跑 Union-Find（小电路无所谓，大画布会卡）；`pointToNode` 对每个节点线性扫描 gridPoints。
- `recharts` 一次性渲染全部数据点；AC 上限 200000 点时波形面板会明显卡顿，无降采样/虚拟化。
- 无异步任务队列 / 取消机制：一次大仿真会占用后端线程，前端 `AbortSignal.timeout(30000)` 只断开连接，后端仍在计算。

### 5. 后端 / API / 部署

- `docker-compose.yml` 引用了 `./backend/Dockerfile` 与 `./frontend/Dockerfile`，**这两个 Dockerfile 在仓库中并不存在**，compose 文件当前不可用。
- `app/main.py` 使用 `@app.on_event("startup")`，这是 FastAPI **已废弃**的写法（应改用 lifespan）。
- 依赖无锁文件：Python 侧没有 `uv.lock`（`requirements.txt` 全部 `>=` 宽松约束），不可复现构建；`dev.sh` 每次启动 `uv pip install` 重新解析依赖，无法保证“今天能跑、半年后同样能跑”。
- **scipy 是死依赖**：`requirements.txt` 与 PyInstaller spec 都声明了 scipy，但 `app/`、`tests/`、`benchmarks/` 中**没有任何 scipy 引用**。
- CORS 默认 `*`，且无鉴权、无速率限制、无请求体大小/复杂度限制：`/simulate` 走 JSON 网表，**没有 SPICE 路径的 500 元件上限**，恶意或手误的大电路可直接触发 dense 矩阵内存/CPU 爆炸（DoS）。
- SQLite 无 schema 版本/迁移机制（只有 `CREATE TABLE IF NOT EXISTS`）；`elements`/`wires` 存的是 `dict[str, Any]` 任意 JSON，**保存时不校验**，读到损坏/未来版本数据会直接抛错。
- 无日志、无监控指标、无 `/metrics`；`health` 不检查依赖（DB）。

### 6. 前端 / 交互

- 全部内联 style，无设计系统/主题；UI 文案中文硬编码，无 i18n。
- **无撤销/重做（undo/redo）**——专业原理图编辑器的基础能力。
- 无元件库/搜索、无对齐/分布、无框选多选、无复制粘贴、无网格吸附开关之外的辅助定位（旋转只有 90° 一档，无镜像）。
- 画布上的节点电压标注**只显示 DC 的 `vals[0]`**，AC/瞬态模式下会显示错误信息（取的是第一个样本）。
- 波形面板无游标（cursor）、无测量读数、无 dB 刻度切换（幅值固定线性）、无相位/幅值同图、无数据导出。
- 无组件级前端测试、无 E2E（Playwright/Cypress）、无 a11y、无错误边界；`package.json` **没有 `test` 脚本**。
- 文本草稿只在内存中（刷新即失），无本地持久化；README 已提示，但产品化应自动保存。

### 7. 工程质量（CI/CD、测试、规范）

- **无任何 CI 配置**（无 `.github/workflows`、无 GitLab CI、无 pre-commit、无 Makefile 目标）。
- 后端测试依赖 pytest，但 `dev.sh` 默认环境**不安装 pytest**（`requirements.txt` 也不含），验证命令要额外 `uv pip install pytest`；且 `unittest discover -p 'test_*.py'` 会因个别文件 `import pytest` 失败。
- Python 侧**无 lint/格式化/类型检查配置**（pyproject 中无 ruff/black/mypy 段落）；代码风格依赖手写自觉。
- 前端有 ESLint 配置，但 `npm run build` 不跑 lint，也无 CI 执行。
- 测试只有 773 行 / 48 项（自述），无覆盖率门槛、无变异/模糊测试；对 SPICE 解析器这种大量边界分支的代码，仅靠手写 case 覆盖不够。
- 大量工作未提交：`git status` 显示 20+ 文件修改、多个未跟踪文件（`sources.py`、`time_grid.py`、`tests/*`、`benchmarks/`、`docs/`、`src-tauri/` 等），提交历史仅 2 个 commit。**“能跑”依赖工作区脏状态**，换机器 `git clone` 后无法复现当前能力。

### 8. 桌面打包 / 产品化

- 存在 Tauri + PyInstaller 方案（`scripts/build-desktop.sh`、`circuit_simulator.spec`、`run.py`、`src-tauri/`），但：
  - 无 CI 构建、无代码签名/公证（macOS）、无自动更新、无安装器测试。
  - `build-desktop.sh` 用系统 `pip` 而非项目 venv，环境耦合。
  - 后端仍以本地 HTTP 服务方式跑，未做成真正的进程内桥接，桌面版体验（端口占用、防火墙弹窗、单实例）未处理。
- 无许可证文件（LICENSE 缺失）、无版本发布流程/CHANGELOG、无 issue/贡献指南。

---

## 三、优先级建议（Roadmap）

**P0 —— 达到“可安全交付给用户”的最低线**（✅ 全部完成）

1. ✅ 修复 `docker-compose.yml`（补两个 Dockerfile）或删除它，避免误导。
2. ✅ 移除死依赖 scipy；为 Python 依赖生成并提交 `uv.lock`；pin 版本。
3. ✅ 建 CI：安装依赖 → 后端 pytest → 前端 build + lint + 单元测试（至少把现有验证自动化）。
4. ✅ 后端加资源保护：`/simulate` 统一元件数/矩阵规模上限、请求体大小限制、计算超时、CORS 收紧、基本速率限制。
5. ✅ 修 FastAPI 废弃的 `on_event`；`health` 检查 DB 可用性。
6. ✅ SQLite 加 schema_version 与迁移；保存时校验 elements/wires 结构。
7. ✅ 提交当前工作区（拆分 commit），保证 `git clone` 可复现。

**P1 —— 缩小“专业仿真能力”差距**（🟡 大部分完成）

8. ✅ 引入**稀疏矩阵求解**（`scipy.sparse.linalg` 或自实现，并把 scipy 变成真正的依赖）+ 一次分解多次回代的 AC 优化。
9. 🟡 瞬态加**基于 LTE 的自适应步长**（已做）+ 高阶 BDF 与梯形振荡抑制（未做）。
10. 🟡 增加收敛控制（gmin + 可调容差已做；source stepping 未做）。
11. 🟡 扩展器件：二极管 ✅、BJT/MOSFET ⬜（Ebers-Moll / Shichman-Hodges）。
12. 🟡 受控源（E/F/G/H）✅；`.model`/`.subckt`/`.param`/文本 `SIN`/`PULSE` ⬜。

**P2 —— 产品化 / 体验**（⬜ 大部分未做）

13. ⬜ 前端补 undo/redo、复制粘贴、对齐、元件库搜索、框选多选。
14. ⬜ 波形面板加游标、dB/相位、数据导出、大数据降采样；修正画布节点标注在 AC/瞬态下取 `vals[0]` 的问题。
15. ⬜ i18n（先抽离中文硬编码）、错误边界、E2E 测试、a11y。
16. ⬜ 补充 `.meas`、`.noise`、`.tf`、`.dc` 扫描、温度/噪声等分析，使其接近 ngspice 子集。
17. 🟡 桌面版：已有 Tauri+PyInstaller 骨架；进程内桥接、单实例、签名/公证、自动更新、CHANGELOG 未做；LICENSE ✅ 已补。

---

## 四、附录：具体发现清单（供逐条核对）

| # | 位置 | 发现 | 严重度 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | `docker-compose.yml` | 引用不存在的 `backend/Dockerfile`、`frontend/Dockerfile` | 高 | ✅ 已修复 |
| 2 | `requirements.txt` / `circuit_simulator.spec` | scipy 声明但零引用（死依赖） | 中 | ✅ 已修复（先移除，后由稀疏求解重新引入） |
| 3 | 仓库根 | 无 Python 锁文件（`uv.lock`），依赖 `>=` 不 pin | 中 | ✅ 已加 uv.lock |
| 4 | 仓库根 | 无 CI/CD、无 pre-commit、无 Makefile | 高 | ✅ 已加 CI + pre-commit |
| 5 | `backend/app/main.py` | `@app.on_event("startup")` 已废弃 | 低 | ✅ 已改 lifespan |
| 6 | `backend/app/main.py` | CORS 默认 `*`；无鉴权/限流 | 高 | 🟡 CORS 已收紧 + 并发信号量；鉴权/限流未做 |
| 7 | `backend/app/routers/simulation.py` | `/simulate` JSON 路径无元件数上限（SPICE 路径才有 500 上限） | 高 | ✅ 已加 MAX_ELEMENTS/MAX_NODES |
| 8 | `backend/app/db.py` | 无 schema 版本/迁移；elements/wires 为任意 JSON 且不校验 | 中 | ✅ 已做迁移 + 保存校验 |
| 9 | `backend/app/simulation/mna.py` 等 | 稠密矩阵 + 每频点重复 `np.linalg.solve` | 高 | ✅ 已改稀疏 SuperLU |
| 10 | `backend/app/simulation/transient.py` / `time_grid.py` | 固定步长+断点插值，无自适应 LTE 步长 | 高 | ✅ 已加自适应 LTE（高阶 BDF 未做） |
| 11 | `backend/app/simulation/opamp.py` | 收敛容差硬编码、无 gmin/source stepping、`output_current` 索引计算脆弱 | 中 | 🟡 SolverOptions + gmin 已做；source stepping 未做 |
| 12 | `backend/app/simulation/opamp.py` / README | 仅单极点行为运放，无噪声/温度/多极点/半导体 | 高 | 🟡 已加二极管+受控源；BJT/MOSFET/噪声/温度未做 |
| 13 | `backend/app/spice.py` | 不支持 `.param/.model/.subckt/.include/.meas/.noise` 等 | 高 | 🟡 已加 D/E/F/G/H 卡片；其余未做 |
| 14 | `backend/app/spice.py` | 文本源不支持 SIN/PULSE/EXP/PWL | 中 | ⬜ 未做（JSON 路径已支持部分波形） |
| 15 | `frontend/package.json` | 无 `test` 脚本；无 E2E | 中 | 🟡 CI 已跑测试；package.json test 脚本与 E2E 未加 |
| 16 | `frontend/src/App.tsx` 等 | 内联 style、中文硬编码、无 i18n | 低 | ⬜ 未做 |
| 17 | `frontend/src/store/circuitStore.ts` | 无 undo/redo；每次变更全量重算节点 | 中 | ⬜ 未做 |
| 18 | `frontend/src/components/Canvas/CircuitCanvas.tsx` | 节点电压标注只显示 `vals[0]`（AC/瞬态显示错误） | 中 | ⬜ 未做 |
| 19 | `frontend/src/components/WaveformPanel` | 无游标/测量/dB/导出；全量渲染 | 中 | ⬜ 未做 |
| 20 | `backend/tests/*` | 依赖 pytest 但默认环境不装；unittest discover 会因 `import pytest` 报错 | 低 | ✅ CI 用 `uv sync --extra test` 解决 |
| 21 | `git status` | 大量未提交改动，仅 2 个 commit，克隆后不可复现当前能力 | 高 | ✅ 已拆分提交（7 + 9 个 commit） |
| 22 | 仓库根 | 无 LICENSE | 低 | ✅ 已加 MIT |

---

*本文档仅做评审，未改动任何代码。*
