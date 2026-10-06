import os
import sys
from typing import Dict, List, Set

import pandas as pd
import requests

MLB_LIVE_FEED_URL_TEMPLATE = "https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
PROGRESS_STEP = 10

PITCH_BY_PITCH_COLUMNS = [
    "pitch_id",
    "game_id",
    "season",
    "pitcher_batter_index",
    "pitch_number",
    "inning",
    "inning_half",
    "outs",
    "batter_id",
    "pitcher_id",
    "batter_name",
    "pitcher_name",
    "batting_team_id",
    "batting_team_abbr",
    "fielding_team_id",
    "fielding_team_abbr",
    "is_home_batting",
    "balls",
    "strikes",
    "pitch_type",
    "release_speed",
    "release_spin_rate",
    "release_extension",
    "release_pos_x",
    "release_pos_y",
    "release_pos_z",
    "plate_x",
    "plate_z",
    "zone",
    "pfx_x",
    "pfx_z",
    "vx0",
    "vy0",
    "vz0",
    "ax",
    "ay",
    "az",
    "description",
    "event",
    "is_in_play",
    "is_at_bat_end",
    "launch_speed",
    "launch_angle",
    "hit_distance_sc",
    "bb_type",
    "hc_x",
    "hc_y",
    "hit_location",
    "estimated_ba_using_speedangle",
    "estimated_woba_using_speedangle",
    "woba_value",
    "woba_denom",
    "babip_value",
    "iso_value",
    "on_1b",
    "on_2b",
    "on_3b",
]


def print_section(message):
    # 统一打印逐球脚本的关键执行步骤。
    print(f"[pitch] {message}")


def print_progress(current, total, label):
    # 批量读取比赛或逐球事件时按固定步长显示进度。
    if total == 0:
        return
    if current == 1 or current % PROGRESS_STEP == 0 or current == total:
        print_section(f"{label}: {current}/{total}")


def get_data_dir() -> str:
    # 获取 data 目录，不存在时自动创建。
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_games_file_path() -> str:
    # 返回 games.csv 的完整路径。
    return os.path.join(get_data_dir(), "games.csv")


def get_pitch_by_pitch_file_path() -> str:
    # 返回 pitch_by_pitch.csv 的完整路径。
    return os.path.join(get_data_dir(), "pitch_by_pitch.csv")


def initialize_pitch_by_pitch_table() -> None:
    # 初始化空的 pitch_by_pitch.csv，保证后续写入时文件一定存在。
    file_path = get_pitch_by_pitch_file_path()
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print_section("开始初始化 pitch_by_pitch.csv")
        pd.DataFrame(columns=PITCH_BY_PITCH_COLUMNS).to_csv(file_path, index=False)
        print_section("结束初始化 pitch_by_pitch.csv")


def load_games_df() -> pd.DataFrame:
    # 读取 games.csv，作为逐球数据更新的比赛索引。
    file_path = get_games_file_path()
    print_section("开始读取 games.csv")

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise FileNotFoundError("games.csv does not exist or is empty.")

    games_df = pd.read_csv(file_path)
    if games_df.empty:
        raise ValueError("games.csv is empty.")

    total_rows = len(games_df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, "读取比赛索引进度")

    print_section(f"结束读取 games.csv，共检测到 {total_rows} 场比赛")
    return games_df


def load_pitch_by_pitch_df() -> pd.DataFrame:
    # 读取已有的 pitch_by_pitch.csv，用于判断哪些逐球记录已经存在。
    file_path = get_pitch_by_pitch_file_path()
    initialize_pitch_by_pitch_table()
    print_section("开始读取 pitch_by_pitch.csv")
    pitch_df = pd.read_csv(file_path)

    if pitch_df.empty:
        print_section("结束读取 pitch_by_pitch.csv，当前为空表")
        return pd.DataFrame(columns=PITCH_BY_PITCH_COLUMNS)

    total_rows = len(pitch_df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, "读取已有逐球数据进度")

    pitch_df["game_id"] = pitch_df["game_id"].astype(int)
    pitch_df["pitch_id"] = pitch_df["pitch_id"].astype(str)
    print_section(f"结束读取 pitch_by_pitch.csv，共加载 {total_rows} 条记录")
    return pitch_df


