set root [file normalize [file join [file dirname [info script]] ..]]
create_project ip_package_work [file join $root verification ip_package_work] -part xcku060-ffva1156-2-i -force
set_property target_language Verilog [current_project]
foreach name {spi_reg_master hmc7044_init clock_bridge_core} { add_files [file join $root rtl ${name}.v] }
set_property top clock_bridge_core [current_fileset]
update_compile_order -fileset sources_1
ipx::package_project -root_dir [file join $root packaged_ip] -vendor user.org -library clocking -taxonomy /UserIP -import_files -set_current true -force
set core [ipx::current_core]
set_property name clock_bridge_core $core
set_property display_name {HMC7044 Clock Configuration Bridge} $core
set_property description {Register request/response bridge with power-on initialization, masked readback verification, arbitration and three-wire SPI.} $core
set_property version 2.0 $core
set clk_interface [ipx::get_bus_interfaces clk -of_objects $core]
set freq [ipx::add_bus_parameter FREQ_HZ $clk_interface]
set_property value 5000000 $freq
set reset_parameter [ipx::add_bus_parameter ASSOCIATED_RESET $clk_interface]
set_property value rst_n $reset_parameter
ipx::create_xgui_files $core
ipx::update_checksums $core
ipx::check_integrity $core
ipx::save_core $core
close_project
puts "IP_PACKAGE_OK"
