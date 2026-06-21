# Shadowrocket 防 DNS 泄露配置

基于 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) 规则集的 Shadowrocket 配置文件，国内 UDP + 境外 DoH 混合策略，兼顾防泄露与 CDN 调度精准。

## 订阅链接

复制以下任一链接到 Shadowrocket 进行订阅。电脑端如使用 v2rayN，请直接跳转到下方 [v2rayN 配置](#v2rayn-配置) 段落。

**raw.githubusercontent.com（权威源）：**

```
https://raw.githubusercontent.com/DuskWander87/shadowrocket-config/main/shadowrocket.conf
```

**jsDelivr CDN（国内推荐，速度更快）：**

```
https://cdn.jsdelivr.net/gh/DuskWander87/shadowrocket-config@main/shadowrocket.conf
```

## 使用方法

1. 打开 Shadowrocket → 底栏「配置」→ 右上角 `+`
2. 粘贴上述任一订阅链接 → 「下载」
3. 等待下载完成后，长按该配置 → 「使用配置」
4. 配置生效后，规则集会自动从远端拉取（首次加载需联网）

## 核心特性

### DNS 防泄露

- **国内 UDP + 境外 DoH 混合并发**：阿里/腾讯 UDP + Cloudflare/Google DoH 四路并发取最快
- **国内站点保最优 CDN**：UDP DNS 携带 ECS 客户端子网，CDN 调度精准到本地节点
- **境外站点防污染**：Cloudflare/Google DoH 加密兜底，自动剔除被污染的 IP
- **禁用 IPv6**：避免 v6 通道绕过 DNS 配置造成泄露
- **拒绝私有 IP 应答**：防 DNS rebinding 攻击
- **DNS 失败请求走代理重试**：`FINAL,PROXY,dns-failed`

### URL 重写

- **Google 域名重定向**：`g.cn` / `google.cn` 自动 302 跳转至 `google.com`，避免访问国内镜像

### 分流策略

| 类型 | 处理 | 来源 |
|---|---|---|
| 广告 / 追踪 SDK 补充拦截 | REJECT | 自建 Reject.list |
| 国内直连补充域名 | DIRECT | 自建 ChinaDirect.list |
| 局域网 / 解禁名单 | DIRECT | ACL4SSR LocalAreaNetwork / UnBan |
| 广告域名 | REJECT | ACL4SSR BanAD / BanProgramAD |
| 国内域名 / 流媒体 | DIRECT | ACL4SSR ChinaDomain / ChinaMedia |
| 国内 IP / 国内企业 IP | DIRECT | ACL4SSR ChinaIp / ChinaCompanyIp |
| `GEOIP,CN` | DIRECT | 内置 GeoIP |
| 其他 | PROXY | FINAL 兜底 |

## 维护

### 规则集同步

`RULE-SET` 分两类：

- **ACL4SSR 远程规则**：引用 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) 仓库，上游更新后下次刷新订阅自动同步，无需手动维护。
- **自建规则**（`rules/` 目录）：`Reject.list` 和 `ChinaDirect.list` 引用本仓库，手动维护，新增域名推送后下次刷新生效。

### 修改配置

直接编辑 `shadowrocket.conf` 并推送到本仓库，Shadowrocket 下次刷新订阅即生效。

### 自建规则维护

| 文件 | 用途 |
|---|---|
| `rules/Reject.list` | ACL4SSR 未覆盖的广告 / 追踪 SDK 域名，新增后走 REJECT |
| `rules/ChinaDirect.list` | ACL4SSR 未覆盖的国内厂商域名，新增后走 DIRECT |

新增域名前建议先用 `domain-verify` skill 确认归属，避免误添加抢注域名。

### 切换 CDN 源

如发现 `raw.githubusercontent.com` 在国内拉取失败，临时改用 jsDelivr 订阅链接即可。如需让配置文件内部的 `RULE-SET` 也走 jsDelivr，替换以下两处前缀：

**ACL4SSR 规则：**

```
https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/
```
→
```
https://cdn.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/
```

**自建规则：**

```
https://raw.githubusercontent.com/DuskWander87/shadowrocket-config/main/rules/
```
→
```
https://cdn.jsdelivr.net/gh/DuskWander87/shadowrocket-config@main/rules/
```

文件路径保持不变。

## v2rayN 配置

基于同一份规则源（`rules/*.list`），通过构建脚本生成 v2rayN (Xray-core) 兼容的自定义路由规则 JSON。

### 订阅链接

在 v2rayN 中通过「从 URL 导入自定义路由规则」导入：

```
https://raw.githubusercontent.com/DuskWander87/shadowrocket-config/main/v2rayn/routing.json
```

### 分流策略

| 序号 | 策略 | 规则 | 说明 |
|----|---|---|---|
| 1  | block | UDP 443 | 阻断 QUIC，强制回落 TCP 走代理 |
| 2  | block | 自定义域名 | 来源 `rules/Reject.list` |
| 3  | direct | 自定义域名 | 来源 `rules/ChinaDirect.list` |
| 4  | block | geosite:category-ads-all | 广告拦截（geosite.dat 内置） |
| 5  | direct | geoip:private | 局域网 IP 直连 |
| 6  | direct | geosite:private | 局域网域名直连 |
| 7  | direct | geosite:cn | 国内域名直连（geosite.dat 内置） |
| 8  | direct | geoip:cn | 国内 IP 直连（geoip.dat 内置） |
| 9  | proxy | 0-65535 | 兜底全局代理 |

### 构建方式

修改 `rules/*.list` 后，运行构建脚本重新生成：

```bash
python v2rayn/build.py
```

输出文件 `v2rayn/routing.json`，推送后 v2rayN 下次刷新即生效。

### 关于 geosite.dat / geoip.dat

v2rayN 路由引擎通过本地 `geosite.dat` 和 `geoip.dat` 文件匹配域名和 IP，无需远程下载规则列表。这两个文件随 Xray-core 附带，v2rayN 会自动更新。数据来源：

- `geosite.dat` — [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) + [Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) 增强
- `geoip.dat` — [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip)（基于 MaxMind GeoLite2 + china-operator-ip）

## 许可证

仅供个人使用。规则集版权归 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) 所有。
