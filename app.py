#!/usr/bin/env python3
"""
競馬オッズ取得Streamlitアプリケーション
JRAの公式サイトから現在のオッズを取得し、テーブル表示・CSVダウンロード機能を提供
"""

import streamlit as st
import asyncio
import pandas as pd
import json
import io
from datetime import datetime, date
from typing import Dict, List
import time

# scraping.pyからJRAOddsScraperクラスをインポート
from scraping import JRAOddsScraper


def format_odds_for_display(odds_data: Dict) -> pd.DataFrame:
    """
    オッズデータをテーブル表示用のDataFrameに変換
    
    Args:
        odds_data (Dict): オッズデータ
        
    Returns:
        pd.DataFrame: 表示用のDataFrame
    """
    try:
        # レース基本情報
        race_info = {
            'レースID': odds_data.get('race_id', ''),
            'レース名': odds_data.get('race_name', ''),
            '発走時刻': odds_data.get('post_time', ''),
            'ステータス': odds_data.get('status', ''),
            'メッセージ': odds_data.get('message', '')
        }
        
        # 単勝オッズ
        tansho_data = []
        for umaban, odds in odds_data.get('tansho', {}).items():
            tansho_data.append({
                '馬番': umaban,
                '単勝オッズ': f"{odds:.1f}倍",
                'オッズ値': odds
            })
        
        # 複勝オッズ
        fukusho_data = []
        for umaban, odds in odds_data.get('fukusho', {}).items():
            fukusho_data.append({
                '馬番': umaban,
                '複勝オッズ': f"{odds:.1f}倍",
                'オッズ値': odds
            })
        
        # 馬連オッズ
        umaren_data = []
        for (umaban1, umaban2), odds in odds_data.get('umaren', {}).items():
            umaren_data.append({
                '馬番1': umaban1,
                '馬番2': umaban2,
                '馬連オッズ': f"{odds:.1f}倍",
                'オッズ値': odds
            })
        
        return {
            'race_info': race_info,
            'tansho': pd.DataFrame(tansho_data) if tansho_data else pd.DataFrame(),
            'fukusho': pd.DataFrame(fukusho_data) if fukusho_data else pd.DataFrame(),
            'umaren': pd.DataFrame(umaren_data) if umaren_data else pd.DataFrame()
        }
        
    except Exception as e:
        st.error(f"データ変換エラー: {e}")
        return {
            'race_info': {},
            'tansho': pd.DataFrame(),
            'fukusho': pd.DataFrame(),
            'umaren': pd.DataFrame()
        }


def create_race_summary_table(races_data: List[Dict]) -> pd.DataFrame:
    """
    レース一覧のサマリーテーブルを作成
    
    Args:
        races_data (List[Dict]): レースデータのリスト
        
    Returns:
        pd.DataFrame: サマリーテーブル
    """
    summary_data = []
    
    for race in races_data:
        summary_data.append({
            'レースID': race.get('race_id', ''),
            'レース名': race.get('race_name', ''),
            '発走時刻': race.get('post_time', ''),
            '単勝頭数': len(race.get('tansho', {})),
            '複勝頭数': len(race.get('fukusho', {})),
            '馬連組み数': len(race.get('umaren', {})),
            'ステータス': race.get('status', ''),
            'メッセージ': race.get('message', '')
        })
    
    return pd.DataFrame(summary_data)


def create_place_summary_table(races_data: List[Dict]) -> pd.DataFrame:
    """
    競馬場別サマリーテーブルを作成
    
    Args:
        races_data (List[Dict]): レースデータのリスト
        
    Returns:
        pd.DataFrame: 競馬場別サマリーテーブル
    """
    place_mapping = {
        1: "札幌", 2: "函館", 3: "福島", 4: "新潟", 5: "東京", 
        6: "中山", 7: "中京", 8: "京都", 9: "阪神", 10: "小倉"
    }
    
    place_stats = {}
    
    for race in races_data:
        if race.get('status') != 'success':
            continue
            
        race_id = race.get('race_id', '')
        if len(race_id) >= 10:
            place_code = int(race_id[4:6])
            place_name = place_mapping.get(place_code, f"不明({place_code})")
            
            if place_name not in place_stats:
                place_stats[place_name] = {
                    '競馬場': place_name,
                    'レース数': 0,
                    '成功レース数': 0,
                    '単勝平均オッズ': 0,
                    '複勝平均オッズ': 0,
                    '馬連平均オッズ': 0
                }
            
            place_stats[place_name]['レース数'] += 1
            if race.get('status') == 'success':
                place_stats[place_name]['成功レース数'] += 1
                
                # 平均オッズを計算
                tansho_odds = list(race.get('tansho', {}).values())
                fukusho_odds = list(race.get('fukusho', {}).values())
                umaren_odds = list(race.get('umaren', {}).values())
                
                if tansho_odds:
                    place_stats[place_name]['単勝平均オッズ'] = sum(tansho_odds) / len(tansho_odds)
                if fukusho_odds:
                    place_stats[place_name]['複勝平均オッズ'] = sum(fukusho_odds) / len(fukusho_odds)
                if umaren_odds:
                    place_stats[place_name]['馬連平均オッズ'] = sum(umaren_odds) / len(umaren_odds)
    
    return pd.DataFrame(list(place_stats.values()))


