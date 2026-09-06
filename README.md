## Introduction:
This paper documents a systematic, full-stack investigation to determine the root cause of severe CPU frequency throttling on an Intel Braswell system. The investigation progresses from high-level OS telemetry and Linux kernel-level data logging to microarchitectural Model-Specific Register (MSR) bitfield decoding, all the way to boardview software and motherboard schema analysis.

## System Info:
* Processor: Intel Pentium N3710
	* Base Frequency: 1.6GHz (1600MHz)
	* Burst Frequency: 2.56GHz (2560MHz)
* RAM: 1x4GB DDR3L @ 1600MHz
* Primary Storage Device: 1TB 5400RPM HDD
* GPU: Intel HD 405 (integrated graphics)

## Problem Statement:
The given device is an Acer Aspire ES1-531-P7KK, manufactured in 2016. Since 2017-2018, the system has hovered at 0.48GHz, regardless of battery state (AC/Battery Power). Using CPU-Z shows that the clock multiplier ratio is at 6x, which is absurdly low.

### Hypothesis 1:
CPU-Z showed a BCLK of 80MHz, which is quite abnormal, as most Intel chips from this era (and by extension, most modern chips) tend to have a BCLK (Base/Bus Clock) of 100MHz. While having an 80MHz BCLK rather than a 100MHz BCLK wouldn’t make the clock multiplier plummet, it is an inconsistency that should be addressed.

