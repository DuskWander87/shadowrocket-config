# Shadowrocket 防 DNS 泄露配置

基于 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) 规则集的 Shadowrocket 配置文件，国内 UDP + 境外 DoH 混合策略，兼顾防泄露与 CDN 调度精准。

## 订阅链接

复制以下任一链接到 Shadowrocket 进行订阅。

**raw.githubusercontent.com（权威源）：**

```
https://raw.githubusercontent.com/Duskwander87/shadowrocket-config/main/shadowrocket.conf
```

**jsDelivr CDN（国内推荐，速度更快）：**

```
https://cdn.jsdelivr.net/gh/Duskwander87/shadowrocket-config@main/shadowrocket.conf
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

### 分流策略

| 类型 | 处理 | 来源 |
|---|---|---|
| 局域网 / 解禁名单 | DIRECT | ACL4SSR LocalAreaNetwork / UnBan |
| 广告域名 | REJECT | ACL4SSR BanAD / BanProgramAD |
| 国内域名 / 流媒体 | DIRECT | ACL4SSR ChinaDomain / ChinaMedia |
| 国内 IP / 国内企业 IP | DIRECT | ACL4SSR ChinaIp / ChinaCompanyIp |
| `GEOIP,CN` | DIRECT | 内置 GeoIP |
| 其他 | PROXY | FINAL 兜底 |

## 维护

### 规则集同步

所有 `RULE-SET` 都引用 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) 仓库的远程文件，**上游一更新，下次 Shadowrocket 刷新订阅时自动同步**。无需手动维护规则列表。

### 修改配置

直接编辑 `shadowrocket.conf` 并推送到本仓库，Shadowrocket 下次刷新订阅即生效。

### 切换 CDN 源

如发现 `raw.githubusercontent.com` 在国内拉取失败，临时改用 jsDelivr 订阅链接即可。如需让配置文件内部的 `RULE-SET` 也走 jsDelivr，把所有：

```
https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/
```

替换为：

```
https://cdn.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/
```

文件路径保持不变。

## 安全说明

- 本配置文件不含任何节点信息、token、密码或个人数据
- 代理节点请在 Shadowrocket App 内单独管理，不要写入本仓库
- 即使仓库公开，配置文件被任意他人获取也无安全影响

## 许可证

仅供个人使用。规则集版权归 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) 所有。
