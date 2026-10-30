# 电路仿真器 —— 主要差距技术方案设计

> 本文档是《专业使用差距分析》的配套技术方案，针对每个主要差距给出**可落地的设计**（架构、接口、算法、文件组织、验收标准、风险）。只做设计，不改代码。
> 方案按上一份文档的 P0/P1/P2 优先级组织。每条方案标注**目标工作量量级**（S < 1 天，M 数天，L 数周，XL 数月），供排期参考。

---

## 0. 总原则

1. **内核保持纯 Python 可独立运行**：所有新能力（稀疏求解、器件模型、自适应步长）必须继续通过 `run_simulation()` 暴露，CLI/HTTP/前端零改动即可受益。
2. **渐进替换，不推倒重来**：现有 MNA + `build_mna_*` 的接口是稳定边界，新求解器以“新模块 + 适配层”方式接入，旧的 `dc_analysis/ac_analysis/transient` 保留为回退路径，测试作为回归护栏。
3. **可观测性优先于炫技**：每个新特性都要带解析解/交叉验证测试，延续项目“有据可查”的风格。
4. **依赖最小化**：优先复用 scipy（把死依赖变成真依赖）、标准库；引入 C 扩展前先测收益。

---

## 1. 稀疏矩阵求解器（P1，M）

**现状**：`mna.py` 全 dense，`np.linalg.solve` 每次重建矩阵并全分解；80 节点 241 点 AC 约 0.13s，但 n=5000 时内存 ~400MB、求解不可用。

### 1.1 方案：COO 装配 + SuperLU 分解 + 缓存复用

```
后端矩阵层（新）
backend/app/simulation/matrix.py
  - SparseBuilder：元素装配期间累积 (row, col, val) 三元组
  - finalize() -> scipy.sparse.csc_matrix
  - LinearSolver：持有 splu 分解对象，提供 solve(rhs) / solve_matrix(RHS)
  - solve_linear(A, b) -> x（带条件数检查与错误映射）
```

**关键点**：

- **装配**：`_stamp_conductance` 改为往 `SparseBuilder` 里 `add(i, j, g)`。MNA 结构不变，只是存储变稀疏。
- **求解**：`scipy.sparse.linalg.splu(A)`（内部 SuperLU + COLAMD 重排）返回可复用对象 `lu.solve(b)`。
- **复用策略**（决定性能上限）：
  - DC：分解一次，Newton 每步 RHS 变化只回代（但运放 Jacobian 每步变，见 §3 处理）。
  - AC：矩阵含 `jωC`、`1/(jωL)`，**每个频点都不同** → 无法复用分解。优化点改为：对每个频点用 `splu` 直接分解（稀疏仍然远快于 dense）；或对线性 R-only 电路缓存结构一次。**不要**为 AC 做因子复用（收益小、复杂度高）。
  - 瞬态（固定 h）：companion 电导 `C/h`、`L/h` 恒定 → **矩阵数值恒定**，只 RHS 变。分解一次，整个瞬态只回代。这是瞬态性能的最大杠杆。自适应步长（§2）时 h 变，按“h 是否改变”决定是否重新分解，并缓存“最近一次分解的 (h, order) 键”。
- **条件数与错误映射**：`splu` 前用 `estimate_cond`（可选，开销大时可关）或捕获 `RuntimeError`（矩阵奇异），映射到现有 `ValueError("Singular circuit ...")`。
- **规模上限**：在 `run_simulation` 入口加“非地节点数上限”（如默认 5000，环境变量可调），超出报错而不是 OOM。

### 1.2 验收标准

- 80 节点基准：稀疏版 AC 中位耗时低于 dense 版（复用现有 `benchmarks/solver.py` 并新增 5000 节点 case）。
- 5000 节点电阻网络 DC 可解（内存 < 500MB）。
- 全部 48 项现有测试通过（结果与 dense 一致到 1e-9 相对误差）。

### 1.3 风险

- SuperLU 对复对称（AC 矩阵不是 Hermitian）可用，但需注意 `splu` 对 complex 支持（SciPy ≥ 1.7 支持）。降级：`spsolve`。
- 运放分段线性的 Jacobian 每步变（§3 会重构），分解缓存命中率低是预期，不要过度优化。

