set root [file normalize [file join [file dirname [info script]] ..]]
create_project tb_bridge [file join $root verification sim_project] -part xcku060-ffva1156-2-i -force
add_files [list [file join $root rtl spi_reg_master.v] [file join $root rtl hmc7044_init.v] [file join $root rtl clock_bridge_core.v] [file join $root rtl bridge_protocol.v] [file join $root rtl uart_rx.v] [file join $root rtl uart_tx.v]]
add_files -fileset sim_1 [glob [file join $root sim *.v] [file join $root sim *.sv]]
set_property top tb_bridge [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
set_property xsim.simulate.log_all_signals false [get_filesets sim_1]
launch_simulation
close_sim
set log_path [file join $root verification sim_project tb_bridge.sim sim_1 behav xsim simulate.log]
set fp [open $log_path r]
set output [read $fp]
close $fp
if {[string first "PASS:" $output]<0 || [string first "Fatal:" $output]>=0} { error "Simulation assertions failed; see $log_path" }
close_project
puts "SIMULATION_FINISHED"
