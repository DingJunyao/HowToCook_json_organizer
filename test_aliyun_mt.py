#!/usr/bin/env python
# test_aliyun_mt.py
"""阿里云机器翻译 API 独立验证脚本。

用法:
  python test_aliyun_mt.py ACCESS_KEY_ID ACCESS_KEY_SECRET
  或设置环境变量 ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET 后直接运行。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid


HOST = "mt.cn-hangzhou.aliyuncs.com"
ENDPOINT = f"https://{HOST}"
ACTION = "TranslateGeneral"
API_VERSION = "2018-10-12"


def sign_v3(method: str, host: str, query_params: dict[str, str],
            access_key_id: str, access_key_secret: str) -> dict[str, str]:
    """构造阿里云 V3 签名，返回需要附加到请求的 headers。"""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    nonce = str(uuid.uuid4())
    # 空 body 的 SHA256
    hashed_payload = hashlib.sha256(b"").hexdigest()

    # 参与签名的 headers（小写键名，按字母排序）
    sign_headers: dict[str, str] = {
        "content-type": "application/json; charset=utf-8",
        "host": host,
        "x-acs-action": ACTION,
        "x-acs-content-sha256": hashed_payload,
        "x-acs-date": now,
        "x-acs-signature-nonce": nonce,
        "x-acs-version": API_VERSION,
    }
    sorted_keys = sorted(sign_headers.keys())
    signed_headers_str = ";".join(sorted_keys)
    canonical_headers = "".join(
        f"{k}:{sign_headers[k].strip()}\n" for k in sorted_keys
    )

    # 规范化查询字符串
    canonical_qs = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(query_params.items())
    )

    # 规范化请求
    canonical_request = (
        f"{method}\n/\n{canonical_qs}\n"
        f"{canonical_headers}\n{signed_headers_str}\n{hashed_payload}"
    )

    # 待签名字符串
    string_to_sign = (
        f"ACS3-HMAC-SHA256\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    # HMAC-SHA256 签名
    signature = hmac.new(
        access_key_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    authorization = (
        f"ACS3-HMAC-SHA256 "
        f"Credential={access_key_id},"
        f"SignedHeaders={signed_headers_str},"
        f"Signature={signature}"
    )

    return {
        **sign_headers,
        "Authorization": authorization,
    }


def translate(source_text: str, source_lang: str = "en", target_lang: str = "zh") -> None:
    """发送一次翻译请求并打印完整的请求/响应信息。"""
    ak_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ALIYUN_ACCESS_KEY_ID", "")
    ak_secret = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")

    if not ak_id or not ak_secret:
        print("错误: 请提供 AccessKey ID 和 Secret（命令行参数或环境变量）")
        sys.exit(1)

    # RPC 风格：参数放在查询字符串
    query_params: dict[str, str] = {
        "Action": ACTION,
        "Version": API_VERSION,
        "FormatType": "text",
        "SourceLanguage": source_lang,
        "TargetLanguage": target_lang,
        "SourceText": source_text,
        "Scene": "general",
    }

    qs = urllib.parse.urlencode(query_params)
    url = f"{ENDPOINT}/?{qs}"

    headers = sign_v3("POST", HOST, query_params, ak_id, ak_secret)

    # ---- 调试输出 ----
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Method: POST")
    print("Headers:")
    for k, v in headers.items():
        # 隐藏 Secret
        val = v if "Signature" not in k else v[:30] + "..."
        print(f"  {k}: {val}")
    print("=" * 60)

    req = urllib.request.Request(url, data=b"", method="POST")
    for k, v in headers.items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
        print(f"\nHTTP {status}")
        print("Response:")
        try:
            data = json.loads(body)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            translated = data.get("Data", {}).get("Translated", "")
            if translated:
                print(f"\n翻译结果: {source_text!r} → {translated!r}")
        except json.JSONDecodeError:
            print(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"\nHTTP {e.code} {e.reason}")
        print("Response:")
        print(body)
    except Exception as e:
        print(f"\n请求异常: {e}")


if __name__ == "__main__":
    translate("Butter, salted")