---

## 2. 自适应步长 + 高阶积分（P1，L）

**现状**：`transient.py` 固定 `t_step` + `time_grid.py` 插入已知断点；只有欧拉/梯形；梯形在刚性电路会“梯形振荡”。

### 2.1 方案：变步长 BDF1–BDF5 控制器（Gear 法）

```
backend/app/simulation/transient_gear.py（新，替换 transient.py 的主循环）
backend/app/simulation/lte.py          （误差估计）
backend/app/simulation/breakpoints.py  （断点集合，取代/增强 time_grid.py）
```

**算法骨架**（与 SPICE 一致）：

1. 用户仍给 `t_step` 作为**初始/最大步长**，但内部 `h` 可变。
2. 维护解的历史缓存 `[x_{n-k}...x_n]`。用 BDF-k 的**变步长系数**（分步比 `ratio` 计算系数）求 `x_{n+1}`。
3. **LTE 估计**：对 BDF-k，用“k+1 阶外推”与“k 阶解”之差近似局部截断误差 `ε`。
4. **接受/拒绝**：
   - `ε ≤ reltol·|x| + abstol` → 接受，`h_{next} = h · min(2, 0.9·(tol/ε)^{1/(k+1)})`。
   - 否则拒绝，`h = h · max(0.1, 0.9·(tol/ε)^{1/(k+1)})`，重算（不推进时间）。
5. **断点处理**：在源不连续处（step/pulse 边沿）强制落点；越过断点后**重置历史、k=1（隐式欧拉）重启**（等价于现有 `jumps` 逻辑，但改由 `breakpoints.py` 提供）。
6. **梯形振荡抑制**：默认 `method="trapezoidal"` 保持兼容；检测到相邻两步解“正负交替”时，临时降为 BDF1 或改用 BDF3（即 Gear 的 `METHOD=GEAR` 思路）。新增 `method="gear"` 作为推荐默认。
7. **初始条件**：沿用现有“`t_start` 之前的工作点”语义；BDF 启动从 k=1 逐渐升阶。

**误差控制参数**（新增到 `TransientSettings`）：`reltol`（默认 1e-3）、`abstol`（默认 1e-9）、`max_order`（默认 5）、`itl4`（每步 Newton 上限）。

### 2.2 与稀疏求解器的结合

- 每个试步：组装 companion 电导（依赖当前 h）→ 若 h 与缓存不同则重新 `splu` 分解 → Newton 回代（§3）。
- 电荷守恒：电容/电感用**梯形/向后欧拉的电荷形式**（`i = C·dv/dt` 直接对电荷积分），与现有 state 更新一致，避免“数值电荷泄漏”。

### 2.3 验收标准

- 现有欠阻尼 RLC 步长细化测试改造为：`reltol` 收紧一半 → 误差至少减半（自适应收敛性）。
- 高 Q / 快慢时间常数混叠电路（新 benchmark）在自适应下比固定步长“更快达到同等精度”。
- 现有全部瞬态测试（含 pulse 捕获窄脉冲）通过。

### 2.4 风险

- 变步长 BDF 系数推导易错 → 用解析解 + 与固定小步长 dense 结果交叉验证。
- 输出时间轴不再等距（已有心理预期，README 需更新）；如需等距可后处理插值。

---

## 3. 收敛控制与非线性框架（P1，M）

**现状**：`opamp.py` 里硬编码 Newton（外层 100、阻尼二分 40、容差 `1e-9`）；无 gmin/source stepping；非线性只有运放。

### 3.1 方案：通用 Newton + 同伦连续

```
backend/app/simulation/nonlinear.py（新）
  - NewtonSolver（可配 itl1/itl4/reltol/abstol/vntol）
  - 阻尼：线性回溯 + 残差范数判据（保留现有“按分段方程验残差”的正确做法）
  - gmin_stepping / source_stepping 作为“收敛失败后的自动重试”阶段
```

