# munder セットアップ手順（DAHanae / 部活コンシェルジュ）

munder は、AI チーム（りじちょー＋スタッフ5名）の働く様子をオフィス画面で見られるデスクトップアプリです。中では Claude Code が動いています。
この手順では、**DAHanae のフォルダで りじちょー が返事をするところまで**進めます。所要時間は 30〜45 分です。

## 最初に：どの方法で進める？

AI チームの中身は、DAHanae に入っている `.claude/agents/*.md` と `CLAUDE.md` です。どの方法を選んでも、りじちょー＋スタッフ5名の役割と話し方は変わりません。

| あなたの状況 | 進め方 | 手間 |
| --- | --- | --- |
| 気軽に試したい／壁打ちやレビューに使いたいだけ | **[9. munder なしで試す](#9-munder-なしで試す)**（Claude Code だけ） | 5分 |
| Tech0 の munder 配布リポ（Private）への**招待を受けている** | **0〜7 の順に進める**（Tech0 版 munder。チームが自動で登録される） | 30〜45分 |
| 招待は受けていないが、オフィス画面を使いたい | **[10. 本家の munder で使う](#10-招待がない人本家の-munder-で使う)**（チームを手で登録する） | 45〜60分 |

招待を受けているか分からないときは、https://github.com/nonooktk/munder-difflin-tech0/releases を開いてみてください。ページが表示されれば招待済み、404 なら未招待です。

> **Tech0 版のインストーラー（dmg / exe）を、招待を受けていない人に渡さないでください。** 配布リポが Private なのは、運営が配る範囲を決めているためです。

## 全体の流れ（Tech0 版）

```
0. 前提を確認する（Claude Code・GitHub の招待）
1. DAHanae を手元に用意する
2. 案件資料を inputs/ に置く
3. munder をインストールする
4. 初回設定（STEP 1〜4）
5. りじちょーとスタッフが出たか確認して、2か所を直す
6. りじちょーに最初の指示を出す
7. 画面の使い方
```

---

## 0. 前提を確認する

| 確認すること | 確認の仕方 |
| --- | --- |
| Claude Code が入っていて、ログインしている | ターミナルで `claude --version` を実行してバージョンが出る。`claude` を一度起動してログインしておく |
| Claude のプランが Pro 以上 | claude.ai の設定で確認する |
| munder の配布リポへの招待を受けている | https://github.com/nonooktk/munder-difflin-tech0/releases を開いて、ページが表示される |

- munder の配布リポは **Private** です。ページが 404 になるときは、まだ招待を受けていません。Tech0 の参加者なら、Tech0 運営に Slack で GitHub のユーザー名を伝えて、招待してもらってください。Tech0 の参加者でなければ、[9](#9-munder-なしで試す) か [10](#10-招待がない人本家の-munder-で使う) で進めます。
- munder は中で `claude` コマンドを呼び出します。`claude --version` が動かない状態では、起動した後に止まってしまいます。

## 1. DAHanae を手元に用意する

### はじめて clone する人

Mac:
```bash
mkdir -p ~/GitHub && cd ~/GitHub && gh repo clone akapuu14-bit/DAHanae && cd DAHanae
```
Windows（PowerShell）:
```powershell
mkdir -Force "$HOME\GitHub"; cd "$HOME\GitHub"; gh repo clone akapuu14-bit/DAHanae; cd DAHanae
```

### すでに clone している人

```bash
git switch main && git pull
```

- PR #6（munder キットの導入）が **まだマージされていない** ときは、`git switch main` の代わりに `git fetch && git switch feature/munder-kit` を実行してください。
- 手元に `.claude/agents/rijicho.md` があれば準備完了です。munder はこのファイルを目印にして、チームを自動で登録します。

### DAHanae のフォルダのパスを控えておく

この後の手順で何度か使います。DAHanae のフォルダで次を実行し、表示されたパスをメモしてください。

Mac:
```bash
pwd
```
Windows:
```powershell
Get-Location
```

例: Mac `/Users/あなたの名前/GitHub/DAHanae`、Windows `C:\Users\あなたの名前\GitHub\DAHanae`
以下では、このパスを **`<DAHANAE>`** と書きます。

## 2. 案件資料を inputs/ に置く

企画書と要件定義書は **Git に入れていません**（社外秘の可能性があることと、ファイルが大きいため）。Slack で受け取って、次のフォルダに置いてください。

```
<DAHANAE>/02_プロジェクト/bukatsu_concierge/inputs/
```

- `.gitignore` で PDF と docx は除外しているので、ここに置いても commit されません。
- **Word（.docx）は PDF に書き出してから置いてください。** Claude Code は PDF ならそのまま読めますが、docx は読むのが苦手です。

## 3. munder をインストールする

https://github.com/nonooktk/munder-difflin-tech0/releases から **最新版（現在 v0.5.0）** をダウンロードします。

### Mac
1. `Munder-Difflin-0.5.0-mac-universal.dmg` をダウンロードして開く（Intel Mac と Apple シリコンのどちらでも使えます）
2. アイコンを「アプリケーション」フォルダにドラッグする
3. 初回は「開発元を確認できないため開けません」と表示されます。**アプリを右クリック → 開く → 開く** の順で開いてください。
   - それでも開けないときは、システム設定 → プライバシーとセキュリティ → 一番下の「このまま開く」を押します。

### Windows
1. `Munder-Difflin-0.5.0-win-x64-setup.exe` をダウンロードして実行する（インストール不要で使いたい場合は `-portable.exe` でも可）
2. 「Windows によって PC が保護されました」と表示されたら、「詳細情報」→「実行」を押します。

## 4. 初回設定（STEP 1〜4）

munder を起動すると、設定画面が順番に出てきます。

### STEP 1 · A HOME FOR THE APP（いちばん大事）

入力欄に最初から入っている `~/HarnessAgents` を消して、**`<DAHANAE>/.munder`** を貼り付けます。

```
例（Mac）    /Users/あなたの名前/GitHub/DAHanae/.munder
例（Windows） C:\Users\あなたの名前\GitHub\DAHanae\.munder
```

- フォルダが無くても munder が作ってくれるので、そのまま **next** を押して大丈夫です。
- 「create / pick」ボタンは使わないでください。Mac のフォルダ選択画面では、`.munder` のように `.` で始まるフォルダが表示されないためです。
- ここで `~/HarnessAgents` のまま進めると、りじちょーが DAHanae 以外の場所で働いてしまいます。
- `.munder/` は `.gitignore` に入っているので、Git には混ざりません。

### STEP 2 · YOUR CLONE（boss のエンジン）
- エンジン: **Claude Code**
- モデル: **Sonnet** を選んでください。画面には Opus が推奨と出ますが、Opus は使用量の上限に早く届きます。
- この画面で boss の名前が「Michael」と表示されていても問題ありません。STEP 1 のフォルダが正しければ、設定が終わったあとに Rijicho に変わります。

### STEP 3 · YOUR PROJECTS
- 「add a project」を押し、`<DAHANAE>`（`.munder` を付けない DAHanae のフォルダそのもの）を追加します。

### STEP 4 · PERMISSIONS & RELIABILITY

| 項目 | 設定 |
| --- | --- |
| LET AGENTS WORK ON THEIR OWN | **Off（チェックを外す）**。On にすると、AI が確認なしでファイルを変更したりコマンドを実行したりします |
| KEEP WORKING WHILE AWAY | Off のままで OK |
| DESKTOP NOTIFICATIONS | どちらでも OK（AI に呼ばれたとき気付きやすくなります） |
| OPEN AT LOGIN | Off のままで OK |
| SHARE ANONYMOUS USAGE STATS | 好みで選んでください（プロンプトやコードは送られません） |

最後に完了ボタンを押します。

## 5. りじちょーとスタッフが出たか確認して、2か所を直す

**成功した状態:** 画面下の列の左端に **「Rijicho（りじちょー）BOSS」** のカードがあり、数秒後に **Kurosu / Mi-rin / Takahiro / Terao / yamapi** の5人が席に着きます。

うまくいったら、次の2か所を直します。

1. **りじちょーのモデルを Sonnet にする**
   BOSS カードを選び、右上の **edit** でモデルを Sonnet に変えます。
2. **各エージェントの auto mode を切る**
   カードを選ぶと右側に TERMINAL が出ます。その下のほうに `▸▸ auto mode on` と表示されていたら、ターミナルをクリックして **Shift＋Tab** を何度か押し、この表示を消してください。6人それぞれで同じ操作が必要です。

うまくいかないとき:
- boss が「Michael」のままでスタッフも出てこない → STEP 1 のフォルダが違います。🔧 Settings → General → **Home folder** を `<DAHANAE>/.munder` に変えて、**fresh** を選んでください。

## 6. りじちょーに最初の指示を出す

1. 画面下の列から **BOSS カードをクリック**します（右下の入力欄が「Message Rijicho…」になります）。
2. 次の文の **`<DAHANAE>` 3か所をすべて自分のパスに置き換えて** 入力欄（QUEUE）に貼り、**send** を押します。

```
あなたはこのチームの boss「Rijicho（りじちょー）」です。まず <DAHANAE>/CLAUDE.md と <DAHANAE>/.claude/agents/rijicho.md を読み、以後その「仕事」と「話し方」に従ってください。作業フォルダは <DAHANAE> です（ハーネスのフォルダ .munder ではありません）。スタッフ（Takahiro / Mi-rin / Terao / Kurosu / yamapi）を起動するときは cwd を同じフォルダにし、objective に「最初に .claude/agents/<slug>.md と 00_ルール/スタッフ共通ブリーフィング.md を読んで、その役割として振る舞う」と書いてください。provider は claude、model は sonnet です。案件は「部活コンシェルジュ」で、文書の保存先は 02_プロジェクト/bukatsu_concierge/ です。別の worktree を作らず、同じフォルダで作業してください。読み終わったら、このチームの進め方を 5 行で答えてください。
```

数十秒後に、りじちょーが進め方を5行で返してくれればセットアップは完了です 🎉

次の頼み方の例:
```
りじちょー、02_プロジェクト/bukatsu_concierge/inputs の資料を読んで、要件の未決と質問を一覧にして
```

## 7. 画面の使い方

| 場所 | 使うとき |
| --- | --- |
| **QUEUE**（右下の入力欄） | ふだんの指示を出す。宛先は、画面下で**選んでいるカードの人**です |
| **TERMINAL**（右側の黒い部分） | カードが赤い **needs you** になったら、AI が質問して待っています。ここをクリックし、矢印キーで選んで Enter を押します |
| **steer**（上の細い入力欄） | 作業中のエージェントに一言だけ補足を伝える |

- 文書やコードは DAHanae の中の Markdown とファイルです。作業の進み具合は `git status` で確認できます。
- 決めたことを残すときは、ふだんどおり **ブランチ → PR → レビュー → マージ** で進めます。munder を閉じても、文書は DAHanae に残ります。

## 8. すでに別のリポで munder を使っている人

例えば Tech0 の tech0-ballon-a などで、すでに munder を使っている人向けの手順です。

1. 🔧 Settings → General → **Home folder** を `<DAHANAE>/.munder` に変える
2. 「move / fresh」と聞かれたら **fresh** を選ぶ（元のリポの台帳は残ります）
3. 元のリポに戻るときは、Home folder を元の `.munder` に戻す

## 9. munder なしで試す

オフィス画面が無いだけで、同じ AI チームが動きます。いちばん手軽な方法です。

```bash
cd <DAHANAE>
claude
```
```
りじちょー、CLAUDE.md と 00_ルール を読んで、このチームの進め方を 5 行で教えて
```

## 10. 招待がない人：本家の munder で使う

本家の munder（[chaitanyagiri/munder-difflin](https://github.com/chaitanyagiri/munder-difflin)、MIT ライセンスで公開）を使い、りじちょーとスタッフを **手で登録** します。

Tech0 版との違い:
- りじちょーとスタッフは自動では登録されません。boss の名前変更と、スタッフ5名の読み込み（Import hire）を自分で行います。
- 見た目（ドット絵）は本家のキャラクターです（boss = Michael、Kurosu = Angela など）。**役割と話し方は同じ**です（定義ファイルを読ませるため）。

> この節は、Tech0 版 munder の手順と共通の定義ファイル（`munder/hires/*.json`、本家と同じ `munder-difflin/hire@1` 形式）をもとに書いています。本家 munder での動作はまだ試していません。画面の表示が違ったら、Slack で教えてください。

### 10.1 本家 munder をインストールする

https://github.com/chaitanyagiri/munder-difflin/releases から最新版（現在 v0.5.2）をダウンロードします。

| OS | ファイル |
| --- | --- |
| Mac | `Munder-Difflin-0.5.2-mac-universal.dmg` |
| Windows | `Munder-Difflin-0.5.2-win-x64-setup.exe` |

インストールの仕方（右クリック → 開く、SmartScreen の「詳細情報 → 実行」）は、[3.](#3-munder-をインストールする) と同じです。

### 10.2 初回設定

1〜2（DAHanae の用意、inputs への資料配置）を済ませてから、[4.](#4-初回設定step-14) と同じ設定をします。STEP 1 は `<DAHANAE>/.munder`、モデルは Sonnet、auto mode は Off です。
設定が終わると、boss は「Michael」のまま表示され、スタッフはいません。これは本家版の正常な状態です。

### 10.3 boss を Rijicho にする

1. 画面下の列の左端にある **「M… ✎ BOSS」** の鉛筆アイコン（✎）を押し、名前を `Rijicho` に変えて保存します（変わるのは表示名だけです）。
2. BOSS カードを選び、右上の **edit** でモデルを Sonnet にします。
3. TERMINAL に `▸▸ auto mode on` と表示されていたら、**Shift＋Tab** を押して消します。

### 10.4 スタッフ5名の定義ファイルを用意する

`munder/hires/*.json` の中にある `<KIT_PATH>` を、自分の DAHanae のパスに置き換えます。
パスは人によって違うので、元のファイルは書き換えずに、**Git に入らない `.munder/hires/` にコピーしてから置き換えます。**

DAHanae のフォルダで実行します。

Mac:
```bash
mkdir -p .munder/hires && cp munder/hires/*.json .munder/hires/ && sed -i '' "s#<KIT_PATH>#$(pwd)#g" .munder/hires/*.json && grep -c "<KIT_PATH>" .munder/hires/*.json
```

Windows（PowerShell）:
```powershell
$p = (Get-Location).Path -replace '\\','/'
New-Item -ItemType Directory -Force .munder\hires | Out-Null
Get-ChildItem munder\hires\*.json | ForEach-Object {
  $t = [IO.File]::ReadAllText($_.FullName) -replace '<KIT_PATH>', $p
  [IO.File]::WriteAllText((Join-Path (Resolve-Path .munder\hires) $_.Name), $t)
}
Select-String -Path .munder\hires\*.json -Pattern '<KIT_PATH>'
```

- Mac では、6ファイルすべてに `:0` と表示されれば置き換えは完了です。Windows では、何も表示されなければ完了です。
- Windows のパスは `/` 区切りに変えています（例 `C:/Users/名前/GitHub/DAHanae`）。`\` のままだと JSON として読めなくなるためです。

### 10.5 スタッフ5名を読み込む（Import hire）

Import hire はファイルの URL を指定する方式なので、手元で一時的にファイルを配信します。**新しいターミナル**を開き、DAHanae のフォルダで次を実行します。

Mac:
```bash
cd .munder/hires && python3 -m http.server 8765
```
Windows:
```powershell
cd .munder\hires; python -m http.server 8765
```

munder に戻り、次の手順を **5人分** 繰り返します。

1. 画面右下の **＋**（Add agent）を押す
2. **import hire…** を選び、URL に `http://localhost:8765/takahiro.json` を入力する
3. 読み込まれた内容を確認します。名前・モデル（sonnet）・作業フォルダが `<DAHANAE>` になっているかを見て、違っていたら直します。
4. **spawn** を押す

| 5人の URL |
| --- |
| `http://localhost:8765/takahiro.json` |
| `http://localhost:8765/mirin.json` |
| `http://localhost:8765/terao.json` |
| `http://localhost:8765/kurosu.json` |
| `http://localhost:8765/yamapi.json` |

- `rijicho.json` は読み込みません。boss（10.3 で名前を変えたカード）が りじちょー になります。
- 5人を読み込んだら、配信しているターミナルで **Ctrl＋C** を押して止めます。
- 読み込んだスタッフの TERMINAL にも `auto mode on` と出ていたら、**Shift＋Tab** で消します。
- Windows で `python` が見つからないときは、Microsoft Store の Python を入れるか、`npx http-server -p 8765` で配信します（Node.js が必要）。

### 10.6 最初の指示

[6.](#6-りじちょーに最初の指示を出す) と同じ文を、BOSS カードの QUEUE に貼って send します。進め方の5行が返ってくれば完了です。

スタッフに自分から仕事を振ってもらいたい場合は、🔧 Settings → Autonomy & Budgets → **Who can add agents** を「me and Rijicho」にし、予算上限（tokenCap）を入れて保存します。

## 11. 注意

- **使用量:** munder では、りじちょーとスタッフ5人が同時に Claude を使います。Pro プランだと上限に早く届くので、使わない時間は munder を閉じておきましょう。
- **ルールは Tech0 向けのまま:** `00_ルール/` や `CLAUDE.md` は Tech0 の講座用の内容（V字フロー、W0〜W4、「運営に相談」など）です。りじちょーが「運営に確認して」と言ってきたら、それは Tech0 向けのルールが残っているためです。合わないところは、チームで相談して書き換えて構いません（書き換えも PR で行います）。
- **commit しないもの:** `.env`、`.munder/`、inputs の PDF / docx は、`.gitignore` で除外済みです。

## 困ったとき

| 出た表示 | 直し方 |
| --- | --- |
| Releases のページが 404 | 招待を受けていません。Tech0 運営に GitHub のユーザー名を伝える |
| Mac「開発元を確認できないため開けません」 | 右クリック → 開く |
| Windows「PC が保護されました」 | 詳細情報 → 実行 |
| `claude: command not found` | Claude Code を入れ、ターミナルで `claude --version` が動くのを確認してから munder を再起動する |
| 「Not logged in」「ログインしてください」 | ターミナルで `claude` を起動してログインし、munder を再起動する |
| boss が Michael、スタッフが出ない | 5. の「うまくいかないとき」を参照 |
| りじちょーが英語で返す／CLAUDE.md が見つからない | 6. の指示文で `<DAHANAE>` の置き換えを間違えています |
| 画面が真っ白 | 5 秒待つ。変わらなければ munder を閉じて起動し直す |
| `Rate limit` / `usage limit` | Claude の使用量の上限です。表示された時刻まで待つ |

分からないことがあれば、Slack で気軽に聞いてください。
