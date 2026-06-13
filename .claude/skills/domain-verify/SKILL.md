---
name: domain-verify
description: "验证域名是否真实存在、归属哪家公司，排除抢注域名。当用户提到要核查某个域名、在代理日志中发现陌生域名、或在 Shadowrocket 配置中添加直连规则之前，主动使用此 skill。"
---

# Domain Verify

对给定的一个或多个域名执行 DNS 查询，输出「是否存在 + 归属判断 + 是否抢注」的结论，帮助决策是否将其加入直连规则。

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
| `*.cloudflare.com` | Cloudflare，境外服务为主 |
| `*.awsdns-*.com` | AWS Route53 |
| 其他小众 DNS | 需进一步核查 |

### 2. 查 TXT 记录（排除抢注域名）

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

### 3. 输出结论

对每个域名给出一行结论：

```
✅ example-a.com — 真实存在，NS: alidns.com（阿里云），可加直连
✅ example-b.com — 真实存在，NS: bytedns.com（字节跳动自有），可加直连
❌ example-c.com — 无 NS 记录，域名不存在，疑似拼写错误
⚠️ example-d.com — 存在但 NS 为小众服务商，TXT 含 afternic，疑似抢注，不建议添加
```

## 注意事项

- NS 指向某家 DNS 服务商不能 100% 确认归属，应结合域名命名规律与用户提供的上下文综合判断
- 如用户提供的是不带后缀的关键词（如 `bytegecko`），默认补全 `.com` 后查询
- DNS 查询命令按运行环境二选一：Unix/macOS 用 `dig`，Windows 用系统自带 `nslookup`（无需额外安装）
- **不要给 nslookup 加 `2>/dev/null`**：否则会吞掉“域名不存在”的报错（`Non-existent domain`），把不存在的域名误判为查询无结果
- 批量查询时并发执行所有 dig / nslookup 命令，提高效率