- **容差参数化**：把 `1e-9` 等替换为 settings 可选项；`vntol` 与 `reltol` 语义对齐 SPICE。
- **gmin stepping**：收敛失败时，给每个节点对地并接极小电导 `gmin`（默认 1e-12），从 `gmin_scale=1e-6` 逐步逼近 `1`，作为最后手段。
- **source stepping**：把所有独立源乘 `λ`，从 `λ=0.01` 逐步 `→1`，用上一解作初值，专治正反馈/多稳态启动。
- **迭代诊断**：返回 `convergence: {iterations, method, gmin_scale, source_scale}`，供前端提示与调试（响应模型加可选字段）。
- **接口统一**：`opamp.py` 的 `solve()` 重构成 `nonlinear.solve(A, z, devices, ...)`，运放只是 `devices` 的一种“非线性器件接口”（`stamp_linear` / `jacobian_rhs(x)` / `update_state`）。这是 §4 器件框架的起点。

### 3.2 验收标准

- 现有饱和/压摆/正反馈报错测试保持通过。
- 新增“难收敛”用例（如高增益正反馈、两个运放互锁）在 source stepping 下可解或给出更可读的失败信息。

---

## 4. 器件模型框架与半导体器件（P1/P2，XL）

这是“从教学到工程”的质变项，工作量最大，建议**分阶段**。

### 4.1 阶段一：器件抽象 + 受控源 + 二极管（L）

```
backend/app/simulation/devices/
  base.py       Device 抽象：terminals, stamp_dc, stamp_ac, stamp_transient(companion), post_process(电流)
  linear.py     R/C/L/独立源/受控源 E,F,G,H（迁移现有逻辑）
  diode.py      二极管：Shockley + Rs + 结电容
```

- **抽象接口**（统一线性与非线性）：
  ```python
  class Device(Protocol):
      def stamp(self, sys: MNAContext, x, *, omega=None, h=None, state=None) -> None: ...
      def branch_current(self, x, sys) -> float: ...
  ```
  `MNAContext` 提供稀疏装配、节点索引、RHS/雅可比访问。这样 §1 稀疏求解与 §3 Newton 对所有器件通用。
- **二极管模型**：
  - DC/瞬态：`I = Is·(exp(V/(N·Vt)) - 1)`，Jacobian 易求；加串联电阻 `Rs` 与结电容 `Cj = Cj0/(1-V/Vj)^m`。
  - 瞬态：结电容用电荷 `Qj` 形式（保证电荷守恒），二极管作为“电流源 + 电荷”进入 companion。
- **受控源**：VCVS/CCCS/VCCS/CCVS，扩展 MNA 的附加列（CCCS/CCVS 需要感测支路，复用现有电压源列机制）。

### 4.2 阶段二：BJT + MOSFET Level 1（L）

- **BJT（Gummel-Poon 简化 / Ebers-Moll）**：`Ic = Is·(exp(Vbe/(Nf·Vt)) - exp(Vbc/(Nr·Vt)))`，基区电荷 `Qb`，结电容 Cje/Cjc。电流用“三个端子的电流源 + 两个结电容”。
- **MOSFET Level 1（Shichman-Hodges）**：阈值 `Vth`、线性/饱和区连续，栅电容 Cox 与交叠电容。瞬态用**电荷模型**（Meyer 或更简单的分段电荷）避免电荷不守恒导致的错误。
- 全部参数走 `.model` 卡片（§5），前端属性面板新增对应模型选择器。

### 4.3 阶段三：厂商宏模型 / BSIM（XXL，可延后）

- 支持 `.subckt` 后，用户可直接挂厂商运放宏模型（用二极管/BJT/MOSFET 搭建），优先打通这一路径，而非自研 BSIM。
- BSIM3/4、VBIC、HiSIM 等工业模型建议**直接集成开源引擎**（如 Xyce/ngspice 的模型库）而非自研——这是战略选择，见 §12。

### 4.4 验收标准

- 二极管：与 `Is·(exp(V/(NVt))-1)` 解析解对照；整流/限幅电路瞬态波形合理。
- BJT/MOSFET：与 SPICE 参考值（手算或 ngspice 输出）对比关键工作点。
- 受控源：四种受控源的传递关系解析对照。

---

## 5. SPICE 解析器扩展（P1/P2，L）

