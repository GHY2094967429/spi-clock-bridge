set root [file normalize [file join [file dirname [info script]] ..]]
open_project [file join $root spi_bridge_v2.xpr]
update_compile_order -fileset sources_1
set fp [open [file join $root verification local_files_report.txt] w]
foreach path [get_files -all] {
 set path [file normalize $path]
 puts $fp $path
 if {![file exists $path] || ![string match -nocase "${root}/*" $path]} { error "Missing or external project dependency: $path" }
}
close $fp
report_compile_order -of_objects [get_filesets sources_1] -used_in synthesis -file [file join $root verification compile_order.rpt]
reset_run synth_1
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} { error "Synthesis failed" }
open_run synth_1
report_utilization -file [file join $root verification utilization.rpt]
report_timing_summary -file [file join $root verification timing_synth.rpt]
close_design
close_project
puts "BUILD_SYNTHESIS_OK"
