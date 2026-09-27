# 排查手册

Shadowrocket 配置在使用中遇到的运行时问题与排查方法。配置约定见 [CLAUDE.md](../CLAUDE.md)，v2rayN 端的排查记录见 [v2rayn.md](v2rayn.md)，本文件只记录运行时排查。

排查原则：**代理异常先查本文件，避免误改分流规则**。很多"看起来像分流问题"的症状实为系统层原因，动规则文件无效。

## BlockHttpDNS 拦截导致依赖 HTTPDNS 的国内 App 卡顿

**症状**：美团外卖等 App 页面加载明显变慢（首屏卡顿）；关闭代理或换配置后恢复。浏览器等不依赖内置 HTTPDNS 的应用不受影响。

**根因**：`shadowrocket.conf` 曾加入 `BlockHttpDNS` 拦截（`RULE-SET, ...BlockHttpDNS.list, REJECT`），其中包含 `DOMAIN,httpdns.meituan.com`。美团 App 内置 HTTPDNS 请求被 REJECT 后，SDK 要等握手失败/超时才回落系统 DNS，首屏因此明显变慢。**同类问题会出现在任何重度依赖内置 HTTPDNS 的国内 App**（支付宝、腾讯系等）。

**处置**：已移除 `BlockHttpDNS` 拦截（提交 `fd6cc5d`）。国内 App 回落系统 DNS 后走 `dns-server` 的阿里/腾讯 UDP（带 ECS），解析与 CDN 调度无损，防泄露目标不受影响。

**相关排查**：同批加入的 `block-quic = all-proxy` 曾先被怀疑为元凶，实测排除（移除后仍慢——美团的 QUIC 走直连，`all-proxy` 不拦直连流量），已恢复（提交 `5128f97`）。

### 排查路径回顾（避免重走弯路）

| 线索 | 指向 |
|---|---|
| 移除 block-quic 仍慢 | QUIC 屏蔽不背锅——all-proxy 只拦走代理的 QUIC |
| 移除 BlockHttpDNS 后恢复 | HTTPDNS 被 REJECT → App 回落系统 DNS 前的超时等待是元凶 |
| 美团主域被 ACL4SSR 覆盖走直连 | 流量未漏走代理，无需改分流规则 |

**教训**：App（尤其国内大厂 App）卡顿时，先查 `BlockHttpDNS` 拦截——它置于 `[Rule]` 最前、拦截面最大，且症状（卡顿而非断流）容易被误判为网络或分流问题。

## 影视聚合站视频无法播放（第三方资源域名未收录）

**症状**：影迷窝（`yingmiwo.me`）等影视聚合站，开代理时**网页能正常打开，但视频始终加载不出来**；关闭代理即可正常播放。网页与视频流表现不一致。

**根因**：这类站点的**网页域名与视频资源域名不是同一个**。站点只是壳，真正的视频走第三方采集源——本次实测为「极速资源」（`jisu` 系列）：

| 域名 | 用途 |
|---|---|
| `yingmiwo.me` | 站点页面、播放信息接口 |
| `vv.jisuzyv.com` | 播放列表（m3u8） |
| `p.jisuts.com` | 视频分片（`.ts`） |
| `img.jisuimage.com` | 封面图 |

这些资源域的 **NS 在阿里云（`vip7/vip8.alidns.com`），但 A 记录指向境外 IP**（如 `185.34.146.254`）。它们未被任何规则集收录，于是：

1. `GEOIP,CN,DIRECT,no-resolve` **带 `no-resolve`，不会为域名触发 DNS 解析**，直接跳过
2. 请求落到最末的 `MATCH` → 走代理（美国节点）
3. **服务端拒绝来自代理的连接，TLS 握手直接失败**（实测 `SEC_E_ILLEGAL_MESSAGE`）
4. 视频加载不出来

关代理时家宽 IP 直连，服务端放行（实测 HTTP 200），故能正常播放。

**处置**：三个资源域已收录至 `rules/ChinaDirect.list` 末尾特例区。

### 关键机制：`no-resolve` 决定了「域名是否被收录」才是分水岭

