# Minitab 进程观察

2026-10-31 一次 COM 执行前，系统已有 Minitab PID 34528。DispatchEx("Mtb.Application") 返回的本轮 PID 为 25980，AppPath 和进程映像均指向 D:\Program\Minitab 19\Mtb.exe。本轮 worker 退出后 PID 25980 已结束，但 PID 34528 也已不在进程列表，保护检查因此记为 preexisting_pids_preserved=False。

本脚本只通过 PID 25980 对应的 DispatchEx 对象执行命令，没有连接 PID 34528 的 COM 对象。PID 34528 消失的原因无法从现有证据判定；因此不能声称原有进程已被完整保留。之后的一次检查中未发现运行中的 Mtb.exe。
