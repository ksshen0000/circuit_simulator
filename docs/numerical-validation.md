# 复杂电路数值验证

本次验证使用 Python 3.12、NumPy 双精度和单线程 BLAS。所有新增示例、测试和基准脚本均保存在项目内。没有采用外部 SPICE 软件交叉验证；以下证据是解析解、守恒关系、时间步长细化和模型约束检查。

## 电路与判据

| 电路 | 检查内容 | 验证方式 |
| --- | --- | --- |
| 四级缓冲 RC 低通，四个运放 | 1 Hz～100 kHz 的幅值与相位 | 与四个 RC 传递函数及有限带宽跟随器传递函数的乘积比较；相对误差容限 1e-7，绝对容限 1e-12 |
| 运放跟随器，1 μF / 10 kΩ 并联负载 | 输出电阻和容性负载对反馈的影响 | 与 `A / (1 + A + Rout × (1/RL + jωCL))` 比较，使用极高输入电阻隔离输入负载影响，相对容限 1e-9 |
| 欠阻尼串联 RLC | 阶跃过冲、衰减和支路电流 | 与二阶系统解析解比较，步长从 2 μs 减到 1 μs 时最大误差至少减半；电感/电容电流一致到 1e-11 A |
| 三级 3 倍运放放大器，含容性负载 | 饱和、压摆率、正负过载恢复 | 1 kHz、2 V 正弦输入，持续三个周期；检查内部输出不超过 ±10 V、变化率不超过 0.2 V/μs，末周期仍能恢复到两种极性 |
| 80 段电阻串联网络 | 较大 MNA 系统的 DC 解 | 所有节点与均匀分压解析解比较，检查到小数点后 10 位 |

四级低通测试使用 `RIN=1e15 Ω`、`ROUT=1e-6 Ω` 来接近独立级联的解析假设；这两个参数是验证条件，不是某个实际芯片的规格。默认输出电阻的影响由独立的容性负载测试覆盖。

## 修复与优化

- 窄对数扫频（例如 100～101 Hz）此前可能只有起点；现在不同起止频率至少生成两个样本，精确保留两端，并通过向上取整保证采样密度。
- AC 总点数限制统一进入后端设置模型，JSON 和 SPICE 入口均受到限制，最大 200000 点。
- 线性电路和 AC 小信号分析直接进行一次线性求解，避免重复非线性迭代。
- 瞬态运放沿用上一时刻的解作为初值。每个候选解根据实际分段饱和方程检查残差，而不是仅依赖局部线性化结果。
- 瞬态遇到求解错误时报告时间和步长；结束时间的浮点舍入不会造成零步长重复计算。

## 性能记录

`benchmarks/solver.py` 对 80 段电阻网络运行 241 点 AC 扫频，预热一次后计时五次。在同一环境、`OPENBLAS_NUM_THREADS=1` 下，中位耗时：

| 版本 | 中位时间 |
| --- | --- |
| 优化前 | 0.156092 s |
| 优化后 | 0.134537 s |

该案例耗时下降约 14%。这是本机单个基准的测量，不代表所有电路都具有相同提升；当前仍使用稠密矩阵，并未引入稀疏求解或矩阵分解缓存。

## 复现

在项目根目录运行基准：

```sh
OPENBLAS_NUM_THREADS=1 backend/.venv/bin/python benchmarks/solver.py
```

新增复杂电路测试只用标准库 unittest 和现有科学计算依赖：

```sh
cd backend
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m unittest discover -s tests -p test_complex_circuits.py -v
```

也可以通过原有 pytest 命令运行完整后端测试。此次完整测试结果为 **48 项通过**。

在 `backend` 目录用 CLI 查看示例结果：

```sh
.venv/bin/python -m app.cli ../examples/complex/four-stage-lowpass.cir --format csv
.venv/bin/python -m app.cli ../examples/complex/capacitive-follower.cir --format csv
.venv/bin/python -m app.cli ../examples/complex/rlc-step.json --format csv
.venv/bin/python -m app.cli ../examples/complex/cascaded-saturation.json --format csv
```

阶跃和正弦瞬态示例使用 JSON，因为目前 SPICE 文本入口尚不支持 SIN/PULSE。运放仍是单极点行为模型；这些测试不构成对真实芯片或任意高阶反馈电路的精度保证。
