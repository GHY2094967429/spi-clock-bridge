# Qt 时钟配置工具

Windows 首次运行 `install_gui.cmd`，之后运行 `start_gui.cmd`。也可创建虚拟环境，安装 `requirements-gui-lock.txt` 并运行 `clock_bridge_gui.py`。程序使用带 CRC 的 FPGA v2 协议；真实串口默认 115200 / 8N1。CLI 入口为 `clock_bridge.py`。

## 配置导入

HMC704X 官方 GUI 导出的 `.py` 可在批量页导入。解析器静态读取整数形式的 `dut.write(address, data)`，不执行脚本；保留顺序、重复地址、行号和注释。支持受限的 `time.sleep`，每次最多 60 秒、总计最多 300 秒；文件最多 1 MiB、4096 个操作。未知语句或超界数值导致整份拒收，旧预览保留。`address,data` CSV 的数值按十六进制解析。

导入只预览，不发送硬件命令。官方文件默认仅写入，逐条等待响应；普通写回复为完成回显，寄存器一致性需另行回读。可选 Restart 默认关闭，启用后读取 0x0001，仅操作 bit1 并保留其他模式位。失败停止，不自动重试写入或回滚已完成写入。

在线下发不会改变 FPGA 的上电 ROM。示例文件并非所有板卡通用；参考源、VCXO、输出标准和业务恢复流程由使用者核对。

## 状态与验证

真实串口模式不显示固定的上板验证横幅；离线模式保留软件模型说明。GPIO 是原始同步电平，含义需结合接线及 GPO 配置。超时不证明芯片未执行写入，程序不会据此宣称状态正确。

在仓库根目录执行：

```text
python -m unittest discover -s host -v
python host/clock_bridge_gui.py --self-test verification/gui_smoke.json --self-test-config host/examples/7044out.py
```

两者均不访问物理串口。构建 Windows 免安装程序前，在 `host/.venv` 安装依赖，再运行 `build_gui.ps1`。输出为 `dist_ui/ClockBridgeStudio`，分享时复制整个目录并保留 `licenses`，不能仅复制 exe。运行 `package_gui.py` 可打包免安装目录和源码。
