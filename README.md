# TimeTable

茨木〜神戸方面のCSV時刻表を検索し、行き・帰りをダイヤグラムで表示する、本人専用のFlaskアプリです。Python 3.10以上を使用します。

## 教室でcloneしてローカル起動する

Windows / PowerShell（Python・Git導入済み）：

```powershell
git clone https://github.com/mappoll/TimeTable.git
cd TimeTable
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
'TIMETABLE_AUTH_ENABLED=0' | Set-Content -Encoding utf8 .env
.\.venv\Scripts\python.exe -m flask --app app run --port 5050
```

ブラウザで http://127.0.0.1:5050/ を開きます。停止はCtrl+C。
作成済みの環境では最後のコマンドで再起動できます。
`.env` はソースフォルダから `load_dotenv(override=False)` で読み、OS環境変数を優先します。
上の例は新規clone時の手順です。既存の本番設定ファイルを上書きしないでください。

自宅LANのスマホ確認は、信頼できるLAN内で認証OFFにして起動します：

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --host 0.0.0.0 --port 5050
```

スマホは同じLANから `http://PCのLANアドレス:5050/` へアクセスします。
LAN IPのHTTPでWebAuthnは使用しません。認証OFFではダイヤを閲覧できるため、本番公開にこの設定を使わないでください。
認証OFFは文字列 `0` の場合だけです。未設定・空欄・`false` などはすべて認証ONになります。

## スマホUIとダイヤ操作

- 左固定駅名軸・角のカバーを削除しました。駅名は各駅箱で確認します。
- `templates/index.html` の `DIAGRAM_LEFT_PADDING = 18` を時間線、駅横線、列車線、駅箱、希望到着線の共通基準としています。
  JavaScriptへはSVGの `data-diagram-left-padding` で渡します。幅34pxの駅箱は左端に1px残り、半分切れません。
  駅名表示専用の幅やCSSの左軸幅はありません。
- 上部の固定時間軸は維持。`syncAxes()` は時刻文字のxと横スクロールを同期し、駅名の複製・縦同期は行いません。
- ズームはピンチ専用で100〜300%。＋／－のDOM、参照、イベント処理、ボタン用倍率刻みを削除しました。
- 下部操作バーは「リセット / 倍率 / ☰」。倍率はピンチにリアルタイム追従します。
  操作ボタンは44px、バー本体は54px。下余白は70px＋safe-area、バー下は8px＋safe-areaです。
- ピンチ開始時の2本指の中間点を、SVGの画面位置と現在倍率から基準座標へ逆変換して記録します。
  `scaleX(x) = padding + (x - padding) * zoom`、縦方向もtopMarginを基準に変換します。
  再描画後、記録地点と現在の指の中間点との差をscrollLeft / scrollTopへ加算し、時間軸も再同期します。
  中間点が動けば表示も追従します。駅箱の重なり回避offsetは従来どおり拡大しません。
  スクロール範囲の端ではブラウザが位置を制限するため、完全には中心を維持できない場合があります。
  ピンチ直後500msの誤クリック防止は維持しています。
- リセットは乗車中列車・乗換候補・赤線だけを解除します。倍率、スクロール、検索結果、保存条件、行き／帰り、指定時刻は変えません。
- ☰からボトムシートを開き、方向・指定時刻を検索します。背景・閉じるボタン・Escapeで閉じます。
  認証ON時だけ、最下部にPOSTのログアウトボタンを表示します。

行きは神戸の希望到着時刻（始発〜9:30）の前7本＋後3本、帰りは希望出発時刻（15:00〜終電）以降の最大10本です。
帰りは神戸→茨木の駅順、0〜2時台は翌日として配置し時間軸に「翌日」を表示します。
神戸時刻が空欄の列車は検索対象外です。現CSVの神戸発最終列車は23:47です。
希望時刻の赤い縦線は行きだけです。

列車線・駅箱のタップで乗車中列車を選び、別列車の同じ駅の箱をタップすると乗換赤線を表示します。
乗車中の列車や候補の再タップでも解除できます。乗車中列車に同じ駅箱がない場合は候補にできません。
赤線は手動選択の表示であり、乗換可否や必要時間を判定しません。着時刻がCSVにない駅では着時刻を表示しません。

