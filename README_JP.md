# マルチギルド対応 運営＆経済Bot

Discordチャンネルをデータベースとして活用する（DaaB: Discord-as-a-Database）、マルチギルド対応の運営・経済Botです。Renderなどの再起動時にデータが消えてしまう環境でも、Discord上にデータが保存されるため、ステートレスに運用可能です。

## 主な機能

- **Discord-as-a-Database (DaaB)**: 隠しチャンネルにJSONファイルを投稿することでデータを永続化。外部DB不要。
- **経済システム**: `/balance`, `/daily`, `/work`, `/pay`, `/leaderboard`。
- **ショップ**: 商品登録（`/product-add`）、購入（`/buy`）、在庫管理、注文履歴、払い戻し。
  - ロールの自動付与や、DMでのファイル/キー配布に対応。
- **レベルシステム**: メッセージ送信によるXP獲得、レベルアップ通知。倍率設定可能。
- **ギャンブル**: `/coinflip`, `/slot`。税金徴収機能付き。
- **管理・監査**: 管理者向けコマンド、監査ログ（`/set-audit-channel`）、通貨名・税率の設定。

## セットアップ手順

### 1. Discord Botの作成
1. [Discord Developer Portal](https://discord.com/developers/applications) で新しいアプリケーションを作成します。
2. **Bot** セクションで **Privileged Gateway Intents** の以下の3つをすべてONにします：
   - Presence Intent
   - Server Members Intent
   - Message Content Intent
3. Botのトークンをコピーしておきます。

### 2. 環境変数の設定
プロジェクトのルートに `.env` ファイルを作成し、トークンを設定します：
```env
DISCORD_TOKEN=あなたのBotトークン
```

### 3. デプロイ (Render)
このBotは Render の **Background Worker** または **Web Service** で動作します。

1. GitHub リポジトリを Render に接続します。
2. `Environment Variables` に `DISCORD_TOKEN` を追加します。
3. Renderが `Dockerfile` を自動的に検出し、ビルドとデプロイを行います。

## コマンド一覧

### ユーザー向け
- `/balance`: 残高・XPの確認
- `/daily`: 1日1回のボーナス
- `/work`: 1時間ごとの報酬
- `/pay`: 他のユーザーへの送金（税金が発生します）
- `/shop`: 商品一覧の表示
- `/buy`: 商品の購入
- `/inventory`: 購入済みアイテムの確認
- `/leaderboard`: ランキング表示
- `/coinflip`: コインポスで賭け
- `/slot`: スロットマシンで賭け

### 管理者向け
- `/setup`: データベース用チャンネルの初期設定
- `/set-currency-name`: 通貨名の設定
- `/set-tax`: 税率（%）の設定
- `/config-xp`: XP獲得倍率の設定
- `/set-audit-channel`: 監査ログ送信先チャンネルの設定
- `/product-add`: 商品の追加
- `/product-edit`: 商品の編集
- `/product-remove`: 商品の削除
- `/give`: 指定ユーザーに通貨を付与
- `/orders`: 注文履歴の表示
- `/refund`: 注文の払い戻し
- `/audit-logs`: 過去の監査ログの表示

## 技術的な注意点
- データの保存は5分おき、または重要なアクション（購入・送金など）の直後に行われます。
- Discordのレート制限を避けるため、メッセージごとのXP保存はバックグラウンドで一括処理されます。
- 各サーバーで最初に `/setup` を実行して、データ保存用のカテゴリとチャンネルを作成してください。