#### Investigation:
Using CPU-Z Validator to cross reference data from other users on the same
platform. The search query was literally “pentium n3710 cpu z validator”, and yieldedseveral results, namely, [reference A](https://valid.x86.fr/kgxyxn), [reference B](https://valid.x86.fr/ctxfls), and [reference C](https://valid.x86.fr/rx7r0n). I created a
similar CPU-Z Validator export from my device, which can be found [here](https://valid.x86.fr/arcgyt).

| Metric                   | Reference A    | Reference B    | Reference C    | My Device     |
| ------------------------ | -------------- | -------------- | -------------- | ------------- |
| CPU-Z Validator ID       | kgxyxn         | ctxfls         | rx7r0n         | arcgyt        |
| Reported Frequency       | 2558.95 MHz    | 2558.95 MHz    | 2558.95 MHz    | 479.8 MHz     |
| BCLK Frequency           | 79.97MHz       | 79.97MHz       | 79.97MHz       | 79.97MHz      |
| Current Clock Multiplier | 32x (maximum)  | 32x (maximum)  | 32x (maximum)  | 6x (minimum)  |
| VCore                    | 0.86V          | 0.98V          | 1.00V          | 0.45V         |
| Microcode Revision       | 0x411          | 0x411          | 0x411          | 0x408         |
| Temperature              | 57 °C / 135 °F | 73 °C / 163 °F | 85 °C / 185 °F | 57 °C / 135°F |
<div align="center">Table 1A: Relevant Data from CPU-Z Validator References A, B, C, and my own report</div>

There are immediate discrepancies visible, specifically, the clock multiplier is at the minimum allowed state (6x) and the microcode version is different from that observed on other reference machines. It’s unlikely that the microcode is the reason for the clock issues, because this behavior would be well documented had this bug shipped with the many devices that came with microcode 0x408. Another observation is that the VCore is at 0.45V, which is absurdly low. However, I believe this to be a symptom, rather than the root cause, because if the system was expecting higher voltages and was being under-supplied power, it’d face instability and kernel panics, which hasn’t been observed. It makes more sense to assume that the OS or the processor itself is enforcing a lower clock speed, and thus VCore lowers due to Dynamic Voltage and Frequency Scaling.

It is quite clear that the BCLK is, in fact, ~80MHz for CPU’s on this platform. As such, we can confirm that Hypothesis 1 fails to explain observed behaviour adequately.

### Hypothesis 2:
The throttling is not actually due to Windows mishandling the processor, but rather an ACPI/Firmware/EC bug, or a potential hardware defect, like a broken clock generator.

#### Investigation:
Despite Windows being configured to keep the processor’s minimum and maximum state at 100%, the processor remained hovering at ~0.48GHz. To eliminate the chance of OS mismanagement regarding power states, I will use antiX Linux to observe CPU frequency under both idle and stressed conditions under the default schedutil and performance governor. Should Linux also exhibit the same behavior under both governors, OS mismanagement can be ruled out as a possible cause, and would point to some form of throttling enforced by the firmware itself.

Since the known baseline from windows was 480MHz, the goal on antiX was to sample the system’s CPU frequency every 0.1 seconds, gathering a total of 3000 samples, and data was collected using a simple linux bash script with the following source code:​

```bash
for i in {1..3000}; do
ts=$(date +%s.%3N)
freqs=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq | paste
-sd,)
echo "$ts,$freqs" >> cpu_freqs.csv
sleep 0.1
done
```

For the following scenarios:
A.​ Idle (default governor)
B.​ Under load (stress-ng) (default governor)
C.​ Under load (stress-ng) (performance governor)

The datasets created were used to plot graphs corresponding to each scenario using matplotlib in a python program. While the program is too long for its source code to be pasted here, it will be available on the project [repo](https://github.com/supersonicjellybean/aspire-es1-531-p7kk-pentium-N3710-Investigation) on github. However, the graphs plotted from the datasets are as pasted below:

![[CPUFreq_Baseline_scatter_900DPI.png]]
<div align="center">Graph 2A: Frequency-Sample graph under Idle conditions</div>

![[CPUFreq_schedutil_Stress_scatter_900DPI.png]]
<div align="center">Graph 2B: Frequency-Sample graph under load (default governor)</div>

![[CPUFreq_Performance_Stress_scatter_900DPI.png]]
<div align="center">Graph 2C: Frequency-Sample graph under load (performance governor)</div>

In a perfect test, the logger would have taken exactly 5 minutes. However, in real-world use, it took an average of 553.32 seconds, or around 9 minutes and 13 seconds.

From the data observed, we can make a few observations:
1. The issue with CPU frequency was independent of Operating Systems.
2. The logging program was hardwired to take 3000 samples with an interval of 0.1seconds. However, due to experimental error, every execution had an average interval of 0.164242667s (Graph 2A), 0.194385s (Graph 2B), and 0.194692333s (Graph 2C). While these numbers seem to be a negligible delay, each delay pushed the timing by several seconds in each test case. Due to this, an unintended observation can be made. Since the logger ran for longer than the 5-minute stress test, graphs 2B and 2C show both the CPU frequency activity under load, and activity immediately after load. Reevaluating the same graphs, no activity over 480MHz is observed for the initial ~1250 samples. With the knowledge that the graph recorded both under stress and idle cases, we can conclude that the CPU Frequency goes over 480MHz only when the system is idle.
3. We can conclude that the fault lies not with the OS, but rather a firmware intervention to prevent going over the minimum allowed performance state when the CPU is at C0 (high performance state), much like thermal throttling.

### Hypothesis 3:
Since the processor only appears to throttle under C0 states (non-idle), it is possible that when the operating system selects a P-state (performance state) and hands the processor the V/F pair (defines a CPU’s clock speed and the voltage required to run it safely), the processor’s power management controller attempts to scale accordingly, but faces throttling in the form of BD_PROCHOT.

BD_PROCHOT is a hardware safety signal that forces a processor to ‘slow down’. It can be asserted by the EC in case of a failing/degraded component on the motherboard, such as Power ICs, battery controllers, etc.

#### Investigation:
PROCHOT# is an active-low electrical signal to the processor. Essentially, a pull up resistor keeps the PROCHOT# line at a stable voltage (1.8V or 3.3V depending on the system). PROCHOT and BD_PROCHOT are two different methods of triggering PROCHOT#, but have the same result when asserted, creating a low resistance path to ground, often using a MOSFET, reducing the voltage to 0V across the trace, setting the PROCHOT# signal to “ON”

When PROCHOT# is asserted, the processor throttles itself as a safety mechanism to prevent damage to the system, which can explain the low frequency observed.

A few searches showed that tools existed to ‘disable’ BD_PROCHOT entirely, as it was known to cause performance issues much like what I was seeing. Upon installing [ThrottleStop](https://www.techpowerup.com/download/techpowerup-throttlestop/), however, which is a utility well known for changing CPU throttling behavior, I saw that the “BD_PROCHOT” box was greyed out and unchecked.

![[Pasted image 20260906195257.png]]
<div align="center">Image 3A: ThrottleStop showing greyed out and unchecked “BD_PROCHOT” box</div>

As BD_PROCHOT is a physical safety mechanism, it cannot simply be turned ‘off’. Instead, clearing bit 0 of MSR 0x1FC acts as a logical mask inside the processor, forcing the hardware to ‘ignore’ the BD_PROCHOT signal regardless of the line's physical voltage. Indeed, this is what popular tools like ThrottleStop use to ‘disable’ BD_PROCHOT.

Since ThrottleStop greyed out the BD_PROCHOT box, I used another program designed to read, inspect, and modify almost all computer hardware settings, [RWEVerything](https://rweverything.com/).

![[Screenshot (2).png]]
<div align="center">Image 3B: RWEverything window showing results of querying MSR 0x1FC</div>

Querying MSR 0x1FC using RWEverything returned a 64-bit hexadecimal zero (0x0000000000000000) that was greyed out. It was unclear whether the register held an active zero value (PROCHOT# not asserted) or if the program was encountering an error trying to read the register address. After spending nearly a week cross-referencing RWEverything screenshots and forum threads without finding a single documented case on a Braswell chip, a forum reference pointed me to documentation I didn't know existed, the [Intel® 64 and IA-32 Architectures Software Developer Manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html). “Volume 4: Model-Specific Registers” details what registers were available on each processor family and their corresponding microarchitecture (here, the 06_4CH family, on the ‘Airmont’ microarchitecture). Indeed, 0x1FC was not listed in any of the corresponding tables. As such, there is not enough information to confirm or deny if BD_PROCHOT is active.

### Hypothesis 4:
Since there is not enough data to make a conclusion on Hypothesis 3, as reflected above, we must consider other possibilities. It is possible that the severe frequency throttling is being triggered by the CPU’s own safety mechanisms, like an active thermal safeguard or power constraint causing the drop in frequency. This can be verified by reading the processor’s MSRs, which are special registers that contain ‘toggles’ and ‘telemetry’ regarding the CPU state.

#### Investigation:
Using Intel’s SDM Volume 4, MSRs potentially relevant to throttling, performance states, power limits, performance telemetry, and power consumption were shortlisted.

<div align="center">
  <table>
    <thead>
      <tr>
        <th align="left">Register Name</th>
        <th align="left">Register Address</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>IA32_PERF_STATUS</td><td>0x198</td></tr>
      <tr><td>IA32_PERF_CTL</td><td>0x199</td></tr>
      <tr><td>IA32_THERM_STATUS</td><td>0x19C</td></tr>
      <tr><td>MSR_PKG_POWER_LIMIT</td><td>0x610</td></tr>
      <tr><td>MSR_PLATFORM_INFO</td><td>0xCE</td></tr>
      <tr><td>MSR_FSB_FREQ</td><td>0xCD</td></tr>
    </tbody>
  </table>
</div>
<div align="center">Table 4A: List of shortlisted MSRs (sourced from Intel SDM Vol.4, “MSRs in Intel Atom® Processors Based on Airmont Microarchitecture”)</div>

![[Screenshot (3).png]]
<div align="center">Image 4A: RWEverything window showing MSR values
(Relevant values from Image 4A will be copied over to Table 4B for reference)</div>

| Register<br>Address | Observed Value<br>(CPU 1) | Observed Value<br>(CPU 2) | Observed Value<br>(CPU 3) | Observed Value<br>(CPU 4) |
| ------------------- | ------------------------- | ------------------------- | ------------------------- | ------------------------- |
| 0x198               | 00007C000000062D          | 00007C000000062D          | 00007C000000103B          | 00007C000000062D          |
| 0x199               | 00007C000000103B          | 00007C000000103B          | 00007C000000103B          | 00007C000000103B          |
| 0x19C               | 00000000882A03CF          | 00000000882503CF          | 00000000882E03CF          | 00000000882E03CF          |
| 0x610               | 001481E0003880A0          | 001481E0003880A0          | 001481E0003880A0          | 001481E0003880A0          |
| 0xCE                | 0000060002001400          | 0000060002001400          | 0000060002001400          | 0000060002001400          |
| 0XCD                | 0000000000000004          | 0000000000000004          | 0000000000000004          | 0000000000000004          |
<div align="center">Table 4B: MSR values captured via RWEverything reflecting hardware throttling triggers</div>

The values in table 4B are 64 bit hexadecimal integers, which are meaningless in their raw form. The Intel SDM Vol 4 provides the bitfields for extracting useful data from these MSRs. Using these bitfields, values from the MSRs can be interpreted as meaningful information as done in table 4C:


| Register Name                   | Value(s) (hex)                                           | Bit Field(s)                                                                                                                                                                       | Comment(s)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MSR_FSB_FREQ<br>(0xCD)          | 0000000000000004                                         | [3:0]                                                                                                                                                                              | Scalable Bus Frequency: 0100b Corresponds to 80MHz BCLK (SDM Vol. 4 Table 2-11) Validates Hypothesis 1 conclusion                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| MSR_PLATFORM_INFO<br>(0xCE)     | 0000060002001400                                         | [15:8]<br>[47:40]                                                                                                                                                                  | Maximum allowed non-turbo multiplier == 0x14 <br>                == 20<br>Maximum allowed non-turbo frequency == 20 * 80MHz<br>                == 1600MHz<br>Minimum allowed multiplier   == 0x06 <br>== 6                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| MSR_PKG_POWER_LIM<br>IT (0x610) | 001481E0003880A0                                         | [14:0]<br>[15]                                                                                                                                                                     | [14:0] == 0x00A0 == 160<br>PL1 = 160 x (scaling factor)<br>​<br>Scaling factor is 0.125W here, as is common for modern intel chips<br>PL1 = 20W<br>[15] == 1<br>Power Limit 1 is active                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| IA32_THERM_STATUS<br>(0x19C)    | 00000000882A03CF<br>00000000882503CF<br>00000000882E03CF | [0]<br><br><br><br>[2]<br><br><br>[4]<br><br><br><br>[5]<br><br><br><br>[6]<br><br><br><br>[10]<br><br><br>[22:16]<br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>[31] | [0] == 1<br>Currently Throttling (PROCHOT#)<br><br>[2] == 1<br>PROCHOT# actively asserted<br><br>[4] == 0<br>CPU has not passed T<sub>junction</sub>, 90°C<br><br>[5] == 0<br>CPU has not passed T<sub>junction</sub> since boot<br><br>[6] == 1<br>Current temperature is over threshold<br><br>[10] == 0<br>Power is not being capped<br><br>[22:16] Core1 == 0x2A <br>                     == 42<br>Core 1 is 42°C away from <br>T<sub>junction</sub><br><br>[22:16] Core2 == 0x25 <br>                        == 37 <br>Core 2 is 37°C away from <br>T<sub>junction</sub><br><br>[22:16] Core3&4 == 0x2E<br>                            == 46 <br>Core 3 & 4 are 46°C away from T<sub>junction</sub><br><br>[31] == 1<br>All readings are valid |
| IA32_PERF_CTL<br>(0x199)        | 00007C000000103B                                         | [15:8]                                                                                                                                                                             | [15:8] == 0x10 <br>          == 16<br>Target Multiplier is 16x                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| IA32_PERF_STATUS<br>(0x198)     | 00007C000000062D<br>00007C000000103B                     | [15:8]                                                                                                                                                                             | [15:8] Core 1 & 2 & 4 == 0x06                                    == 6<br>Core 1, Core 2, and Core 4’s Multiplier value is 6x (480MHz)<br><br>[15:8] Core 3 == 0x10 <br>                       == 16<br>Core 3’s Multiplier value is 16x<br>(1600MHz)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
<div align="center">Table 4C: Parsing of relevant MSR bitfields from MSRs table 4B</div>

From the above information, the following conclusions can be made:
1. 80MHz is, indeed, the BCLK for this processor. This had been validated by cross-referencing values with other users who had the same processor in Hypothesis 1, but MSR 0xCD bits 3:0 help confirm this with empirical data from Intel’s official documentation.
2. MSR_PLATFORM_INFO returned 0x0000060002001400. Bits [15:8] explicitly define the Maximum Non-Turbo Ratio (0x14 = 20x). While bits [63:16] are categorized as reserved for the Airmont microarchitecture, byte 5 [47:40] contains 0x06, which directly mirrors the 6x minimum multiplier. This is interesting as the Goldmont microarchitecture (successor to Airmont) definesbits [47:40] as the LFM multiplier (low frequency mode), the highest performance per watt ratio. It’s noteworthy that the bits that hold the multiplier values for the highest performance per watt on the next generation of processors coincides with the multiplier my processor is enforcing while holding a very low VCore value and throttling, **though this doesn’t prove anything for certain.**
3. The CPU has an active PL1 (sustained power limit) of 20W, which is plenty for a chip with a 6W TDP. Insufficient power due to corrupted NVRAM variables is not suspect.
4. MSR 0x19C is a minefield of information. The system was undergoing throttling at the instance of reading, with PROCHOT# (or FORCEPR#) being actively pulled. FORCEPR# assertion is an illogical assumption, since we have already ascertained that the processor is drawing extremely low voltage (and therefore low power) as seen in Table 1A. However, according to bits 4 and 5, the system had not crossed T<sub>junction</sub> (maximum allowed temperature on the processor die), and yet the processor was also over Thermal Threshold 1, despite the highest core temperature being 53°C (Core 2), which was completely normal, and at a 37°C gap from T<sub>junction</sub>. **This contradiction between what the hardware is reporting and what the firmware believes points at a hardware defect.**
5. The OS was requesting a P-State with 16x multiplier, however, as seen in 0x198 [15:8], Cores 1, 2, and 4 were at 480MHz, but Core 3 was able to boost to 1600MHz. This proves nothing beyond what was already proved in Hypothesis 2: The processor seems to be able to clock above 480MHz, but only momentarily, and only while idle.

In **spirit and in mechanism, Hypothesis 3 was correct.** Something is triggering PROCHOT# externally, since it’s unlikely to be the CPU itself (internal PROCHOT#) as all core temps are well below Thermal Junction. Either a bug in the EC is erroneously triggering BD_PROCHOT and asserting PROCHOT#, or a degraded physical component is unintentionally triggering BD_PROCHOT, and thus asserting PROCHOT#.

### Hypothesis 5:
Taking into account the contradicting values obtained from the MSRs in Hypothesis 4, it is possible that the CPU throttling is caused by physical hardware damage or component degradation on the motherboard, rather than an actual system-level thermal or power trip.

#### Investigation:
It is worth noting that BD_PROCHOT can be asserted for more than just overheating components on the board, as mentioned in the statement for Hypothesis 3. The common causes for a BD_PROCHOT assertion are:
1. Faulty/Non-Genuine Adapters: Not the case here, as a new Acer charger is being used to power this laptop.
2. Exceeding Power Limits: The Intel Pentium N3710 has a TDP of 6W, and as seen from 0x610 bits [14:0] and [15], the power limit is 20W and is being enforced.
3. Overheating Components: Disproved by 0x19C bits [4],[5], [22:16], and [31], yet being supported by bits [0],[2],[6], and [31].
Reason 3 directly contradicts itself, with PROCHOT# being asserted, the temperature being over the thermal threshold, yet the processor’s die temperatures staying relatively cool and at a large delta from T<sub>junction</sub>, as established in the conclusion of Hypothesis 4. To progress from here, I must map the physical route of PROCHOT# using a schematic of the motherboard (Wistron Domino BA14285-1) and trace the process on it physically, visually inspecting the board for defects.

Because board schematics and CAD layouts (and by extension, boardview files) for original design manufacturer platforms are proprietary and rarely publicly available, sourcing the exact schematics and layout files for the Wistron Domino BA14285-1 required almost an entire day of relentless searching.

![[SchemaAnnotated.png]]
<div align="center">Image 5A: Annotated Schematic page of processor I/O, detailing components relevant to PROCHOT#. R1860 and R1809 are the primary points of failure, since the absence/malfunction of R1809 (0Ω bridge for AD50 pin, which is the pin for PROCHOT#_CPU) or R1860 (20kΩ pull up resistor keeping PROCHOT# at 1.8V, failure to do so would drop the voltage to 0V and set PROCHOT# to “ON”) could easily result in a false positive PROCHOT# assertion.</div>

![[Collated 1.png]]<div align="center">Image 5B: Collated view of motherboard. These pictures were used to orient myself in OpenBoardView and locate R1860 after pinpointing its location in the boardview file.</div>
 
 Using a free tool named [OpenBoardView](), a PDF viewer, and old photos of the motherboard, I oriented myself in the boardview by searching up component names printed on the silkscreen, before looking for R1860 and R1809 in the boardview file. A screen capture of me doing the same is available [here](https://youtu.be/d524AaAN8lI) on YouTube.

![[View.png]]
<div align="center">Image 5C: Location of R1860 (Left: Boardview Macro, Right: Full Boardview)</div>

Zooming in on the ‘front’ portion of Image 5B, we can locate R1860 and R1809 on the physical board:

![[IMG_1322.png]]
<div align="center">Image 5D: Zoomed in photo of R1809 and R1860 (first and second resistor in the line of resistors below screw mount) and surrounding area.</div>

The image is rather grainy, but it is clear enough for a preliminary statement: severe corrosion is visible in the area immediately surrounding the screw mount, and R1860 seems to have taken severe damage.

![[Untitled.png]]
<div align="center">Image 5E: Left: Macro shot of R1809, R1860 and surrounding area Middle: Closeup of R1809, R1860 and surrounding area in boardview Right: Elevated view of R1809, R1860 and surrounding area.</div>
For the lack of a better term, both R1809 and R1860 have disintegrated. Crusty copper oxide surrounds the resistor, and blackened pads are visible. **This explains the erroneous assertion of PROCHOT#.**

The observations made in Hypothesis 2 might be attributed to improper contacts for each resistor. When the CPU is not in C0 power state, it occasionally boosts up due to the oxide having irregular conduction. When the CPU enters C0 and requests higher voltages, the oxide may heat up by marginal amounts and lose what little conductivity it had, forcing the net voltage to drop below the input logic-low threshold (V<sub>IL</sub>), and resulting in a ‘false positive’ PROCHOT# activation. However, this theory is an educated guess given the evidence obtained, and certainly not a confident statement explaining the clock speed ambiguity when in C0 and when not in C0.

### Summary and Next Steps:
This was an incredibly fun rabbit hole to get into. Along the way I picked up bash scripting, matplotlib, the fundamentals of processor safety features, MSR bitfield decoding, and how to read a motherboard schematic. The investigation moved from surface-level OS probing, to CPU register-level forensics, to a physical inspection of the board itself, systematically ruling out the BCLK, the OS, and the CPU's own thermal and power limits along the way, before converging on an externally-asserted BD_PROCHOT signal and, ultimately, two corroded resistors (R1809, R1860) on the PROCHOT# line.

More than the technical skills, I learned that persistence closes some gaps, but not all of them. Diagnosing this issue took nothing but a laptop, patience, documentation, and a month of spare time. However, fixing it is a different problem. R1809 and R1860 are 0402 package Surface Mount Devices (1.0mm × 0.5mm), and reworking them requires hot-air soldering skill and equipment I don't currently have. The diagnosis is complete, and the repair is the natural next step. I plan to have the board reflowed by someone experienced with SMD work.