**现状**：`spice.py` 是“逐行 + 少量正则”，只支持一个小子集，对 `.param/.model/.subckt/.include` 直接报错。

### 5.1 方案：分层解析器 + 表达式引擎 + 网表展开

```
backend/app/spice/
  tokenizer.py    （保留现有数值/节点/续行/注释逻辑，作为 token 层）
  parser.py       （语法树：卡片 -> 元件/模型/子电路/分析/测量）
  expr.py         （安全表达式求值：四则、函数、{expr}、.param 引用）
  expander.py     （.subckt 展开：实例参数替换、节点作用域映射）
  models.py       （.model 卡片 -> 器件模型对象，接入 §4）
```

- **递归下降解析**：卡片级文法（`<letter><name> <nodes> <value | model-name> [params]`），比现在逐行 `split()` 更结构化，保留**错误行号**。
- **表达式引擎**：递归下降 + 白名单函数（`sqrt/exp/log/sin/pow/min/max/abs`），**禁止 `eval`**；支持 `{expr}` 内联与 `.param name=expr`、参数引用 `{R}`。
- **`.subckt` 展开**：解析到子电路定义 → 实例化时做“节点前缀重命名 + 参数覆盖”，展平成顶层网表（不追求层级求解，先展平，简单且与现有 MNA 兼容）。`.include`/`.lib` 做文本级文件拼接（解析相对路径 + `SPICE_LIB_DIR` 搜索），`仅拾取被引用的 .subckt` 以控制规模。
- **多分析**：允许一个文件多个分析卡片，但求解仍一次一个；新增 `.dc`（源扫描）、`.noise`、`.tf`、`.meas` 作为结果后处理。
- **源波形**：文本入口补 `SIN/PULSE/EXP/PWL/SFFM`，映射到现有 `NetlistElement` 波形字段（`sources.py` 已支持 sine/pulse/step，需补 exp/pwl）。
- **导出**：`export_spice` 支持输出 `.subckt`（当有可识别子电路结构时）与 `.model` 卡片。

### 5.2 验收标准

- 现有全部 SPICE 解析/导出/往返语义测试通过。
- 新增：`.param` 表达式、`.subckt` 两级嵌套实例、`.include` 相对路径、SIN/PULSE 文本 → 与 JSON 等价路径结果一致。
- 模糊/边界：非法表达式、循环 `.include`、子电路名冲突都要明确报错（不静默）。

---

## 6. 后端 / API / 部署（P0，S–M）

### 6.1 Docker 修复

- `backend/Dockerfile`：`python:3.12-slim` + 安装 `uv` + `uv sync --frozen`（引入锁文件后）→ `uvicorn app.main:app`。
- `frontend/Dockerfile`：多阶段 `node:24` build → `nginx:alpine` 托管静态产物，并反向代理 `/simulate` 等到后端（解决浏览器 CORS/端口一致问题）。
- `docker-compose.yml`：两个服务 + volume 持久化 `circuit.db`；前端 `VITE_API_URL` 在 build 期改为 `/api` 相对路径（生产正确形态）。

### 6.2 FastAPI 现代化 + 资源保护

- 用 lifespan 替代 `@app.on_event`。
- 统一 `/simulate` 与 `/simulate/spice` 的**资源限制**（`pydantic` 校验 + 运行时检查）：
  - 元件数 ≤ 500（JSON 与 SPICE 一致，或统一提升到一个可配置值并配合稀疏求解）。
  - 非地节点数 ≤ 5000（防止 dense/稀疏超限）。
  - 请求体 ≤ 1MB（已有）、瞬态/AC 点数 ≤ 200000（已有）。
- **计算超时与并发**：`run_in_threadpool` 已隔离阻塞；再加“单进程最大并发仿真数”信号量（如 2），超出的排队或立即 429；超时用线程无法强杀，改在求解器内部检查“预算步数/时间”并抛错（协作式取消）。
- **鉴权/限流**：本地单机默认无需登录，但加：
  - 可选 `API_TOKEN`（`X-API-Token` 头校验）用于暴露公网。
  - slowapi 或自实现 token bucket 限流（按 IP + 端点）。
  - CORS 默认收紧为 `http://localhost:5173`，`*` 仅当显式设 `CORS_ORIGINS=*`。
