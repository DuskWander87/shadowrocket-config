"""
将 rules/*.list (Shadowrocket 格式) 转换为 v2rayN 自定义路由规则 JSON。

用法: python v2rayn/build.py
输出: v2rayn/routing.json
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = REPO_ROOT / "rules"
OUTPUT_FILE = Path(__file__).resolve().parent / "routing.json"

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
    """构建 v2rayN 路由规则 JSON 数组，对齐 Shadowrocket 完整分流策略。"""
    rules = []

    # 1. 阻断 QUIC (UDP 443) - 强制回落 TCP 走代理
    rules.append({
        "port": "443",
        "network": "udp",
        "outboundTag": "block",
        "enabled": True,
        "remarks": "阻断 QUIC (UDP 443)",
    })

    # 2. 自定义拦截 (Reject.list -> block)
    reject_file = RULES_DIR / "Reject.list"
    if reject_file.exists():
        domains = parse_list_file(reject_file)
        if domains:
            rules.append({
                "port": "",
                "outboundTag": "block",
                "domain": domains,
                "enabled": True,
                "remarks": "自定义拦截 (DuskWander87/shadowrocket-config)",
            })

    # 3. 广告拦截
    rules.append({
        "port": "",
        "outboundTag": "block",
        "domain": ["geosite:category-ads-all"],
        "enabled": True,
        "remarks": "广告拦截",
    })

    # 4. 自定义直连 (ChinaDirect.list -> direct)
    direct_file = RULES_DIR / "ChinaDirect.list"
    if direct_file.exists():
        domains = parse_list_file(direct_file)
        if domains:
            rules.append({
                "port": "",
                "outboundTag": "direct",
                "domain": domains,
                "enabled": True,
                "remarks": "自定义直连 (DuskWander87/shadowrocket-config)",
            })

    # 5. 局域网直连
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

    # 6. 国内域名直连
    rules.append({
        "port": "",
        "outboundTag": "direct",
        "domain": ["geosite:cn"],
        "enabled": True,
        "remarks": "国内域名直连",
    })

    # 7. 国内 IP 直连
    rules.append({
        "port": "",
        "outboundTag": "direct",
        "ip": ["geoip:cn"],
        "enabled": True,
        "remarks": "国内 IP 直连",
    })

    # 8. 兜底代理
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