def fetch_live_feed(game_id: int) -> dict:
    # 按比赛读取 live feed，这里包含逐打席和逐球数据。
    response = requests.get(
        MLB_LIVE_FEED_URL_TEMPLATE.format(game_id=game_id),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def safe_value(value):
    # 保持缺失值为空字符串，方便 CSV 落库；其他值原样保留。
    if value is None or pd.isna(value):
        return ""
    return value


def safe_int_flag(value) -> int:
    # 将布尔值标准化成 0/1。
    return 1 if bool(value) else 0


def normalize_outs(value) -> int:
    # 将出局数统一标准化为 0/1/2，缺失时默认按 0 处理。
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(2, normalized))


def build_play_event_row(
    game_row: pd.Series,
    play: dict,
    event: dict,
    pitcher_batter_index: int,
    batting_team_id: int,
    batting_team_abbr: str,
    fielding_team_id: int,
    fielding_team_abbr: str,
    is_home_batting: int,
) -> Dict[str, object]:
    # 将一颗球的 live feed 数据整理成一行逐球记录。
    matchup = play.get("matchup", {})
    batter = matchup.get("batter", {})
    pitcher = matchup.get("pitcher", {})
    count = event.get("count", {})
    details = event.get("details", {})
    pitch_data = event.get("pitchData", {})
    coordinates = pitch_data.get("coordinates", {})
    breaks = pitch_data.get("breaks", {})
    hit_data = event.get("hitData", {})
    play_result = play.get("result", {})
    about = play.get("about", {})
    runners = play.get("runners", [])
    # 这里不再使用全场打席序号，
    # 而是改成“当前投手本场面对的第几个打者”。
    matchups_index = pitcher_batter_index
    play_events = play.get("playEvents", [])
    pitch_number = play_events.index(event) + 1 if event in play_events else ""

    runs_scored_on_pitch = sum(
        1
        for runner in runners
        if runner.get("details", {}).get("isScoringEvent")
        and runner.get("playIndex") == event.get("index")
    )

    matchup_data = play.get("matchup", {})
    post_on_first = matchup_data.get("postOnFirst", {})
    post_on_second = matchup_data.get("postOnSecond", {})
    post_on_third = matchup_data.get("postOnThird", {})

    is_in_play = details.get("isInPlay", False)
    is_at_bat_end = details.get("isOut", False) or bool(play_result.get("event"))
    pitch_id = event.get("playId") or f"{game_row['game_id']}_{matchups_index}_{pitch_number}"

    return {
        "pitch_id": str(pitch_id),
        "game_id": int(game_row["game_id"]),
        "season": int(game_row["season"]),
        "pitcher_batter_index": safe_value(matchups_index),
        "pitch_number": safe_value(pitch_number),
        "inning": safe_value(about.get("inning")),
        "inning_half": safe_value(about.get("halfInning")),
        "outs": normalize_outs(count.get("outs", about.get("outs"))),
        "batter_id": safe_value(batter.get("id")),
        "pitcher_id": safe_value(pitcher.get("id")),
        "batter_name": safe_value(batter.get("fullName")),
        "pitcher_name": safe_value(pitcher.get("fullName")),
        "batting_team_id": safe_value(batting_team_id),
        "batting_team_abbr": safe_value(batting_team_abbr),
        "fielding_team_id": safe_value(fielding_team_id),
        "fielding_team_abbr": safe_value(fielding_team_abbr),
        "is_home_batting": safe_int_flag(is_home_batting),
        "balls": safe_value(count.get("balls")),
        "strikes": safe_value(count.get("strikes")),
        "pitch_type": safe_value(details.get("type", {}).get("code")),
        "release_speed": safe_value(pitch_data.get("startSpeed")),
        "release_spin_rate": safe_value(pitch_data.get("breaks", {}).get("spinRate")),
        "release_extension": safe_value(pitch_data.get("extension")),
        "release_pos_x": safe_value(coordinates.get("x0")),
        "release_pos_y": safe_value(coordinates.get("y0")),
        "release_pos_z": safe_value(coordinates.get("z0")),
        "plate_x": safe_value(coordinates.get("pX")),
        "plate_z": safe_value(coordinates.get("pZ")),
        "zone": safe_value(pitch_data.get("zone")),
        "pfx_x": safe_value(coordinates.get("pfxX")),
        "pfx_z": safe_value(coordinates.get("pfxZ")),
        "vx0": safe_value(coordinates.get("vX0")),
        "vy0": safe_value(coordinates.get("vY0")),
        "vz0": safe_value(coordinates.get("vZ0")),
        "ax": safe_value(coordinates.get("aX")),
        "ay": safe_value(coordinates.get("aY")),
        "az": safe_value(coordinates.get("aZ")),
        "description": safe_value(details.get("description")),
        "event": safe_value(play_result.get("event")),
        "is_in_play": safe_int_flag(is_in_play),
        "is_at_bat_end": safe_int_flag(event.get("isLastPitch", False)),
        "launch_speed": safe_value(hit_data.get("launchSpeed")),
        "launch_angle": safe_value(hit_data.get("launchAngle")),
        "hit_distance_sc": safe_value(hit_data.get("totalDistance")),
        "bb_type": safe_value(hit_data.get("trajectory")),
        "hc_x": safe_value(hit_data.get("coordinates", {}).get("coordX")),
        "hc_y": safe_value(hit_data.get("coordinates", {}).get("coordY")),
        "hit_location": safe_value(hit_data.get("location")),
        # 这些高级打击质量指标在当前 live feed 中通常不会稳定返回，
        # 先统一留空，避免把无关字段误写成错误数值。
        "estimated_ba_using_speedangle": safe_value(""),
        "estimated_woba_using_speedangle": safe_value(""),
        "woba_value": safe_value(""),
        "woba_denom": safe_value(""),
        "babip_value": safe_value(""),
        "iso_value": safe_value(""),
        "on_1b": safe_value(post_on_first.get("id")),
        "on_2b": safe_value(post_on_second.get("id")),
        "on_3b": safe_value(post_on_third.get("id")),
    }


