import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
GAMES_COLUMNS = [
    "game_id",
    "season",
    "game_date",
    "game_datetime",
    "game_type",
    "home_team_id",
    "home_abbr",
    "away_team_id",
    "away_abbr",
    "home_score",
    "away_score",
    "home_win",
    "inning",
]
FINAL_STATES = {"Final", "Completed Early", "Game Over"}
REGULAR_SEASON_GAME_TYPE = "R"
POSTSEASON_GAME_TYPES = {"F", "D", "L", "W"}
PROGRESS_STEP = 10
TEAM_TIMEZONES = {
    108: "America/Los_Angeles",
    109: "America/Phoenix",
    110: "America/New_York",
    111: "America/New_York",
    112: "America/Chicago",
    113: "America/New_York",
    114: "America/New_York",
    115: "America/Denver",
    116: "America/New_York",
    117: "America/Chicago",
    118: "America/Chicago",
    119: "America/Los_Angeles",
    120: "America/New_York",
    121: "America/New_York",
    133: "America/Los_Angeles",
    134: "America/New_York",
    135: "America/Los_Angeles",
    136: "America/Los_Angeles",
    137: "America/Los_Angeles",
    138: "America/Chicago",
    139: "America/New_York",
    140: "America/Chicago",
    141: "America/Toronto",
    142: "America/Chicago",
    143: "America/New_York",
    144: "America/New_York",
    145: "America/Chicago",
    146: "America/New_York",
    147: "America/New_York",
    158: "America/Chicago",
}


def print_section(message):
    # 统一打印 games 脚本的关键步骤。
    print(f"[games] {message}")


def print_progress(current, total, label):
    # 批量处理比赛或读取 CSV 时，按固定步长打印进度。
    if total == 0:
        return
    if current == 1 or current % PROGRESS_STEP == 0 or current == total:
        print_section(f"{label}: {current}/{total}")


def parse_args():
    # 保留空的参数解析器，当前脚本统一使用终端交互输入。
    parser = argparse.ArgumentParser(
        description="Fetch completed MLB games for a date range."
    )
    return parser.parse_args()


def prompt_for_date(label):
    # 如果命令行没传日期，就在终端里交互输入。
    while True:
        value = input(f"Enter {label} (YYYY-MM-DD): ").strip()
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            print(f"Invalid {label}. Please use YYYY-MM-DD.")


def prompt_for_team_filter():
    # 如果命令行没传球队缩写，就在终端里交互输入；留空表示不过滤球队。
    value = input("Enter team abbreviation filter (optional, e.g. SD): ").strip()
    if not value:
        return None
    return value.upper()


def resolve_date_range():
    # 使用终端交互输入起止日期和可选的球队过滤条件，并检查日期顺序是否合法。
    parse_args()
    start_date = prompt_for_date("start date")
    end_date = prompt_for_date("end date")
    team_filter = prompt_for_team_filter()

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    if start_dt > end_dt:
        raise ValueError("start_date must be earlier than or equal to end_date.")

    return start_date, end_date, team_filter


def get_data_dir():
    # 获取 data 目录，不存在时自动创建。
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_games_file_path():
    # 返回 games.csv 的完整路径。
    return os.path.join(get_data_dir(), "games.csv")


def get_teams_file_path():
    # 返回 teams.csv 的完整路径。
    return os.path.join(get_data_dir(), "teams.csv")


def initialize_games_table():
    # 初始化空的 games.csv，确保后续追加写入时文件一定存在。
    file_path = get_games_file_path()

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print_section("开始初始化 games.csv 空表")
        pd.DataFrame(columns=GAMES_COLUMNS).to_csv(file_path, index=False)
        print_section("结束初始化 games.csv 空表")

    return file_path


def load_team_abbr_map():
    # 读取 teams.csv，构建 team_id -> team_abbr 的映射，用于接口缺字段时兜底。
    teams_file_path = get_teams_file_path()
    print_section("开始读取 teams.csv")

    if not os.path.exists(teams_file_path) or os.path.getsize(teams_file_path) == 0:
        print_section("结束读取 teams.csv，文件不存在或为空，返回空映射")
        return {}

    teams_df = pd.read_csv(teams_file_path)
    if teams_df.empty:
        print_section("结束读取 teams.csv，文件为空表，返回空映射")
        return {}

    total_rows = len(teams_df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, "读取球队字典进度")

    teams_df["team_id"] = teams_df["team_id"].astype(int)
    team_abbr_map = dict(zip(teams_df["team_id"], teams_df["team_abbr"]))
    print_section(f"结束读取 teams.csv，共加载 {len(team_abbr_map)} 条球队映射")
    return team_abbr_map


def resolve_team_abbr(team, team_abbr_map):
    # 先优先使用接口直接返回的缩写，如果没有再回退到本地字典表。
    team_id = team.get("id")
    if team_id is None:
        return None

    return team.get("abbreviation") or team_abbr_map.get(int(team_id))


def convert_to_local_game_time(game_datetime_utc, home_team_id):
    # 将接口返回的 UTC 开赛时间转换成主场当地时间。
    timezone_name = TEAM_TIMEZONES.get(int(home_team_id))
    if timezone_name is None:
        return None, None

    utc_dt = datetime.fromisoformat(game_datetime_utc.replace("Z", "+00:00"))
    local_dt = utc_dt.astimezone(ZoneInfo(timezone_name))
    local_game_date = local_dt.strftime("%Y-%m-%d")
    local_game_datetime = local_dt.isoformat(timespec="seconds")
    return local_game_date, local_game_datetime


