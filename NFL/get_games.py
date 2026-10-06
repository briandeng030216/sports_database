import argparse
import os
import sys
from datetime import datetime

import pandas as pd
import requests

try:
    import nflreadpy as nfl
except ImportError:  # pragma: no cover
    nfl = None


GAMES_COLUMNS = [
    "game_id",
    "season",
    "game_date",
    "game_datetime",
    "game_type",
    "week",
    "home_team_id",
    "home_abbr",
    "away_team_id",
    "away_abbr",
    "home_score",
    "away_score",
    "home_win",
    "is_tie",
]
REGULAR_SEASON_GAME_TYPE = "REG"
POSTSEASON_GAME_TYPES = {"WC", "DIV", "CON", "SB"}
POSTSEASON_WEEK_OFFSETS = {
    "WC": 1,
    "DIV": 2,
    "CON": 3,
    "SB": 4,
}
PROGRESS_STEP = 10
TEAM_ABBR_ALIASES = {
    "WAS": "WSH",
    "LA": "LAR",
}


def print_section(message):
    # 统一打印 NFL games 脚本的关键步骤。
    print(f"[games] {message}")


def print_progress(current, total, label):
    # 批量处理比赛或读取 CSV 时，按固定步长打印进度。
    if total == 0:
        return
    if current == 1 or current % PROGRESS_STEP == 0 or current == total:
        print_section(f"{label}: {current}/{total}")


def normalize_team_abbr(team_abbr):
    # 统一 nflverse 与本地 teams.csv 的球队缩写口径。
    value = str(team_abbr or "").strip().upper()
    if not value:
        return ""
    return TEAM_ABBR_ALIASES.get(value, value)