def extract_pitch_rows_for_game(game_row: pd.Series, live_feed: dict) -> List[Dict[str, object]]:
    # 从单场比赛的 live feed 中提取所有逐球记录。
    linescore = live_feed.get("liveData", {}).get("linescore", {})
    teams_meta = live_feed.get("gameData", {}).get("teams", {})
    home_meta = teams_meta.get("home", {})
    away_meta = teams_meta.get("away", {})

    home_team_id = safe_value(home_meta.get("id") or game_row["home_team_id"])
    away_team_id = safe_value(away_meta.get("id") or game_row["away_team_id"])
    home_team_abbr = safe_value(home_meta.get("abbreviation") or game_row["home_abbr"])
    away_team_abbr = safe_value(away_meta.get("abbreviation") or game_row["away_abbr"])

    all_plays = live_feed.get("liveData", {}).get("plays", {}).get("allPlays", [])
    rows: List[Dict[str, object]] = []
    pitcher_batter_counts: Dict[str, int] = {}

    total_plays = len(all_plays)
    for play_index, play in enumerate(all_plays, start=1):
        print_progress(play_index, total_plays, "读取逐打席进度")

        about = play.get("about", {})
        half_inning = about.get("halfInning")
        is_top = str(half_inning).lower() == "top"

        batting_team_id = away_team_id if is_top else home_team_id
        batting_team_abbr = away_team_abbr if is_top else home_team_abbr
        fielding_team_id = home_team_id if is_top else away_team_id
        fielding_team_abbr = home_team_abbr if is_top else away_team_abbr
        is_home_batting = 0 if is_top else 1

        # 按投手累计其本场面对的打者顺序。
        pitcher_id = str(play.get("matchup", {}).get("pitcher", {}).get("id", ""))
        pitcher_batter_counts[pitcher_id] = pitcher_batter_counts.get(pitcher_id, 0) + 1
        pitcher_batter_index = pitcher_batter_counts[pitcher_id]

        play_events = play.get("playEvents", [])
        total_events = len(play_events)
        for event_index, event in enumerate(play_events, start=1):
            print_progress(event_index, total_events, f"读取打席 {play.get('atBatIndex', 0)} 逐球进度")

            if not event.get("isPitch"):
                continue

            rows.append(
                build_play_event_row(
                    game_row=game_row,
                    play=play,
                    event=event,
                    pitcher_batter_index=pitcher_batter_index,
                    batting_team_id=batting_team_id,
                    batting_team_abbr=batting_team_abbr,
                    fielding_team_id=fielding_team_id,
                    fielding_team_abbr=fielding_team_abbr,
                    is_home_batting=is_home_batting,
                )
            )

    return rows


