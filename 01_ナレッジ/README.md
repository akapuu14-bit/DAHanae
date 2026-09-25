# ナレッジ運用スキーマ

チームの学びを資産にする。毎回ゼロから調べ直さないための台帳。主担当は書記、記録は全員の責務。

## 記事の形式
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
ファイル名は kebab-case。相互参照は `[[wikilink]]`。日付は絶対表記。

## 操作
- **還元**: 案件の学び（詰まり・判断理由・失敗）を記事にする。`log.md` に `## [YYYY-MM-DD] 還元 | <タイトル>` を追記し、`index.md` に載せる。
- **query**: まず `index.md` を読み、関連記事を辿って答える。
- **lint**: 矛盾・古い記事・孤立ページを点検する。

## 品質の目安
- 3 か月後の自分が読んで再現できるか。「なぜそうしたか」が書かれているか。
- 「やって駄目だったこと」も資産。
