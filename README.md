# 可嵌入式 FPGA 时钟配置调试桥接 IP

UART → FPGA → SPI / SDIO，面向 HMC7044 的上电自动配置与在线寄存器调试。

本仓库是独立桥接发布工程，包含桥接 RTL、HMC7044 配置表、独立板级示例、数字仿真、Qt 上位机和构建脚本。**不包含 ADS6445 采集卡程序、ADC/LVDS 接收、DDR/PCIe 数据通路、整卡 Block Design 或整卡下载文件。** 桥接 IP 可与用户业务逻辑并行实例化，业务数据不经过桥接模块。

## 功能

- 自动下发 242 项启动配置，并对 5 个关键寄存器进行有效位掩码回读。
- 自动配置、UART 请求及 VIO 只读入口共享一个 SPI 主机，响应按事务来源返回。
- HMC7044 三线半双工访问：13 位地址、8 位数据、模式 0、高位先发，读阶段释放 SDIO。
- UART v2 帧头、序号、CRC-8、4 条等待队列、超时及错误状态；保留旧四字节命令。
- Qt 6 图形界面支持单次读写、写后回读、批量执行、状态及日志导出。
- 静态导入官方 GUI 的 `dut.write(...)` 配置文件，不执行其 Python 代码，保留写入顺序及重复地址。支持受限延时和显式选择的 Restart。

## 快速开始

工具：Vivado 2024.2；独立示例目标 `xcku060-ffva1156-2-i`。Python 3.10 或以上，测试使用 Python 3.13。Vivado 与器件库需要自行安装，不随仓库分发。

```text
vivado -mode batch -source scripts/create_project.tcl
vivado -mode batch -source scripts/simulate.tcl
vivado -mode batch -source scripts/build.tcl
vivado -mode batch -source scripts/implement.tcl
vivado -mode batch -source scripts/package_ip.tcl
```

`create_project.tcl` 在根目录生成 `spi_bridge_v2.xpr`。已有项目时直接打开，不重复创建。输出的工程缓存、厂商生成代码和 bit/ltx 留在本机，不进入 Git。下载前核对 [板级说明](docs/hardware.md) 的引脚、电压、参考源和配置表。

```text
python -m venv host/.venv
host/.venv/Scripts/python -m pip install -r host/requirements-gui-lock.txt
host/.venv/Scripts/python host/clock_bridge_gui.py
host/.venv/Scripts/python -m unittest discover -s host -v
```

Windows 可运行 `host/install_gui.cmd` 安装并启动，随后使用 `host/start_gui.cmd`。其他系统使用虚拟环境的 Python 启动同一脚本。免安装 GUI 可在本机用 `host/build_gui.ps1` 构建。

离线自检（不打开串口）：

```text
host/.venv/Scripts/python host/clock_bridge_gui.py --self-test verification/gui_smoke.json --self-test-config host/examples/7044out.py
```

## 核心接入

只复用核心时加入 `rtl/spi_reg_master.v`、`rtl/hmc7044_init.v`、`rtl/clock_bridge_core.v`，或运行 IP 打包脚本。板级示例的 UART、Clock Wizard、VIO 与 IOBUF 不属于核心依赖。请求与响应均在 `clk` 时钟域；保持 `req_valid` 和载荷直至 `req_ready` 接受。详细说明见 [接口与集成](docs/integration.md) 和 [主机协议](docs/protocol.md)。

核心时钟必须在待配置的时钟芯片启动前可用。改变时钟输出可能要求用户业务暂停、复位或重新同步；本仓库不提供任意频率无缝切换。

## 官方 GUI 对接

在 HMC704X 官方 GUI 导出 `.py` 配置，使用 Qt 批量页导入，检查预览后再连接串口下发。示例 `7044out.py` 有 238 条写入，用于检查解析和执行顺序，**不保证适合所有参考源、VCXO 和输出连接**。它与启动 ROM 的 242 项示例是不同配置，不能据条数判断二者等价。在线下发不修改 ROM，重新上电仍执行 RTL 中的启动表。

## 目录和复现材料

| 目录 | 内容 | 竞赛推荐目录的对应项 |
| --- | --- | --- |
| rtl | 桥接及独立顶层源码 | src |
| ip / constraints | 三个本地 IP 配置及板级约束 | board |
| scripts | 建工程、仿真、综合、实现、IP 打包 | build |
| sim / verification | 数字测试及发布验证摘要 | sim / data |
| host | Qt、CLI、协议、导入器及测试 | src |
| docs | 系统、接口、板级与复现说明 | report |
| skill | 可复用的接口和验证工作流 | skill |
| report | 设计报告及 AI 协作摘要 | report |

证据和版本边界见 [验证记录](verification/README.md)。软件模型和 RTL 仿真不证明真实芯片锁定、频率或抖动。当前 FPGA 发布源码包含已核对的 AXKU062 UART 3.3 V 约束；不分发此前使用不同电压约束的历史 bit。

原创桥接代码、工具及文档采用 [MIT 许可证](LICENSE)。第三方工具、厂商 IP 配置及运行库保留其自身许可证，见 [第三方说明](third_party.md)。
