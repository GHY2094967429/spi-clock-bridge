set root [file normalize [file join [file dirname [info script]] ..]]
if {[file exists [file join $root spi_bridge_v2.xpr]]} { error "Project exists; open spi_bridge_v2.xpr instead." }
create_project spi_bridge_v2 $root -part xcku060-ffva1156-2-i
set_property target_language Verilog [current_project]
add_files [glob [file join $root rtl *.v]]
add_files -fileset constrs_1 [file join $root constraints board.xdc]
set_property top uart_spi_top [current_fileset]
foreach name {clk_wiz_0 proc_sys_reset_0 vio_hmc} {
 read_ip [file join $root ip $name ${name}.xci]
}
set_property CONFIG.C_PROBE_IN1_WIDTH {8} [get_ips vio_hmc]
generate_target all [get_ips]
update_compile_order -fileset sources_1
close_project
puts "PROJECT_CREATED"
