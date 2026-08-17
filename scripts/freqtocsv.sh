for i in {1..3000}; do
  ts=$(date +%s.%3N)
  freqs=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq | paste -sd,)
  echo "$ts,$freqs" >> cpu_freqs.csv
  sleep 0.1
done