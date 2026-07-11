# 排查手册

本仓库双端代理配置（Shadowrocket + v2rayN）在使用中遇到的运行时问题与排查方法。配置约定见 [CLAUDE.md](../CLAUDE.md)，本文件只记录运行时排查。

排查原则：**代理异常先查本文件，避免误改分流规则**。很多"看起来像分流问题"的症状（如 UWP 应用联网失败）实为系统层原因，动 `AllowList.list` / `routing.json` 无效。

## UWP 应用（Microsoft Store 等）开启代理后无法联网

**症状**：v2rayN 开启系统代理后，Microsoft Store 等 UWP 应用提示"网络连接异常"或页面空白；关闭代理则一切正常。浏览器等 Win32 应用不受影响。

**根因**：UWP 应用运行在 AppContainer 沙箱，默认禁止访问 `127.0.0.1` 回环地址。v2rayN 系统代理监听 `127.0.0.1:7897`，UWP 连不上该回环地址 → "网络连接异常"。这是 Windows 系统层隔离机制，**与分流规则无关**。

**修复**（需管理员 PowerShell）：

```powershell
CheckNetIsolation LoopbackExempt -a -n="Microsoft.WindowsStore_8wekyb3d8bbwe"
```

执行后关闭并重新打开 Microsoft Store 即可恢复。

**适用其他 UWP 应用**：用以下命令查 PackageFamilyName，替换上式的值：

```powershell
Get-AppxPackage -Name "*应用名*" | Select-Object PackageFamilyName
```

**注意**：豁免非永久，UWP 应用更新或系统重置后需重跑命令。

### 排查路径回顾（避免重走弯路）

该问题曾一度被误判为分流配置问题，先后排查过"图片 CDN 裂图加白名单""节点连不通 Akamai""QUIC 阻断"均未解决。关键区分点：

| 线索 | 指向 |
|---|---|
| 关代理正常、开代理失败 | 代理介入是变量，但未必是节点链路 |
| 浏览器走代理能打开同一域名 | 节点链路通，问题在应用层而非网络层 |
| 症状是"网络连接异常"而非裂图 | 网络层失败，非内容加载层 |
| 仅 UWP 应用受影响、Win32 正常 | UWP 沙箱隔离问题 |

**教训**：症状为"网络连接异常"（网络层）时，优先排查 UWP loopback 隔离等系统层原因，不要先动分流规则。