- **可观测性**：结构化日志（`logging` + JSON formatter）、`/health` 检查 DB 读写、`prometheus-fastapi-instrumentator` 暴露 `/metrics`。

### 6.3 验收标准

- `docker compose up` 一键可用（前端/后端/DB 持久化）。
- 恶意大网表返回 400/429 而不是拖垮服务。
- 现有 HTTP 测试（`test_http_simulation.py`）通过。

---

## 7. 数据持久化（P0，S）

**现状**：`db.py` 无版本/迁移，`elements/wires` 为 `dict[str, Any]` 不校验。

### 7.1 方案

- **schema_version**：`PRAGMA user_version` 存版本；`init_db` 里跑迁移列表（`migrations = [(1, ddl1), (2, ddl2), ...]`）。
- **保存校验**：`SaveCircuitRequest.elements/wires` 从 `dict[str, Any]` 改为 Pydantic 模型（对应前端 `CircuitElement`/`Wire` 结构），非法数据 422。
- **软删除/版本历史（可选 P2）**：增加 `deleted_at` 列或另存 `circuit_versions` 表，支持“撤销保存”。
- **并发写**：SQLite `WAL` 模式 + `busy_timeout`，降低多请求写锁冲突。

### 7.2 验收标准

- 旧库文件能通过迁移自动升级；损坏/未来版本数据返回清晰错误。
- 保存非法 elements/wires 返回 422。

---

## 8. 前端（P2，M–L）

### 8.1 撤销/重做（M）

- 用 zustand 中间件 **zundo**（或自实现 command 栈）对 `circuitStore` 的关键 mutation（add/move/rotate/delete/wire/load）做快照历史。
- 快照应存**不可变引用**（当前 store 已经用 `{...s.elements}` 生成新对象，天然适配），避免深拷贝大对象；`nodes` 可不在历史中（可由 elements/wires 重算）。
- 快捷键 Ctrl+Z / Ctrl+Shift+Z；历史深度上限（如 100）。

### 8.2 波形面板专业化（M）

- **游标/测量**：自绘 overlay（或换 ECharts，其内置 dataZoom + 游标更成熟），支持两条游标读 Δx/Δy。
- **AC 显示**：Y 轴可选 `线性 / dB`，相位单独切换（`node_voltages_phase` 已就绪，前端未用）。
- **大数据降采样**：>10000 点用 **LTTB**（largest-triangle-three-buckets）抽稀，hover 时局部放大原始数据。
- **导出**：`导出 CSV`（后端 `cli.write_csv` 已有同款逻辑，前端直接复用结果）。
- **修正节点标注**：`CircuitCanvas.tsx` 里 `vals[0]` 改为按 mode 取（DC 取第 0 点；AC 取某频点的 mag+phase；瞬态取游标时刻或末点）。

### 8.3 编辑器能力补齐（M）

- 复制/粘贴（含内部剪贴板）、框选多选、对齐/等距分布、元件库搜索、旋转/镜像（R 已有，加 flip）。
- 元件与导线吸附：已有 grid 吸附，补“端点/中点”磁吸。

### 8.4 工程化（S–M）

- **i18n**：`react-i18next`，抽出所有中文硬编码到 `locales/zh-CN.json`（先只做资源文件，不急着多语言）。
- **错误边界**：顶层 `ErrorBoundary`，求解/画布异常不白屏。
- **测试**：Vitest + Testing Library 补组件测试；Playwright 补 3 条 E2E（放置元件→仿真→看到波形；SPICE 粘贴→校验→画布；保存→刷新→加载）。
- `package.json` 增加 `test`、`test:e2e` 脚本。

---

## 9. 工程质量（P0，S–M）

### 9.1 CI

`.github/workflows/ci.yml`：
1. **backend**：`uv sync --frozen`（含 test extra）→ `ruff check` → `mypy app` → `pytest -q`。
2. **frontend**：`npm ci` → `npm run lint` → `npm run build` → `npm test`。
3. **smoke**：`./dev.sh` 后台起服务 → curl `/health`、`/simulate` 用 example → 关闭。

