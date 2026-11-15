# -*- coding: utf-8 -*-
"""queue.json の「今日の分」を Threads に投稿する（GitHub Actions から毎日実行）。

- 投稿するのは status が "approved" で、date が今日（セブ時間）以前のものを1本だけ
- 画像は images/ に置き、raw.githubusercontent.com の公開URLで渡す（1枚=画像、2枚以上=カルーセル）
- reply があれば、投稿のあと自分の返信としてぶら下げる（リンク用）
- 終わったら queue.json に posted / thread_id を書き戻す（コミットは workflow 側）

必要な環境変数: THREADS_ACCESS_TOKEN, THREADS_USER_ID, GITHUB_REPOSITORY
  --dry   投稿せずに、今日投稿されるものを表示するだけ
"""
from __future__ import print_function
import datetime, json, os, sys, time, urllib.error, urllib.parse, urllib.request

API = "https://graph.threads.net/v1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "queue.json")
CEBU = datetime.timezone(datetime.timedelta(hours=8))


def call(method, path, params):
    params = dict(params, access_token=os.environ["THREADS_ACCESS_TOKEN"])
    data = urllib.parse.urlencode(params).encode()
    url = API + path
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s: %s" % (e.code, path, e.read().decode()[:400]))


def wait_ready(cid, limit=180):
    # コンテナの処理が終わるまで待つ（画像は数十秒かかることがある）
    t0 = time.time()
    while time.time() - t0 < limit:
        st = call("GET", "/%s" % cid, {"fields": "status,error_message"})
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError("コンテナ %s が %s: %s" % (cid, st.get("status"), st.get("error_message")))
        time.sleep(5)
    raise RuntimeError("コンテナ %s の処理が %d 秒で終わらなかった" % (cid, limit))


def image_url(name):
    repo = os.environ["GITHUB_REPOSITORY"]
    return "https://raw.githubusercontent.com/%s/main/images/%s" % (repo, urllib.parse.quote(name))


def publish(uid, item):
    imgs = item.get("images") or []
    text = item["text"]
    if not imgs:
        cid = call("POST", "/%s/threads" % uid, {"media_type": "TEXT", "text": text})["id"]
    elif len(imgs) == 1:
        cid = call("POST", "/%s/threads" % uid,
                   {"media_type": "IMAGE", "image_url": image_url(imgs[0]), "text": text})["id"]
    else:
        children = []
        for im in imgs:
            c = call("POST", "/%s/threads" % uid,
                     {"media_type": "IMAGE", "image_url": image_url(im), "is_carousel_item": "true"})["id"]
            wait_ready(c)
            children.append(c)
        cid = call("POST", "/%s/threads" % uid,
                   {"media_type": "CAROUSEL", "children": ",".join(children), "text": text})["id"]
    wait_ready(cid)
    tid = call("POST", "/%s/threads_publish" % uid, {"creation_id": cid})["id"]
    if item.get("reply"):
        time.sleep(10)
        rid = call("POST", "/%s/threads" % uid,
                   {"media_type": "TEXT", "text": item["reply"], "reply_to_id": tid})["id"]
        wait_ready(rid)
        call("POST", "/%s/threads_publish" % uid, {"creation_id": rid})
    return tid


def main():
    dry = "--dry" in sys.argv
    q = json.load(open(QUEUE, encoding="utf-8"))
    today = datetime.datetime.now(CEBU).strftime("%Y-%m-%d")
    due = [i for i in q["items"] if i.get("status") == "approved" and i["date"] <= today]
    if not due:
        print("今日（%s）投稿するものはありません。" % today)
        return
    item = sorted(due, key=lambda i: i["date"])[0]
    print("投稿するもの: %s（予定日 %s / 画像 %d 枚）" % (item["id"], item["date"], len(item.get("images") or [])))
    print(item["text"])
    if dry:
        for im in item.get("images") or []:
            print("  画像URL:", image_url(im) if os.environ.get("GITHUB_REPOSITORY") else im)
        return
    uid = os.environ["THREADS_USER_ID"]
    tid = publish(uid, item)
    item["status"] = "posted"
    item["thread_id"] = tid
    item["posted_at"] = datetime.datetime.now(CEBU).strftime("%Y-%m-%dT%H:%M:%S")
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("✅ 投稿しました: %s → %s" % (item["id"], tid))


if __name__ == "__main__":
    main()