def fetch_completed_games(start_date, end_date, team_abbr_map, team_filter=None):
    # 从 schedule 接口读取指定时间范围内的比赛，并筛选出已结束的常规赛/季后赛。
    if team_filter:
        print_section(
            f"开始读取比赛数据，时间范围 {start_date} 到 {end_date}，球队过滤 {team_filter}"
        )
    else:
        print_section(f"开始读取比赛数据，时间范围 {start_date} 到 {end_date}")

    response = requests.get(
        MLB_SCHEDULE_URL,
        params={
            "sportId": 1,
            "startDate": start_date,
            "endDate": end_date,
            "hydrate": "linescore",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    date_blocks = data.get("dates", [])
    raw_game_count = sum(len(date_block.get("games", [])) for date_block in date_blocks)
    print_section(f"检测到 {raw_game_count} 场原始比赛记录")

    games = []
    processed_games = 0

    for date_block in date_blocks:
        for game in date_block.get("games", []):
            processed_games += 1
            print_progress(processed_games, raw_game_count, "读取比赛进度")

            # 只保留已经完赛的比赛。
            detailed_state = game.get("status", {}).get("detailedState")
            if detailed_state not in FINAL_STATES:
                continue

            # 只保留常规赛和季后赛，常规赛记为 1，季后赛记为 0。
            source_game_type = game.get("gameType")
            if source_game_type != REGULAR_SEASON_GAME_TYPE and (
                source_game_type not in POSTSEASON_GAME_TYPES
            ):
                continue

            home = game.get("teams", {}).get("home", {})
            away = game.get("teams", {}).get("away", {})
            home_team = home.get("team", {})
            away_team = away.get("team", {})
            home_score = home.get("score")
            away_score = away.get("score")
            home_team_id = home_team.get("id")
            away_team_id = away_team.get("id")
            home_abbr = resolve_team_abbr(home_team, team_abbr_map)
            away_abbr = resolve_team_abbr(away_team, team_abbr_map)
            local_game_date, local_game_datetime = convert_to_local_game_time(
                game["gameDate"],
                home_team_id,
            )

            # games 表要求字段完整，所以有任何关键字段缺失时都直接跳过。
            if (
                home_team_id is None
                or away_team_id is None
                or home_abbr is None
                or away_abbr is None
                or local_game_date is None
                or local_game_datetime is None
                or home_score is None
                or away_score is None
                or home_score == away_score
            ):
                continue

            # 如果用户指定了球队缩写，只保留该球队参与的比赛。
            if team_filter and home_abbr != team_filter and away_abbr != team_filter:
                continue

            # 读取比赛结束时的局数，常规赛通常是 9，延长赛会大于 9。
            linescore = game.get("linescore", {})
            inning = (
                linescore.get("currentInning")
                or len(linescore.get("innings", []))
                or linescore.get("scheduledInnings")
            )

            if inning is None:
                continue

            games.append(
                {
                    "game_id": game["gamePk"],
                    "season": int(game["season"]),
                    "game_date": local_game_date,
                    "game_datetime": local_game_datetime,
                    "game_type": 1
                    if source_game_type == REGULAR_SEASON_GAME_TYPE
                    else 0,
                    "home_team_id": int(home_team_id),
                    "home_abbr": home_abbr,
                    "away_team_id": int(away_team_id),
                    "away_abbr": away_abbr,
                    "home_score": int(home_score),
                    "away_score": int(away_score),
                    "home_win": 1 if home_score > away_score else 0,
                    "inning": int(inning),
                }
            )

    print_section(f"结束读取比赛数据，共得到 {len(games)} 场可写入比赛")
    return games


def save_games(new_games):
    # 将新读取到的比赛写入 games.csv，并按照 game_id 去重、按时间倒序排序。
    file_path = initialize_games_table()
    print_section("开始读取现有 games.csv")
    existing_df = pd.read_csv(file_path)
    existing_count = len(existing_df)

    for index in range(1, existing_count + 1):
        print_progress(index, existing_count, "读取现有比赛进度")

    print_section(f"结束读取现有 games.csv，共有 {existing_count} 条记录")

    if existing_df.empty:
        existing_game_ids = set()
    else:
        existing_game_ids = set(existing_df["game_id"].astype(int))

    filtered_games = [
        game for game in new_games if int(game["game_id"]) not in existing_game_ids
    ]

    if not filtered_games:
        print_section("没有检测到需要新增的比赛记录")
        return

    print_section(f"开始写入新比赛，共 {len(filtered_games)} 场")
    new_df = pd.DataFrame(filtered_games, columns=GAMES_COLUMNS)
    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
    updated_df = updated_df.drop_duplicates(subset=["game_id"], keep="first")
    updated_df = updated_df.sort_values(
        by=["game_date", "game_datetime", "game_id"],
        ascending=[False, False, False],
    )
    updated_df.to_csv(file_path, index=False)

    print_section(f"结束写入 games.csv，新增 {len(filtered_games)} 场比赛")
    print(f"Added {len(filtered_games)} new games to: {file_path}")


def main():
    # 主入口：先确定时间范围和球队过滤条件，再读取比赛并写入本地 CSV。
    start_date, end_date, team_filter = resolve_date_range()
    initialize_games_table()
    team_abbr_map = load_team_abbr_map()
    try:
        games = fetch_completed_games(start_date, end_date, team_abbr_map, team_filter)
    except requests.RequestException as exc:
        print(f"Failed to fetch MLB games: {exc}")
        sys.exit(1)

    save_games(games)


if __name__ == "__main__":
    main()
