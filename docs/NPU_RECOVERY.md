# NPU Troubleshooting & Recovery (AXERA/AXCL)

Status: draft — created 2025-11-09

This document summarizes the diagnostic steps, findings, in-repo mitigations, and recommended next steps for the AXERA/AXCL NPU (AX650) on this node.

## One-line summary
The AXERA NPU entered a kernel/firmware-level bad state (repeated heartbeat timeouts and PCI port create failures). Userspace kills and module reload/unbind attempts did not reliably recover it; a full reboot is the most reliable recovery.

---

## What we ran (diagnostics)
- `lsmod` to inspect loaded AX-related kernel modules (examples found: `axcl_host`, `ax_pcie_*`).
- `dmesg | tail -n N` to capture recent kernel log messages.
- `ls -la /dev/ax*` to verify device nodes (`/dev/axcl_host`, `/dev/ax_mmb_dev`).
- `timeout 6 axcl-smi` to capture `axcl-smi` output without blocking.
- Searched PCI devices and drivers under `/sys/bus/pci/devices` and `lspci -nnk` to find the AX device (example: `0001:01:00.0` bound to `ax_pcie_dev_host`).
- Attempted `modprobe -r`/`modprobe` on AX modules (failed when modules were in use).
- Attempted PCI unbind/rebind for the device `0001:01:00.0`.

Commands were run from the workspace shell; many require `sudo`.

## Key log excerpts (representative)
```
[E][device manager][request_ports][464]: request ports from device 1 fail, errno: 1 Operation not permitted
[...]
[heartbeat_recv_thread, 591]: device 1: dead!
[axcl_pcie_port_create, 872]: Recv port ack timeout.
[axcl_pcie_port_manage, 917]: axcl pcie port create failed.
axcl init fail, ret = 0x8030010b
open /dev/axcl_host fail, errno: 2 No such file or directory
```
`axcl-smi` output was often blank of card data or printed the error above and an empty Processes table.

## Observations / interpretation
- Kernel logs show repeated "device 1: dead" heartbeat messages and PCI port creation timeouts. That suggests the PCI endpoint or its firmware is unresponsive.
- User-space actions (killing processes, restarting `axcl-smi`, unbind/rebind, module reload attempts) did not reliably bring the device back to a healthy state.
- When `axcl-smi` reports no card info and dmesg repeats heartbeat timeouts, the driver has lost contact with the device and cannot recover it from userspace in our tests.

## Actions taken in this repository
To make recovery easier and reduce the chance of leaving user-space processes holding the NPU locked, the following low-risk changes were made:

- Added `scripts/cleanup_npu.sh` — a force cleanup script that:
  - kills `python src/app.py` and `main_axcl*` processes,
  - kills hung `axcl-smi`,
  - removes runtime files `logs/*.log` and `run/*.pid|sock`,
  - runs a short `axcl-smi` to verify device accessibility.

- Updated `Makefile` with a `make clean-npu` target that runs the above script.

- Hardened `src/model_manager.py` stop logic to:
  - attempt a graceful shutdown by sending `q\n` to the model's stdin,
  - if that times out, kill the model process group (SIGTERM then SIGKILL fallback), and
  - sleep briefly to allow kernel resources to be freed.

Files changed/added:
- `scripts/cleanup_npu.sh` (new)
- `Makefile` (added `clean-npu` target)
- `src/model_manager.py` (improved `stop()` logic)

> These changes reduce the chance of leaving user-space processes holding the NPU. They do not fix kernel/firmware-level faults.

## Recommended next steps (ordered)
1. Reboot the host (strongly recommended)
   - Reason: a clean kernel/PPCI bus/firmware initialization is the most reliable way to restore an NPU that has lost heartbeat.
   - Command: `sudo reboot`

2. After reboot, verify the device is healthy before starting the model:
   ```bash
   axcl-smi
   dmesg | grep -i axcl
   lsmod | egrep 'axcl|ax_pcie|ax_pcie_dev_host'
   ```
   Expectation: `axcl-smi` shows card(s) with memory/power usage and a non-empty Processes table. dmesg contains normal AX init messages instead of repeated "device dead"/port timeouts.

3. If you cannot reboot and want to try one more userspace reset (low chance of success):
   - Stop services and kill model processes:
     ```bash
     pkill -f "python src/app.py" || true
     sudo pkill -9 -f main_axcl || true
     sudo pkill -9 axcl-smi || true
     ```
   - Attempt PCI unbind/rebind (example device `0001:01:00.0` — verify yours):
     ```bash
     echo -n "0001:01:00.0" | sudo tee /sys/bus/pci/devices/0001:01:00.0/driver/unbind
     sleep 1
     echo -n "0001:01:00.0" | sudo tee /sys/bus/pci/drivers/ax_pcie_dev_host/bind
     ```
   - Check `dmesg` and `axcl-smi` again.
   - Note: this may fail if the device firmware is unresponsive.

4. If the device remains unresponsive after reboot:
   - Consider a hardware power/firmware cycle of the card (if supported by your hardware).
   - Collect full `dmesg` and `axcl-smi` outputs after the failure and open a support ticket with the NPU vendor (AXERA). Provide the full kernel logs and `axcl-smi` outputs.

## Quick recovery checklist (copy/paste)
```bash
# Attempt repo-level cleanup (uses sudo)
make clean-npu

# If still bad, reboot the host
sudo reboot

# After reboot, verify
axcl-smi
dmesg | grep -i axcl
```

## Caveats and risks
- Many recovery operations require `sudo` and may disrupt running services. Use with care.
- If the dmesg logs continue to show repeated heartbeat timeouts or PCI port failures, this is most likely a hardware/firmware fault that requires a reboot or vendor support.
- Avoid repeatedly starting the model while the NPU is in this state — it will only produce repeated kernel errors and make diagnosis noisier.

---

If you want, I can also add a short `README` snippet to `README.md` explaining `make clean-npu` and when to use it. Want that added too?