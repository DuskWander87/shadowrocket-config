---
name: domain-verify
description: "验证域名是否真实存在、归属哪家公司，排除抢注域名。当用户提到要核查某个域名、在代理日志中发现陌生域名、或在 Shadowrocket 配置中添加直连规则之前，主动使用此 skill。"
---

# Domain Verify

对一个或多个域名执行 DNS 查询与 ICP 备案核查，输出「是否存在 + 归属主体 + 是否抢注 + 解析特征」的结论，帮助决策是否将其加入直连规则，以及是否需要域名级直连（而非依赖 IP 兜底）。

## 步骤

### 1. 查 NS 记录（判断域名是否存在及归属）

```bash
# Linux / macOS
dig +short <domain> NS

# Windows（系统自带 nslookup，无 dig）
nslookup -type=NS <domain>
```

> 按运行环境二选一即可：Unix/macOS 用 `dig`，Windows 用 `nslookup`。

- 有 NS 记录 → 域名已注册，进入归属判断
- 无 NS 记录 → 域名不存在，可能是日志拼写错误，**不应添加规则**
  - `dig`：输出为空
  - `nslookup`：出现以 `***` 开头、含 `Non-existent domain` 的报错（中文系统中间文字可能本地化或显示为乱码，认准 `Non-existent domain` / `NXDOMAIN` / `Server failed` 关键词即可；该报错走 **stderr**）

> **读 nslookup 输出**：忽略开头的 `服务器:` / `Address:`（那是本机 DNS，中文 Windows 下可能显示为乱码 `������`，无害）；真正的 NS 在 `<domain>  nameserver = xxx` 行。

**常见 NS 归属参考：**

| NS 服务器 | 归属 |
|---|---|
| `*.alidns.com` | 阿里云，国内大厂常用 |
| `*.bytedns.com` | 字节跳动自有 DNS |
| `*.dnspod.com` / `*.dnspod.net` | 腾讯 DNSPod |
| `*.huaweicloud.com` | 华为云 |
| `*.volcengine-dns.com` | 火山引擎（字节旗下云 DNS），任何火山引擎客户均可使用 |
| `*.cloudflare.com` | Cloudflare，境外服务为主 |
| `*.awsdns-*.com` | AWS Route53 |
| `*.parklogic.com` | 域名停放/变现商，非真实业务主体，**排除** |
| 其他小众 DNS | 需进一步核查 |

### 2. 查 ICP 备案（确定运营主体，最权威依据）

NS 只能定位 DNS 托管商，**不能确定域名归属**。要确认运营主体，查 ICP 备案：

```
# 单域名备案（用 WebFetch 或 curl 抓取，提取「主办单位名称 / 备案号 / 审核时间」）
https://www.ip.cn/beian/<domain>.html
https://www.beiancx.com/<domain>.html

# 按主体穷举名下全部域名（省份用小写拼音，主体名用中文）
https://gongshang.mingluji.com/<province>/icp/<主办单位名称>
```

- 有备案 → 主办单位即运营主体，归属确定
- 备案号形如 `京ICP备12345678号-7`，**后缀序号是该主体名下网站的序号**——同一主体的域名序号应连续，若出现序号缺口（已知 `-1 / -2 / -5`，缺 `-3 / -4`），说明主体名下还有未探明的域名，值得补查
- **无备案 ≠ 非国内业务**：CDN / 静态资源 / API 类域名普遍不做网站备案，仅凭备案查不到不能否定归属

> **关键警告：第三方备案站多为 JS 前端渲染，抓取常返回空白或停在「正在查询」。空白结果不可作为「无备案」依据，必须换源复核。** 可用来源：ip.cn、7icp.com、beiancx.com、mingluji.com；各站同步时间不同，还会出现同一域名返回不同主办单位，以审核时间较新者为准。

### 3. 查 TXT 记录（排除抢注域名）

当 NS 归属不明确或使用小众 DNS 时执行：

```bash
# Linux / macOS
dig +short <domain> TXT

# Windows
nslookup -type=TXT <domain>
```

若 TXT 含以下关键词，说明域名可能在挂售或被抢注，**不应添加规则**：

- `afternic` — Afternic 域名交易市场
- `sedo` — Sedo 域名交易市场
- `dan.com` — 域名交易平台
- `purelymail` / `improvmx` 等个人邮件托管服务（大厂不会用）

> **读 nslookup 输出**：TXT 内容在 `<domain>  text = "..."` 行。若该域名无 TXT 记录，nslookup 会改返回 SOA（`primary name server` / `responsible mail addr`）——其中 responsible mail 的域名可辅助判断托管商（如 `hostmaster.hichina.com` → 阿里云/万网）；`dig +short` 此时则输出为空。

### 4. 解析行为检测（识别 DNS 调度型域名）

查 A 记录，看 CNAME 链与跨地域解析是否一致，判断该域名是否依赖国内 DNS 调度：

```bash
# 国内 DNS（阿里）
nslookup <domain> 223.5.5.5
# 境外 DNS（Google）
nslookup <domain> 8.8.8.8
```

> Linux/macOS 用 `dig @223.5.5.5 <domain>` / `dig @8.8.8.8 <domain>`。并发执行两条命令。

读输出看三点：

