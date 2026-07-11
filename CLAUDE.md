# CLAUDE.md

本文件为维护者与 AI 助手提供仓库的架构约定与操作规范。修改规则前请通读本文件。

## 仓库定位

Shadowrocket（iOS）+ v2rayN（Windows）双端代理分流配置。核心策略：国内域名/IP 直连，境外走代理，强化 DNS 防泄露与防污染。

> **两端规则源不对等（关键认知）：**
>
> | | 国内域名/IP 匹配来源 | 自定义规则 |
> |---|---|---|
> | **Shadowrocket** | ACL4SSR 远程规则集（`ChinaDomain` / `ChinaMedia` / `BanAD` 等） + `GEOIP,CN` | `rules/*.list`（`ChinaDirect` + `Reject`） |
> | **v2rayN** | **不使用 ACL4SSR**；Xray 内置 `geosite:cn` / `geoip:cn`（数据源 v2fly + Loyalsoldier） | **仅** `v2rayn/AllowList.list`（直连白名单） |
>
> **v2rayN 端不引用 `rules/*.list`，独立管理。** 因 Xray 内置 `geosite:cn` / `geoip:cn` 已覆盖绝大多数国内域名/IP，v2rayN 端只需一个「直连白名单」`v2rayn/AllowList.list`（优先级高于广告拦截，捞回被广告库误伤的功能域），其余全交给 `geosite:cn` / `geoip:cn` 兜底。银行 .com、字节 CDN 等无需手动收录，由 `geoip:cn` 按国内 IP 兜底直连。

## 目录结构

| 路径 | 作用 | 是否手改 |
|------|------|---------|
| `shadowrocket.conf` | Shadowrocket 主配置（DNS、Rule、URL Rewrite） | 手改 |
| `rules/ChinaDirect.list` | 国内域名直连补充（**仅 Shadowrocket 用**） | **手改（唯一数据源）** |
| `rules/Reject.list` | 自定义广告/追踪拦截（**仅 Shadowrocket 用**） | **手改（唯一数据源）** |
| `v2rayn/AllowList.list` | v2rayN 直连白名单（捞回被广告库误伤的功能域） | **手改（唯一数据源）** |
| `v2rayn/routing.json` | v2rayN 路由规则 | **禁止手改，由脚本生成** |
| `v2rayn/build.py` | 将 `AllowList.list` 转换为 `routing.json` | 手改 |

## 核心约定

### DRY：规则数据源唯一

每份规则清单是其对应配置的**唯一数据源**：

- **Shadowrocket**：`rules/ChinaDirect.list`（直连）、`rules/Reject.list`（拦截），通过远程 `RULE-SET` 直接拉取，订阅更新即生效，无需构建。
- **v2rayN**：`v2rayn/AllowList.list`（直连白名单）是唯一手改源；`v2rayn/routing.json` 完全由 `v2rayn/build.py` 生成，**绝不可手改**。

修改 v2rayN 规则的标准流程：

```bash
# 1. 编辑数据源 v2rayn/AllowList.list（直连白名单）
# 2. 重新生成 v2rayN 路由
python v2rayn/build.py
# 3. 校验落盘
grep "新增域名" v2rayn/AllowList.list v2rayn/routing.json
```

### build.py 规则映射

`.list` 行格式 `RULE-TYPE,value` → v2rayN domain 前缀：

| Shadowrocket | v2rayN |
|---|---|
| `DOMAIN-SUFFIX` | `domain:` |
| `DOMAIN` | `full:` |
| `DOMAIN-KEYWORD` | `keyword:` |

注释行（`#`）与空行被忽略。

### 路由规则顺序绝不可乱改

代理分流按**首条匹配生效**（first-match-wins），规则顺序即优先级。`build.py` 的 `build_routing_rules()` 输出顺序固定，**绝对不能调整其中的 append 顺序**：

```
阻断 QUIC → 直连白名单 → 广告拦截 → 局域网 → 国内域名 → 国内 IP → 兜底代理
```

关键约束：

- **直连白名单必须在广告拦截之前** —— 白名单的唯一目的就是从 `category-ads-all` 误伤中捞回功能域。若排到广告拦截之后，会先被拦，白名单形同虚设。
- **兜底代理（`0-65535`）必须在最末** —— 它匹配一切流量，一旦前移会吞掉后续所有规则，分流形同虚设。

Shadowrocket 端（`shadowrocket.conf` 的 `[Rule]`）遵循同一优先级逻辑——自定义规则在广告拦截之前（`Reject → ChinaDirect → ACL4SSR(含 BanAD) → GEOIP,CN → FINAL`），自上而下匹配，`FINAL` 必须置于末尾。两端规则源不同（见「仓库定位」），但都遵循「自定义规则优先于广告拦截、兜底置于最末」。

### 新增直连域名前必须验证归属

新增任何直连域名前，**必须**先用 `.claude/skills/domain-verify` skill 核实域名真实存在、归属可信、非抢注。完整查询命令与归属判断规则见该 skill 文档，此处不复述。

硬性底线：

- 无 NS 记录（不存在 / 拼写错误）的域名**不得添加**
- 归属无法确认或疑似抢注（TXT 含 afternic / sedo / dan.com 等挂售特征）的域名**不得添加**

目的：避免把抢注或拼写错误的域名误加进直连，造成流量错误放行。

### 优先依赖上游规则，不重复收录

**Shadowrocket 端** `ChinaDirect.list` 只补 **ACL4SSR `ChinaDomain.list` 与 `GEOIP,CN` 均未覆盖**的域名。已被上游覆盖的不重复添加（DRY）：

- `.com.cn` / `.cn` 域名：由 `GEOIP,CN,DIRECT`（Shadowrocket）/ `geoip:cn`（v2rayN）兜底，通常无需手动添加
- ACL4SSR 已收录的域名：如 `abchina.com`、`cmbchina.com`、`ecitic.com`

真正需要手动补的是 **`.com` 顶级域且不被 GEOIP-CN 兜底** 的国内业务域名。

**v2rayN 端** `AllowList.list` 只收两类域名，其余一律交给 `geoip:cn` / `geosite:cn` 兜底，不重复收录：

1. 被 `geosite:category-ads-all` **误伤**、但属功能性通道的域名——不放白名单就会被广告拦截误杀。
2. **海外服务器**、不被 `geoip:cn` 兜底、又需强制直连的国内业务域名——不放白名单会掉进兜底代理。

判断某域名是否需进白名单：看它是否真被广告库拦（查 v2fly `category-ads` 相关源，或看 v2rayN 日志 `-> block`），或解析 IP 是否在境外。仅国内 IP 且未被误拦的域名**无需**加入。

### DOMAIN-SUFFIX 优先

银行、大厂等多子域场景优先用 `DOMAIN-SUFFIX`（后缀匹配），一条覆盖全部子域（如 `example.com` 覆盖 `www.example.com` / `api.example.com`）。仅在需精确匹配单个域名时用 `DOMAIN`。

## 排查参考

运行时问题排查见 [docs/troubleshooting.md](docs/troubleshooting.md)。遇到代理异常**先查该文档**，避免误改分流规则——许多"看似分流问题"的症状实为系统层原因。已知问题：

- **UWP 应用（Microsoft Store 等）开代理后无法联网** → Windows AppContainer 沙箱禁止 UWP 访问 `127.0.0.1` 回环，系统层问题，非规则问题，修复见排查手册。
