# ナレッジ運用スキーマ

チームの学びを資産にする。毎回ゼロから調べ直さないための台帳。主担当は書記、記録は全員の責務。

## 構成

ナレッジは `01_ナレッジ/` に集約する。`02_プロジェクト/` には成果物（5文書・実装ガイド・コード）だけを置き、ナレッジの本体は置かない。

| 種類 | 場所 | 中身 |
|---|---|---|
| 台帳 | `01_ナレッジ/index.md` | 全記事の所在と要点の索引 |
| 台帳 | `01_ナレッジ/log.md` | 還元の記録 |
| 台帳 | `01_ナレッジ/README.md`（このファイル） | 運用スキーマと同期ルール |
| 記事の本体（汎用） | `01_ナレッジ/` 直下 | 複数の案件で再利用できる知見の正本（`.md`） |
| 記事の本体（案件固有） | `01_ナレッジ/<案件>/` | その案件にしか効かない知見の正本（`.md`） |

- 記事を探すときは、まず `index.md` を読む。本体がどこにあっても、`index.md` の「場所」列で辿れる。
- 閲覧用の HTML（`docs/` 配下、GitHub Pages で配信）を持つ記事は、下の「正本と閲覧用 HTML の同期」に従う。

## 置き分けルール

| 知見の種類 | 本体の置き場所 |
|---|---|
| 複数の案件で再利用できる汎用の知見 | `01_ナレッジ/` 直下 |
| 案件固有の知見 | `01_ナレッジ/<案件>/` サブフォルダ |

- どちらに置いた記事も、`index.md` に必ず登録する。
- 既存の記事のうち、次のものは今の場所のままとする。所在は `index.md` の「場所」列で示す。
  - HTML のみが本体の記事（`docs/be-cheatsheet.html`、`docs/supabase-setup-guide.html`）
  - `02_プロジェクト/bukatsu_concierge/実装ガイド/用語集.md`（実装ガイドの一部として issue・タスクバックログから参照されている）

## 記事の形式

新しい記事は、ファイル名を kebab-case にし、次の frontmatter を付けることを推奨する。

```
---
title: <何についての知見か>
type: knowledge | source | synthesis
origin: internal | external | mixed   # internal＝自分たちで確かめた
tags: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: []
---
```

相互参照は `[[wikilink]]`。日付は絶対表記。

既存の正本 `01_ナレッジ/実践ナレッジ.md` は、日本語のファイル名で frontmatter も無いが、現状のままでよい。このスキーマとの不整合とは扱わない。`type`・`origin`・更新日は `index.md` の列で補う。

## 正本と閲覧用 HTML の同期

| 正本 | 閲覧用 HTML（Pages で配信） |
|---|---|
| `01_ナレッジ/実践ナレッジ.md` | `docs/practice-knowledge.html` |

- 正本は `.md`。HTML は、開発ハブから読むための写し。内容が食い違ったときは `.md` を正とする。
- 同期の手順:
  1. 内容を直すときは、先に `.md` を直す。
  2. 同じ PR で HTML にも同じ変更を入れる。`.md` だけ、HTML だけの PR にしない。
  3. HTML にだけある要素（ナビ、開発ハブへの戻りリンク、デザイン）は、`.md` に持ち込まなくてよい。
  4. PR を出す前に、下のコマンドで `.md` の本文が HTML に入っているかを確かめる。`missing: 0` なら同期できている。
- `.md` を正本にした新しい記事に HTML を付けるときは、上の表に1行足す。

```bash
python3 - <<'PY'
import re, html
norm = lambda s: re.sub(r"[^\w]", "", s)
h = open("docs/practice-knowledge.html", encoding="utf-8").read()
t = norm(html.unescape(re.sub(r"<[^>]+>", "", h[h.index("<main>"):])))
md = open("01_ナレッジ/実践ナレッジ.md", encoding="utf-8").read()
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

## 操作
- **還元**: 案件の学び（詰まり・判断理由・失敗）を記事にする。手順は次の3つ。
  1. 記事の本体を置く（汎用なら `01_ナレッジ/` 直下、案件固有なら `01_ナレッジ/<案件>/`）。既存記事への追記でもよい。
  2. `index.md` に載せる（新規なら行を足し、追記なら要点と更新日を直す）。
  3. `log.md` に `## [YYYY-MM-DD] 還元 | <タイトル>` を追記する。
- **query**: まず `index.md` を読み、関連記事を辿って答える。
- **lint**: 矛盾・古い記事・孤立ページを点検する。`index.md` に載っていない記事も「孤立」に含める。

## 品質の目安
- 3 か月後の自分が読んで再現できるか。「なぜそうしたか」が書かれているか。
- 「やって駄目だったこと」も資産。