def build_pitch_by_pitch(games_df: pd.DataFrame, pitch_df: pd.DataFrame) -> pd.DataFrame:
    # 以 games.csv 为索引，逐场补齐 pitch_by_pitch.csv。
    target_game_ids = set(games_df["game_id"].astype(int))
    if not pitch_df.empty:
        # 当前索引内的比赛重新抓取并覆盖，便于修正字段或补全旧数据。
        pitch_df = pitch_df[~pitch_df["game_id"].astype(int).isin(target_game_ids)].copy()

    existing_pitch_ids: Set[str] = set()
    if not pitch_df.empty:
        existing_pitch_ids = set(pitch_df["pitch_id"].astype(str))

    all_new_rows: List[Dict[str, object]] = []
    total_games = len(games_df)
    print_section(f"开始读取逐球数据，共 {total_games} 场比赛")

    for index, (_, game_row) in enumerate(games_df.iterrows(), start=1):
        print_progress(index, total_games, "读取比赛逐球进度")

        game_id = int(game_row["game_id"])
        live_feed = fetch_live_feed(game_id)
        game_rows = extract_pitch_rows_for_game(game_row, live_feed)

        new_game_rows = [
            row for row in game_rows if str(row["pitch_id"]) not in existing_pitch_ids
        ]
        for row in new_game_rows:
            existing_pitch_ids.add(str(row["pitch_id"]))

        print_section(f"比赛 {game_id} 新增 {len(new_game_rows)} 条逐球记录")
        all_new_rows.extend(new_game_rows)

    print_section(f"结束读取逐球数据，共新增 {len(all_new_rows)} 条记录")

    if not all_new_rows:
        return pitch_df

    new_pitch_df = pd.DataFrame(all_new_rows, columns=PITCH_BY_PITCH_COLUMNS)
    pitch_df = pd.concat([pitch_df, new_pitch_df], ignore_index=True)
    pitch_df = pitch_df.drop_duplicates(subset=["pitch_id"], keep="first")
    pitch_df = pitch_df.sort_values(
        by=["season", "game_id", "pitcher_batter_index", "pitch_number"],
        ascending=[False, False, True, True],
    )
    return pitch_df


def save_pitch_by_pitch_df(pitch_df: pd.DataFrame) -> None:
    # 将更新后的逐球数据写回 pitch_by_pitch.csv。
    print_section("开始写入 pitch_by_pitch.csv")
    pitch_df = pitch_df[PITCH_BY_PITCH_COLUMNS]
    pitch_df.to_csv(get_pitch_by_pitch_file_path(), index=False)
    print_section(f"结束写入 pitch_by_pitch.csv，共 {len(pitch_df)} 条记录")


def main() -> None:
    # 主入口：依赖 games.csv，逐场抓取并补齐 pitch_by_pitch.csv。
    try:
        games_df = load_games_df()
        pitch_df = load_pitch_by_pitch_df()
        pitch_df = build_pitch_by_pitch(games_df, pitch_df)
        save_pitch_by_pitch_df(pitch_df)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Initialization failed: {exc}")
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Failed to fetch MLB pitch_by_pitch data: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Failed to update pitch_by_pitch.csv: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