### 検索条件と重なり回避

localStorageの `timetable.search.v2` に成功した検索だけを方向別で保存します。

```json
{
  "outbound": {"target_time": "09:15"},
  "return": {"target_time": "18:00"},
  "active_direction": "return"
}
```

再アクセスでは最後の方向を復元して自動検索します。保存済みの方向への切り替えは1タップで検索、
未保存の方向は空欄です。検索エラーでは保存値を上書きしません。保存できなくても手動検索は利用できます。
新キーがない場合だけ、旧 `timetable.search` のdirection / target_timeを検証して移行します。
保存対象は検索条件だけです。ログアウトしても検索条件は残りますが、再検索には認証が必要です。

`stack_overlapping_stops(diagram_trains, stack_step=34, box_width=34)` は同じ駅の中心xを並べ、
隣り合う差が34px未満の箱を連続グループにします。34pxちょうどは別グループです。
2箱は−17／17、3箱は−34／0／34の上下offsetを付けます。中心x・箱幅・CSV・検索ロジックは今回変更していません。

## Passkey認証

サーバー側は [py_webauthnの正式な生成・検証関数](https://duo-labs.github.io/py_webauthn/overview.html) を使います。
ブラウザのWebAuthnレスポンスをライブラリで検証し、独自の署名検証はしません。
登録・ログインとも `userVerification=required` を指定し、検証側でも本人確認を必須にしています。

Face IDなどの顔情報・生体情報はサーバーへ送信・保存しません。
秘密鍵は端末・Passkeyプロバイダー側が管理します。サーバーに保存するのはcredential ID、公開鍵、sign count、user handle等だけです。
Face ID以外の端末側本人確認が選ばれる場合もあります。

### 初回登録

1. HTTPS本番設定と、十分長いランダムな `PASSKEY_SETUP_TOKEN` を用意して起動します。
2. 本人のiPhone Safariで `https://telcation.f5.si/timetable/setup` を開きます。
3. セットアップトークンをフォームに入力しPOSTします。URLのqueryへトークンを入れないでください。
4. `hmac.compare_digest()` で一致を確認すると、5分間だけ登録ボタンを表示できます。
5. 「パスキーを登録」から端末の本人確認を行います。
6. challenge・origin・RP ID・user verificationを正式なライブラリで検証し、成功した公開情報だけをDBへ保存します。そのままログイン状態になります。

登録件数が1件以上ならsetup画面・登録APIを閉じます。DBへの書込み直前にもトランザクション内で確認するため、同時登録で2件にはなりません。
初回setupコードを削除する必要はありません。登録後は `PASSKEY_SETUP_TOKEN` をサーバー設定から削除して再起動することを推奨します。
削除しても登録済みPasskeyのログインはできます。今回、追加端末のPasskey登録・管理画面は実装していません。
別端末からは、端末側で利用可能な同じ登録済みPasskeyを使います。未登録の別Passkeyは拒否します。

### ログインとセッション

未認証でダイヤへアクセスするとログイン画面へ移動します。
「Face ID / パスキーでログイン」で登録済みcredentialを指定し、端末の本人確認後、
challenge・origin・RP ID・公開鍵・sign count・user verificationを検証します。
成功時だけsign countを更新し、セッションにauthenticatedと認証時刻を保存します。
公開鍵をCookieやセッションに保存しません。失敗から初回setupや新規登録へは誘導しません。

- Cookie名：`timetable_session`
- Secure / HttpOnly / SameSite=Lax
- Path：`TIMETABLE_SESSION_COOKIE_PATH`（既定 `/`、本番 `/timetable/`）
- `session.permanent = True`、既定16時間、`SESSION_REFRESH_EACH_REQUEST = False`
- 保存した認証時刻も検査し、セッション書込みで絶対期限が延長されないようにしています。
- ログアウトはCSRF保護付きPOSTで `session.clear()` し、ログインへ戻します。
- 認証画面・ダイヤの応答は `Cache-Control: no-store`。外部へのReferer送信を防ぐsame-origin設定です。

許可する未認証endpointはlogin / setup / WebAuthn options・verify / staticだけです。将来追加する画面も既定で認証対象になります。
認証APIとlogoutはCSRFトークンを検証し、Originが付いている場合は設定と一致することも確認します。

チャレンジはFlaskの署名付きsessionにbase64urlで保存します。さらにDBへSHA-256ダイジェストと5分の期限を保存します。
verifyの成功・失敗ともsessionから削除し、DB側も原子的に消費します。古いCookieを再送しても使用済みチャレンジは通りません。
秘密値・チャレンジ・公開鍵・credential ID全体・WebAuthnレスポンス全文をアプリからログ出力しません。
認証失敗画面には内部パスや検証例外の詳細を表示しません。

## ZIP更新と外部SQLite

認証ONでは `TIMETABLE_AUTH_DB_PATH` でソース外のSQLiteファイルを絶対パス指定します。
`instance/auth.db` 等へのフォールバックはありません。
起動時に絶対パス・ソース外・既存親ディレクトリを検査し、DBの読取りと書込みトランザクションを実行します。
ファイル・ジャーナルを書き込めない場合も明確な起動エラーになります。親フォルダは自動作成しません。
親ディレクトリは管理者が用意し、Flask実行ユーザーだけに必要な読み書き権限を与えてください。

| テーブル | 保存内容 |
| --- | --- |
| auth_owner | 固定id=1、安全な乱数32バイトのuser_handle（BLOB）、created_at |
| credentials | id、credential_id（BLOB・一意）、credential_public_key（BLOB）、sign_count、transports（JSON文字列）、created_at |
| auth_challenges | 一時チャレンジのダイジェスト（BLOB）、expires_at。期限切れは削除 |

テーブル作成とowner作成は冪等です。アプリ再起動やZIP更新で既存credentialやuser_handleを作り直しません。
同じDBパスをすべてのソースバージョンへ設定します：

```text
/home/xxx/apps/TimeTable/       ← ZIP更新するソース
/home/xxx/timetable-data/auth.db ← 更新対象外の永続DB
```

Windowsなら `C:/Users/xxx/timetable-data/auth.db` のように指定できます。
DBには秘密鍵がなくても認証の信頼データなので、不正な書換え・読取りを防ぎバックアップしてください。
SQLiteの整合性を保つため、停止中のコピーかSQLite backup機能でバックアップします。
DBを消失しバックアップから戻せない場合は、管理者が空のDBと新しいsetup tokenを用意し、本人がPasskeyを再登録する必要があります。
端末上の古い登録は新しいDBでは利用できません。
SECRET_KEYを変更すると既存セッションは無効になり再ログインが必要ですが、DB内のPasskey登録は残ります。

## 本番設定と講師への確認事項

秘密値のない `.env.example` は設定項目の見本です。**このまま本番利用しないでください。**
`.env`、`.env.*`（exampleを除く）、DB・SQLite補助ファイルはGitから除外します。
ZIPはGit追跡ファイルから作成し、作業フォルダを丸ごと圧縮しないでください。
ローカルの認証OFF用.env、仮想環境、実DB、秘密値をZIPへ含めないでください。

本番ではサービスの環境変数に以下を設定します。`.env` を使う場合もZIP上書き対象から外し、
管理者が秘密設定を保持する必要があります。永続DBのパス変更でPythonソースを書き換える必要はありません。

```dotenv
TIMETABLE_AUTH_ENABLED=1
TIMETABLE_AUTH_DB_PATH=/home/xxx/timetable-data/auth.db
SECRET_KEY=<十分長いランダム値>
WEBAUTHN_RP_ID=telcation.f5.si
WEBAUTHN_ORIGIN=https://telcation.f5.si
TIMETABLE_SESSION_COOKIE_PATH=/timetable/
TIMETABLE_SESSION_HOURS=16
# 初回登録時のみ。登録後は削除して再起動
PASSKEY_SETUP_TOKEN=<SECRET_KEYとは別の十分長いランダム値>
```

SECRET_KEYは必須、32文字以上です。setup tokenも指定するなら32文字以上にしてください。
長さは乱数の強さを保証しないため、両方ともパスワード管理ソフトなどで独立したランダム値を生成します。
未設定のDBパス・SECRET_KEY・WebAuthn設定を安全でない値へ自動補完しません。

RP IDはホスト名のみ。HTTPSや `/timetable/` は含めません。
OriginはHTTPSのschemeとホスト名（必要ならポート）だけで、パスや末尾スラッシュを含めません。
このアプリではRP IDとOriginのホスト名を一致させます。

講師には次を確認してください：

1. ZIP更新・サーバー再起動後も残るソース外ディレクトリ、絶対パス、Flask実行ユーザーの読み書き権限、バックアップ方法。
2. 有効なHTTPS証明書と実際の公開ドメイン。`telcation.f5.si` を変更するとPasskeyの利用条件も変わります。
3. 本番のWSGIサービスと環境変数の保存・再起動方法。開発用Flaskサーバー・debugは本番に使いません。
4. `/timetable/` のマウント設定。WSGIへ `SCRIPT_NAME=/timetable`、`PATH_INFO=/login` 等のアプリ内パスを正しく渡します。
   URLを削っただけの転送では不十分です。例えばWSGIのDispatcherMiddlewareへ `{'/timetable': app}` でマウントできます。
   cookie pathだけ設定してもルーティングはマウントされません。
5. リバースプロキシ配下のHTTPS判定と信頼境界。アプリは任意のX-Forwarded-*を自動で信用しません。
   必要な場合は講師側で信頼できるプロキシに限定した設定を行います。
6. SECRET_KEYの継続保持、setup tokenの安全な受渡しと登録後削除、DBバックアップ・復旧手順。

Flaskは `create_app()` と `app = create_app()` を公開します。
HTML、認証fetch、redirect、static、logoutのURLは `url_for()` から生成し、サブパスをJavaScriptへdata属性で渡します。
本番URLでのiPhone Safari確認は、講師の環境設定後に行ってください。

## テストと今回の確認結果（2026-09-14）

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

**67件成功：従来35件＋認証32件。**
既存テストの画面座標期待値は48→18へ更新し、認証OFFの専用appで検証しています。
検索・CSV・深夜処理・重なり回避のテストは維持しました。

追加テストは認証OFF、既定ON、未認証拒否、認証後検索、設定欠落・無効値、
DB初期化・権限エラー・再生成時の永続性、setup token不一致・期限・登録済み閉鎖・競合、
登録／ログイン成功・失敗、sign count更新、未知credential／user handle拒否、
チャレンジ消費・期限・古いCookieの再送、logout・CSRF・絶対セッション期限・非延長、
サブパスURL・Cookie属性、OS環境変数優先、WindowsのBOM付き.env読込みを確認します。
正式verify関数の成功・失敗はunit testでmockしています。
DBを保存してappを破棄し、setup tokenなしの別appから同じcredentialとuser_handleを読み出すテストを含みます。

別途、390×844のEdge＋模擬タッチで、左駅名軸・＋／－の削除、倍率の配置・更新、
芦屋18:35付近・大阪・尼崎・三ノ宮・神戸の100→200→100%で中心誤差1px以内、
中間点移動、固定時間軸、赤線接続、ピンチ直後の誤クリック抑止、リセットで倍率・位置・保存条件を維持することを確認しました。
バー実測54px、最下部駅箱がバーより上に表示できることも確認済み。JavaScriptエラーはありません。

HTTPSのローカルテストサーバーを `/timetable/` へマウントし、ブラウザの仮想WebAuthn認証器で
実際の暗号レスポンスによる登録→検索→ログアウト→再ログイン→保存条件復元に成功しました。
CookieのSecure/HttpOnly/SameSite/Pathとsetup閉鎖も確認済みです。
このテスト用証明書・鍵・DBは本番用ではなく、リポジトリにも含めていません。

残る実機確認：iPhone SafariのFace ID画面、実際のPasskey保存／同期、safe-area・Home Indicator、
アドレスバー伸縮、実指のピンチ操作感、講師サーバー上の永続領域とWSGI設定。
仮想認証器の成功をiPhone実機・本番デプロイ済みの意味では扱いません。

## 開発元

元の教室リポジトリは https://github.com/user06-practice/TimeTable 、基準は `864cb5d` です。
共有する開発先は https://github.com/mappoll/TimeTable です。
今回の基準mainは `303a179e682bfcc3ddcf86a4865512e5cfb222ce`。
教室PCに未push変更が残る場合は、削除せず比較してから統合してください。