def create_csv_data_for_place(races_data: List[Dict], place_name: str) -> pd.DataFrame:
    """
    指定競馬場のCSVデータを作成
    
    Args:
        races_data (List[Dict]): レースデータのリスト
        place_name (str): 競馬場名
        
    Returns:
        pd.DataFrame: CSV用のDataFrame
    """
    place_mapping = {
        1: "札幌", 2: "函館", 3: "福島", 4: "新潟", 5: "東京", 
        6: "中山", 7: "中京", 8: "京都", 9: "阪神", 10: "小倉"
    }
    
    csv_data = []
    
    for race in races_data:
        if race.get('status') != 'success':
            continue
            
        race_id = race.get('race_id', '')
        if len(race_id) >= 10:
            place_code = int(race_id[4:6])
            current_place_name = place_mapping.get(place_code, f"不明({place_code})")
            
            if current_place_name == place_name:
                # 単勝データ
                for umaban, odds in race.get('tansho', {}).items():
                    csv_data.append({
                        'レースID': race_id,
                        'レース名': race.get('race_name', ''),
                        '発走時刻': race.get('post_time', ''),
                        '競馬場': current_place_name,
                        '馬券種': '単勝',
                        '馬番1': umaban,
                        '馬番2': '',
                        'オッズ': odds
                    })
                
                # 複勝データ
                for umaban, odds in race.get('fukusho', {}).items():
                    csv_data.append({
                        'レースID': race_id,
                        'レース名': race.get('race_name', ''),
                        '発走時刻': race.get('post_time', ''),
                        '競馬場': current_place_name,
                        '馬券種': '複勝',
                        '馬番1': umaban,
                        '馬番2': '',
                        'オッズ': odds
                    })
                
                # 馬連データ
                for (umaban1, umaban2), odds in race.get('umaren', {}).items():
                    csv_data.append({
                        'レースID': race_id,
                        'レース名': race.get('race_name', ''),
                        '発走時刻': race.get('post_time', ''),
                        '競馬場': current_place_name,
                        '馬券種': '馬連',
                        '馬番1': umaban1,
                        '馬番2': umaban2,
                        'オッズ': odds
                    })
    
    return pd.DataFrame(csv_data)


