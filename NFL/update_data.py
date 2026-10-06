import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set

import pandas as pd

try:
    import nflreadpy as nfl
except ImportError:  # pragma: no cover
    nfl = None

import get_games

STATUS_COLUMNS = [
    "game_id",
    "season",
    "game_date",
    "home_abbr",
    "away_abbr",
    "games_loaded",
    "players_loaded",
    "play_by_play_loaded",
    "team_loaded",
    "passing_loaded",
    "rushing_loaded",
    "receiving_loaded",
    "def_loaded",
    "block_loaded",
    "fully_loaded",
    "last_updated",
    "error_message",
]
STAGE_COLUMNS = [
    "games_loaded",
    "players_loaded",
    "play_by_play_loaded",
    "team_loaded",
    "passing_loaded",
    "rushing_loaded",
    "receiving_loaded",
    "def_loaded",
    "block_loaded",
]
PLAYERS_COLUMNS = [
    "player_id",
    "gsis_id",
    "full_name",
    "first_name",
    "last_name",
    "birth_date",
    "position",
    "college",
    "height",
    "weight",
    "draft_year",
]
PLAY_BY_PLAY_COLUMNS = [
    "play_id",
    "game_id",
    "season",
    "week",
    "quarter",
    "quarter_minutes_remaining",
    "quarter_seconds_remaining",
    "posteam",
    "defteam",
    "home_team",
    "away_team",
    "yardline_100",
    "down",
    "ydstogo",
    "goal_to_go",
    "home_score",
    "away_score",
    "score_differential",
    "drive",
    "drive_play_index",
    "series",
    "series_success",
    "play_type",
    "play_type_nfl",
    "desc",
    "shotgun",
    "no_huddle",
    "qb_dropback",
    "qb_spike",
    "qb_kneel",
    "qb_scramble",
    "pass_attempt",
    "complete_pass",
    "incomplete_pass",
    "interception",
    "air_yards",
    "yards_after_catch",
    "passing_yards",
    "rush_attempt",
    "rushing_yards",
    "yards_gained",
    "first_down",
    "touchdown",
    "turnover",
    "fumble",
    "fumble_lost",
    "safety",
    "penalty",
    "penalty_yards",
    "two_point_attempt",
    "two_point_conv_result",
    "field_goal_attempt",
    "extra_point_attempt",
    "sack",
    "return_yards",
    "timeout",
    "timeout_team",
    "passer_gsis_id",
    "receiver_gsis_id",
    "rusher_gsis_id",
    "tackler_gsis_id",
]
TEAM_GAME_STATS_COLUMNS = [
    "game_id",
    "season",
    "week",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "team_win",
    "is_tie",
    "points_for",
    "points_against",
    "score_differential",
    "offensive_plays",
    "yards",
    "first_downs",
    "turnovers",
    "fumbles_lost",
    "pass_attempts",
    "completions",
    "passing_yards",
    "passing_tds",
    "interceptions_thrown",
    "sacks_allowed",
    "sack_yards_lost",
    "net_passing_yards",
    "rush_attempts",
    "rushing_yards",
    "rushing_tds",
    "penalties",
    "penalty_yards",
    "third_down_attempts",
    "third_down_conversions",
    "fourth_down_attempts",
    "fourth_down_conversions",
    "time_of_possession",
]
PLAYER_PASSING_COLUMNS = [
    "game_id",
    "season",
    "week",
    "player_id",
    "full_name",
    "position",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "pass_attempts",
    "completions",
    "incompletions",
    "passing_yards",
    "passing_tds",
    "interceptions",
    "sacks_taken",
    "sack_yards_lost",
    "passing_first_downs",
    "passing_air_yards",
    "passing_yards_after_catch",
    "longest_completion",
    "completion_percentage",
    "qb_rating",
    "pass_attempts_0_5",
    "pass_completions_0_5",
    "pass_attempts_5_10",
    "pass_completions_5_10",
    "pass_attempts_10_20",
    "pass_completions_10_20",
    "pass_attempts_20_plus",
    "pass_completions_20_plus",
]
PLAYER_RUSHING_COLUMNS = [
    "game_id",
    "season",
    "week",
    "player_id",
    "full_name",
    "position",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "rush_attempts",
    "rushing_yards",
    "rushing_tds",
    "rushing_first_downs",
    "longest_rush",
    "fumbles",
    "fumbles_lost",
    "rush_0_5",
    "rush_5_10",
    "rush_10_20",
    "rush_20_plus",
]
PLAYER_RECEIVING_COLUMNS = [
    "game_id",
    "season",
    "week",
    "player_id",
    "full_name",
    "position",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "targets",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "receiving_first_downs",
    "air_yards",
    "yards_after_catch",
    "longest_reception",
    "fumbles",
    "fumbles_lost",
    "targets_0_5",
    "receptions_0_5",
    "targets_5_10",
    "receptions_5_10",
    "targets_10_20",
    "receptions_10_20",
    "targets_20_plus",
    "receptions_20_plus",
    "receiving_0_5",
    "receiving_5_10",
    "receiving_10_20",
    "receiving_20_plus",
]
PLAYER_DEF_COLUMNS = [
    "game_id",
    "season",
    "week",
    "player_id",
    "full_name",
    "position",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "def_snaps",
    "special_teams_snaps",
    "tackles",
    "solo_tackles",
    "assist_tackles",
    "tackles_for_loss",
    "qb_hits",
    "sacks",
    "sack_yards",
    "passes_defended",
    "interceptions",
    "interception_yards",
    "interception_tds",
    "forced_fumbles",
    "fumble_recoveries",
    "fumble_recovery_yards",
    "fumble_recovery_tds",
    "defensive_tds",
    "safeties",
    "special_teams_tackles",
    "special_teams_solo_tackles",
    "special_teams_assist_tackles",
    "kick_returns",
    "kick_return_yards",
    "kick_return_tds",
    "longest_kick_return",
    "punt_returns",
    "punt_return_yards",
    "punt_return_tds",
    "longest_punt_return",
    "blocked_punts",
    "blocked_field_goals",
    "blocked_extra_points",
    "blocked_kicks",
]
PLAYER_BLOCK_COLUMNS = [
    "game_id",
    "season",
    "week",
    "player_id",
    "full_name",
    "position",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "off_snaps",
    "pass_block_snaps",
    "run_block_snaps",
    "pressures_allowed",
    "hurries_allowed",
    "qb_hits_allowed",
    "sacks_allowed",
    "sack_yards_allowed",
    "penalties",
    "holding_penalties",
    "false_start_penalties",
    "special_teams_block_snaps",
    "punt_block_snaps",
    "field_goal_block_snaps",
    "extra_point_block_snaps",
    "blocked_punts_allowed",
    "blocked_field_goals_allowed",
    "blocked_extra_points_allowed",
]
PROGRESS_STEP = 10


def print_section(message: str) -> None:
    # 统一打印 NFL pipeline 的关键执行步骤。
    print(f"[pipeline] {message}")


def print_progress(current: int, total: int, label: str) -> None:
    # 批量读取或逐场处理时按固定步长输出进度。
    if total == 0:
        return
    if current == 1 or current % PROGRESS_STEP == 0 or current == total:
        print_section(f"{label}: {current}/{total}")


def require_nflreadpy() -> None:
    # 确保 nflreadpy 已安装。
    if nfl is None:
        raise ImportError(
            "nflreadpy is not installed. Please activate the project venv first."
        )


def get_data_dir() -> str:
    # 获取 NFL data 目录。
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_file_path(file_name: str) -> str:
    # 返回 data 目录下文件的完整路径。
    return os.path.join(get_data_dir(), file_name)


def now_text() -> str:
    # 生成状态表更新时间。
    return datetime.now().isoformat(timespec="seconds")


def prompt_for_inputs():
    # 在终端读取 season、起止 week 和可选球队过滤条件。
    season = get_games.prompt_for_season()
    while True:
        start_text = input("Enter start week: ").strip()
        if start_text.isdigit() and int(start_text) > 0:
            start_week = int(start_text)
            break
        print("Invalid start week. Please enter a positive integer.")

    while True:
        end_text = input("Enter end week: ").strip()
        if end_text.isdigit() and int(end_text) > 0:
            end_week = int(end_text)
            break
        print("Invalid end week. Please enter a positive integer.")

    if start_week > end_week:
        raise ValueError("start_week must be less than or equal to end_week.")
    team_filter = get_games.prompt_for_team_filter()
    return season, start_week, end_week, team_filter


def initialize_csv(file_name: str, columns: List[str]) -> None:
    # 初始化空 CSV，保证后续读写安全。
    file_path = get_file_path(file_name)
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        pd.DataFrame(columns=columns).to_csv(file_path, index=False)


def load_local_df(file_name: str, columns: List[str], label: str) -> pd.DataFrame:
    # 读取本地业务表，空文件时返回空表。
    initialize_csv(file_name, columns)
    file_path = get_file_path(file_name)
    print_section(f"开始读取 {label}")
    df = pd.read_csv(file_path)
    if df.empty:
        print_section(f"结束读取 {label}，当前为空表")
        return pd.DataFrame(columns=columns)
    print_section(f"结束读取 {label}，共加载 {len(df)} 条记录")
    return df


def save_local_df(df: pd.DataFrame, file_name: str, columns: List[str], label: str) -> None:
    # 将表写回本地。
    print_section(f"开始写入 {label}")
    df = df[columns]
    df.to_csv(get_file_path(file_name), index=False)
    print_section(f"结束写入 {label}，共 {len(df)} 条记录")


def load_status_df() -> pd.DataFrame:
    # 读取逐场更新状态表。
    initialize_csv("game_update_status.csv", STATUS_COLUMNS)
    status_df = pd.read_csv(get_file_path("game_update_status.csv"))
    if status_df.empty:
        return pd.DataFrame(columns=STATUS_COLUMNS)
    status_df["game_id"] = status_df["game_id"].astype(str)
    for column in STAGE_COLUMNS + ["fully_loaded"]:
        status_df[column] = pd.to_numeric(status_df[column], errors="coerce").fillna(0).astype(int)
    return status_df