### 9.2 依赖与规范

- 提交 `uv.lock`（`uv lock` 生成），`dev.sh` 改为 `uv sync`（一次解析，可复现）；`requirements.txt` 由 lock 导出或保留为宽松声明。
- pyproject 增加 `[tool.ruff]`、`[tool.mypy]`、`[tool.pytest.ini_options]`。
- `.pre-commit-config.yaml`：ruff、mypy、eslint、prettier。
- **提交 hygiene**：把当前 20+ 未提交改动按主题拆成 commit（如 “feat: sources 波形模型”“feat: 时间网格断点”“test: 复杂电路回归”），打 tag，写 CHANGELOG。
- 补 `LICENSE`（建议 MIT 或 Apache-2.0）。

---

## 10. 桌面打包 / 产品化（P2，L）

### 10.1 架构改进

- 现状：Tauri 前端 + 独立后端 sidecar（PyInstaller），后端监听固定 8000 端口。问题：端口冲突、防火墙弹窗、多实例、生命周期。
- **方案 A（短期，推荐）**：后端 sidecar 改绑 `127.0.0.1:0`（随机端口）或 Unix domain socket；Rust 端负责拉起、读到实际端口、注入前端 `VITE_API_URL`；`single-instance` 插件防多开；应用退出时 kill sidecar。
- **方案 B（中期）**：用 PyO3 把 `run_simulation` 编成 Rust 可直接调用的 native 扩展，彻底去掉 HTTP sidecar。工作量大，仅在需要离线/性能极致时做。

### 10.2 发布

- CI matrix（Linux/macOS/Windows）构建 Tauri + PyInstaller。
- macOS 签名+公证、Windows 代码签名、Linux AppImage/deb。
- `tauri-plugin-updater` 自动更新。
- 版本号统一（后端 pyproject、前端 package.json、tauri.conf.json 同源）。

---

## 11. 分析与测量扩展（P2，L）

在器件与解析器就绪后补分析类型，复用同一求解内核：

| 分析 | 方案要点 |
| --- | --- |
| `.dc` 扫描 | 对独立源值做参数扫描，循环调用 DC 求解，输出曲线 |
| `.tf` 传递函数 | 在 DC 工作点做小信号线性化，求指定输出/输入之比 |
| `.noise` | 工作点线性化 + 各器件噪声源（热噪声/散粒/闪烁）等效输入 |
| `.meas` | 结果后处理 DSL：`find/max/min/avg/integ/param`，作用于波形 |
| Monte Carlo / `.step` | 参数分布采样 + 批量仿真（配合后端并发信号量） |

---

## 12. 战略建议：何时“自研” vs “集成”

**强烈建议**：半导体器件、先进模型（BSIM）、超大规模电路是**重投入且边际收益递减**的领域。两条路：

- **A（推荐）**：保持“自有 MNA 内核 + 教学级模型”，但把“专业仿真”定位为**对接 ngspice/Xyce**——即本项目负责原理图、SPICE 编辑、结果可视化，求解可切换到外部引擎。这样用极低成本获得专业精度。
- **B**：坚持自研求解器，则必须接受“多年投入才能逼近 ngspice”，且先做 §1–§5 的稀疏/BDF/二极管/受控源，形成差异化后再评估。

---

## 13. 落地顺序建议（汇总）

```
第 1 批（P0，可立即做，约 1–2 周）
  §6 部署/资源保护  →  §7 持久化  →  §9 工程质量/CI  →  提交工作区

第 2 批（P1，约 1–2 月）
  §1 稀疏求解  →  §3 收敛控制  →  §2 自适应步长  →  §4.1 二极管/受控源

第 3 批（P2，约 1–3 月）
  §5 SPICE 解析扩展  →  §4.2 BJT/MOSFET  →  §8 前端  →  §11 分析扩展

第 4 批（视战略）
  §10 桌面打包  →  §4.3 宏模型/BSIM（或 §12 的集成路线）
```

---

*本文档只做设计，未改动任何代码。每条方案均可拆分为独立可验收的 issue/任务。*
