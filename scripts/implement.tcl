set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root spi_bridge_v2.xpr]
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} { error "Run scripts/build.tcl first" }
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} { error "Implementation failed" }
open_run impl_1
report_utilization -hierarchical -file [file join $root verification utilization_hier.rpt]
report_timing_summary -file [file join $root verification timing_routed.rpt]
report_bus_skew -file [file join $root verification bus_skew.rpt]
report_drc -file [file join $root verification drc.rpt]
file mkdir [file join $root release]
foreach extension {bit ltx} {
 file copy -force [file join $root spi_bridge_v2.runs impl_1 uart_spi_top.$extension] [file join $root release uart_spi_top.$extension]
}
close_design
close_project
puts "IMPLEMENTATION_BITSTREAM_OK"
