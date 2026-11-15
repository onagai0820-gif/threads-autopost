# threads-autopost

いち（@ichi_souzouryoku）の Threads 予約投稿。毎日 17:00（セブ・香港時間）に GitHub Actions が `queue.json` の
`approved` の中から一番日付が古い1本を投稿する。

- 写真は `images/`（Threads で公開する写真だけを置く）
- 投稿後、`queue.json` の status が `posted` になる
