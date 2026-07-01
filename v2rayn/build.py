"""
生成 v2rayN 自定义路由规则 JSON。

v2rayN 端与 Shadowrocket 端已解耦：不再引用 rules/*.list 的自定义拦截/直连，
仅使用 v2rayn/AllowList.list（直连白名单）+ Xray 内置 geosite/geoip 兜底。
白名单优先级高于广告拦截，用于从 category-ads-all 误伤中捞回功能性域名。

用法: python v2rayn/build.py
输出: v2rayn/routing.json
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
V2RAYN_DIR = Path(__file__).resolve().parent
ALLOWLIST_FILE = V2RAYN_DIR / "AllowList.list"
OUTPUT_FILE = V2RAYN_DIR / "routing.json"

# Shadowrocket 规则类型 -> v2rayN domain 前缀映射
DOMAIN_PREFIX_MAP = {
    "DOMAIN-SUFFIX": "domain:",
    "DOMAIN": "full:",
    "DOMAIN-KEYWORD": "keyword:",
}


def parse_list_file(filepath: Path) -> list[str]:
    """解析 .list 文件，提取域名并转换为 v2rayN 格式。"""
    domains = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 格式: RULE-TYPE,value
            match = re.match(r"^(DOMAIN-SUFFIX|DOMAIN|DOMAIN-KEYWORD),(.+)$", line)
            if match:
                rule_type, value = match.group(1), match.group(2)
                prefix = DOMAIN_PREFIX_MAP[rule_type]
                domains.append(f"{prefix}{value}")
    return domains


def build_routing_rules() -> list[dict]:
    """构建 v2rayN 路由规则 JSON 数组。

    链路顺序（first-match-wins，绝不可乱改）：
        阻断 QUIC → 直连白名单 → 广告拦截 → 局域网 → 国内域名 → 国内 IP → 兜底代理

    关键约束：
    - 直连白名单必须在广告拦截【之前】—— 否则被 category-ads-all 收录的功能域
      （如剪映客服 feedback-c.zijieapi.com）会先被拦，白名单形同虚设。
    - 兜底代理（0-65535）必须在最末 —— 它匹配一切流量，前移会吞掉后续所有规则。
    """
    rules = []

    # 1. 阻断 QUIC (UDP 443) - 强制回落 TCP 走代理
    rules.append({
        "port": "443",
        "network": "udp",
        "outboundTag": "block",
        "enabled": True,
        "remarks": "阻断 QUIC (UDP 443)",
    })

    # 2. 直连白名单 (AllowList.list -> direct)，优先级高于广告拦截
    if ALLOWLIST_FILE.exists():
        domains = parse_list_file(ALLOWLIST_FILE)
        if domains:
            rules.append({
                "port": "",
                "outboundTag": "direct",
                "domain": domains,
                "enabled": True,
                "remarks": "直连白名单 (DuskWander87/shadowrocket-config)",
            })

    # 3. 广告拦截
    rules.append({
        "port": "",
        "outboundTag": "block",
        "domain": ["geosite:category-ads-all"],
        "enabled": True,
        "remarks": "广告拦截",
    })

    # 4. 局域网直连
    rules.append({
        "port": "",
        "outboundTag": "direct",
        "ip": ["geoip:private"],
        "enabled": True,
        "remarks": "局域网 IP 直连",
    })
    rules.append({
        "port": "",
        "outboundTag": "direct",
        "domain": ["geosite:private"],
        "enabled": True,
        "remarks": "局域网域名直连",
    })

    # 5. 国内域名直连
    rules.append({
        "port": "",
        "outboundTag": "direct",
        "domain": ["geosite:cn"],
        "enabled": True,
        "remarks": "国内域名直连",
    })

    # 6. 国内 IP 直连
    rules.append({
        "port": "",
        "outboundTag": "direct",
        "ip": ["geoip:cn"],
        "enabled": True,
        "remarks": "国内 IP 直连",
    })

    # 7. 兜底代理
    rules.append({
        "port": "0-65535",
        "outboundTag": "proxy",
        "enabled": True,
        "remarks": "兜底全局代理",
    })

    return rules


def main():
    rules = build_routing_rules()
    OUTPUT_FILE.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    output_rel = OUTPUT_FILE.relative_to(REPO_ROOT)
    print(f"[OK] Generated {output_rel} ({len(rules)} rules)")
    for rule in rules:
        tag = rule["outboundTag"]
        domains = rule.get("domain", [])
        ips = rule.get("ip", [])
        parts = []
        if domains:
            parts.append(f"{len(domains)} domains")
        if ips:
            parts.append(f"{len(ips)} IPs")
        if rule.get("port") and not domains and not ips:
            parts.append(f"port {rule['port']}")
        if rule.get("network"):
            parts.append(f"network={rule['network']}")
        print(f"   - [{tag}] {', '.join(parts)} | {rule['remarks']}")


if __name__ == "__main__":
    main()