这是本次问题的核心。配置文件末尾两条兜底：

```
GEOIP,CN,DIRECT,no-resolve     ← 不解析域名
MATCH,<代理组>                  ← 一切未匹配的落这里
```

`no-resolve` 的含义是**不为了匹配 IP 规则而触发 DNS 解析**。因此：

> 任何**域名**请求，只要不在 `ChinaDirect` / `ChinaDomain` / `ChinaMedia` 等**域名类规则集**里，**无论解析到国内还是境外 IP，都会直接落到 `MATCH` 走代理**。

也就是说，一个域名走不走代理，取决于**它有没有被域名规则集收录**，而不取决于它的 IP 归属。这与「国内 IP 直连」的直觉相反，是本类问题的认识起点。

### 定位方法（可复用）

**不要靠推测，直接抓实际数据流**——影视聚合站的域名至少有「站点 / 列表 / 分片」三组，猜不出来。

**第一步：找出站点的播放信息接口**

用无头 Chrome 记录页面请求：

```bash
chrome --headless=new --log-net-log=netlog.json \
       --user-data-dir=<临时目录> --virtual-time-budget=30000 \
       --dump-dom "<播放页 URL>" > /dev/null
grep -oE '"url":"https?://[^"/]+' netlog.json | sed 's/"url":"//' | sort -u
```

本次抓到：`https://yingmiwo.me/api/filmPlayInfo?id=...&playFrom=...&episode=...`

**第二步：调用该接口看返回**

该接口需登录态，**在已登录的浏览器地址栏直接打开即可**。返回内容会直接给出视频地址：

```json
{"current": {"episode": "第102集",
             "link": "https://vv.jisuzyv.com/play/elYpPV1a/index.m3u8"}}
```

**第三步：拉取 m3u8 找出分片域名**

```bash
curl -s --noproxy '*' "https://vv.jisuzyv.com/play/elYpPV1a/index.m3u8" | grep -oE 'https?://[^" ]+'
```

分片（`.ts`）**往往在另一个域名上**（本次为 `p.jisuts.com:999`），必须一并收录，否则视频仍会卡在加载分片这一步。

**第四步：对比直连与代理的差异**

```bash
curl -s -o /dev/null --noproxy '*'            -w "直连 HTTP:%{http_code}\n" "https://vv.jisuzyv.com/..."
curl -s -o /dev/null -x http://127.0.0.1:7897 -w "代理 HTTP:%{http_code}\n" "https://vv.jisuzyv.com/..."
```

### ⚠️ 测试陷阱：`https_proxy` 环境变量会让 curl 静默走代理

本机 Git Bash 环境预设了 `https_proxy=http://127.0.0.1:7897`，curl 会**自动读取并走代理**。不加 `--noproxy '*'` 的所谓「直连测试」实际上走了代理，结论会被完全带偏。

测试前先用 `curl -v` 确认实际路径，输出中会有：

```
* Uses proxy env variable https_proxy == 'http://127.0.0.1:7897'
```

**任何直连/代理对比测试，都必须先确认这一点。**

### 排查路径回顾（避免重走弯路）

本次先后做过两次错误归因，共同点是**用间接线索推测，而非抓实际数据**：

| 错误归因 | 当时的依据 | 为什么错 |
|---|---|---|
| 「站点排斥代理出口 IP」 | 站点开 Cloudflare 挑战、whois 隐私保护、经代理耗时异常 | 方向沾边但没定位到具体域名；据此加 `yingmiwo.me` 直连，对视频毫无作用 |
| 「夸克网盘未收录」 | 站点 JS 里出现 `pan.quark.cn`、存在 `panparse` 子域 | JS 引用只说明站点**支持**该网盘；本例影片实际走「极速资源」，与夸克无关 |

**教训**：影视聚合站的「站点域名 / 播放列表域名 / 分片域名」通常是三组不同的域，**只看站点或 JS 里的片段线索必然误判**。应尽早抓播放接口的返回内容——那里有权威答案，一步到位。

第二个教训在测试方法上：`https_proxy` 环境变量会让 curl 静默走代理，**直连测试不显式 `--noproxy '*'` 等于没测**。
