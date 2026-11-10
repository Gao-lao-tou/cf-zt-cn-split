import os
import re
import requests

# ===== 配置区域 =====
DNS_SERVERS = ["223.5.5.5", "119.29.29.29"]  # 阿里、腾讯 DNS
DOMAIN_URL = "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/direct.txt"
MAX_DOMAINS = 2000  # Cloudflare 回退域名数量上限（保守值）
# ====================

def fetch_domains():
    """从 Loyalsoldier 拉取直连域名，过滤后返回前 N 条"""
    resp = requests.get(DOMAIN_URL, timeout=30)
    resp.raise_for_status()

    domains = []
    seen = set()

    for line in resp.text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # 严格过滤：只保留纯 ASCII 域名（字母、数字、连字符、点）
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$", line):
            continue

        # 排除下划线、通配符、中文等非法字符
        if "_" in line or "*" in line:
            continue

        if line not in seen:
            seen.add(line)
            domains.append(line)

    return domains[:MAX_DOMAINS]


def build_payload(domains):
    """构造 Cloudflare fallback_domains API 要求的请求体（直接数组）"""
    return [
        {
            "suffix": d,
            "description": "CN Direct Fallback",
            "dns_server": DNS_SERVERS,
        }
        for d in domains
    ]


def main():
    account_id = os.environ["CF_ACCOUNT_ID"]
    api_token = os.environ["CF_API_TOKEN"]
    policy_id = os.environ.get("CF_PROFILE_ID", "").strip()

    domains = fetch_domains()
    if not domains:
        raise RuntimeError("没有获取到任何有效域名，停止执行。")

    print(f"📦 准备同步 {len(domains)} 条回退域名")
    print(f"   前5条示例: {domains[:5]}")

    payload = build_payload(domains)

    if policy_id:
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
            f"/devices/policy/{policy_id}/fallback_domains"
        )
    else:
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
            f"/devices/policy/fallback_domains"
        )

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    # ⚠️ 必须是 PUT：它会用新列表完整替换旧列表
    resp = requests.put(url, headers=headers, json=payload, timeout=60)

    if not resp.ok:
        print(f"❌ 请求失败，状态码: {resp.status_code}")
        print(f"错误详情: {resp.text}")
        resp.raise_for_status()

    print(f"✅ 回退域名同步成功，共 {len(payload['domains'])} 条")
    print(f"   DNS 服务器: {DNS_SERVERS}")


if __name__ == "__main__":
    main()
