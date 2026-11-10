import os
import re
import requests

# ===== 配置区域 =====
DNS_SERVERS = ["223.5.5.5", "119.29.29.29"]  # 阿里、腾讯 DNS
DOMAIN_URL = "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/direct.txt"
# ====================

def fetch_domains():
    """从 Loyalsoldier 拉取直连域名，过滤后返回前 N 条"""
    resp = requests.get(DOMAIN_URL, timeout=30)
    resp.raise_for_status()
    domains = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 去重并过滤非法格式
        if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", line):
            if line not in domains:
                domains.append(line)
    # 回退域名列表也建议控制在 2000 条以内，与 API 返回的 total_count 暗示一致
    return domains[:2000]

def build_payload(domains):
    """构造 Cloudflare fallback_domains API 要求的请求体"""
    return [
        {
            "suffix": d,
            "description": "CN Direct Fallback",
            "dns_server": DNS_SERVERS
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

    payload = build_payload(domains)

    # 根据是否有 CF_PROFILE_ID 决定使用默认策略还是自定义策略的 API 端点
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
        "Content-Type": "application/json"
    }

    # ⚠️ 必须是 PUT：它会用新列表完整替换旧列表
    resp = requests.put(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()

    print(f"✅ 回退域名同步成功，共 {len(payload)} 条")
    print(f"   DNS 服务器：{DNS_SERVERS}")

if __name__ == "__main__":
    main()