def save_status_df(status_df: pd.DataFrame) -> None:
    # 保存状态表。
    status_df = status_df[STATUS_COLUMNS]
    status_df = status_df.sort_values(
        by=["fully_loaded", "season", "game_date", "game_id"],
        ascending=[True, False, False, False],
    )
    status_df.to_csv(get_file_path("game_update_status.csv"), index=False)


def recompute_fully_loaded(status_df: pd.DataFrame) -> pd.DataFrame:
    # 当所有阶段都完成时，将 fully_loaded 标为 1。
    if status_df.empty:
        return status_df
    status_df["fully_loaded"] = (
        status_df["games_loaded"].astype(int)
        & status_df["players_loaded"].astype(int)
        & status_df["play_by_play_loaded"].astype(int)
        & status_df["team_loaded"].astype(int)
        & status_df["passing_loaded"].astype(int)
        & status_df["rushing_loaded"].astype(int)
        & status_df["receiving_loaded"].astype(int)
        & status_df["def_loaded"].astype(int)
        & status_df["block_loaded"].astype(int)
    ).astype(int)
    return status_df


def ensure_status_rows(status_df: pd.DataFrame, target_games_df: pd.DataFrame) -> pd.DataFrame:
    # 确保本次目标比赛都在状态表中。
    existing_game_ids = set()
    if not status_df.empty:
        existing_game_ids = set(status_df["game_id"].astype(str))

    new_rows = []
    for _, game_row in target_games_df.iterrows():
        game_id = str(game_row["game_id"])
        if game_id in existing_game_ids:
            continue
        new_rows.append(
            {
                "game_id": game_id,
                "season": int(game_row["season"]),
                "game_date": str(game_row["game_date"]),
                "home_abbr": str(game_row["home_abbr"]),
                "away_abbr": str(game_row["away_abbr"]),
                "games_loaded": 1,
                "players_loaded": 0,
                "play_by_play_loaded": 0,
                "team_loaded": 0,
                "passing_loaded": 0,
                "rushing_loaded": 0,
                "receiving_loaded": 0,
                "def_loaded": 0,
                "block_loaded": 0,
                "fully_loaded": 0,
                "last_updated": now_text(),
                "error_message": "",
            }
        )

    if new_rows:
        status_df = pd.concat([status_df, pd.DataFrame(new_rows, columns=STATUS_COLUMNS)], ignore_index=True)

    target_games_map = {
        str(row["game_id"]): row for _, row in target_games_df.iterrows()
    }
    for index, row in status_df.iterrows():
        game_id = str(row["game_id"])
        if game_id not in target_games_map:
            continue
        game_row = target_games_map[game_id]
        status_df.loc[index, "season"] = int(game_row["season"])
        status_df.loc[index, "game_date"] = str(game_row["game_date"])
        status_df.loc[index, "home_abbr"] = str(game_row["home_abbr"])
        status_df.loc[index, "away_abbr"] = str(game_row["away_abbr"])
        status_df.loc[index, "games_loaded"] = 1

    return recompute_fully_loaded(status_df)


def get_status_row(status_df: pd.DataFrame, game_id: str) -> pd.Series:
    # 读取单场比赛状态。
    row_df = status_df.loc[status_df["game_id"].astype(str) == str(game_id)]
    if row_df.empty:
        raise ValueError(f"Missing status row for game {game_id}")
    return row_df.iloc[0]


def mark_stage_success(status_df: pd.DataFrame, game_id: str, stage_column: str) -> pd.DataFrame:
    # 标记单个阶段完成。
    mask = status_df["game_id"].astype(str) == str(game_id)
    status_df.loc[mask, stage_column] = 1
    status_df.loc[mask, "last_updated"] = now_text()
    status_df.loc[mask, "error_message"] = ""
    return recompute_fully_loaded(status_df)


def mark_stage_error(status_df: pd.DataFrame, game_id: str, error_message: str) -> pd.DataFrame:
    # 记录单场比赛错误。
    mask = status_df["game_id"].astype(str) == str(game_id)
    status_df.loc[mask, "last_updated"] = now_text()
    status_df.loc[mask, "error_message"] = error_message
    return recompute_fully_loaded(status_df)


def safe_int(value, default: int = 0) -> int:
    # 安全转 int。
    if pd.isna(value) or value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value, default: float = 0.0) -> float:
    # 安全转 float。
    if pd.isna(value) or value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_text(value, default: str = "") -> str:
    # 安全文本化。
    if pd.isna(value) or value is None:
        return default
    return str(value)


def normalize_team_abbr(value) -> str:
    # 统一 nflverse 源数据与本地 teams.csv 的球队缩写口径。
    return get_games.normalize_team_abbr(safe_text(value))


def bool_flag(value) -> int:
    # 将真值转成 0/1。
    return 1 if safe_float(value, 0.0) != 0 else 0


def bucket_name(value) -> Optional[str]:
    # 将码数分到对应区间。
    if pd.isna(value) or value is None:
        return None
    yards = float(value)
    if yards <= 5:
        return "0_5"
    if yards <= 10:
        return "5_10"
    if yards <= 20:
        return "10_20"
    return "20_plus"


def compute_qb_rating(completions: int, attempts: int, yards: int, tds: int, interceptions: int) -> float:
    # 计算 NFL passer rating。
    if attempts <= 0:
        return 0.0
    a = ((completions / attempts) - 0.3) * 5
    b = ((yards / attempts) - 3) * 0.25
    c = (tds / attempts) * 20
    d = 2.375 - ((interceptions / attempts) * 25)
    components = [a, b, c, d]
    components = [max(0.0, min(2.375, item)) for item in components]
    return round((sum(components) / 6) * 100, 2)


def parse_clock(time_text: str) -> tuple[int, int]:
    # 将 MM:SS 转成分和秒。
    if not time_text or ":" not in time_text:
        return 0, 0
    minutes_text, seconds_text = str(time_text).split(":", 1)
    return safe_int(minutes_text), safe_int(seconds_text)


def sum_time_strings(time_values: List[str]) -> str:
    # 汇总一组 MM:SS 文本。
    total_seconds = 0
    for value in time_values:
        if not value or ":" not in str(value):
            continue
        minutes, seconds = parse_clock(str(value))
        total_seconds += minutes * 60 + seconds
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def get_all_gsis_ids_from_participation(game_participation_df: pd.DataFrame) -> Set[str]:
    # 从 participation 数据里提取该场所有出现过的 GSIS ID。
    gsis_ids: Set[str] = set()
    for column in ["players_on_play", "offense_players", "defense_players"]:
        if column not in game_participation_df.columns:
            continue
        for value in game_participation_df[column].dropna().astype(str):
            for gsis_id in value.split(";"):
                gsis_id = gsis_id.strip()
                if gsis_id:
                    gsis_ids.add(gsis_id)
    return gsis_ids


def get_all_gsis_ids_from_pbp(game_pbp_df: pd.DataFrame) -> Set[str]:
    # 从 pbp 中提取各类 player_id 字段。
    gsis_ids: Set[str] = set()
    candidate_columns = [
        column
        for column in game_pbp_df.columns
        if "player_id" in column or column in {"passer_id", "receiver_id", "rusher_id"}
    ]
    for column in candidate_columns:
        for value in game_pbp_df[column].dropna().astype(str):
            value = value.strip()
            if value:
                gsis_ids.add(value)
    return gsis_ids


def build_players_master_map(players_master_df: pd.DataFrame) -> Dict[str, dict]:
    # 建立 gsis_id -> 玩家主数据映射。
    players_master_df = players_master_df.copy()
    players_master_df["gsis_id"] = players_master_df["gsis_id"].astype(str)
    return {
        str(row["gsis_id"]): row.to_dict()
        for _, row in players_master_df.iterrows()
        if safe_text(row.get("gsis_id")) != ""
    }


def build_team_id_map_df(teams_df: pd.DataFrame) -> Dict[str, int]:
    # 建立 team_abbr -> team_id 映射。
    team_id_map = {
        str(row["team_abbr"]): int(row["team_id"])
        for _, row in teams_df.iterrows()
    }
    for alias, canonical in get_games.TEAM_ABBR_ALIASES.items():
        if canonical in team_id_map and alias not in team_id_map:
            team_id_map[alias] = team_id_map[canonical]
    return team_id_map


def build_player_lookup_maps(players_df: pd.DataFrame) -> tuple[Dict[str, int], Dict[str, dict]]:
    # 建立 gsis_id -> player_id 与 gsis_id -> 完整本地主数据映射。
    if players_df.empty:
        return {}, {}
    players_df = players_df.copy()
    players_df["player_id"] = pd.to_numeric(players_df["player_id"], errors="coerce").astype("Int64")
    player_id_map = {}
    player_row_map = {}
    for _, row in players_df.iterrows():
        gsis_id = safe_text(row.get("gsis_id"))
        if gsis_id == "" or pd.isna(row.get("player_id")):
            continue
        player_id_map[gsis_id] = int(row["player_id"])
        player_row_map[gsis_id] = row.to_dict()
    return player_id_map, player_row_map