def parse_args():
    # 保留空的参数解析器，当前脚本统一使用终端交互输入。
    parser = argparse.ArgumentParser(
        description="Fetch completed NFL games for a date range."
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
    value = input("Enter team abbreviation filter (optional, e.g. KC): ").strip()
    if not value:
        return None
    return normalize_team_abbr(value)


def prompt_for_season():
    # 在终端里交互输入赛季年份。
    while True:
        value = input("Enter season (e.g. 2024): ").strip()
        if value.isdigit():
            return int(value)
        print("Invalid season. Please enter a year like 2024.")


def prompt_for_week():
    # 在终端里交互输入周数。
    while True:
        value = input("Enter week: ").strip()
        if value.isdigit():
            week = int(value)
            if week > 0:
                return week
        print("Invalid week. Please enter a positive integer.")


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


def resolve_season_week():
    # 使用终端交互输入赛季和周数。
    parse_args()
    season = prompt_for_season()
    week = prompt_for_week()
    return season, week


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


def load_team_id_map():
    # 读取 teams.csv，构建 team_abbr -> team_id 的映射。
    teams_file_path = get_teams_file_path()
    print_section("开始读取 teams.csv")

    if not os.path.exists(teams_file_path) or os.path.getsize(teams_file_path) == 0:
        raise FileNotFoundError("teams.csv does not exist or is empty.")

    teams_df = pd.read_csv(teams_file_path)
    if teams_df.empty:
        raise ValueError("teams.csv is empty.")

    total_rows = len(teams_df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, "读取球队字典进度")

    teams_df["team_id"] = teams_df["team_id"].astype(int)
    team_id_map = dict(zip(teams_df["team_abbr"], teams_df["team_id"]))
    for alias, canonical in TEAM_ABBR_ALIASES.items():
        if canonical in team_id_map and alias not in team_id_map:
            team_id_map[alias] = team_id_map[canonical]
    print_section(f"结束读取 teams.csv，共加载 {len(team_id_map)} 条球队映射")
    return team_id_map


def resolve_schedule_seasons(start_date: str, end_date: str):
    # NFL 赛季会跨年，这里按输入日期推断需要读取的赛季范围。
    start_year = datetime.strptime(start_date, "%Y-%m-%d").year
    end_year = datetime.strptime(end_date, "%Y-%m-%d").year
    seasons = list(range(start_year - 1, end_year + 1))
    return sorted(set(seasons))


def load_schedule_df(seasons):
    # 通过 nflreadpy 读取相关赛季的 schedule 数据，再按日期范围过滤。
    if nfl is None:
        raise ImportError(
            "nflreadpy is not installed. Please install it first with: pip install nflreadpy"
        )

    print_section(f"开始读取 nflreadpy schedules，目标赛季 {seasons}")
    schedule_df = nfl.load_schedules(seasons).to_pandas()
    print_section(f"结束读取 nflreadpy schedules，共加载 {len(schedule_df)} 场原始比赛记录")
    return schedule_df


def build_game_datetime(gameday, gametime):
    # nflverse schedule 提供 gameday 和 gametime，这里直接拼成标准字符串。
    if pd.isna(gameday):
        return None

    game_date = str(gameday)
    if pd.isna(gametime) or str(gametime).strip() == "":
        return game_date

    return f"{game_date}T{str(gametime).strip()}"


def build_regular_season_max_week_map(schedule_df):
    # 先统计每个赛季常规赛的最大周数，供季后赛周数顺延使用。
    regular_df = schedule_df[
        schedule_df["game_type"].astype(str).str.upper() == REGULAR_SEASON_GAME_TYPE
    ].copy()

    if regular_df.empty:
        return {}

    regular_df["season"] = pd.to_numeric(regular_df["season"], errors="coerce")
    regular_df["week"] = pd.to_numeric(regular_df["week"], errors="coerce")
    regular_df = regular_df.dropna(subset=["season", "week"])

    regular_max_week_map = (
        regular_df.groupby("season")["week"].max().astype(int).to_dict()
    )
    return {int(season): int(max_week) for season, max_week in regular_max_week_map.items()}


def normalize_week(season, source_week, game_type, regular_max_week_map):
    # 常规赛保留原周数；季后赛从常规赛最大周数后继续顺延。
    season = int(season)
    source_week = int(source_week)
    game_type = str(game_type).strip().upper()

    if game_type == REGULAR_SEASON_GAME_TYPE:
        return source_week

    max_regular_week = int(regular_max_week_map.get(season, source_week))
    postseason_offset = int(POSTSEASON_WEEK_OFFSETS.get(game_type, 0))
    return max_regular_week + postseason_offset


def fetch_completed_games(start_date, end_date, team_id_map, team_filter=None):
    # 从 nflreadpy 的 schedule 数据中筛选指定日期范围内的已结束比赛。
    if team_filter:
        print_section(
            f"开始读取比赛数据，时间范围 {start_date} 到 {end_date}，球队过滤 {team_filter}"
        )
    else:
        print_section(f"开始读取比赛数据，时间范围 {start_date} 到 {end_date}")

    seasons = resolve_schedule_seasons(start_date, end_date)
    schedule_df = load_schedule_df(seasons)
    schedule_df["gameday"] = pd.to_datetime(schedule_df["gameday"], errors="coerce")
    regular_max_week_map = build_regular_season_max_week_map(schedule_df)
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    filtered_df = schedule_df[
        (schedule_df["gameday"] >= start_dt)
        & (schedule_df["gameday"] <= end_dt)
    ].copy()

    raw_game_count = len(filtered_df)
    print_section(f"检测到 {raw_game_count} 场日期范围内的原始比赛记录")

    games = []
    for index, (_, game) in enumerate(filtered_df.iterrows(), start=1):
        print_progress(index, raw_game_count, "读取比赛进度")

        home_abbr = normalize_team_abbr(game.get("home_team", ""))
        away_abbr = normalize_team_abbr(game.get("away_team", ""))
        game_type = str(game.get("game_type", "")).strip().upper()
        home_score = game.get("home_score")
        away_score = game.get("away_score")
        game_id = game.get("game_id")
        season = game.get("season")
        week = game.get("week")
        gameday = game.get("gameday")
        game_datetime = build_game_datetime(
            gameday.strftime("%Y-%m-%d") if not pd.isna(gameday) else None,
            game.get("gametime"),
        )

        # 只保留常规赛和季后赛。
        if game_type != REGULAR_SEASON_GAME_TYPE and game_type not in POSTSEASON_GAME_TYPES:
            continue

        # 只保留有最终比分的已结束比赛。
        if pd.isna(home_score) or pd.isna(away_score):
            continue

        # 如果用户指定了球队缩写，只保留该球队参与的比赛。
        if team_filter and home_abbr != team_filter and away_abbr != team_filter:
            continue

        if (
            not game_id
            or pd.isna(season)
            or pd.isna(week)
            or not home_abbr
            or not away_abbr
            or home_abbr not in team_id_map
            or away_abbr not in team_id_map
            or pd.isna(gameday)
            or game_datetime is None
        ):
            continue

        home_score = int(home_score)
        away_score = int(away_score)
        is_tie = 1 if home_score == away_score else 0

        games.append(
            {
                "game_id": str(game_id),
                "season": int(season),
                "game_date": gameday.strftime("%Y-%m-%d"),
                "game_datetime": game_datetime,
                "game_type": 1 if game_type == REGULAR_SEASON_GAME_TYPE else 0,
                "week": normalize_week(season, week, game_type, regular_max_week_map),
                "home_team_id": int(team_id_map[home_abbr]),
                "home_abbr": home_abbr,
                "away_team_id": int(team_id_map[away_abbr]),
                "away_abbr": away_abbr,
                "home_score": home_score,
                "away_score": away_score,
                "home_win": 1 if home_score > away_score else 0,
                "is_tie": is_tie,
            }
        )

    print_section(f"结束读取比赛数据，共得到 {len(games)} 场可写入比赛")
    return games


def fetch_completed_games_for_season_week(season, week, team_id_map, team_filter=None):
    # 按赛季和规范化周数筛选已结束比赛，供 update_data.py 逐周更新使用。
    if team_filter:
        print_section(
            f"开始读取比赛数据，赛季 {season}，周 {week}，球队过滤 {team_filter}"
        )
    else:
        print_section(f"开始读取比赛数据，赛季 {season}，周 {week}")

    schedule_df = load_schedule_df([int(season)])
    schedule_df["gameday"] = pd.to_datetime(schedule_df["gameday"], errors="coerce")
    regular_max_week_map = build_regular_season_max_week_map(schedule_df)
    schedule_df["normalized_week"] = schedule_df.apply(
        lambda row: normalize_week(
            row.get("season"),
            row.get("week"),
            row.get("game_type"),
            regular_max_week_map,
        )
        if not pd.isna(row.get("season")) and not pd.isna(row.get("week"))
        else None,
        axis=1,
    )

    filtered_df = schedule_df[
        pd.to_numeric(schedule_df["normalized_week"], errors="coerce") == int(week)
    ].copy()

    raw_game_count = len(filtered_df)
    print_section(f"检测到 {raw_game_count} 场该周原始比赛记录")

    games = []
    for index, (_, game) in enumerate(filtered_df.iterrows(), start=1):
        print_progress(index, raw_game_count, "读取比赛进度")

        home_abbr = normalize_team_abbr(game.get("home_team", ""))
        away_abbr = normalize_team_abbr(game.get("away_team", ""))
        game_type = str(game.get("game_type", "")).strip().upper()
        home_score = game.get("home_score")
        away_score = game.get("away_score")
        game_id = game.get("game_id")
        gameday = game.get("gameday")
        game_datetime = build_game_datetime(
            gameday.strftime("%Y-%m-%d") if not pd.isna(gameday) else None,
            game.get("gametime"),
        )

        if game_type != REGULAR_SEASON_GAME_TYPE and game_type not in POSTSEASON_GAME_TYPES:
            continue

        if pd.isna(home_score) or pd.isna(away_score):
            continue

        if team_filter and home_abbr != team_filter and away_abbr != team_filter:
            continue

        if (
            not game_id
            or not home_abbr
            or not away_abbr
            or home_abbr not in team_id_map
            or away_abbr not in team_id_map
            or pd.isna(gameday)
            or game_datetime is None
        ):
            continue

        home_score = int(home_score)
        away_score = int(away_score)
        is_tie = 1 if home_score == away_score else 0

        games.append(
            {
                "game_id": str(game_id),
                "season": int(season),
                "game_date": gameday.strftime("%Y-%m-%d"),
                "game_datetime": game_datetime,
                "game_type": 1 if game_type == REGULAR_SEASON_GAME_TYPE else 0,
                "week": int(week),
                "home_team_id": int(team_id_map[home_abbr]),
                "home_abbr": home_abbr,
                "away_team_id": int(team_id_map[away_abbr]),
                "away_abbr": away_abbr,
                "home_score": home_score,
                "away_score": away_score,
                "home_win": 1 if home_score > away_score else 0,
                "is_tie": is_tie,
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
        existing_game_ids = set(existing_df["game_id"].astype(str))

    filtered_games = [
        game for game in new_games if str(game["game_id"]) not in existing_game_ids
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
    team_id_map = load_team_id_map()

    try:
        games = fetch_completed_games(start_date, end_date, team_id_map, team_filter)
    except ImportError as exc:
        print(f"Initialization failed: {exc}")
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Failed to fetch NFL games: {exc}")
        sys.exit(1)

    save_games(games)


if __name__ == "__main__":
    main()
