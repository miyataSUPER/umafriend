#!/usr/bin/env python3
"""
競馬オッズ取得スクリプト
レースIDを受け取って、JRAの公式サイトから現在のオッズを取得する
"""

import asyncio
import time
import re
from typing import Dict, List, Optional
import json
import pandas as pd
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


class JRAOddsScraper:
    """JRAオッズスクレイピングクラス"""
    
    def __init__(self):
        # 競馬場名のマッピング
        self.place_mapping = {
            1: "札幌", 2: "函館", 3: "福島", 4: "新潟", 5: "東京", 
            6: "中山", 7: "中京", 8: "京都", 9: "阪神", 10: "小倉"
        }
        
        # 馬券種とファイル名インデックスの対応付け
        self.bet_type_mapping = {
            "単勝・複勝": 0,
            "枠連": 1,
            "馬連": 2,
            "ワイド": 3,
            "馬単": 4,
            "3連複": 5,
            "連複": 5,  # 表記揺れに対応
            "3連単": 6,
        }
        
    async def get_race_odds(self, race_id: str) -> Dict:
        """
        レースIDから現在のオッズを取得（Playwright使用）
        
        Args:
            race_id (str): レースID (例: "202506010501")
            
        Returns:
            Dict: オッズデータ
        """
        try:
            # race_idから日付とレース情報を抽出
            year = race_id[:4]
            month = race_id[4:6]
            day = race_id[6:8]
            place_code = int(race_id[4:6])
            race_num = int(race_id[8:10])
            
            place_name = self.place_mapping.get(place_code, "不明")
            
            print(f"レース情報: {year}年{month}月{day}日 {place_name}{race_num}R")
            
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                try:
                    # JRAサイトにアクセス
                    await page.goto("https://www.jra.go.jp/keiba/")
                    await page.get_by_role("link", name="オッズ", exact=True).click(delay=1000)
                    await page.wait_for_load_state("domcontentloaded")
                    
                    # 開催名を構築
                    kaisai_name = f"{int(race_id[6:8])}回{place_name}{int(race_id[8:10])}日"
                    race_name = f"{race_num}レース"
                    
                    print(f"開催名: {kaisai_name}, レース名: {race_name}")
                    
                    # 開催リンクをクリック
                    kaisai_link = page.get_by_role("link", name=kaisai_name)
                    if await kaisai_link.count() > 0:
                        await kaisai_link.click(delay=1000)
                        await page.get_by_role("link", name=race_name, exact=True).click(delay=1000)
                    else:
                        # オッズページにリンクが存在しない場合、レース結果ページから遷移
                        await page.get_by_role("link", name="レース結果").click(delay=1000)
                        await page.get_by_role("link", name=kaisai_name).click(delay=1000)
                        await page.get_by_role("link", name=race_name, exact=True).click(delay=1000)
                        await page.locator("#race_result").get_by_role("link", name="オッズ").click(delay=1000)
                    
                    await page.wait_for_load_state("domcontentloaded")
                    
                    # オッズデータを取得
                    odds_data = await self._extract_odds_from_page(page, race_id)
                    
                    return odds_data
                    
                finally:
                    await context.close()
                    await browser.close()
                    
        except Exception as e:
            print(f"オッズ取得エラー: {e}")
            return {
                "race_id": race_id,
                "race_name": "不明",
                "post_time": "不明",
                "tansho": {},
                "fukusho": {},
                "umaren": {},
                "status": "error",
                "message": str(e)
            }
    
    async def _extract_odds_from_page(self, page, race_id: str) -> Dict:
        """ページからオッズデータを抽出"""
        try:
            # レース名を取得
            race_name = "不明"
            try:
                race_header = await page.locator("div.race_header div.cell.title strong").text_content()
                if race_header:
                    race_name = race_header.strip()
            except:
                pass
            
            # 発走時刻を取得
            post_time = "不明"
            try:
                time_elem = await page.locator("div.race_header div.cell.time strong").text_content()
                if time_elem:
                    time_match = re.search(r"(\d+)時(\d+)分", time_elem)
                    if time_match:
                        hour = time_match.group(1).zfill(2)
                        minute = time_match.group(2).zfill(2)
                        post_time = f"{hour}:{minute}"
            except:
                pass
            
            # 単勝・複勝オッズを取得
            tansho, fukusho = await self._extract_tanpuku_odds(page)
            
            # 馬連オッズを取得
            umaren = await self._extract_umaren_odds(page, tansho)
            
            return {
                "race_id": race_id,
                "race_name": race_name,
                "post_time": post_time,
                "tansho": tansho,
                "fukusho": fukusho,
                "umaren": umaren,
                "status": "success",
                "message": "オッズ取得成功"
            }
            
        except Exception as e:
            print(f"オッズ抽出エラー: {e}")
            return {
                "race_id": race_id,
                "race_name": "不明",
                "post_time": "不明",
                "tansho": {},
                "fukusho": {},
                "umaren": {},
                "status": "error",
                "message": str(e)
            }
    
    async def _extract_tanpuku_odds(self, page) -> tuple[Dict[int, float], Dict[int, float]]:
        """単勝・複勝オッズを抽出"""
        tansho = {}
        fukusho = {}
        
        try:
            # 単勝・複勝タブをクリック
            nav_pills = page.locator("ul.nav.pills")
            bet_type_items = nav_pills.locator("li")
            
            for i in range(await bet_type_items.count()):
                bet_item = bet_type_items.nth(i)
                bet_link = bet_item.locator("a")
                bet_type_name = await bet_link.inner_text()
                
                if "単勝・複勝" in bet_type_name:
                    await bet_link.click()
                    await page.wait_for_load_state("domcontentloaded")
                    
                    # 単勝・複勝テーブルを取得
                    odds_table = page.locator("table.tanpuku")
                    if await odds_table.count() > 0:
                        rows = odds_table.locator("tbody tr")
                        
                        for j in range(await rows.count()):
                            row = rows.nth(j)
                            
                            # 馬番を取得
                            umaban_elem = row.locator("td.num")
                            if await umaban_elem.count() > 0:
                                umaban = int(await umaban_elem.text_content())
                                
                                # 単勝オッズを取得
                                tan_odds_elem = row.locator("td.odds_tan")
                                if await tan_odds_elem.count() > 0:
                                    tan_odds_text = await tan_odds_elem.text_content()
                                    tan_odds = float(tan_odds_text.replace(",", ""))
                                    tansho[umaban] = tan_odds
                                
                                # 複勝オッズを取得
                                fuku_odds_elem = row.locator("td.odds_fuku")
                                if await fuku_odds_elem.count() > 0:
                                    min_odds_span = fuku_odds_elem.locator("span.min")
                                    max_odds_span = fuku_odds_elem.locator("span.max")
                                    
                                    if await min_odds_span.count() > 0 and await max_odds_span.count() > 0:
                                        fuku_odds_low = float(await min_odds_span.text_content())
                                        fuku_odds_high = float(await max_odds_span.text_content())
                                        # 複勝オッズは平均値を取る
                                        fukusho[umaban] = (fuku_odds_low + fuku_odds_high) / 2
                    break
                    
        except Exception as e:
            print(f"単勝・複勝オッズ抽出エラー: {e}")
        
        return tansho, fukusho
    
    async def _extract_umaren_odds(self, page, tansho: Dict[int, float]) -> Dict[tuple, float]:
        """馬連オッズを抽出（単勝一番人気の馬を軸にした全パターン）"""
        umaren = {}
        
        try:
            # 単勝オッズから一番人気の馬を特定
            if not tansho:
                return umaren
            
            # オッズが最も低い（人気が高い）馬を特定
            favorite_horse = min(tansho.keys(), key=lambda x: tansho[x])
            print(f"一番人気の馬: {favorite_horse}番 (オッズ: {tansho[favorite_horse]}倍)")
            
            # 馬連タブをクリック
            nav_pills = page.locator("ul.nav.pills")
            bet_type_items = nav_pills.locator("li")
            
            for i in range(await bet_type_items.count()):
                bet_item = bet_type_items.nth(i)
                bet_link = bet_item.locator("a")
                bet_type_name = await bet_link.inner_text()
                
                if "馬連" in bet_type_name:
                    await bet_link.click()
                    await page.wait_for_load_state("domcontentloaded")
                    
                    # 馬連オッズを取得
                    list_blocks = page.locator("ul.umaren_list")
                    
                    for j in range(await list_blocks.count()):
                        list_block = list_blocks.nth(j)
                        table_elements = list_block.locator("li")
                        
                        for k in range(await table_elements.count()):
                            table_element = table_elements.nth(k)
                            
                            # キャプションから第一馬番を取得
                            caption = table_element.locator("caption")
                            if await caption.count() > 0:
                                first_horse = int(await caption.text_content())
                                
                                # 一番人気の馬を含むテーブルのみを処理
                                if first_horse == favorite_horse:
                                    rows = table_element.locator("tbody tr")
                                    
                                    for l in range(await rows.count()):
                                        row = rows.nth(l)
                                        
                                        second_horse_elem = row.locator("th")
                                        odds_td = row.locator("td")
                                        
                                        if await second_horse_elem.count() > 0 and await odds_td.count() > 0:
                                            second_horse = int(await second_horse_elem.text_content())
                                            odds_text = await odds_td.text_content()
                                            odds = float(odds_text.replace(",", ""))
                                            
                                            umaren[(first_horse, second_horse)] = odds
                    break
                    
        except Exception as e:
            print(f"馬連オッズ抽出エラー: {e}")
        
        return umaren
    


    async def get_daily_odds(self, date: str) -> Dict:
        """
        指定日付の全レースのオッズを取得
        
        Args:
            date (str): 日付 (例: "2025-01-13" または "20250113")
            
        Returns:
            Dict: 全レースのオッズデータ
            {
                "date": str,
                "races": [
                    {
                        "race_id": str,
                        "race_name": str,
                        "post_time": str,
                        "tansho": Dict[int, float],
                        "fukusho": Dict[int, float],
                        "umaren": Dict[tuple, float],
                        "status": str,
                        "message": str
                    },
                    ...
                ],
                "total_races": int,
                "successful_races": int,
                "failed_races": int
            }
        """
        try:
            # 日付形式を統一 (YYYY-MM-DD -> YYYYMMDD)
            if '-' in date:
                date = date.replace('-', '')
            
            if len(date) != 8:
                raise ValueError("日付は8桁の数字である必要があります (例: 20250113)")
            
            print(f"日付 {date} の全レースオッズを取得中...")
            
            # その日のレースIDリストを取得
            race_ids = self._get_race_ids_for_date(date)
            
            if not race_ids:
                return {
                    "date": date,
                    "races": [],
                    "total_races": 0,
                    "successful_races": 0,
                    "failed_races": 0,
                    "status": "error",
                    "message": f"日付 {date} のレースが見つかりません"
                }
            
            print(f"取得対象レース数: {len(race_ids)}")
            
            # 各レースのオッズを取得
            races_data = []
            successful_count = 0
            failed_count = 0
            
            for i, race_id in enumerate(race_ids, 1):
                print(f"\n[{i}/{len(race_ids)}] レース {race_id} のオッズを取得中...")
                
                try:
                    odds_data = await self.get_race_odds(race_id)
                    races_data.append(odds_data)
                    
                    if odds_data['status'] == 'success':
                        successful_count += 1
                        print(f"✅ 成功: {odds_data['race_name']}")
                    else:
                        failed_count += 1
                        print(f"❌ 失敗: {odds_data['message']}")
                    
                    # リクエスト間隔を空ける
                    time.sleep(1)
                    
                except Exception as e:
                    failed_count += 1
                    error_data = {
                        "race_id": race_id,
                        "race_name": "不明",
                        "post_time": "不明",
                        "tansho": {},
                        "fukusho": {},
                        "umaren": {},
                        "status": "error",
                        "message": str(e)
                    }
                    races_data.append(error_data)
                    print(f"❌ エラー: {e}")
            
            return {
                "date": date,
                "races": races_data,
                "total_races": len(race_ids),
                "successful_races": successful_count,
                "failed_races": failed_count,
                "status": "success" if successful_count > 0 else "error",
                "message": f"成功: {successful_count}レース, 失敗: {failed_count}レース"
            }
            
        except Exception as e:
            print(f"日別オッズ取得エラー: {e}")
            return {
                "date": date,
                "races": [],
                "total_races": 0,
                "successful_races": 0,
                "failed_races": 0,
                "status": "error",
                "message": str(e)
            }
    
    def _get_race_ids_for_date(self, date: str) -> List[str]:
        """指定日付のレースIDリストを取得"""
        try:
            # 予測用データからレースIDを取得
            population_file = Path("common/data/prediction/population.csv")
            if population_file.exists():
                df = pd.read_csv(population_file, sep="\t")
                # 日付でフィルタリング
                target_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
                race_ids = df[df['date'] == target_date]['race_id'].unique().tolist()
                return [str(race_id) for race_id in race_ids]
            
            # タイムテーブルからレースIDを取得
            time_table_file = Path(f"common/data/prediction/time_table_{date}.csv")
            if time_table_file.exists():
                df = pd.read_csv(time_table_file, sep="\t")
                return df['race_id'].astype(str).tolist()
            
            # どちらも見つからない場合は空リストを返す
            return []
            
        except Exception as e:
            print(f"レースID取得エラー: {e}")
            return []


