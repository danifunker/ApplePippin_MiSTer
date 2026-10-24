project_open BandaiPippin
create_timing_netlist -model slow
read_sdc
update_timing_netlist
set c [get_clocks {emu|pll|pll_inst|altera_pll_i|cyclonev_pll|counter[1].output_counter|divclk}]
report_timing -to_clock $c -setup -npaths 120 -detail path_only -file scratch/sta66_paths.txt
report_timing -to_clock $c -setup -npaths 3 -detail full_path -file scratch/sta66_detail.txt
project_close
