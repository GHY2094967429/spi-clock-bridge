# 集成与比赛演示

## 可复用核心

`clock_bridge_core` 不依赖板卡管脚、Clock Wizard、VIO 或 UART IP。将 `spi_reg_master.v`、`hmc7044_init.v`、`clock_bridge_core.v` 加入工程，或将 `packaged_ip` 加入 Vivado IP Repository。

| 接口 | 使用约定 |
| --- | --- |
| clk / rst_n | 同一时钟域，同步低有效复位；不跨时钟域传递事务 |
| req_valid / req_ready | 两者同时为 1 的上升沿接受一个请求，等待期间保持 valid 和负载不变 |
| req_write / req_addr / req_wdata | 1=写、0=读，13 位地址、8 位数据 |
| rsp_valid / rsp_rdata | 单周期完成脉冲；每个已受理事务仅对应一次完成。写操作 rdata 不作为回读结果 |
| vio_valid / vio_ready / vio_addr | 第二个只读请求入口，优先级低于用户入口；不用时绑 0 |
| vio_rsp_valid / vio_rdata | 独立 VIO 读取响应 |
| cfg_done / verify_done / verify_error | 分别表示初始化写完、校验结束和发现不一致 |
| fail_addr / fail_expected / fail_actual | 第一个上电校验错误，复位前保留 |
| busy | SPI 物理事务及片选间隔期间为 1；不包括初始化序列的空隙 |
| sdio_out / sdio_oe / sdio_in | 连接外部 IOBUF；T 接 ~sdio_oe，勿直接将 oe 接到 T |
| spi_csn / spi_sclk | SPI 模式 0、24 位、高位先发 |

复位后初始化优先占用总线，直到 `verify_done`。未受理的用户请求必须保持；不得只脉冲 valid 一拍后丢弃。初始化校验失败也释放总线。所有响应是无反压单周期脉冲，消费者必须始终能够接收。核心没有命令 FIFO，UART 队列位于 `bridge_protocol` 中。核心用户入口已经被 UART 使用时，业务侧的额外主机需要独立仲裁，不能直接并线。

SPI_HALF_PERIOD 必须 >=1；SPI 频率 = clk / (2 × SPI_HALF_PERIOD)。SETTLE_CYCLES 必须 >=1，默认 5000；板级 5 MHz 时钟下为 1 ms。更改初始化表时，同时更新选定回读寄存器、期望值和掩码。此核心针对 HMC7044 协议及配置表，不能直接声称支持任意时钟芯片。

## 与业务逻辑并行部署

保留原业务逻辑接口，使用稳定且不受待配时钟芯片影响的时钟驱动桥接模块。若桥接时钟本身来自正在修改的 HMC7044 输出，调频/失锁可能中断桥接通信，必须由系统设计解决。当前板级 wrapper 使用原工程的 200 MHz 差分输入和 5 MHz 内部时钟，实际来源需要板卡原理图确认。

在线修改时钟芯片寄存器不需要重新生成 bit，但重新部署本次新增的 FPGA 逻辑需要先生成并下载新版 bit。时钟输出变化可能影响采集、JESD204 链路和业务复位/重同步，不能把在线可配置等同于业务运行无中断。

## VIO 和 LED

VIO probe_out1 为读取地址；probe_out0 从 0 置 1 发起读取，再回到 0 才能触发下一次。板级 wrapper 缓存 1 个待处理 VIO 请求；待处理或执行期间的额外触发沿被忽略。probe_in1 保持最近一次完整 8 位读数，probe_in0 为单周期完成脉冲。

- led[0]：心跳。
- led[1]：SPI busy。
- led[2]：自动校验失败或 VIO 待处理/执行中。
- led[3]：自动校验结束且通过。
- fmc_led：两级同步后的 hmc7044_gpio1 电平。

原始 0x0050=0x37 选择 GPO1 的 PLL1+PLL2 联合锁定。先确认 FPGA 的 hmc7044_gpio1 管脚确实连到该输出，再将此信号作为联合锁定证据。

## 建议演示顺序

1. 下载新版 bit，上电后查询 status，分别展示 FPGA 时钟 locked、初始化写完、回读校验和芯片锁定引脚。
2. 用 read 读取产品 ID 寄存器 0x78～0x7A，按实际芯片版本核实。
3. 用 verify 在 0x0008 暂存器写 0x5A、0xA5，展示回读一致；该暂存器不改变时钟输出。
4. 用串口助手发送错误 CRC，展示明确错误码与后续正常事务恢复。
5. 演示 VIO 与 UART 交替读取，确认读数不会串到另一个控制源。
6. 根据板卡参考时钟和芯片频率方案，选择实际可用的分频寄存器，测量在线修改前后的输出频率、锁定变化和业务重同步情况。步骤 6 需要示波器/频率计实测，现有数字仿真无法替代。

## 数据手册依据

[ADI HMC7044 Rev. E 数据手册](https://www.analog.com/media/en/technical-documentation/data-sheets/hmc7044.pdf)：Serial Control Port；表 32 的 0x0008 暂存器；表 33 的输入缓冲器控制有效位；表 56 的 GPO 功能选择。此工程保留原配置，不替代具体板卡的频率规划和电气验证。
