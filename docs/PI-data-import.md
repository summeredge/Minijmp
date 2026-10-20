# PI 数据导入

通过 File → Import PI Data 打开窗口。选择可运行的 PIReader.exe 和现有 config.txt；PIReader 所需的 PI SDK 必须安装在本机，且能够访问配置的服务器。Minijmp 不包含 PI SDK 或 PIReader 二进制文件，也不需要启动 Dash 服务。

默认查找 Minijmp 项目目录内的 PIReader.exe 和 config.txt，也可通过 PI_READER_EXE、PI_CONFIG 环境变量或窗口浏览按钮指定位置。不会读取、保存或记录配置文件内容；不要将带凭据的 config.txt 加入版本控制。

每行输入一个 Tag（最多 20 个，忽略大小写去重），或输入 Tag Mask 搜索、勾选后添加。时间支持绝对时间及现有 PI 表达式（如 *、*-1h、*-1d）；采样间隔支持 1m、5m、10m、30m、1h。预计超过一百万个数据点或无法估算时会要求确认，不截断查询数据。搜索结果如被 PIReader 限制会明确提示缩小 Mask。

成功后以 Timestamp 列及原始 Tag 列替换当前工作表；若 Tag 名为 Timestamp，保留 Tag 原名，时间列使用 Timestamp (time 1)，编号递增避开已有 Tag 名，可继续统计、绘图和保存。未保存的原工作表会被替换；需要保留时请先保存。空结果、错误、超时和取消不改变原工作表。

查询在后台线程运行，最长等待 300 秒。取消会立即关闭窗口并丢弃迟到结果；已经启动的 PIReader 仍可能运行到完成或超时。窗口不持久化路径、Tag 或凭据。

查询状态和完整错误信息显示在固定高度的只读文本框中，可滚动查看和复制。
