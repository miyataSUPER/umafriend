# 競馬オッズ取得アプリ

JRAの公式サイトから競馬のオッズデータを取得し、テーブル表示・CSVダウンロード機能を提供するStreamlitアプリケーションです。

## 機能

- 📅 日付選択による日別全レースオッズ取得
- 📊 オッズデータのテーブル表示（単勝・複勝・馬連）
- 🏟️ 競馬場別サマリー表示
- 💾 データダウンロード機能
  - 全データのJSONダウンロード
  - 競馬場別CSVダウンロード
- 📈 進捗バーと取得状況表示

## 技術スタック

- **Frontend**: Streamlit
- **Backend**: Python 3.8+
- **Web Scraping**: Playwright, BeautifulSoup4
- **Data Processing**: Pandas

## 必要なライブラリ

```
streamlit>=1.28.0
pandas>=1.5.0
playwright>=1.40.0
beautifulsoup4>=4.12.0
```

## ローカル実行方法

1. リポジトリをクローン
```bash
git clone <repository-url>
cd umafriend
```

2. 依存関係をインストール
```bash
pip install -r requirements.txt
```

3. Playwrightブラウザをインストール
```bash
playwright install chromium
```

4. アプリケーションを起動
```bash
streamlit run app.py
```

## Streamlit Cloud デプロイ

1. GitHubリポジトリにプッシュ
2. [Streamlit Cloud](https://share.streamlit.io/)にアクセス
3. "New app"をクリック
4. リポジトリとブランチを選択
5. メインファイルパス: `app.py`
6. "Deploy!"をクリック

## ファイル構成

```
umafriend/
├── app.py                 # Streamlitアプリケーション
├── scraping.py           # JRAオッズスクレイピングクラス
├── requirements.txt      # 依存関係
├── .streamlit/
│   └── config.toml      # Streamlit設定
└── README.md            # このファイル
```

## 使用方法

1. 日付を選択
2. "オッズを取得"ボタンをクリック
3. 結果をテーブルで確認
4. 必要に応じてデータをダウンロード

## 注意事項

- JRAの公式サイトからデータを取得するため、サイトの仕様変更により動作しなくなる可能性があります
- 大量のデータ取得時は時間がかかる場合があります
- 取得したデータは個人利用の範囲でご利用ください

## ライセンス

MIT License
