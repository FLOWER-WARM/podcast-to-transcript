# -*- coding: utf-8 -*-
"""解析小宇宙单集页 -> 提取元数据与音频直链。
用法: python fetch_episode.py <episode_url> [out_json]
输出: JSON（标题/播客/主播/时长/发布时间/音频直链/shownotes 是否存在）
"""
import json
import re
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: fetch_episode.py <episode_url> [out_json]")
        return 1
    url = sys.argv[1]
    out_json = sys.argv[2] if len(sys.argv) > 2 else None

    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        print("ERROR: __NEXT_DATA__ not found (page may be walled)", file=sys.stderr)
        return 2
    ep = json.loads(m.group(1))["props"]["pageProps"]["episode"]
    info = {
        "eid": ep.get("eid"),
        "title": ep.get("title"),
        "podcast": (ep.get("podcast") or {}).get("title"),
        "author": (ep.get("podcast") or {}).get("author"),
        "duration_sec": ep.get("duration"),
        "pubDate": ep.get("pubDate"),
        "audio_url": (ep.get("enclosure") or {}).get("url"),
        "has_shownotes": bool((ep.get("shownotes") or "").strip()
                              and ep.get("shownotes") != "<p></p>"),
        "ai_summarize_allowed": any(
            p.get("name") == "AI_SUMMARIZE_EPISODE" and p.get("status") == "PERMITTED"
            for p in (ep.get("podcast") or {}).get("permissions", [])
        ),
        "url": url,
    }
    text = json.dumps(info, ensure_ascii=False, indent=2)
    print(text)
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
