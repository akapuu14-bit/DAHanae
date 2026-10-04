# ナレッジ（部活コンシェルジュ）

このフォルダには、案件のナレッジ記事の正本（Markdown）を置く。索引は `01_ナレッジ/index.md`。

## 正本と閲覧用 HTML

| 正本（このフォルダ） | 閲覧用 HTML（Pages で配信） |
|---|---|
| `実践ナレッジ.md` | `docs/practice-knowledge.html` |

- 正本は `.md`。HTML は、開発ハブから読むための写し。
- 内容が食い違ったときは `.md` を正とする。

## 同期ルール

1. 内容を直すときは、先に `.md` を直す。
2. 同じ PR で `docs/practice-knowledge.html` にも同じ変更を入れる。`.md` だけ、HTML だけの PR にしない。
3. HTML にだけある要素（ナビ、開発ハブへの戻りリンク、デザイン）は、`.md` に持ち込まなくてよい。
4. PR を出す前に、下のコマンドで `.md` の本文が HTML に入っているかを確かめる。`missing: 0` なら同期できている。

```bash
python3 - <<'PY'
import re, html
norm = lambda s: re.sub(r"[^\w]", "", s)
h = open("docs/practice-knowledge.html", encoding="utf-8").read()
t = norm(html.unescape(re.sub(r"<[^>]+>", "", h[h.index("<main>"):])))
md = open("02_プロジェクト/bukatsu_concierge/ナレッジ/実践ナレッジ.md", encoding="utf-8").read()
miss = []
for line in md.splitlines():
    for c in (line.split("|") if line.startswith("|") else [line]):
        n = norm(re.sub(r"^\s*(\d+\.|[-*])\s+", "", c))
        if len(n) > 3 and n not in t:
            miss.append(c.strip())
print("missing:", len(miss))
print("\n".join(miss[:20]))
PY
```

このコマンドは `.md` → HTML の向きだけを確かめる（HTML にだけ足した文は検出しない）。リポジトリのルートで実行する。

## 新しい記事を足すとき

- 正本の `.md` をこのフォルダに置くか、HTML のみにするかを決め、`01_ナレッジ/index.md` に載せ、`01_ナレッジ/log.md` に記録する。
- `.md` を正本にする場合は、上の表に対応する HTML を追記する。