def build_target_games_df(
    season: int,
    start_week: int,
    end_week: int,
    team_filter: Optional[str] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    # 读取目标周区间的比赛，并同步写入 games.csv；可按球队过滤。
    print_section("开始更新 games.csv")
    team_id_map = get_games.load_team_id_map()
    target_games = []
    for week in range(int(start_week), int(end_week) + 1):
        target_games.extend(
            get_games.fetch_completed_games_for_season_week(
                season=season,
                week=week,
                team_id_map=team_id_map,
                team_filter=team_filter,
            )
        )
    get_games.save_games(target_games)

    if not target_games:
        return pd.DataFrame(columns=get_games.GAMES_COLUMNS), pd.DataFrame()

    target_games_df = pd.DataFrame(target_games, columns=get_games.GAMES_COLUMNS)
    schedule_obj = get_games.load_schedule_df([int(season)])
    schedule_df = (
        schedule_obj.to_pandas()
        if hasattr(schedule_obj, "to_pandas")
        else schedule_obj
    )
    schedule_df["gameday"] = pd.to_datetime(schedule_df["gameday"], errors="coerce")
    regular_max_week_map = get_games.build_regular_season_max_week_map(schedule_df)
    schedule_df["normalized_week"] = schedule_df.apply(
        lambda row: get_games.normalize_week(
            row.get("season"),
            row.get("week"),
            row.get("game_type"),
            regular_max_week_map,
        )
        if not pd.isna(row.get("season")) and not pd.isna(row.get("week"))
        else None,
        axis=1,
    )
    target_schedule_df = schedule_df[
        pd.to_numeric(schedule_df["normalized_week"], errors="coerce").between(
            int(start_week), int(end_week)
        )
    ].copy()
    target_schedule_df["game_id"] = target_schedule_df["game_id"].astype(str)

    target_games_df["game_id"] = target_games_df["game_id"].astype(str)
    merged_df = target_games_df.merge(
        target_schedule_df[["game_id", "week", "game_type"]].rename(
            columns={"week": "source_week", "game_type": "source_game_type"}
        ),
        on="game_id",
        how="left",
    )
    merged_df["source_season_type"] = merged_df["source_game_type"].apply(
        lambda value: "REG" if safe_text(value).upper() == get_games.REGULAR_SEASON_GAME_TYPE else "POST"
    )
    merged_df = merged_df.sort_values(
        by=["game_date", "game_datetime", "game_id"],
        ascending=[False, False, False],
    )
    print_section(
        f"结束更新 games.csv，本次目标比赛共 {len(merged_df)} 场"
    )
    return merged_df, target_schedule_df


def load_sources_for_weeks(
    season: int,
    start_week: int,
    end_week: int,
    target_game_ids: Set[str],
) -> Dict[str, object]:
    # 一次性加载本次周区间处理需要的 nflreadpy 源数据。
    require_nflreadpy()
    print_section(
        f"开始加载 NFL 源数据，season={season}, weeks={start_week}-{end_week}"
    )

    players_master_df = nfl.load_players().to_pandas()
    player_stats_df = nfl.load_player_stats(int(season), summary_level="week").to_pandas()
    team_stats_df = nfl.load_team_stats(int(season), summary_level="week").to_pandas()
    pbp_df = nfl.load_pbp(int(season)).to_pandas()
    participation_df = nfl.load_participation(int(season)).to_pandas()

    pbp_df["game_id"] = pbp_df["game_id"].astype(str)
    participation_df["nflverse_game_id"] = participation_df["nflverse_game_id"].astype(str)

    for column in ["team", "opponent_team"]:
        if column in player_stats_df.columns:
            player_stats_df[column] = player_stats_df[column].apply(normalize_team_abbr)
        if column in team_stats_df.columns:
            team_stats_df[column] = team_stats_df[column].apply(normalize_team_abbr)

    for column in ["posteam", "defteam", "home_team", "away_team", "timeout_team"]:
        if column in pbp_df.columns:
            pbp_df[column] = pbp_df[column].apply(normalize_team_abbr)

    pbp_df = pbp_df[pbp_df["game_id"].isin(target_game_ids)].copy()
    participation_df = participation_df[
        participation_df["nflverse_game_id"].isin(target_game_ids)
    ].copy()

    print_section(
        "结束加载 NFL 源数据，"
        f"players={len(players_master_df)}, "
        f"player_stats={len(player_stats_df)}, "
        f"team_stats={len(team_stats_df)}, "
        f"pbp={len(pbp_df)}, "
        f"participation={len(participation_df)}"
    )
    return {
        "players_master_df": players_master_df,
        "player_stats_df": player_stats_df,
        "team_stats_df": team_stats_df,
        "pbp_df": pbp_df,
        "participation_df": participation_df,
    }


def filter_game_player_stats(player_stats_df: pd.DataFrame, game_row: pd.Series) -> pd.DataFrame:
    # 取出当前比赛对应的 player_stats 行。
    source_week = safe_int(game_row.get("source_week"))
    season_type = safe_text(game_row.get("source_season_type"))
    home_abbr = safe_text(game_row.get("home_abbr"))
    away_abbr = safe_text(game_row.get("away_abbr"))

    filtered_df = player_stats_df.copy()
    filtered_df["team_normalized"] = filtered_df["team"].apply(normalize_team_abbr)
    filtered_df["opponent_team_normalized"] = filtered_df["opponent_team"].apply(normalize_team_abbr)

    return filtered_df[
        (pd.to_numeric(filtered_df["season"], errors="coerce") == int(game_row["season"]))
        & (pd.to_numeric(filtered_df["week"], errors="coerce") == source_week)
        & (filtered_df["season_type"].astype(str).str.upper() == season_type)
        & (
            ((filtered_df["team_normalized"] == home_abbr) & (filtered_df["opponent_team_normalized"] == away_abbr))
            | ((filtered_df["team_normalized"] == away_abbr) & (filtered_df["opponent_team_normalized"] == home_abbr))
        )
    ].copy()


def filter_game_team_stats(team_stats_df: pd.DataFrame, game_row: pd.Series) -> pd.DataFrame:
    # 取出当前比赛对应的 team_stats 行。
    source_week = safe_int(game_row.get("source_week"))
    season_type = safe_text(game_row.get("source_season_type"))
    home_abbr = safe_text(game_row.get("home_abbr"))
    away_abbr = safe_text(game_row.get("away_abbr"))

    filtered_df = team_stats_df.copy()
    filtered_df["team_normalized"] = filtered_df["team"].apply(normalize_team_abbr)
    filtered_df["opponent_team_normalized"] = filtered_df["opponent_team"].apply(normalize_team_abbr)

    return filtered_df[
        (pd.to_numeric(filtered_df["season"], errors="coerce") == int(game_row["season"]))
        & (pd.to_numeric(filtered_df["week"], errors="coerce") == source_week)
        & (filtered_df["season_type"].astype(str).str.upper() == season_type)
        & (
            ((filtered_df["team_normalized"] == home_abbr) & (filtered_df["opponent_team_normalized"] == away_abbr))
            | ((filtered_df["team_normalized"] == away_abbr) & (filtered_df["opponent_team_normalized"] == home_abbr))
        )
    ].copy()


def filter_game_pbp(pbp_df: pd.DataFrame, game_id: str) -> pd.DataFrame:
    # 取出单场 pbp。
    return pbp_df[pbp_df["game_id"].astype(str) == str(game_id)].copy()


def filter_game_participation(participation_df: pd.DataFrame, game_id: str) -> pd.DataFrame:
    # 取出单场 participation。
    return participation_df[
        participation_df["nflverse_game_id"].astype(str) == str(game_id)
    ].copy()


def infer_team_from_participation(
    game_row: pd.Series,
    game_pbp_df: pd.DataFrame,
    game_participation_df: pd.DataFrame,
    gsis_id: str,
) -> tuple[str, str]:
    # 根据本场 participation 和 pbp 推断球员代表球队，避免只依赖 latest_team。
    home_abbr = safe_text(game_row["home_abbr"])
    away_abbr = safe_text(game_row["away_abbr"])

    if game_pbp_df.empty or game_participation_df.empty:
        return away_abbr, home_abbr

    play_team_map: Dict[str, tuple[str, str]] = {}
    for _, play in game_pbp_df.iterrows():
        play_id = safe_text(play.get("play_id"))
        if play_id == "":
            continue
        play_team_map[play_id] = (
            normalize_team_abbr(play.get("posteam")),
            normalize_team_abbr(play.get("defteam")),
        )

    team_counts: Dict[str, int] = {}
    for _, row in game_participation_df.iterrows():
        play_id = safe_text(row.get("play_id"))
        posteam, defteam = play_team_map.get(play_id, ("", ""))

        offense_players = {
            item.strip()
            for item in safe_text(row.get("offense_players")).split(";")
            if item.strip()
        }
        defense_players = {
            item.strip()
            for item in safe_text(row.get("defense_players")).split(";")
            if item.strip()
        }

        if gsis_id in offense_players and posteam:
            team_counts[posteam] = team_counts.get(posteam, 0) + 1
        if gsis_id in defense_players and defteam:
            team_counts[defteam] = team_counts.get(defteam, 0) + 1

    if not team_counts:
        return away_abbr, home_abbr

    team_abbr = max(team_counts.items(), key=lambda item: item[1])[0]
    opponent_abbr = away_abbr if team_abbr == home_abbr else home_abbr
    return team_abbr, opponent_abbr


def process_players_for_game(
    game_row: pd.Series,
    players_df: pd.DataFrame,
    players_master_map: Dict[str, dict],
    game_pbp_df: pd.DataFrame,
    game_participation_df: pd.DataFrame,
    game_player_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    # 基于当前比赛出现过的 GSIS ID 更新 players.csv。
    existing_gsis_ids = set()
    if not players_df.empty:
        existing_gsis_ids = set(players_df["gsis_id"].astype(str))

    target_gsis_ids = set(game_player_stats_df["player_id"].dropna().astype(str))
    target_gsis_ids.update(get_all_gsis_ids_from_pbp(game_pbp_df))
    target_gsis_ids.update(get_all_gsis_ids_from_participation(game_participation_df))
    missing_gsis_ids = sorted(gsis_id for gsis_id in target_gsis_ids if gsis_id not in existing_gsis_ids)

    if not missing_gsis_ids:
        return players_df

    next_player_id = 0 if players_df.empty else safe_int(pd.to_numeric(players_df["player_id"], errors="coerce").max(), 0) + 1
    new_rows = []
    for gsis_id in missing_gsis_ids:
        player_source = players_master_map.get(gsis_id)
        if player_source is None:
            continue

        draft_year = player_source.get("draft_year")
        if pd.isna(draft_year):
            draft_year = player_source.get("rookie_season")

        new_rows.append(
            {
                "player_id": next_player_id,
                "gsis_id": gsis_id,
                "full_name": safe_text(player_source.get("display_name")),
                "first_name": safe_text(player_source.get("first_name")),
                "last_name": safe_text(player_source.get("last_name")),
                "birth_date": safe_text(player_source.get("birth_date")),
                "position": safe_text(player_source.get("position")),
                "college": safe_text(player_source.get("college_name")),
                "height": safe_int(player_source.get("height")),
                "weight": safe_int(player_source.get("weight")),
                "draft_year": safe_int(draft_year),
            }
        )
        next_player_id += 1

    if not new_rows:
        return players_df

    new_df = pd.DataFrame(new_rows, columns=PLAYERS_COLUMNS)
    players_df = pd.concat([players_df, new_df], ignore_index=True)
    players_df = players_df.drop_duplicates(subset=["gsis_id"], keep="first")
    players_df = players_df.sort_values(by=["player_id"], ascending=[True])
    save_local_df(players_df, "players.csv", PLAYERS_COLUMNS, "players.csv")
    return players_df


def build_play_by_play_rows(game_row: pd.Series, game_pbp_df: pd.DataFrame) -> List[dict]:
    # 将 nflverse pbp 映射到本地 play_by_play schema。
    rows: List[dict] = []
    for _, play in game_pbp_df.iterrows():
        minutes, seconds = parse_clock(safe_text(play.get("time")))
        tackler_gsis_id = (
            safe_text(play.get("solo_tackle_1_player_id"))
            or safe_text(play.get("tackle_with_assist_1_player_id"))
            or safe_text(play.get("assist_tackle_1_player_id"))
        )

        rows.append(
            {
                "play_id": safe_text(play.get("play_id")),
                "game_id": safe_text(game_row["game_id"]),
                "season": int(game_row["season"]),
                "week": int(game_row["week"]),
                "quarter": safe_int(play.get("qtr")),
                "quarter_minutes_remaining": minutes,
                "quarter_seconds_remaining": seconds,
                "posteam": normalize_team_abbr(play.get("posteam")),
                "defteam": normalize_team_abbr(play.get("defteam")),
                "home_team": normalize_team_abbr(play.get("home_team")),
                "away_team": normalize_team_abbr(play.get("away_team")),
                "yardline_100": safe_int(play.get("yardline_100")),
                "down": safe_int(play.get("down")),
                "ydstogo": safe_int(play.get("ydstogo")),
                "goal_to_go": bool_flag(play.get("goal_to_go")),
                "home_score": safe_int(play.get("total_home_score")),
                "away_score": safe_int(play.get("total_away_score")),
                "score_differential": safe_int(play.get("score_differential")),
                "drive": safe_int(play.get("drive")),
                "drive_play_index": safe_int(play.get("order_sequence")),
                "series": safe_int(play.get("series")),
                "series_success": bool_flag(play.get("series_success")),
                "play_type": safe_text(play.get("play_type")),
                "play_type_nfl": safe_text(play.get("play_type_nfl")),
                "desc": safe_text(play.get("desc")),
                "shotgun": bool_flag(play.get("shotgun")),
                "no_huddle": bool_flag(play.get("no_huddle")),
                "qb_dropback": bool_flag(play.get("qb_dropback")),
                "qb_spike": bool_flag(play.get("qb_spike")),
                "qb_kneel": bool_flag(play.get("qb_kneel")),
                "qb_scramble": bool_flag(play.get("qb_scramble")),
                "pass_attempt": bool_flag(play.get("pass_attempt")),
                "complete_pass": bool_flag(play.get("complete_pass")),
                "incomplete_pass": bool_flag(play.get("incomplete_pass")),
                "interception": bool_flag(play.get("interception")),
                "air_yards": safe_int(play.get("air_yards")),
                "yards_after_catch": safe_int(play.get("yards_after_catch")),
                "passing_yards": safe_int(play.get("passing_yards")),
                "rush_attempt": bool_flag(play.get("rush_attempt")),
                "rushing_yards": safe_int(play.get("rushing_yards")),
                "yards_gained": safe_int(play.get("yards_gained")),
                "first_down": bool_flag(play.get("first_down")),
                "touchdown": bool_flag(play.get("touchdown")),
                "turnover": int(
                    bool_flag(play.get("interception"))
                    or bool_flag(play.get("fumble_lost"))
                    or bool_flag(play.get("fourth_down_failed"))
                ),
                "fumble": bool_flag(play.get("fumble")),
                "fumble_lost": bool_flag(play.get("fumble_lost")),
                "safety": bool_flag(play.get("safety")),
                "penalty": bool_flag(play.get("penalty")),
                "penalty_yards": safe_int(play.get("penalty_yards")),
                "two_point_attempt": bool_flag(play.get("two_point_attempt")),
                "two_point_conv_result": safe_text(play.get("two_point_conv_result")),
                "field_goal_attempt": bool_flag(play.get("field_goal_attempt")),
                "extra_point_attempt": bool_flag(play.get("extra_point_attempt")),
                "sack": bool_flag(play.get("sack")),
                "return_yards": safe_int(play.get("return_yards")),
                "timeout": bool_flag(play.get("timeout")),
                "timeout_team": normalize_team_abbr(play.get("timeout_team")),
                "passer_gsis_id": safe_text(play.get("passer_player_id") or play.get("passer_id")),
                "receiver_gsis_id": safe_text(play.get("receiver_player_id") or play.get("receiver_id")),
                "rusher_gsis_id": safe_text(play.get("rusher_player_id") or play.get("rusher_id")),
                "tackler_gsis_id": tackler_gsis_id,
            }
        )
    return rows


def process_play_by_play_for_game(game_row: pd.Series, play_by_play_df: pd.DataFrame, game_pbp_df: pd.DataFrame) -> pd.DataFrame:
    # 写入单场 play_by_play。
    game_id = safe_text(game_row["game_id"])
    play_by_play_df = play_by_play_df[play_by_play_df["game_id"].astype(str) != game_id].copy() if not play_by_play_df.empty else play_by_play_df
    new_rows = build_play_by_play_rows(game_row, game_pbp_df)
    if new_rows:
        play_by_play_df = pd.concat(
            [play_by_play_df, pd.DataFrame(new_rows, columns=PLAY_BY_PLAY_COLUMNS)],
            ignore_index=True,
        )
    save_local_df(play_by_play_df, "play_by_play.csv", PLAY_BY_PLAY_COLUMNS, "play_by_play.csv")
    return play_by_play_df


def build_player_bucket_counts(
    game_pbp_df: pd.DataFrame,
    id_column: str,
    attempt_flag_column: str,
    completion_flag_column: Optional[str],
    bucket_value_column: str,
    result_value_column: Optional[str] = None,
) -> Dict[str, Dict[str, int]]:
    # 通用分桶统计函数。
    counts: Dict[str, Dict[str, int]] = {}
    for _, play in game_pbp_df.iterrows():
        player_id = safe_text(play.get(id_column))
        if player_id == "":
            continue
        if bool_flag(play.get(attempt_flag_column)) != 1:
            continue

        bucket = bucket_name(play.get(bucket_value_column))
        if bucket is None:
            continue

        if player_id not in counts:
            counts[player_id] = {}

        attempt_key = f"attempts_{bucket}"
        counts[player_id][attempt_key] = counts[player_id].get(attempt_key, 0) + 1

        if completion_flag_column and bool_flag(play.get(completion_flag_column)) == 1:
            complete_key = f"completions_{bucket}"
            counts[player_id][complete_key] = counts[player_id].get(complete_key, 0) + 1

        if result_value_column:
            result_bucket = bucket_name(play.get(result_value_column))
            if result_bucket is not None:
                result_key = f"results_{result_bucket}"
                counts[player_id][result_key] = counts[player_id].get(result_key, 0) + 1

    return counts


def build_team_time_of_possession(game_pbp_df: pd.DataFrame, team_abbr: str) -> str:
    # 通过 drive_time_of_possession 汇总单队控球时间。
    if "drive_time_of_possession" not in game_pbp_df.columns:
        return "00:00"

    drive_rows = (
        game_pbp_df[game_pbp_df["posteam"] == team_abbr]
        .dropna(subset=["drive"])
        .sort_values(by=["drive", "play_id"])
    )
    if drive_rows.empty:
        return "00:00"

    drive_times = (
        drive_rows.groupby("drive")["drive_time_of_possession"]
        .apply(lambda values: next((str(v) for v in values if pd.notna(v) and str(v) != ""), ""))
        .tolist()
    )
    return sum_time_strings(drive_times)


def process_team_game_stats_for_game(
    game_row: pd.Series,
    team_game_stats_df: pd.DataFrame,
    game_team_stats_df: pd.DataFrame,
    game_pbp_df: pd.DataFrame,
    team_id_map: Dict[str, int],
) -> pd.DataFrame:
    # 写入单场 team_game_stats。
    game_id = safe_text(game_row["game_id"])
    team_game_stats_df = (
        team_game_stats_df[team_game_stats_df["game_id"].astype(str) != game_id].copy()
        if not team_game_stats_df.empty
        else team_game_stats_df
    )

    home_abbr = safe_text(game_row["home_abbr"])
    away_abbr = safe_text(game_row["away_abbr"])
    matchup_map = {
        home_abbr: {
            "team_id": safe_int(game_row["home_team_id"]),
            "opponent_team_id": safe_int(game_row["away_team_id"]),
            "opponent_abbr": away_abbr,
            "is_home": 1,
            "team_win": safe_int(game_row["home_win"]),
            "is_tie": safe_int(game_row["is_tie"]),
            "points_for": safe_int(game_row["home_score"]),
            "points_against": safe_int(game_row["away_score"]),
        },
        away_abbr: {
            "team_id": safe_int(game_row["away_team_id"]),
            "opponent_team_id": safe_int(game_row["home_team_id"]),
            "opponent_abbr": home_abbr,
            "is_home": 0,
            "team_win": 0 if safe_int(game_row["home_win"]) == 1 else (0 if safe_int(game_row["is_tie"]) == 1 else 1),
            "is_tie": safe_int(game_row["is_tie"]),
            "points_for": safe_int(game_row["away_score"]),
            "points_against": safe_int(game_row["home_score"]),
        },
    }

    new_rows = []
    for _, stats_row in game_team_stats_df.iterrows():
        team_abbr = safe_text(stats_row.get("team"))
        if team_abbr not in matchup_map:
            continue
        meta = matchup_map[team_abbr]
        points_for = safe_int(meta["points_for"])
        points_against = safe_int(meta["points_against"])
        offensive_plays = int(
            len(
                game_pbp_df[
                    (game_pbp_df["posteam"] == team_abbr)
                    & (pd.to_numeric(game_pbp_df.get("play", 0), errors="coerce").fillna(0) == 1)
                ]
            )
        ) if "play" in game_pbp_df.columns else 0
        turnovers = (
            safe_int(stats_row.get("passing_interceptions"))
            + safe_int(stats_row.get("rushing_fumbles_lost"))
            + safe_int(stats_row.get("receiving_fumbles_lost"))
            + safe_int(stats_row.get("sack_fumbles_lost"))
        )
        fumbles_lost = (
            safe_int(stats_row.get("rushing_fumbles_lost"))
            + safe_int(stats_row.get("receiving_fumbles_lost"))
            + safe_int(stats_row.get("sack_fumbles_lost"))
        )
        third_down_attempts = int(
            len(
                game_pbp_df[
                    (game_pbp_df["posteam"] == team_abbr)
                    & (pd.to_numeric(game_pbp_df["down"], errors="coerce") == 3)
                    & (pd.to_numeric(game_pbp_df.get("play", 0), errors="coerce").fillna(0) == 1)
                ]
            )
        ) if not game_pbp_df.empty and "down" in game_pbp_df.columns else 0
        third_down_conversions = int(
            pd.to_numeric(
                game_pbp_df.loc[game_pbp_df["posteam"] == team_abbr, "third_down_converted"],
                errors="coerce",
            ).fillna(0).sum()
        ) if "third_down_converted" in game_pbp_df.columns else 0
        fourth_down_attempts = int(
            len(
                game_pbp_df[
                    (game_pbp_df["posteam"] == team_abbr)
                    & (pd.to_numeric(game_pbp_df["down"], errors="coerce") == 4)
                    & (pd.to_numeric(game_pbp_df.get("play", 0), errors="coerce").fillna(0) == 1)
                ]
            )
        ) if not game_pbp_df.empty and "down" in game_pbp_df.columns else 0
        fourth_down_conversions = int(
            pd.to_numeric(
                game_pbp_df.loc[game_pbp_df["posteam"] == team_abbr, "fourth_down_converted"],
                errors="coerce",
            ).fillna(0).sum()
        ) if "fourth_down_converted" in game_pbp_df.columns else 0

        new_rows.append(
            {
                "game_id": game_id,
                "season": int(game_row["season"]),
                "week": int(game_row["week"]),
                "team_id": int(meta["team_id"]),
                "team_abbr": team_abbr,
                "opponent_team_id": int(meta["opponent_team_id"]),
                "opponent_abbr": safe_text(meta["opponent_abbr"]),
                "is_home": int(meta["is_home"]),
                "team_win": int(meta["team_win"]),
                "is_tie": int(meta["is_tie"]),
                "points_for": points_for,
                "points_against": points_against,
                "score_differential": points_for - points_against,
                "offensive_plays": offensive_plays,
                "yards": safe_int(stats_row.get("passing_yards")) + safe_int(stats_row.get("rushing_yards")),
                "first_downs": safe_int(stats_row.get("passing_first_downs")) + safe_int(stats_row.get("rushing_first_downs")),
                "turnovers": turnovers,
                "fumbles_lost": fumbles_lost,
                "pass_attempts": safe_int(stats_row.get("attempts")),
                "completions": safe_int(stats_row.get("completions")),
                "passing_yards": safe_int(stats_row.get("passing_yards")),
                "passing_tds": safe_int(stats_row.get("passing_tds")),
                "interceptions_thrown": safe_int(stats_row.get("passing_interceptions")),
                "sacks_allowed": safe_int(stats_row.get("sacks_suffered")),
                "sack_yards_lost": abs(safe_int(stats_row.get("sack_yards_lost"))),
                "net_passing_yards": safe_int(stats_row.get("passing_yards")) + safe_int(stats_row.get("sack_yards_lost")),
                "rush_attempts": safe_int(stats_row.get("carries")),
                "rushing_yards": safe_int(stats_row.get("rushing_yards")),
                "rushing_tds": safe_int(stats_row.get("rushing_tds")),
                "penalties": safe_int(stats_row.get("penalties")),
                "penalty_yards": safe_int(stats_row.get("penalty_yards")),
                "third_down_attempts": third_down_attempts,
                "third_down_conversions": third_down_conversions,
                "fourth_down_attempts": fourth_down_attempts,
                "fourth_down_conversions": fourth_down_conversions,
                "time_of_possession": build_team_time_of_possession(game_pbp_df, team_abbr),
            }
        )

    if new_rows:
        team_game_stats_df = pd.concat(
            [team_game_stats_df, pd.DataFrame(new_rows, columns=TEAM_GAME_STATS_COLUMNS)],
            ignore_index=True,
        )
    save_local_df(
        team_game_stats_df,
        "team_game_stats.csv",
        TEAM_GAME_STATS_COLUMNS,
        "team_game_stats.csv",
    )
    return team_game_stats_df


def build_role_bucket_summary(game_pbp_df: pd.DataFrame, role_column: str, role_flag_column: str, complete_flag_column: Optional[str], bucket_value_column: str, result_value_column: Optional[str] = None) -> Dict[str, dict]:
    # 通用角色分桶统计。
    stats: Dict[str, dict] = {}
    for _, play in game_pbp_df.iterrows():
        player_id = safe_text(play.get(role_column))
        if player_id == "" or bool_flag(play.get(role_flag_column)) != 1:
            continue

        if player_id not in stats:
            stats[player_id] = {}

        bucket = bucket_name(play.get(bucket_value_column))
        if bucket is not None:
            stats[player_id][f"attempts_{bucket}"] = stats[player_id].get(f"attempts_{bucket}", 0) + 1
            if complete_flag_column and bool_flag(play.get(complete_flag_column)) == 1:
                stats[player_id][f"completions_{bucket}"] = stats[player_id].get(f"completions_{bucket}", 0) + 1

        if result_value_column and bool_flag(play.get(complete_flag_column)) == 1:
            result_bucket = bucket_name(play.get(result_value_column))
            if result_bucket is not None:
                stats[player_id][f"results_{result_bucket}"] = stats[player_id].get(f"results_{result_bucket}", 0) + 1
    return stats


def build_longest_value(game_pbp_df: pd.DataFrame, player_column: str, filter_column: str, value_column: str) -> Dict[str, int]:
    # 统计每名球员单场最长值。
    longest_map: Dict[str, int] = {}
    for _, play in game_pbp_df.iterrows():
        player_id = safe_text(play.get(player_column))
        if player_id == "" or bool_flag(play.get(filter_column)) != 1:
            continue
        value = safe_int(play.get(value_column))
        longest_map[player_id] = max(longest_map.get(player_id, 0), value)
    return longest_map


def build_player_identity(game_row: pd.Series, gsis_id: str, player_row_map: Dict[str, dict], team_id_map: Dict[str, int], team_abbr: str, opponent_abbr: str) -> dict:
    # 构造球员逐场表共同身份字段。
    player_row = player_row_map[gsis_id]
    return {
        "game_id": safe_text(game_row["game_id"]),
        "season": int(game_row["season"]),
        "week": int(game_row["week"]),
        "player_id": int(player_row["player_id"]),
        "full_name": safe_text(player_row["full_name"]),
        "position": safe_text(player_row["position"]),
        "team_id": int(team_id_map[team_abbr]),
        "team_abbr": team_abbr,
        "opponent_team_id": int(team_id_map[opponent_abbr]),
        "opponent_abbr": opponent_abbr,
        "is_home": 1 if team_abbr == safe_text(game_row["home_abbr"]) else 0,
    }


def process_player_passing_for_game(
    game_row: pd.Series,
    passing_df: pd.DataFrame,
    game_player_stats_df: pd.DataFrame,
    game_pbp_df: pd.DataFrame,
    player_row_map: Dict[str, dict],
    team_id_map: Dict[str, int],
) -> pd.DataFrame:
    # 写入单场传球逐场表。
    game_id = safe_text(game_row["game_id"])
    passing_df = passing_df[passing_df["game_id"].astype(str) != game_id].copy() if not passing_df.empty else passing_df

    passing_stats_df = game_player_stats_df[
        (pd.to_numeric(game_player_stats_df["attempts"], errors="coerce").fillna(0) > 0)
        | (pd.to_numeric(game_player_stats_df["sacks_suffered"], errors="coerce").fillna(0) > 0)
    ].copy()
    bucket_map = build_role_bucket_summary(
        game_pbp_df,
        "passer_player_id",
        "pass_attempt",
        "complete_pass",
        "air_yards",
    )
    longest_map = build_longest_value(game_pbp_df, "passer_player_id", "complete_pass", "passing_yards")

    new_rows = []
    for _, row in passing_stats_df.iterrows():
        gsis_id = safe_text(row.get("player_id"))
        if gsis_id not in player_row_map:
            continue
        team_abbr = safe_text(row.get("team"))
        opponent_abbr = safe_text(row.get("opponent_team"))
        identity = build_player_identity(game_row, gsis_id, player_row_map, team_id_map, team_abbr, opponent_abbr)
        attempts = safe_int(row.get("attempts"))
        completions = safe_int(row.get("completions"))
        bucket_stats = bucket_map.get(gsis_id, {})

        new_rows.append(
            {
                **identity,
                "pass_attempts": attempts,
                "completions": completions,
                "incompletions": max(attempts - completions, 0),
                "passing_yards": safe_int(row.get("passing_yards")),
                "passing_tds": safe_int(row.get("passing_tds")),
                "interceptions": safe_int(row.get("passing_interceptions")),
                "sacks_taken": safe_int(row.get("sacks_suffered")),
                "sack_yards_lost": abs(safe_int(row.get("sack_yards_lost"))),
                "passing_first_downs": safe_int(row.get("passing_first_downs")),
                "passing_air_yards": safe_int(row.get("passing_air_yards")),
                "passing_yards_after_catch": safe_int(row.get("passing_yards_after_catch")),
                "longest_completion": longest_map.get(gsis_id, 0),
                "completion_percentage": round((completions / attempts) * 100, 2) if attempts > 0 else 0.0,
                "qb_rating": compute_qb_rating(
                    completions,
                    attempts,
                    safe_int(row.get("passing_yards")),
                    safe_int(row.get("passing_tds")),
                    safe_int(row.get("passing_interceptions")),
                ),
                "pass_attempts_0_5": bucket_stats.get("attempts_0_5", 0),
                "pass_completions_0_5": bucket_stats.get("completions_0_5", 0),
                "pass_attempts_5_10": bucket_stats.get("attempts_5_10", 0),
                "pass_completions_5_10": bucket_stats.get("completions_5_10", 0),
                "pass_attempts_10_20": bucket_stats.get("attempts_10_20", 0),
                "pass_completions_10_20": bucket_stats.get("completions_10_20", 0),
                "pass_attempts_20_plus": bucket_stats.get("attempts_20_plus", 0),
                "pass_completions_20_plus": bucket_stats.get("completions_20_plus", 0),
            }
        )

    if new_rows:
        passing_df = pd.concat([passing_df, pd.DataFrame(new_rows, columns=PLAYER_PASSING_COLUMNS)], ignore_index=True)
    save_local_df(passing_df, "player_passing_stats.csv", PLAYER_PASSING_COLUMNS, "player_passing_stats.csv")
    return passing_df


def process_player_rushing_for_game(
    game_row: pd.Series,
    rushing_df: pd.DataFrame,
    game_player_stats_df: pd.DataFrame,
    game_pbp_df: pd.DataFrame,
    player_row_map: Dict[str, dict],
    team_id_map: Dict[str, int],
) -> pd.DataFrame:
    # 写入单场冲球逐场表。
    game_id = safe_text(game_row["game_id"])
    rushing_df = rushing_df[rushing_df["game_id"].astype(str) != game_id].copy() if not rushing_df.empty else rushing_df

    rushing_stats_df = game_player_stats_df[
        pd.to_numeric(game_player_stats_df["carries"], errors="coerce").fillna(0) > 0
    ].copy()
    bucket_map = build_role_bucket_summary(
        game_pbp_df,
        "rusher_player_id",
        "rush_attempt",
        None,
        "rushing_yards",
    )
    longest_map = build_longest_value(game_pbp_df, "rusher_player_id", "rush_attempt", "rushing_yards")

    new_rows = []
    for _, row in rushing_stats_df.iterrows():
        gsis_id = safe_text(row.get("player_id"))
        if gsis_id not in player_row_map:
            continue
        team_abbr = safe_text(row.get("team"))
        opponent_abbr = safe_text(row.get("opponent_team"))
        identity = build_player_identity(game_row, gsis_id, player_row_map, team_id_map, team_abbr, opponent_abbr)
        bucket_stats = bucket_map.get(gsis_id, {})

        new_rows.append(
            {
                **identity,
                "rush_attempts": safe_int(row.get("carries")),
                "rushing_yards": safe_int(row.get("rushing_yards")),
                "rushing_tds": safe_int(row.get("rushing_tds")),
                "rushing_first_downs": safe_int(row.get("rushing_first_downs")),
                "longest_rush": longest_map.get(gsis_id, 0),
                "fumbles": safe_int(row.get("rushing_fumbles")),
                "fumbles_lost": safe_int(row.get("rushing_fumbles_lost")),
                "rush_0_5": bucket_stats.get("attempts_0_5", 0),
                "rush_5_10": bucket_stats.get("attempts_5_10", 0),
                "rush_10_20": bucket_stats.get("attempts_10_20", 0),
                "rush_20_plus": bucket_stats.get("attempts_20_plus", 0),
            }
        )

    if new_rows:
        rushing_df = pd.concat([rushing_df, pd.DataFrame(new_rows, columns=PLAYER_RUSHING_COLUMNS)], ignore_index=True)
    save_local_df(rushing_df, "player_rushing_stats.csv", PLAYER_RUSHING_COLUMNS, "player_rushing_stats.csv")
    return rushing_df


def process_player_receiving_for_game(
    game_row: pd.Series,
    receiving_df: pd.DataFrame,
    game_player_stats_df: pd.DataFrame,
    game_pbp_df: pd.DataFrame,
    player_row_map: Dict[str, dict],
    team_id_map: Dict[str, int],
) -> pd.DataFrame:
    # 写入单场接球逐场表。
    game_id = safe_text(game_row["game_id"])
    receiving_df = receiving_df[receiving_df["game_id"].astype(str) != game_id].copy() if not receiving_df.empty else receiving_df

    receiving_stats_df = game_player_stats_df[
        (pd.to_numeric(game_player_stats_df["targets"], errors="coerce").fillna(0) > 0)
        | (pd.to_numeric(game_player_stats_df["receptions"], errors="coerce").fillna(0) > 0)
    ].copy()
    bucket_map = build_role_bucket_summary(
        game_pbp_df,
        "receiver_player_id",
        "pass_attempt",
        "complete_pass",
        "air_yards",
        result_value_column="receiving_yards",
    )
    longest_map = build_longest_value(game_pbp_df, "receiver_player_id", "complete_pass", "receiving_yards")

    new_rows = []
    for _, row in receiving_stats_df.iterrows():
        gsis_id = safe_text(row.get("player_id"))
        if gsis_id not in player_row_map:
            continue
        team_abbr = safe_text(row.get("team"))
        opponent_abbr = safe_text(row.get("opponent_team"))
        identity = build_player_identity(game_row, gsis_id, player_row_map, team_id_map, team_abbr, opponent_abbr)
        bucket_stats = bucket_map.get(gsis_id, {})

        new_rows.append(
            {
                **identity,
                "targets": safe_int(row.get("targets")),
                "receptions": safe_int(row.get("receptions")),
                "receiving_yards": safe_int(row.get("receiving_yards")),
                "receiving_tds": safe_int(row.get("receiving_tds")),
                "receiving_first_downs": safe_int(row.get("receiving_first_downs")),
                "air_yards": safe_int(row.get("receiving_air_yards")),
                "yards_after_catch": safe_int(row.get("receiving_yards_after_catch")),
                "longest_reception": longest_map.get(gsis_id, 0),
                "fumbles": safe_int(row.get("receiving_fumbles")),
                "fumbles_lost": safe_int(row.get("receiving_fumbles_lost")),
                "targets_0_5": bucket_stats.get("attempts_0_5", 0),
                "receptions_0_5": bucket_stats.get("completions_0_5", 0),
                "targets_5_10": bucket_stats.get("attempts_5_10", 0),
                "receptions_5_10": bucket_stats.get("completions_5_10", 0),
                "targets_10_20": bucket_stats.get("attempts_10_20", 0),
                "receptions_10_20": bucket_stats.get("completions_10_20", 0),
                "targets_20_plus": bucket_stats.get("attempts_20_plus", 0),
                "receptions_20_plus": bucket_stats.get("completions_20_plus", 0),
                "receiving_0_5": bucket_stats.get("results_0_5", 0),
                "receiving_5_10": bucket_stats.get("results_5_10", 0),
                "receiving_10_20": bucket_stats.get("results_10_20", 0),
                "receiving_20_plus": bucket_stats.get("results_20_plus", 0),
            }
        )

    if new_rows:
        receiving_df = pd.concat([receiving_df, pd.DataFrame(new_rows, columns=PLAYER_RECEIVING_COLUMNS)], ignore_index=True)
    save_local_df(receiving_df, "player_receiving_stats.csv", PLAYER_RECEIVING_COLUMNS, "player_receiving_stats.csv")
    return receiving_df


def build_participation_counts(game_pbp_df: pd.DataFrame, game_participation_df: pd.DataFrame) -> tuple[Dict[str, dict], Dict[str, dict]]:
    # 根据 participation 为 defense/blocking 统计 snap 级别信息。
    play_meta = {}
    for _, row in game_pbp_df.iterrows():
        play_id = safe_text(row.get("play_id"))
        play_meta[play_id] = {
            "special_teams_play": bool_flag(row.get("special_teams_play")),
            "qb_dropback": bool_flag(row.get("qb_dropback")),
            "rush_attempt": bool_flag(row.get("rush_attempt")),
            "st_play_type": safe_text(row.get("st_play_type")),
        }

    defense_counts: Dict[str, dict] = {}
    block_counts: Dict[str, dict] = {}
    for _, row in game_participation_df.iterrows():
        play_id = safe_text(row.get("play_id"))
        meta = play_meta.get(play_id, {})
        special_teams_play = int(meta.get("special_teams_play", 0))
        qb_dropback = int(meta.get("qb_dropback", 0))
        rush_attempt = int(meta.get("rush_attempt", 0))
        st_play_type = safe_text(meta.get("st_play_type"))

        for gsis_id in safe_text(row.get("defense_players")).split(";"):
            gsis_id = gsis_id.strip()
            if gsis_id == "":
                continue
            defense_counts.setdefault(gsis_id, {"def_snaps": 0, "special_teams_snaps": 0})
            if special_teams_play == 1:
                defense_counts[gsis_id]["special_teams_snaps"] += 1
            else:
                defense_counts[gsis_id]["def_snaps"] += 1

        for gsis_id in safe_text(row.get("offense_players")).split(";"):
            gsis_id = gsis_id.strip()
            if gsis_id == "":
                continue
            block_counts.setdefault(
                gsis_id,
                {
                    "off_snaps": 0,
                    "pass_block_snaps": 0,
                    "run_block_snaps": 0,
                    "special_teams_block_snaps": 0,
                    "punt_block_snaps": 0,
                    "field_goal_block_snaps": 0,
                    "extra_point_block_snaps": 0,
                },
            )
            if special_teams_play == 1:
                block_counts[gsis_id]["special_teams_block_snaps"] += 1
                if "PUNT" in st_play_type:
                    block_counts[gsis_id]["punt_block_snaps"] += 1
                if "FIELD_GOAL" in st_play_type:
                    block_counts[gsis_id]["field_goal_block_snaps"] += 1
                if "EXTRA_POINT" in st_play_type or "PAT" in st_play_type:
                    block_counts[gsis_id]["extra_point_block_snaps"] += 1
            else:
                block_counts[gsis_id]["off_snaps"] += 1
                if qb_dropback == 1:
                    block_counts[gsis_id]["pass_block_snaps"] += 1
                if rush_attempt == 1:
                    block_counts[gsis_id]["run_block_snaps"] += 1

    return defense_counts, block_counts


def process_player_def_for_game(
    game_row: pd.Series,
    def_df: pd.DataFrame,
    game_player_stats_df: pd.DataFrame,
    game_pbp_df: pd.DataFrame,
    game_participation_df: pd.DataFrame,
    player_row_map: Dict[str, dict],
    team_id_map: Dict[str, int],
) -> pd.DataFrame:
    # 写入单场 defense / special teams 逐场表。
    game_id = safe_text(game_row["game_id"])
    def_df = def_df[def_df["game_id"].astype(str) != game_id].copy() if not def_df.empty else def_df

    defense_counts, _ = build_participation_counts(game_pbp_df, game_participation_df)
    stat_players = game_player_stats_df[
        (
            pd.to_numeric(game_player_stats_df["def_tackles_solo"], errors="coerce").fillna(0)
            + pd.to_numeric(game_player_stats_df["def_tackle_assists"], errors="coerce").fillna(0)
            + pd.to_numeric(game_player_stats_df["def_sacks"], errors="coerce").fillna(0)
            + pd.to_numeric(game_player_stats_df["kickoff_returns"], errors="coerce").fillna(0)
            + pd.to_numeric(game_player_stats_df["punt_returns"], errors="coerce").fillna(0)
            + pd.to_numeric(game_player_stats_df["special_teams_tds"], errors="coerce").fillna(0)
        ) > 0
    ].copy()
    target_gsis_ids = set(stat_players["player_id"].dropna().astype(str))
    target_gsis_ids.update(defense_counts.keys())

    # 特勤 tackle / block 事件来自 pbp。
    st_solo_tackles: Dict[str, int] = {}
    st_assist_tackles: Dict[str, int] = {}
    kick_return_tds: Dict[str, int] = {}
    punt_return_tds: Dict[str, int] = {}
    longest_kick_return = build_longest_value(game_pbp_df, "kickoff_returner_player_id", "kickoff_attempt", "return_yards")
    longest_punt_return = build_longest_value(game_pbp_df, "punt_returner_player_id", "punt_attempt", "return_yards")
    blocked_counts: Dict[str, dict] = {}
    for _, play in game_pbp_df.iterrows():
        if bool_flag(play.get("special_teams_play")) == 1:
            for column in ["solo_tackle_1_player_id", "solo_tackle_2_player_id"]:
                gsis_id = safe_text(play.get(column))
                if gsis_id:
                    st_solo_tackles[gsis_id] = st_solo_tackles.get(gsis_id, 0) + 1
            for column in [
                "assist_tackle_1_player_id",
                "assist_tackle_2_player_id",
                "assist_tackle_3_player_id",
                "assist_tackle_4_player_id",
            ]:
                gsis_id = safe_text(play.get(column))
                if gsis_id:
                    st_assist_tackles[gsis_id] = st_assist_tackles.get(gsis_id, 0) + 1

        if bool_flag(play.get("return_touchdown")) == 1:
            kick_returner = safe_text(play.get("kickoff_returner_player_id"))
            punt_returner = safe_text(play.get("punt_returner_player_id"))
            if kick_returner:
                kick_return_tds[kick_returner] = kick_return_tds.get(kick_returner, 0) + 1
            if punt_returner:
                punt_return_tds[punt_returner] = punt_return_tds.get(punt_returner, 0) + 1

        blocker = safe_text(play.get("blocked_player_id"))
        if blocker:
            blocked_counts.setdefault(
                blocker,
                {
                    "blocked_punts": 0,
                    "blocked_field_goals": 0,
                    "blocked_extra_points": 0,
                    "blocked_kicks": 0,
                },
            )
            if bool_flag(play.get("punt_blocked")) == 1:
                blocked_counts[blocker]["blocked_punts"] += 1
            if bool_flag(play.get("fg_blocked")) == 1:
                blocked_counts[blocker]["blocked_field_goals"] += 1
            if bool_flag(play.get("pat_blocked")) == 1:
                blocked_counts[blocker]["blocked_extra_points"] += 1
            blocked_counts[blocker]["blocked_kicks"] += 1

    new_rows = []
    for gsis_id in sorted(target_gsis_ids):
        if gsis_id not in player_row_map:
            continue

        player_stats_rows = stat_players[stat_players["player_id"].astype(str) == gsis_id]
        if not player_stats_rows.empty:
            row = player_stats_rows.iloc[0]
            team_abbr = safe_text(row.get("team"))
            opponent_abbr = safe_text(row.get("opponent_team"))
        else:
            # 对只在 participation 中出现的球员，按本场实际 on-field 数据推断所属球队。
            team_abbr, opponent_abbr = infer_team_from_participation(
                game_row,
                game_pbp_df,
                game_participation_df,
                gsis_id,
            )
            row = {}

        identity = build_player_identity(game_row, gsis_id, player_row_map, team_id_map, team_abbr, opponent_abbr)
        def_count = defense_counts.get(gsis_id, {})
        blocked = blocked_counts.get(gsis_id, {})
        st_solo = st_solo_tackles.get(gsis_id, 0)
        st_assist = st_assist_tackles.get(gsis_id, 0)

        new_rows.append(
            {
                **identity,
                "def_snaps": def_count.get("def_snaps", 0),
                "special_teams_snaps": def_count.get("special_teams_snaps", 0),
                "tackles": safe_int(row.get("def_tackles_solo")) + safe_int(row.get("def_tackle_assists")),
                "solo_tackles": safe_int(row.get("def_tackles_solo")),
                "assist_tackles": safe_int(row.get("def_tackle_assists")),
                "tackles_for_loss": safe_int(row.get("def_tackles_for_loss")),
                "qb_hits": safe_int(row.get("def_qb_hits")),
                "sacks": safe_int(row.get("def_sacks")),
                "sack_yards": safe_int(row.get("def_sack_yards")),
                "passes_defended": safe_int(row.get("def_pass_defended")),
                "interceptions": safe_int(row.get("def_interceptions")),
                "interception_yards": safe_int(row.get("def_interception_yards")),
                "interception_tds": 0,
                "forced_fumbles": safe_int(row.get("def_fumbles_forced")),
                "fumble_recoveries": safe_int(row.get("fumble_recovery_own")) + safe_int(row.get("fumble_recovery_opp")),
                "fumble_recovery_yards": safe_int(row.get("fumble_recovery_yards_own")) + safe_int(row.get("fumble_recovery_yards_opp")),
                "fumble_recovery_tds": safe_int(row.get("fumble_recovery_tds")),
                "defensive_tds": safe_int(row.get("def_tds")),
                "safeties": safe_int(row.get("def_safeties")),
                "special_teams_tackles": st_solo + st_assist,
                "special_teams_solo_tackles": st_solo,
                "special_teams_assist_tackles": st_assist,
                "kick_returns": safe_int(row.get("kickoff_returns")),
                "kick_return_yards": safe_int(row.get("kickoff_return_yards")),
                "kick_return_tds": kick_return_tds.get(gsis_id, 0),
                "longest_kick_return": longest_kick_return.get(gsis_id, 0),
                "punt_returns": safe_int(row.get("punt_returns")),
                "punt_return_yards": safe_int(row.get("punt_return_yards")),
                "punt_return_tds": punt_return_tds.get(gsis_id, 0),
                "longest_punt_return": longest_punt_return.get(gsis_id, 0),
                "blocked_punts": blocked.get("blocked_punts", 0),
                "blocked_field_goals": blocked.get("blocked_field_goals", 0),
                "blocked_extra_points": blocked.get("blocked_extra_points", 0),
                "blocked_kicks": blocked.get("blocked_kicks", 0),
            }
        )

    if new_rows:
        def_df = pd.concat([def_df, pd.DataFrame(new_rows, columns=PLAYER_DEF_COLUMNS)], ignore_index=True)
    save_local_df(def_df, "player_def_games.csv", PLAYER_DEF_COLUMNS, "player_def_games.csv")
    return def_df


def process_player_block_for_game(
    game_row: pd.Series,
    block_df: pd.DataFrame,
    game_pbp_df: pd.DataFrame,
    game_participation_df: pd.DataFrame,
    player_row_map: Dict[str, dict],
    team_id_map: Dict[str, int],
) -> pd.DataFrame:
    # 写入单场 blocking 逐场表。
    game_id = safe_text(game_row["game_id"])
    block_df = block_df[block_df["game_id"].astype(str) != game_id].copy() if not block_df.empty else block_df

    _, block_counts = build_participation_counts(game_pbp_df, game_participation_df)
    penalty_counts: Dict[str, dict] = {}
    for _, play in game_pbp_df.iterrows():
        player_id = safe_text(play.get("penalty_player_id"))
        if player_id == "":
            continue
        penalty_type = safe_text(play.get("penalty_type")).upper()
        penalty_counts.setdefault(
            player_id,
            {"penalties": 0, "holding_penalties": 0, "false_start_penalties": 0},
        )
        penalty_counts[player_id]["penalties"] += 1
        if "HOLD" in penalty_type:
            penalty_counts[player_id]["holding_penalties"] += 1
        if "FALSE START" in penalty_type:
            penalty_counts[player_id]["false_start_penalties"] += 1

    target_gsis_ids = sorted(set(block_counts.keys()).union(penalty_counts.keys()))
    new_rows = []
    for gsis_id in target_gsis_ids:
        if gsis_id not in player_row_map:
            continue
        team_abbr, opponent_abbr = infer_team_from_participation(
            game_row,
            game_pbp_df,
            game_participation_df,
            gsis_id,
        )
        identity = build_player_identity(game_row, gsis_id, player_row_map, team_id_map, team_abbr, opponent_abbr)
        counts = block_counts.get(gsis_id, {})
        penalties = penalty_counts.get(gsis_id, {})

        new_rows.append(
            {
                **identity,
                "off_snaps": counts.get("off_snaps", 0),
                "pass_block_snaps": counts.get("pass_block_snaps", 0),
                "run_block_snaps": counts.get("run_block_snaps", 0),
                "pressures_allowed": 0,
                "hurries_allowed": 0,
                "qb_hits_allowed": 0,
                "sacks_allowed": 0,
                "sack_yards_allowed": 0,
                "penalties": penalties.get("penalties", 0),
                "holding_penalties": penalties.get("holding_penalties", 0),
                "false_start_penalties": penalties.get("false_start_penalties", 0),
                "special_teams_block_snaps": counts.get("special_teams_block_snaps", 0),
                "punt_block_snaps": counts.get("punt_block_snaps", 0),
                "field_goal_block_snaps": counts.get("field_goal_block_snaps", 0),
                "extra_point_block_snaps": counts.get("extra_point_block_snaps", 0),
                "blocked_punts_allowed": 0,
                "blocked_field_goals_allowed": 0,
                "blocked_extra_points_allowed": 0,
            }
        )

    if new_rows:
        block_df = pd.concat([block_df, pd.DataFrame(new_rows, columns=PLAYER_BLOCK_COLUMNS)], ignore_index=True)
    save_local_df(block_df, "player_block_games.csv", PLAYER_BLOCK_COLUMNS, "player_block_games.csv")
    return block_df


def main() -> None:
    # 总入口：输入 season 和周区间，逐场更新 NFL 数据并维护状态表。
    try:
        require_nflreadpy()
        season, start_week, end_week, team_filter = prompt_for_inputs()
        target_games_df, _ = build_target_games_df(
            season,
            start_week,
            end_week,
            team_filter=team_filter,
        )

        if target_games_df.empty:
            print_section("本周没有可处理的已完赛比赛")
            return

        status_df = load_status_df()
        status_df = ensure_status_rows(status_df, target_games_df)
        save_status_df(status_df)

        teams_df = pd.read_csv(get_file_path("teams.csv"))
        team_id_map = build_team_id_map_df(teams_df)

        players_df = load_local_df("players.csv", PLAYERS_COLUMNS, "players.csv")
        play_by_play_df = load_local_df("play_by_play.csv", PLAY_BY_PLAY_COLUMNS, "play_by_play.csv")
        team_game_stats_df = load_local_df("team_game_stats.csv", TEAM_GAME_STATS_COLUMNS, "team_game_stats.csv")
        passing_df = load_local_df("player_passing_stats.csv", PLAYER_PASSING_COLUMNS, "player_passing_stats.csv")
        rushing_df = load_local_df("player_rushing_stats.csv", PLAYER_RUSHING_COLUMNS, "player_rushing_stats.csv")
        receiving_df = load_local_df("player_receiving_stats.csv", PLAYER_RECEIVING_COLUMNS, "player_receiving_stats.csv")
        def_df = load_local_df("player_def_games.csv", PLAYER_DEF_COLUMNS, "player_def_games.csv")
        block_df = load_local_df("player_block_games.csv", PLAYER_BLOCK_COLUMNS, "player_block_games.csv")

        target_game_ids = set(target_games_df["game_id"].astype(str))
        source_data = load_sources_for_weeks(
            season,
            start_week,
            end_week,
            target_game_ids,
        )
        players_master_map = build_players_master_map(source_data["players_master_df"])

        total_games = len(target_games_df)
        print_section(f"开始逐场更新 NFL 数据，共 {total_games} 场比赛")

        for index, (_, game_row) in enumerate(target_games_df.iterrows(), start=1):
            game_id = safe_text(game_row["game_id"])
            print_progress(index, total_games, "处理比赛进度")
            print_section(
                f"开始处理比赛 {game_id} ({index}/{total_games}) "
                f"{game_row['away_abbr']} @ {game_row['home_abbr']}"
            )

            game_status = get_status_row(status_df, game_id)
            if safe_int(game_status["fully_loaded"]) == 1:
                print_section(f"比赛 {game_id} 已全部完成，直接跳过")
                continue

            game_pbp_df = filter_game_pbp(source_data["pbp_df"], game_id)
            game_participation_df = filter_game_participation(source_data["participation_df"], game_id)
            game_player_stats_df = filter_game_player_stats(source_data["player_stats_df"], game_row)
            game_team_stats_df = filter_game_team_stats(source_data["team_stats_df"], game_row)

            try:
                if safe_int(game_status["players_loaded"]) != 1:
                    players_df = process_players_for_game(
                        game_row,
                        players_df,
                        players_master_map,
                        game_pbp_df,
                        game_participation_df,
                        game_player_stats_df,
                    )
                    status_df = mark_stage_success(status_df, game_id, "players_loaded")
                    save_status_df(status_df)

                _, player_row_map = build_player_lookup_maps(players_df)
                game_status = get_status_row(status_df, game_id)

                if safe_int(game_status["play_by_play_loaded"]) != 1:
                    play_by_play_df = process_play_by_play_for_game(game_row, play_by_play_df, game_pbp_df)
                    status_df = mark_stage_success(status_df, game_id, "play_by_play_loaded")
                    save_status_df(status_df)

                game_status = get_status_row(status_df, game_id)
                if safe_int(game_status["team_loaded"]) != 1:
                    team_game_stats_df = process_team_game_stats_for_game(
                        game_row,
                        team_game_stats_df,
                        game_team_stats_df,
                        game_pbp_df,
                        team_id_map,
                    )
                    status_df = mark_stage_success(status_df, game_id, "team_loaded")
                    save_status_df(status_df)

                game_status = get_status_row(status_df, game_id)
                if safe_int(game_status["passing_loaded"]) != 1:
                    passing_df = process_player_passing_for_game(
                        game_row,
                        passing_df,
                        game_player_stats_df,
                        game_pbp_df,
                        player_row_map,
                        team_id_map,
                    )
                    status_df = mark_stage_success(status_df, game_id, "passing_loaded")
                    save_status_df(status_df)

                game_status = get_status_row(status_df, game_id)
                if safe_int(game_status["rushing_loaded"]) != 1:
                    rushing_df = process_player_rushing_for_game(
                        game_row,
                        rushing_df,
                        game_player_stats_df,
                        game_pbp_df,
                        player_row_map,
                        team_id_map,
                    )
                    status_df = mark_stage_success(status_df, game_id, "rushing_loaded")
                    save_status_df(status_df)

                game_status = get_status_row(status_df, game_id)
                if safe_int(game_status["receiving_loaded"]) != 1:
                    receiving_df = process_player_receiving_for_game(
                        game_row,
                        receiving_df,
                        game_player_stats_df,
                        game_pbp_df,
                        player_row_map,
                        team_id_map,
                    )
                    status_df = mark_stage_success(status_df, game_id, "receiving_loaded")
                    save_status_df(status_df)

                game_status = get_status_row(status_df, game_id)
                if safe_int(game_status["def_loaded"]) != 1:
                    def_df = process_player_def_for_game(
                        game_row,
                        def_df,
                        game_player_stats_df,
                        game_pbp_df,
                        game_participation_df,
                        player_row_map,
                        team_id_map,
                    )
                    status_df = mark_stage_success(status_df, game_id, "def_loaded")
                    save_status_df(status_df)

                game_status = get_status_row(status_df, game_id)
                if safe_int(game_status["block_loaded"]) != 1:
                    block_df = process_player_block_for_game(
                        game_row,
                        block_df,
                        game_pbp_df,
                        game_participation_df,
                        player_row_map,
                        team_id_map,
                    )
                    status_df = mark_stage_success(status_df, game_id, "block_loaded")
                    save_status_df(status_df)

                status_df = recompute_fully_loaded(status_df)
                save_status_df(status_df)
                print_section(f"比赛 {game_id} 已完成全部更新")
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                status_df = mark_stage_error(status_df, game_id, error_message)
                save_status_df(status_df)
                print_section(f"比赛 {game_id} 更新失败，已记录错误：{error_message}")
                continue

        print_section("本次 NFL 数据更新已全部结束")
    except Exception as exc:
        print(f"Failed to run NFL update pipeline: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
