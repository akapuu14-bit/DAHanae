# GitHub管理セットアップ手順（部活コンシェルジュ）

作成：Terao（バックエンド・DB担当）
対象リポジトリ：`akapuu14-bit/DAHanae`

このドキュメントは T-007（GitHub純正のIssue/Project/Milestone/Label、Actions→Pagesダッシュボード自動更新）の
実行手順です。ファイル一式の作成まではTeraoが行いました。ここから先（gh実行・Pages有効化）は人間側の作業です。

## 0. できあがるもの

- **段階1**：GitHub純正のLabel・Milestone・seed Issueのセットアップ資材（`scripts/setup_github.sh`）
- **段階2**：Issue/PRの状態を集計し、担当者別・Milestone別の進捗をHTMLダッシュボードとしてGitHub Pagesに自動公開する仕組み
  （`.github/workflows/dashboard.yml` + `scripts/gen_dashboard.py`）

## 1. gh CLI のインストールと認証

まだ未インストールとのことなので、以下のいずれかで導入してください。

```bash
# macOS（Homebrew）
brew install gh

# 確認
gh --version
```

インストール後、認証します（ブラウザでログインする方式が簡単です）。

```bash
gh auth login
# ? What account do you want to log into? → GitHub.com
# ? What is your preferred protocol? → SSH（このリポジトリのremoteがSSHのため）
# ? Authenticate Git with your GitHub credentials? → Yes
# ? How would you like to authenticate? → Login with a web browser
```

認証できているかは次で確認できます。

```bash
gh auth status
```

## 2. Label・Milestone・Issueの作成（段階1）

リポジトリのルートで実行します。再実行しても、既存のLabel/Milestone/Issueがあれば作り直さずスキップするので、
何度流しても壊れません。

```bash
chmod +x scripts/setup_github.sh
./scripts/setup_github.sh
```

作られるもの：

- Label：`area:be` `area:ui` `area:pdm` `type:feature` `type:bug` `prio:high` `prio:mid` `prio:low`
- Milestone（実装計画.md R-48のスケジュール3節）：
  - `〜9/29 アプリのカタチ`（due: 2026-09-29）
  - `〜10/2 8割`（due: 2026-10-02）
  - `10/7-12 最終`（due: 2026-10-12）
- Seed Issue：実装計画.md 2章「実装順序（マイルストーン）」のW3-1〜W3-4を、そのままIssue化したもの（計12件）

> **保留**：seed Issueのmilestone・assigneeは、実装計画.mdに「どのIssueをどのMilestoneに入れるか」の明記が
> なかったため、スクリプト側では設定していません。GitHub Projects上でPM（はなえ）が割り振ってください。

## 3. GitHub Projectsボードの作成

1. リポジトリの `Projects` タブ → `New project` → `Board` を選択
2. カラム例：`Todo` / `Doing` / `Blocked` / `Done`（hiveのtasks.jsonの並びに合わせています）
3. 作成したLabelでフィルタしたビューを作ると、領域（BE/UI/PdM）ごとの状況が見やすくなります

### Issue↔PRの自動連携（自動クローズ・ボード自動更新）

PRの説明文に次のように書くと、そのPRがマージされたとき対象Issueが自動でCloseされ、Projectボードも
自動的に `Done` に動きます（GitHub純正機能）。

```
Closes #12
```

複数Issueをまとめて閉じたい場合は改行して並べます。

```
Closes #12
Closes #15
```

## 4. GitHub Pagesの有効化（段階2）

1. リポジトリの `Settings` → `Pages`
2. `Build and deployment` の `Source` を **`GitHub Actions`** に変更
3. 保存すると、`.github/workflows/dashboard.yml` が次のタイミングで自動実行されます：
   - Issueの作成・クローズ・編集・再オープン
   - PRの作成・クローズ（マージ含む）・編集・再オープン
   - `main`ブランチへのpush
   - 毎日1回（UTC 21:00 = 日本時間 朝6:00）
   - 手動実行（`Actions`タブ → `dashboard` → `Run workflow`）
4. 初回実行後、`Settings → Pages` に表示されるURLでダッシュボードが見られます

### 動作確認のしかた

```bash
# 手動でワークフローを起動する場合
gh workflow run dashboard.yml

# 実行状況の確認
gh run list --workflow=dashboard.yml
gh run view --log
```

ローカルで生成結果だけ試したい場合（Pagesには公開されません）：

```bash
export GITHUB_TOKEN=$(gh auth token)
export GITHUB_REPOSITORY=akapuu14-bit/DAHanae
python3 scripts/gen_dashboard.py
open site/index.html   # macOS
```

### ダッシュボードの見方

- **担当者別カード**：GitHub上のassignee（ログイン名）ごとに、Issue+PRの完了/未完了件数と進捗%、
  領域ラベル（BE/UI/PdM）の内訳を表示します。担当者名はハードコードしておらず、実際にassignされた人が
  自動で並びます。
- **Milestone進捗バー**：各Milestoneに紐づくIssue/PRの完了割合を表示します。
- **直近マージ済みPR**：マージ済みPRを新しい順に最大10件表示します。

## 5. 秘匿値について

`.github/workflows/dashboard.yml` は Actions が自動発行する `GITHUB_TOKEN`（Secrets経由）のみを使用します。
個人アクセストークンやAPIキーの登録・コミットは不要です。

## 6. 保留（PM判断が必要な点）

- seed Issueへのmilestone紐付け（上記2章参照）
- seed Issueのassignee（あかぷ／だーあさ／はなえの実際のGitHubアカウント名が未確認のため空欄にしています）
- Projectボードのビュー構成（カラム名・自動化ルール）は本手順書のたたき台以外、未確定です
