"""
网络连通性测试 — 检查 LLM API 端点是否可达（支持代理）
运行方法：python test_network.py
"""
import socket
import urllib.request
import urllib.error
import ssl
import time
import winreg  # 读取 Windows 代理设置（仅 Windows）

# ── 自动读取 Windows 代理设置 ──────────────────────────────────────
def get_windows_proxy():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if not enabled:
            return None
        proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        if proxy_server:
            if "://" not in proxy_server:
                proxy_server = "http://" + proxy_server
            return proxy_server
    except Exception:
        pass
    return None

WINDOWS_PROXY = get_windows_proxy()

# ── 测试函数 ───────────────────────────────────────────────────────
def test_https(url, proxy=None, timeout=8):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if proxy:
            handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        else:
            handler = urllib.request.ProxyHandler({})  # 强制不用系统代理
        opener = urllib.request.build_opener(handler, urllib.request.HTTPSHandler(context=ctx))
        req = urllib.request.Request(url, headers={"User-Agent": "connectivity-test/1.0"})
        start = time.time()
        with opener.open(req, timeout=timeout) as r:
            ms = int((time.time() - start) * 1000)
            return True, f"HTTP {r.status}  {ms}ms"
    except urllib.error.HTTPError as e:
        return True, f"HTTP {e.code}（网络通，服务端正常响应）"
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "timed out" in reason.lower():
            return False, "超时"
        return False, f"失败: {reason[:80]}"
    except Exception as e:
        return False, str(e)[:80]


TARGETS = [
    ("DeepSeek API",  "https://api.deepseek.com"),
    ("Anthropic API", "https://api.anthropic.com"),
    ("百度 (对照)",   "https://www.baidu.com"),
    ("Google (对照)", "https://www.google.com"),
]

print("=" * 60)
print("  ChaseBase 网络连通性测试")
print("=" * 60)

# ── 打印代理信息 ───────────────────────────────────────────────────
print(f"\n【检测到的 Windows 代理】")
if WINDOWS_PROXY:
    print(f"  ✅ 代理地址：{WINDOWS_PROXY}")
else:
    print(f"  ❌ 未检测到 Windows 代理设置")

# ── 不走代理直连 ───────────────────────────────────────────────────
print(f"\n【测试一】直连（不走代理）\n")
for name, url in TARGETS:
    ok, msg = test_https(url, proxy=None)
    status = "✅" if ok else "❌"
    print(f"  {status}  {name:<18} →  {msg}")

# ── 走 Windows 代理 ────────────────────────────────────────────────
if WINDOWS_PROXY:
    print(f"\n【测试二】走 Windows 代理 ({WINDOWS_PROXY})\n")
    for name, url in TARGETS:
        ok, msg = test_https(url, proxy=WINDOWS_PROXY)
        status = "✅" if ok else "❌"
        print(f"  {status}  {name:<18} →  {msg}")
else:
    print(f"\n【测试二】手动指定代理")
    proxy_input = input("  请输入公司代理地址（如 http://proxy.corp.com:8080），直接回车跳过：").strip()
    if proxy_input:
        print()
        for name, url in TARGETS:
            ok, msg = test_https(url, proxy=proxy_input)
            status = "✅" if ok else "❌"
            print(f"  {status}  {name:<18} →  {msg}")

# ── 结论 ───────────────────────────────────────────────────────────
print("\n【结论参考】")
print("  - 直连全 ❌ / 代理后 ✅  →  需要在 .env 里配置代理")
print("  - 直连和代理都 ❌       →  代理地址有误，或联系 IT 确认")
print("  - 直连 ✅               →  网络没问题，检查 API Key")
print("=" * 60)
print("\n如果代理后 DeepSeek ✅，请告诉我代理地址，我来帮你写进配置里。")