def main():
    """メイン関数"""
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python uma.py <race_id>           # 単一レースのオッズ取得")
        print("  python uma.py --date <date>       # 指定日の全レースオッズ取得")
        print("例:")
        print("  python uma.py 202506010501")
        print("  python uma.py --date 2025-01-13")
        print("  python uma.py --date 20250113")
        sys.exit(1)
    
    scraper = JRAOddsScraper()
    
    if sys.argv[1] == "--date":
        # 日別オッズ取得モード
        if len(sys.argv) != 3:
            print("エラー: 日付を指定してください")
            print("例: python uma.py --date 2025-01-13")
            sys.exit(1)
        
        date = sys.argv[2]
        daily_data = asyncio.run(scraper.get_daily_odds(date))
        
        # 結果を表示
        print(f"\n=== 日別オッズ取得結果 ===")
        print(f"日付: {daily_data['date']}")
        print(f"総レース数: {daily_data['total_races']}")
        print(f"成功: {daily_data['successful_races']}レース")
        print(f"失敗: {daily_data['failed_races']}レース")
        print(f"ステータス: {daily_data['status']}")
        print(f"メッセージ: {daily_data['message']}")
        
        # 各レースの詳細を表示
        for race in daily_data['races']:
            if race['status'] == 'success':
                print(f"\n--- {race['race_id']} {race['race_name']} ({race['post_time']}) ---")
                print("単勝オッズ:")
                for umaban, odds in sorted(race['tansho'].items()):
                    print(f"  {umaban:2d}番: {odds:6.1f}倍")
                
                print("複勝オッズ:")
                for umaban, odds in sorted(race['fukusho'].items()):
                    print(f"  {umaban:2d}番: {odds:6.1f}倍")
                
                print("馬連オッズ（一番人気の馬を軸）:")
                for (umaban1, umaban2), odds in sorted(race['umaren'].items()):
                    print(f"  {umaban1:2d}-{umaban2:2d}: {odds:6.1f}倍")
            else:
                print(f"\n--- {race['race_id']} エラー ---")
                print(f"  {race['message']}")
        
        # JSONファイルに保存
        output_file = f"daily_odds_{daily_data['date']}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(daily_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n結果を {output_file} に保存しました")
        
    else:
        # 単一レースオッズ取得モード
        race_id = sys.argv[1]
        
        # レースIDの形式チェック
        if not re.match(r'^\d{10}$', race_id):
            print("エラー: レースIDは10桁の数字である必要があります")
            print("例: 202506010501")
            sys.exit(1)
        
        print(f"レースID {race_id} のオッズを取得中...")
        
        odds_data = asyncio.run(scraper.get_race_odds(race_id))
        
        # 結果を表示
        print("\n=== オッズ取得結果 ===")
        print(f"レースID: {odds_data['race_id']}")
        print(f"レース名: {odds_data['race_name']}")
        print(f"発走時刻: {odds_data['post_time']}")
        print(f"ステータス: {odds_data['status']}")
        print(f"メッセージ: {odds_data['message']}")
        
        if odds_data['status'] == 'success':
            print("\n=== 単勝オッズ ===")
            for umaban, odds in sorted(odds_data['tansho'].items()):
                print(f"{umaban:2d}番: {odds:6.1f}倍")
            
            print("\n=== 複勝オッズ ===")
            for umaban, odds in sorted(odds_data['fukusho'].items()):
                print(f"{umaban:2d}番: {odds:6.1f}倍")
            
            print("\n=== 馬連オッズ（一番人気の馬を軸） ===")
            for (umaban1, umaban2), odds in sorted(odds_data['umaren'].items()):
                print(f"{umaban1:2d}-{umaban2:2d}: {odds:6.1f}倍")
        else:
            print(f"\n❌ エラー: {odds_data['message']}")
            sys.exit(1)
        
        # JSONファイルに保存
        output_file = f"odds_{race_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(odds_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n結果を {output_file} に保存しました")


if __name__ == "__main__":
    main()
