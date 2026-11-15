# -*- coding: utf-8 -*-
"""Threads のトークン（通行証）を新しいものに取りかえる（GitHub Actions から毎週実行）。

- 今のトークンを環境変数 THREADS_ACCESS_TOKEN から読む
- 新しいトークンを、引数で渡されたファイルに書く（画面には絶対に出さない）
- 新しい期限を token_status.json に書く（これは秘密ではないのでそのまま保存）

使い方: python refresh_token.py <新しいトークンを書くファイル>
"""
from __future__ import print_function
import datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CEBU = datetime.timezone(datetime.timedelta(hours=8))


def main():
    out = sys.argv[1]
    params = urllib.parse.urlencode({
        "grant_type": "th_refresh_token",
        "access_token": os.environ["THREADS_ACCESS_TOKEN"],
    })
    try:
        with urllib.request.urlopen("https://graph.threads.net/refresh_access_token?" + params, timeout=60) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        # エラー本文にトークンは含まれないが、念のため先頭だけ
        print("❌ 取りかえに失敗: HTTP %s %s" % (e.code, e.read().decode()[:300]))
        sys.exit(1)
    token = resp.get("access_token")
    if not token:
        print("❌ 取りかえに失敗: 新しいトークンが返ってこなかった")
        sys.exit(1)
    with open(out, "w") as f:
        f.write(token)
    now = datetime.datetime.now(CEBU)
    exp = now + datetime.timedelta(seconds=int(resp.get("expires_in", 5184000)))
    status = {
        "refreshed_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "expires_at": exp.strftime("%Y-%m-%d"),
        "note": "GitHub が毎週日曜に自動で取りかえている。expires_at が近づいているのに更新されていなければ、自動の取りかえが失敗している。",
    }
    with open(os.path.join(HERE, "token_status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("✅ 取りかえました。新しい期限: %s" % status["expires_at"])


if __name__ == "__main__":
    main()