def main():
    """メイン関数"""
    st.set_page_config(
        page_title="競馬オッズ取得アプリ",
        page_icon="🏇",
        layout="wide"
    )
    
    st.title("🏇 競馬オッズ取得アプリ")
    st.markdown("---")
    
    # 日付入力フォーム
    st.header("📅 日付選択")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        selected_date = st.date_input(
            "取得する日付を選択してください",
            value=date.today(),
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31)
        )
    
    with col2:
        st.markdown("### 取得ボタン")
        if st.button("🚀 オッズを取得", type="primary", use_container_width=True):
            # 日付を文字列に変換
            date_str = selected_date.strftime("%Y%m%d")
            
            # プログレスバーを表示
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # JRAOddsScraperのインスタンスを作成
                scraper = JRAOddsScraper()
                
                # 非同期処理を実行
                status_text.text("オッズ取得中...")
                progress_bar.progress(0.1)
                
                # 日別オッズを取得
                daily_data = asyncio.run(scraper.get_daily_odds(date_str))
                
                progress_bar.progress(0.8)
                status_text.text("データ処理中...")
                
                # セッションステートにデータを保存
                st.session_state.daily_data = daily_data
                st.session_state.date_str = date_str
                
                progress_bar.progress(1.0)
                status_text.text("完了！")
                
                # 成功メッセージを表示
                if daily_data['status'] == 'success':
                    st.success(f"✅ {daily_data['successful_races']}レースのオッズを取得しました！")
                else:
                    st.warning(f"⚠️ 一部のレースでエラーが発生しました: {daily_data['message']}")
                
            except Exception as e:
                st.error(f"❌ エラーが発生しました: {e}")
                progress_bar.empty()
                status_text.empty()
    
    st.markdown("---")
    
    # 結果表示エリア
    if 'daily_data' in st.session_state:
        daily_data = st.session_state.daily_data
        date_str = st.session_state.date_str
        
        st.header("📊 取得結果")
        
        # サマリー情報を表示
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("総レース数", daily_data['total_races'])
        
        with col2:
            st.metric("成功レース数", daily_data['successful_races'])
        
        with col3:
            st.metric("失敗レース数", daily_data['failed_races'])
        
        with col4:
            success_rate = (daily_data['successful_races'] / daily_data['total_races'] * 100) if daily_data['total_races'] > 0 else 0
            st.metric("成功率", f"{success_rate:.1f}%")
        
        st.markdown("---")
        
        # レース一覧テーブル
        st.subheader("🏁 レース一覧")
        summary_table = create_race_summary_table(daily_data['races'])
        st.dataframe(summary_table, use_container_width=True)
        
        # 競馬場別サマリー
        st.subheader("🏟️ 競馬場別サマリー")
        place_summary = create_place_summary_table(daily_data['races'])
        if not place_summary.empty:
            st.dataframe(place_summary, use_container_width=True)
        else:
            st.info("データがありません")
        
        # 個別レース詳細
        st.subheader("📋 レース詳細")
        
        # レース選択
        successful_races = [race for race in daily_data['races'] if race['status'] == 'success']
        
        if successful_races:
            race_options = [f"{race['race_id']} - {race['race_name']} ({race['post_time']})" for race in successful_races]
            selected_race_idx = st.selectbox("詳細を表示するレースを選択してください", range(len(race_options)), format_func=lambda x: race_options[x])
            
            if selected_race_idx is not None:
                selected_race = successful_races[selected_race_idx]
                formatted_data = format_odds_for_display(selected_race)
                
                # レース情報
                st.write("**レース情報**")
                race_info_df = pd.DataFrame([formatted_data['race_info']])
                st.dataframe(race_info_df, use_container_width=True)
                
                # オッズテーブル
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**単勝オッズ**")
                    if not formatted_data['tansho'].empty:
                        st.dataframe(formatted_data['tansho'], use_container_width=True)
                    else:
                        st.info("データがありません")
                
                with col2:
                    st.write("**複勝オッズ**")
                    if not formatted_data['fukusho'].empty:
                        st.dataframe(formatted_data['fukusho'], use_container_width=True)
                    else:
                        st.info("データがありません")
                
                with col3:
                    st.write("**馬連オッズ**")
                    if not formatted_data['umaren'].empty:
                        st.dataframe(formatted_data['umaren'], use_container_width=True)
                    else:
                        st.info("データがありません")
        
        st.markdown("---")
        
        # ダウンロードセクション
        st.header("💾 データダウンロード")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 全データ（JSON）")
            json_data = json.dumps(daily_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="JSONファイルをダウンロード",
                data=json_data,
                file_name=f"daily_odds_{date_str}.json",
                mime="application/json"
            )
        
        with col2:
            st.subheader("📊 競馬場別CSV")
            
            # 競馬場一覧を取得
            place_mapping = {
                1: "札幌", 2: "函館", 3: "福島", 4: "新潟", 5: "東京", 
                6: "中山", 7: "中京", 8: "京都", 9: "阪神", 10: "小倉"
            }
            
            available_places = set()
            for race in daily_data['races']:
                if race.get('status') == 'success':
                    race_id = race.get('race_id', '')
                    if len(race_id) >= 10:
                        place_code = int(race_id[4:6])
                        place_name = place_mapping.get(place_code, f"不明({place_code})")
                        available_places.add(place_name)
            
            if available_places:
                selected_place = st.selectbox("ダウンロードする競馬場を選択してください", sorted(available_places))
                
                if st.button("CSVファイルをダウンロード", type="secondary"):
                    csv_data = create_csv_data_for_place(daily_data['races'], selected_place)
                    
                    if not csv_data.empty:
                        csv_buffer = io.StringIO()
                        csv_data.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                        csv_content = csv_buffer.getvalue()
                        
                        st.download_button(
                            label=f"{selected_place}のCSVファイルをダウンロード",
                            data=csv_content,
                            file_name=f"{selected_place}_odds_{date_str}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning(f"{selected_place}のデータがありません")
            else:
                st.info("ダウンロード可能なデータがありません")
    
    else:
        st.info("👆 上記の日付を選択して「オッズを取得」ボタンを押してください")


if __name__ == "__main__":
    main()
