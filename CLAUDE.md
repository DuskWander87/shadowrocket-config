# CLAUDE.md

本文件为维护者与 AI 助手提供仓库的架构约定与操作规范。修改规则前请通读本文件。

## 仓库定位

Shadowrocket（iOS）+ v2rayN（Windows）双端代理分流配置。核心策略：国内域名/IP 直连，境外走代理，强化 DNS 防泄露与防污染。

> **两端规则源不对等（关键认知）：**
>
> | | 国内域名/IP 匹配来源 | 自定义规则 |
> |---|---|---|
> | **Shadowrocket** | ACL4SSR 远程规则集（`ChinaDomain` / `ChinaMedia` / `BanAD` 等） + `GEOIP,CN` | `rules/*.list` |
> | **v2rayN** | **不使用 ACL4SSR**；Xray 内置 `geosite:cn` / `geoip:cn`（数据源 v2fly + Loyalsoldier） | `rules/*.list` |
>
> v2rayN 端的 `routing.json` **完全不引用 ACL4SSR**。两端共享的只有自建的 `rules/*.list`，国内域名覆盖范围因此并不完全一致——仅被 ACL4SSR 收录而 `geosite:cn` 未含的域名，在 v2rayN 端只能靠 `geoip:cn` 兜底。新增直连域名时，若该域名属于这种情况，应显式写入 `rules/ChinaDirect.list` 以保证两端一致。

## 目录结构

| 路径 | 作用 | 是否手改 |
|------|------|---------|
| `shadowrocket.conf` | Shadowrocket 主配置（DNS、Rule、URL Rewrite） | 手改 |
| `rules/ChinaDirect.list` | 国内域名直连补充（ACL4SSR 未覆盖部分） | **手改（唯一数据源）** |
| `rules/Reject.list` | 自定义广告/追踪拦截 | **手改（唯一数据源）** |
| `v2rayn/routing.json` | v2rayN 路由规则 | **禁止手改，由脚本生成** |
| `v2rayn/build.py` | 将 `rules/*.list` 转换为 `routing.json` | 手改 |

## 核心约定

### DRY：规则数据源唯一

`rules/*.list` 是直连/拦截规则的**唯一数据源**。`v2rayn/routing.json` 完全由 `v2rayn/build.py` 从 `.list` 生成，**绝不可手改**。

修改规则的标准流程：

```bash
# 1. 编辑数据源
#    rules/ChinaDirect.list（直连）或 rules/Reject.list（拦截）
# 2. 重新生成 v2rayN 路由
python v2rayn/build.py
# 3. 校验两端同步
grep "新增域名" rules/ChinaDirect.list v2rayn/routing.json
```

Shadowrocket 端通过远程 `RULE-SET` 直接拉取 `.list`（见 `shadowrocket.conf` 的 `[Rule]`），无需额外构建，订阅更新即生效。

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
阻断 QUIC → 自定义拦截 → 广告拦截 → 自定义直连 → 局域网 → 国内域名 → 国内 IP → 兜底代理
```

关键约束：

- **拦截必须在直连/代理之前** —— 否则广告/追踪域名被前面的直连规则先放行，拦截彻底失效
- **兜底代理（`0-65535`）必须在最末** —— 它匹配一切流量，一旦前移会吞掉后续所有规则，分流形同虚设
- **自定义直连在上游 `geosite:cn` / `geoip:cn` 之前** —— 保证手动补充的域名优先于宽泛的国家级匹配

Shadowrocket 端（`shadowrocket.conf` 的 `[Rule]`）同理：规则自上而下匹配，`FINAL` 必须置于末尾。

### 新增直连域名前必须验证归属

新增任何直连域名前，**必须**先用 `.claude/skills/domain-verify` skill 核实域名真实存在、归属可信、非抢注。完整查询命令与归属判断规则见该 skill 文档，此处不复述。

硬性底线：

- 无 NS 记录（不存在 / 拼写错误）的域名**不得添加**
- 归属无法确认或疑似抢注（TXT 含 afternic / sedo / dan.com 等挂售特征）的域名**不得添加**

目的：避免把抢注或拼写错误的域名误加进直连，造成流量错误放行。

### 优先依赖上游规则，不重复收录

`ChinaDirect.list` 只补 **ACL4SSR `ChinaDomain.list` 与 `GEOIP,CN` 均未覆盖**的域名。已被上游覆盖的不重复添加（DRY）：

- `.com.cn` / `.cn` 域名：由 `GEOIP,CN,DIRECT`（Shadowrocket）/ `geoip:cn`（v2rayN）兜底，通常无需手动添加
- ACL4SSR 已收录的域名：如 `abchina.com`、`cmbchina.com`、`ecitic.com`

真正需要手动补的是 **`.com` 顶级域且不被 GEOIP-CN 兜底** 的国内业务域名。

### DOMAIN-SUFFIX 优先

银行、大厂等多子域场景优先用 `DOMAIN-SUFFIX`（后缀匹配），一条覆盖全部子域（如 `example.com` 覆盖 `www.example.com` / `api.example.com`）。仅在需精确匹配单个域名时用 `DOMAIN`。
