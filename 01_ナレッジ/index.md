# ナレッジ索引

作業前にここを読み、関連する記事を辿る。各記事の本体は「場所」にある（この索引は所在と要点だけを持つ）。

## 部活コンシェルジュ（bukatsu_concierge）

| タイトル | 場所（正本） | 種別 | origin | 要点 | 更新 |
|---|---|---|---|---|---|
| Munder Difflinでチーム開発を回す実践知 | `02_プロジェクト/bukatsu_concierge/ナレッジ/実践ナレッジ.md`（閲覧用: `docs/practice-knowledge.html`） | synthesis | internal | ハイブ運用・V字・並行開発・進捗基盤・ハマりどころ・チェックリスト（立ち上げ期 2026-09-27〜28 の記録。5.8〜5.15 に 2026-10-01〜04 の失敗と学びを追記） | 2026-10-04 |
| だーあさのBE実装チートシート（Wave0/1/2） | `docs/be-cheatsheet.html`（HTML のみ） | knowledge | internal | 層構成、Supabase・Secrets、repository の書き方（I-F契約 0.4・2層エスケープ・日付境界）、service の書き方（順序・TZ・ソート・集約）、Issue 対応マップ、用語ミニ辞典 | 2026-10-04 |
| Supabaseセットアップ共有会 | `docs/supabase-setup-guide.html`（HTML のみ） | knowledge | internal | 共有 DB と Secrets の仕組み、安全な設定手順 | 2026-09-29 |
| 部活コンシェルジュ 用語集（開発初心者向け） | `02_プロジェクト/bukatsu_concierge/実装ガイド/用語集.md` | knowledge | internal | 層・I-F契約・受入基準・Wave・ID記法・PR/ブランチ/マージ・CHECK制約 | 2026-10-03 |

### 正本の置き方
- 実践ナレッジは `.md` が正本、HTML は閲覧用の写し。同期ルールは `02_プロジェクト/bukatsu_concierge/ナレッジ/README.md`。
- BE実装チートシートと Supabaseセットアップ共有会は HTML が唯一の本体（BE実装チートシートは #87 で .md を HTML に移管）。
