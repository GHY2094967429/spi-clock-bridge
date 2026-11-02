# 第三方组件及发布范围

本仓库不分发 Vivado、AMD 器件库或厂商生成的加密/仿真/综合 IP 实现。`ip/*/*.xci` 仅为项目配置，须由合法安装的 Vivado 重新生成。HMC7044 是验证对象，相关商标属于权利人。

Qt / PySide6 / Shiboken6、pyserial、Python 和 PyInstaller 使用各自许可证，见 `host/third_party_notices.txt`。源码发布不改变依赖的许可条件；打包 GUI 时 `collect_runtime_licenses.py` 收集运行库声明，动态库保持独立文件。

`host/examples/7044out.py` 为用户提供的官方 GUI 配置导出数据，用来验证导入；不包含 GUI 安装包或厂商软件实现。启动寄存器表沿用独立桥接示例。仓库不包含采集卡业务程序、PCB 工程、整卡 bit 或厂家评估软件。