- **CNAME 链**：若指向 `volcgslb*` / `*cdn*` / `cloudfront.net` / `akamai*` / `*.gslb.*` 等 GSLB/CDN，说明是 DNS 调度型域名，A 记录随解析者地域变化
- **跨地域 A 一致性**：国内 DNS 与境外 DNS 返回的 A 不同 → 解析依赖国内 DNS 调度
- **异常返回**：境外 DNS 返回 `127.0.0.1` / 私有 IP 段 / 明显境外 IP，说明代理远端解析拿不到国内节点

若命中以上任一，该域名**不能依赖 `geoip:cn` / `GEOIP,CN` 兜底直连**（代理远端解析到的 IP 不在国内段，会掉进兜底代理），应走域名级直连规则（`DOMAIN-SUFFIX` / `DOMAIN`）。

> 客观报告「解析是否随地域变化」即可，不预测具体分流行为（取决于客户端 DNS 配置与代理模式，变量太多）。该步的目的是提示「依赖 IP 兜底是否可靠」。

**apex 无 A / CNAME 记录时：先探子域，勿据此判定「域名未使用」**

主域（apex）无解析是资源类域名的常态——服务挂在子域上。此时：

1. 查证书透明日志，用 SAN 发现实际在用的子域：
   ```bash
   curl -s "https://crt.sh/?q=%25.<domain>&output=json" | grep -o '"name_value":"[^"]*"' | sort -u
   ```
   证书 SAN 也是判断「该域名族实际服务哪些子域、用途为何」的最佳线索——子域命名常直接暴露业务（如含 `video.` / `live.` 前缀即指向视频/直播 CDN）。
2. 对 SAN 中出现的子域，以及 `www.` / `api.` / `m.` 等常见前缀逐个解析实测。

「apex 无 A 记录」只说明没有站点直接挂在主域，**不能推出域名未使用**；结合 NS 与备案确认归属后，仍应按域名族整体收录（`DOMAIN-SUFFIX` 一条覆盖全部子域）。

### 5. 输出结论

对每个域名给出一行结论：

```
✅ example-a.com — 真实存在，NS: alidns.com（阿里云），可加直连
✅ example-b.com — 真实存在，NS: bytedns.com（字节跳动自有），可加直连
❌ example-c.com — 无 NS 记录，域名不存在，疑似拼写错误
⚠️ example-d.com — 存在但 NS 为小众服务商，TXT 含 afternic，疑似抢注，不建议添加
🌐 example-e.com — 真实存在，NS: 火山引擎（字节旗下云 DNS，非域名归属），CNAME 指向 volcgslb-mlt.com（DNS 调度型），国内/境外 DNS 返回不一致，需域名级直连
✅ example-f.com — 真实存在，ICP 备案主体「某某科技有限公司」（京ICP备12345678号-7），归属确定，CNAME 指向阿里云 CDN，需域名级直连
⏸️ example-g.com — 真实存在，ICP 备案主体同一公司，但 apex 与子域均无解析、无证书 → 归属确凿、当前休眠，可视域名族完整性需要收录
🚫 example-h.com — 存在但 NS 为 parklogic.com（域名停放），TXT `v=spf1 -all`，A 指向境外 → 停放域名，与宣称归属无关，排除
```

## 注意事项

- NS 指向某家 DNS 服务商不能 100% 确认归属，应结合域名命名规律与用户提供的上下文综合判断
- 如用户提供的是不带后缀的关键词（如 `bytegecko`），默认补全 `.com` 后查询
- DNS 查询命令按运行环境二选一：Unix/macOS 用 `dig`，Windows 用系统自带 `nslookup`（无需额外安装）
- **不要给 nslookup 加 `2>/dev/null`**：否则会吞掉“域名不存在”的报错（`Non-existent domain`），把不存在的域名误判为查询无结果
- 批量查询时并发执行所有 dig / nslookup 命令，提高效率
- 若 CNAME 指向 GSLB/CDN，A 记录随地域变化是正常调度行为，不代表域名异常；但此类域名**不应**依赖 `geoip:cn` / `GEOIP,CN` 兜底，需加域名级直连规则（规则按域名匹配，发生在 DNS 解析之前，不受 GSLB 地域调度影响）
- **SOA responsible mail（如 `dnsadmin.bytedance.com`）是 DNS 托管商的默认管理员联系人，不代表域名归属**。火山引擎/阿里云等云 DNS 服务的客户域名都会带托管商特征，归属须结合域名命名规律、用户提供的上下文、TXT 验证记录等综合判断，不能仅凭 SOA/NS 判定为托管商自有域
- **归属证据优先级**：ICP 备案（主办单位）> 域名命名规律 / 用户上下文 > NS、SOA（仅表明 DNS 托管商）。三者冲突时以备案为准——企业普遍把域名 DNS 托管在第三方云 DNS 上，NS 指向哪家托管商与域名归属没有必然关系
- **「无解析」有两种含义，勿混为一谈**：域名停放（NS 为 `parklogic` 等停放商、TXT `v=spf1 -all`、A 指向境外）是他人挂售/变现，**应排除**；而归属确凿（备案在册、NS 属真实业务主体）却暂无解析的域名只是休眠，不代表不属于该公司，可视域名族完整性决定是否收录
