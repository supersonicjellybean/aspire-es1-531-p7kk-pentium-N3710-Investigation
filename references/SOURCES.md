# This document is a catalogue of tools and references used in this project
## Note that each bullet corresponds to each hypothesis; should two or more tools and/or references be used for one hypothesis, it will be explicitly stated

1) [Database] CPU-Z Validator [https://valid.x86.fr/]:
 - Used to compare reported BCLK values against multiple devices containing the same processor
2) [Software] AntiX 26 [https://antixlinux.com/]
- Fast and lightweight Operating System
- Uses legacy init (initialization) systems (like sysvinit or runit) instead of systemd to manage services and the boot process. This reduces background resource usage and complexity, which helps cut overhead that may interfere with observations
3) [Documentation] Intel® 64 and IA-32 Architectures Software Developer’s Manual Volume 4: Model-Specific Registers [https://www.intel.com/content/dam/develop/external/us/en/documents/335592-sdm-vol-4.pdf]
 
 - Official Intel Documentation that details MSRs within different processor families
 - Used to identify the MSRs applicable to the Intel Pentium N3710 (Atom derivative on the Airmont microarchitecture), and to investigate their functions and potential relevance to issues observed
