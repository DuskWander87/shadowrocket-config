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

## v2rayN 端 IPv6 无法彻底禁用（AAAA-only 域名回落走 v6）

**症状**：v2rayN 运行中，在 [iplark.com](https://iplark.com) 等出口检测站的「网络出口 → IPv6 出口」里仍能看到**国内运营商 IPv6 地址**（如 `240e::/20` 电信段），且该地址与本机网卡地址完全一致。同一环境下换用 mihomo / sing-box 系客户端则看不到。

**结论先行**：这是 **v2rayN 的功能缺口，不是配置错误**。当前 Xray 内核下：

- ✅ **双栈域名已被正确压到 IPv4**（覆盖日常 99% 的站点）
- ❌ **AAAA-only 域名仍会走 IPv6**，且 v2rayN GUI 无法设置能阻止它的选项

**当前处置：维持现状**（2026-08-02 决定）。日常浏览几乎碰不到 AAAA-only 域名，检测站能测出来是因为它专门用 AAAA-only 端点探测。彻底禁用需动系统层，见文末「若日后要彻底禁用」。

### 根因：Xray 的 `Use` 系列策略会回落

Xray 官方文档 [transports/sockopt.md](https://github.com/XTLS/Xray-docs-next/blob/main/docs/config/transports/sockopt.md) 对 `domainStrategy` 的原文：

> - 当使用 `"AsIs"` 时, Xray 不对域名进行特殊处理，到最后 Xray 将直接使用 go 自带的 Dial 发起连接，优先级固定为 RFC6724 的默认值（不会遵守 gai.conf 等配置）**通常来说为 IPv6 优先**。
> - 当使用 `"Use"` 开头的选项时，若解析结果不符合要求（如，域名只有 IPv4 解析结果但使用了 UseIPv6），则会**回落回 AsIs**。

于是 `UseIPv4` 的实际行为是：

| 域名类型 | `UseIPv4` 行为 | 结果 |
|---|---|---|
| 双栈（有 A + AAAA） | 只取 A 记录 | 走 IPv4 ✅ |
| **AAAA-only（无 A）** | 解析不到 A → **回落 AsIs** → go Dial → IPv6 优先 | **走 IPv6** ❌ |

要不回落必须用 **`Force` 系列**（`ForceIPv4`）——解析不到就直接失败，不回落。

### v2rayN GUI 设不了 `Force` 系列（三处证据）

| 证据 | 位置 | 说明 |
|---|---|---|
| 选项列表无 Force | `ServiceLib/Global.cs` 的 `DomainStrategy` | 只有 `AsIs / UseIP / UseIPv4v6 / UseIPv6v4 / UseIPv4 / UseIPv6` |
| 基础设置页下拉框不可输入 | `Views/DNSSettingWindow.xaml` | `cmbDirectDNSStrategy` 绑定 `SelectedItem`，样式 `DefComboBox` 基于 `MaterialDesignComboBox`，未设 `IsEditable` |
| 自定义 DNS 页同样不可输入 | 同上 | `cmbdomainStrategy4FreedomCompatible` 用的也是 `DefComboBox` |

### 与其他客户端的差异

| 客户端 / 策略 | 语义 | AAAA-only 域名 |
|---|---|---|
| Xray `UseIPv4`（v2rayN 唯一可选） | 解析不到 A 就回落 AsIs | 走 IPv6 ❌ |
| Xray `ForceIPv4`（GUI 选不到） | 解析不到 A 就失败 | 断开 ✅ |
| mihomo `ipv6: false` | dialer 层直接丢弃 v6，不回落 | 断开 ✅ |
| sing-box `ipv4_only` | 同上 | 断开 ✅ |

「换个客户端就没有国内 IPv6」的原因就在这——那些客户端的实现是 Force 语义。

### 当前已生效的设置（保持不动）

v2rayN → **设置 → DNS 设置 → DNS 基础设置**（不是「参数设置」，这是最常找错的地方）：

```
直连目标解析策略：UseIPv4    ← 已设置，压住双栈域名
代理目标解析策略：Default    ← 保持
连接代理解析策略：Default    ← 保持
启用 Happy Eyeballs：关闭    ← 保持
```

三项的源码映射（`Views/DNSSettingWindow.xaml.cs:37-39`、`Services/CoreConfig/V2ray/V2rayDnsService.cs`）：

| 界面标签 | 源码字段 | 写入 config.json 的位置 |
|---|---|---|
| **直连目标解析策略** | `Strategy4Freedom` | `outbounds[direct].streamSettings.sockopt.domainStrategy` |
| 代理目标解析策略 | `Strategy4Proxy` | `outbounds[proxy].targetStrategy` |
| 连接代理解析策略 | `Strategy4ProxyDial` | `outbounds[proxy].streamSettings.sockopt.domainStrategy` |

- **代理目标解析策略保持 `Default`**：官方说明为「当未选择或 AsIs 时，由远程服务器端 DNS 解析；否则，使用内部 DNS 模块解析」。`Default` 下域名**透传**给代理服务器，本机不产生连接，不存在泄露。改成 `UseIPv4` 反而变成本地解析，代价是 CDN 就近解析优化失效。
- **连接代理解析策略保持 `Default`**：官方界面标注「不建议开启，特殊情况可能回环」。回环成因是解析节点域名时走内部 DNS 模块，而内部 DNS 的远程 DNS 本身又需通过代理才能查通。
- **关 Happy Eyeballs**：官方说明「需配合 UseIP 策略使用。启用后将同时尝试 IPv4 和 IPv6 连接」——与禁 v6 直接冲突。

**副作用**：「直连目标解析策略」为 `UseIPv4` 时，直连域名解析从「系统 DNS」切到「内部 DNS 模块」，即改用界面配置的直连 DNS。对防污染有利。

### 决定性验证方法

**不要用 `curl --noproxy` 或 `curl -6` 测**——那是显式绕过代理，任何客户端都会暴露本机 IPv6，测不出问题（见文末误诊记录）。

正确做法是找一个**只有 AAAA 记录的国内域名**（必然匹配 `geosite:cn` 走 direct），对比直连与走代理：

```bash
# test6.ustc.edu.cn —— AAAA=2001:da8:d800::1043，无 A 记录，.cn 域名
curl -s -o /dev/null -w "HTTP=%{http_code} 远端=%{remote_ip}\n" \
     --noproxy '*' --connect-timeout 10 "http://test6.ustc.edu.cn/"      # 直连：应 200
curl -s -o /dev/null -w "HTTP=%{http_code}\n" \
     --proxy http://127.0.0.1:7897 --connect-timeout 15 "http://test6.ustc.edu.cn/"
```

- 走代理返回 **HTTP 200** → `UseIPv4` 回落到了 IPv6，即当前状态
- 走代理**连接失败** → Force 语义生效，IPv6 已被真正切断

验证双栈域名是否正常压到 IPv4（应返回节点 IP 而非 `240e:` 开头）：

```bash
curl -s --proxy http://127.0.0.1:7897 https://ipv6.icanhazip.com
```

### 节点本身是 IPv6-only 会受影响吗

不会。「直连目标解析策略」只作用于 `outbounds[direct]`（freedom），与代理出站无关；代理出站拨号到节点服务器属于 outbound 内部行为，不经过路由规则匹配。纯 IPv6 节点、或仅有 AAAA 记录的节点域名均可正常连接。

### 为什么不能用路由规则解决（已验证无效）

排查中曾在 `v2rayn/routing.json` 加过一条 `::/0 → block`（排在局域网直连之后），**实测无效，已移除**。原因：

- 系统代理模式下 `routing.domainStrategy = AsIs`，路由**只按域名匹配、不解析 IP**。以域名发起的连接根本不会去匹配 `ip: ["::/0"]` 规则。
- 而上面的回落场景恰恰全都是域名连接——浏览器把域名交给代理，路由按域名判定走 direct，随后才在**出站层**回落到 IPv6。路由决策发生在出站之前，等 IPv6 出现时早已过了路由这关。
- 它仅对「客户端直接发 IPv6 字面量地址」的连接有效，这类连接在日常使用中几乎不存在。

**结论：IPv6 是出站层问题，路由层够不着。** 别再往 `routing.json` 加 IPv6 规则——加了只会让人误以为已经防住了。

### 若日后要彻底禁用

| 方案 | 做法 | 代价 |
|---|---|---|
| **系统层禁用（推荐）** | 网卡属性取消勾选「Internet 协议版本 6 (TCP/IPv6)」 | 一步到位、可逆、与代理软件解耦，等价于 Shadowrocket 的 `ipv6 = false` |
| 注入 `ForceIPv4` | 改 `guiConfigs/guiNDB.db` 的 `DNSItem` 表，`DomainStrategy4Freedom` 置 `ForceIPv4` 且 `Enabled=1` | 启用自定义 DNS 会走 `GenDnsCustom()` 分支并直接 `return`，**简易 DNS 的直连/远程分流整体失效**；且在 GUI 点一次「确定」就被下拉框的值覆盖回去 |
| 切 sing-box 内核 | 用 `ipv4_only` 策略 | 换内核，分流行为需重新验证 |

**注意**：GUI 里的解析策略存在 v2rayN 自己的数据库中，**不随本仓库同步**。换机器或重装 v2rayN 后必须重新设置。

### 排查路径回顾（避免重走弯路）

本次排查走过两段弯路，都源于**测试方法不当**：

| 错误做法 | 得出的错误结论 | 为什么错 |
|---|---|---|
| `curl -6 --noproxy '*'` 测出国内 IPv6 | 「系统代理模式无法禁 IPv6，需切 Tun 或改系统」 | `--noproxy` 显式绕过代理，任何客户端下都是这个结果，证明不了泄露 |
| 遵守系统代理测得出口是节点 IP | 「完全没有泄露，配置已达标」 | 用的是双栈域名，恰好落在 `UseIPv4` 正常工作的路径上，漏掉了 AAAA-only 这个回落场景 |

**教训**：验证「是否禁用 IPv6」必须同时满足两个条件——**① 遵守系统代理（模拟真实应用行为）② 目标是 AAAA-only 域名（覆盖回落路径）**。少任何一个都会得出相反的错误结论。

另外，`sockopt.domainStrategy` 已写入 config.json 并不等于 IPv6 已被禁用——要看策略前缀是 `Use` 还是 `Force`。
