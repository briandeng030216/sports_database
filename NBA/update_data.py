import argparse
import calendar
import os
import re
import sys
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    from nba_api.stats.endpoints import (
        boxscoretraditionalv3,
        boxscoreadvancedv3,
        commonplayerinfo,
        leaguegamefinder,
        playbyplayv3,
    )
    from nba_api.live.nba.endpoints import boxscore as live_boxscore
except ImportError:  # pragma: no cover
    boxscoretraditionalv3 = None
    boxscoreadvancedv3 = None
    commonplayerinfo = None
    leaguegamefinder = None
    playbyplayv3 = None
    live_boxscore = None


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
    "overtime",
]
PLAYERS_COLUMNS = [
    "player_id",
    "nba_id",
    "full_name",
    "first_name",
    "last_name",
    "birth_date",
    "position",
    "height",
    "weight",
    "college",
    "country",
    "draft_year",
]
PLAY_BY_PLAY_COLUMNS = [
    "action_id",
    "game_id",
    "season",
    "period",
    "period_type",
    "clock_minutes_remaining",
    "clock_seconds_remaining",
    "home_team_id",
    "home_abbr",
    "away_team_id",
    "away_abbr",
    "team_id",
    "team_abbr",
    "possession_team_abbr",
    "action_type",
    "sub_type",
    "description",
    "qualifiers",
    "player_id",
    "player_name",
    "assist_player_id",
    "assist_player_name",
    "block_player_id",
    "block_player_name",
    "steal_player_id",
    "steal_player_name",
    "points_scored",
    "score_home",
    "score_away",
    "score_margin",
    "shot_type",
    "shot_result",
    "shot_value",
    "shot_distance",
    "x",
    "y",
    "foul_type",
    "turnover_type",
    "rebound_type",
    "free_throw_num",
    "free_throw_total",
    "jump_ball_won_player_id",
    "jump_ball_won_player_name",
    "is_field_goal_attempt",
    "is_field_goal_made",
    "is_three_point_attempt",
    "is_free_throw_attempt",
    "is_free_throw_made",
    "is_rebound",
    "is_offensive_rebound",
    "is_defensive_rebound",
    "is_turnover",
    "is_steal",
    "is_block",
    "is_foul",
    "is_timeout",
    "is_substitution",
    "is_jump_ball",
]
PLAYER_GAME_STATS_COLUMNS = [
    "game_id",
    "season",
    "player_id",
    "full_name",
    "position",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "starter",
    "minutes",
    "points",
    "fgm",
    "fga",
    "fg3m",
    "fg3a",
    "ftm",
    "fta",
    "oreb",
    "dreb",
    "reb",
    "ast",
    "stl",
    "blk",
    "tov",
    "pf",
    "plus_minus",
    "fg_pct",
    "fg3_pct",
    "ft_pct",
    "efg_pct",
    "ts_pct",
    "usg_pct",
    "ast_pct",
    "reb_pct",
    "off_rating",
    "def_rating",
    "net_rating",
    "pace",
    "possessions",
]
TEAM_GAME_STATS_COLUMNS = [
    "game_id",
    "season",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "team_win",
    "minutes",
    "points",
    "fgm",
    "fga",
    "fg3m",
    "fg3a",
    "ftm",
    "fta",
    "oreb",
    "dreb",
    "reb",
    "ast",
    "stl",
    "blk",
    "tov",
    "pf",
    "fast_break_points",
    "points_in_paint",
    "second_chance_points",
    "largest_lead",
    "lead_changes",
    "times_tied",
    "fg_pct",
    "fg3_pct",
    "ft_pct",
    "efg_pct",
    "ts_pct",
    "pace",
    "possessions",
    "off_rating",
    "def_rating",
    "net_rating",
]
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
    "player_loaded",
    "fully_loaded",
    "last_updated",
    "error_message",
]
STAGE_COLUMNS = [
    "games_loaded",
    "players_loaded",
    "play_by_play_loaded",
    "team_loaded",
    "player_loaded",
]
REGULAR_SEASON_TYPE = "Regular Season"
PLAYOFF_TYPE = "Playoffs"
PROGRESS_STEP = 10

# LeagueGameFinder can miss a small number of neutral-site / NBA Cup regular season
# games. Keep these as explicit supplements so downstream tables can still be
# loaded through the normal per-game boxscore endpoints.
SUPPLEMENTAL_REGULAR_SEASON_GAMES = {
    2024: [
        {
            "game_id": "0022400147",
            "game_date": "2024-11-02",
            "home_abbr": "WAS",
            "away_abbr": "MIA",
            "home_score": 98,
            "away_score": 118,
        },
        {
            "game_id": "0022400621",
            "game_date": "2025-01-23",
            "home_abbr": "IND",
            "away_abbr": "SAS",
            "home_score": 110,
            "away_score": 140,
        },
        {
            "game_id": "0022400633",
            "game_date": "2025-01-25",
            "home_abbr": "SAS",
            "away_abbr": "IND",
            "home_score": 98,
            "away_score": 136,
        },
        {
            "game_id": "0022401229",
            "game_date": "2024-12-14",
            "home_abbr": "MIL",
            "away_abbr": "ATL",
            "home_score": 110,
            "away_score": 102,
        },
        {
            "game_id": "0022401230",
            "game_date": "2024-12-14",
            "home_abbr": "OKC",
            "away_abbr": "HOU",
            "home_score": 111,
            "away_score": 96,
        },
    ],
    2025: [
        {
            "game_id": "0022500147",
            "game_date": "2025-11-01",
            "home_abbr": "DET",
            "away_abbr": "DAL",
            "home_score": 122,
            "away_score": 110,
        },
        {
            "game_id": "0022500578",
            "game_date": "2026-01-15",
            "home_abbr": "ORL",
            "away_abbr": "MEM",
            "home_score": 118,
            "away_score": 111,
        },
        {
            "game_id": "0022500602",
            "game_date": "2026-01-18",
            "home_abbr": "MEM",
            "away_abbr": "ORL",
            "home_score": 126,
            "away_score": 109,
        },
        {
            "game_id": "0022501229",
            "game_date": "2025-12-13",
            "home_abbr": "ORL",
            "away_abbr": "NYK",
            "home_score": 120,
            "away_score": 132,
        },
        {
            "game_id": "0022501230",
            "game_date": "2025-12-13",
            "home_abbr": "OKC",
            "away_abbr": "SAS",
            "home_score": 109,
            "away_score": 111,
        },
    ],
}


def print_section(message: str) -> None:
    # 统一打印 NBA pipeline 的关键日志。
    print(f"[pipeline] {message}")


def print_progress(current: int, total: int, label: str) -> None:
    # 大批量读取或逐场处理时按固定步长打印进度。
    if total == 0:
        return
    if current == 1 or current % PROGRESS_STEP == 0 or current == total:
        print_section(f"{label}: {current}/{total}")


def require_nba_api() -> None:
    # 检查 nba_api 是否已经安装。
    if (
        leaguegamefinder is None
        or playbyplayv3 is None
        or boxscoretraditionalv3 is None
        or boxscoreadvancedv3 is None
    ):
        raise ImportError(
            "nba_api is not installed. Please activate the project venv and install it first."
        )


def get_data_dir() -> str:
    # 获取 NBA data 目录。
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_file_path(file_name: str) -> str:
    # 返回 data 目录下文件的完整路径。
    return os.path.join(get_data_dir(), file_name)


def now_text() -> str:
    # 生成状态更新时间。
    return datetime.now().isoformat(timespec="seconds")


def safe_text(value, default: str = "") -> str:
    # 安全文本化。
    if value is None or pd.isna(value):
        return default
    return str(value)


def normalize_game_id(value) -> str:
    # NBA game_id 必须保留前导 0，统一标准化为 10 位字符串。
    text = safe_text(value)
    if text == "":
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits == "":
        return text
    return digits.zfill(10)


def safe_int(value, default: int = 0) -> int:
    # 安全转成整数。
    if value is None or pd.isna(value) or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value, default: float = 0.0) -> float:
    # 安全转成浮点数。
    if value is None or pd.isna(value) or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bool_flag(value) -> int:
    # 将真值标准化为 0/1。
    return 1 if safe_int(value, 0) != 0 else 0


def prompt_for_season() -> int:
    # 读取赛季起始年份，例如 2024 表示 2024-25。
    while True:
        value = input("Enter season start year (e.g. 2024 for 2024-25): ").strip()
        if value.isdigit():
            season = int(value)
            if season >= 1946:
                return season
        print("Invalid season. Please enter a valid NBA season start year.")


def prompt_for_month(label: str) -> int:
    # 读取月份范围。
    while True:
        value = input(f"Enter {label} month (1-12): ").strip()
        if value.isdigit():
            month = int(value)
            if 1 <= month <= 12:
                return month
        print(f"Invalid {label} month. Please enter an integer from 1 to 12.")


def build_season_text(season_start_year: int) -> str:
    # 将 2024 转成 2024-25 这种赛季文本。
    return f"{season_start_year}-{str(season_start_year + 1)[-2:]}"


def season_month_to_year(season_start_year: int, month: int) -> int:
    # NBA 赛季跨年，7-12 视为赛季起始年，1-6 视为下一年。
    return season_start_year if month >= 7 else season_start_year + 1


def resolve_date_range(season_start_year: int, start_month: int, end_month: int) -> Tuple[date, date]:
    # 根据赛季和月份范围换算真实日期区间。
    start_year = season_month_to_year(season_start_year, start_month)
    end_year = season_month_to_year(season_start_year, end_month)
    start_date = date(start_year, start_month, 1)
    end_day = calendar.monthrange(end_year, end_month)[1]
    end_date = date(end_year, end_month, end_day)
    # 2019-20、2020-21 等特殊赛季可能在次年 7-9 月继续进行。
    # 当结束月份按常规映射落在开始日期之前时，将它解释为下一自然年。
    if end_date < start_date and end_month >= 7:
        end_year += 1
        end_day = calendar.monthrange(end_year, end_month)[1]
        end_date = date(end_year, end_month, end_day)
    if start_date > end_date:
        raise ValueError("start month must be earlier than or equal to end month within the season window.")
    return start_date, end_date


def initialize_csv(file_name: str, columns: List[str]) -> None:
    # 初始化空 CSV。
    file_path = get_file_path(file_name)
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        pd.DataFrame(columns=columns).to_csv(file_path, index=False)


def load_local_df(file_name: str, columns: List[str], label: str) -> pd.DataFrame:
    # 读取本地业务表。
    initialize_csv(file_name, columns)
    file_path = get_file_path(file_name)
    print_section(f"开始读取 {label}")
    df = pd.read_csv(file_path, dtype=str)
    if df.empty:
        print_section(f"结束读取 {label}，当前为空表")
        return pd.DataFrame(columns=columns)
    if "game_id" in df.columns:
        df["game_id"] = df["game_id"].apply(normalize_game_id)
    print_section(f"结束读取 {label}，共加载 {len(df)} 条记录")
    return df


def save_local_df(df: pd.DataFrame, file_name: str, columns: List[str], label: str) -> None:
    # 将业务表写回本地。
    print_section(f"开始写入 {label}")
    df = df[columns]
    df.to_csv(get_file_path(file_name), index=False)
    print_section(f"结束写入 {label}，共 {len(df)} 条记录")


def load_status_df() -> pd.DataFrame:
    # 读取状态表。
    initialize_csv("game_update_status.csv", STATUS_COLUMNS)
    status_df = pd.read_csv(get_file_path("game_update_status.csv"), dtype=str)
    if status_df.empty:
        return pd.DataFrame(columns=STATUS_COLUMNS)
    status_df["game_id"] = status_df["game_id"].apply(normalize_game_id)
    for column in STAGE_COLUMNS + ["fully_loaded"]:
        status_df[column] = (
            pd.to_numeric(status_df[column], errors="coerce")
            .fillna(0)
            .astype(int)
        )
    return status_df


def recompute_fully_loaded(status_df: pd.DataFrame) -> pd.DataFrame:
    # 重新计算 fully_loaded。
    if status_df.empty:
        return status_df
    status_df["fully_loaded"] = (
        status_df["games_loaded"].astype(int)
        & status_df["players_loaded"].astype(int)
        & status_df["play_by_play_loaded"].astype(int)
        & status_df["team_loaded"].astype(int)
        & status_df["player_loaded"].astype(int)
    ).astype(int)
    return status_df


def save_status_df(status_df: pd.DataFrame) -> None:
    # 保存状态表。
    status_df = recompute_fully_loaded(status_df)
    if not status_df.empty:
        status_df["game_id"] = status_df["game_id"].apply(normalize_game_id)
        status_df = status_df.drop_duplicates(subset=["game_id"], keep="last")
    status_df = status_df[STATUS_COLUMNS]
    status_df = status_df.sort_values(
        by=["fully_loaded", "season", "game_date", "game_id"],
        ascending=[True, False, False, False],
    )
    status_df.to_csv(get_file_path("game_update_status.csv"), index=False)


def reconcile_play_by_play_status() -> None:
    """Make play-by-play status reflect the game IDs actually present on disk."""
    play_by_play_path = get_file_path("play_by_play.csv")
    status_df = load_status_df()
    if not os.path.exists(play_by_play_path) or os.path.getsize(play_by_play_path) == 0:
        present_game_ids: set[str] = set()
    else:
        play_by_play_ids = pd.read_csv(
            play_by_play_path,
            usecols=["game_id"],
            dtype={"game_id": str},
        )["game_id"].apply(normalize_game_id)
        present_game_ids = set(play_by_play_ids)
    status_df["play_by_play_loaded"] = status_df["game_id"].isin(
        present_game_ids
    ).astype(int)
    save_status_df(status_df)
    print_section(
        "play_by_play状态校正完成："
        f"file_games={len(present_game_ids)}, status_games={len(status_df)}"
    )


def ensure_status_rows(status_df: pd.DataFrame, target_games_df: pd.DataFrame) -> pd.DataFrame:
    # 确保目标比赛都存在于状态表中。
    existing_game_ids = set(status_df["game_id"].astype(str)) if not status_df.empty else set()
    new_rows = []
    for _, game_row in target_games_df.iterrows():
        game_id = safe_text(game_row["game_id"])
        if game_id in existing_game_ids:
            continue
        new_rows.append(
            {
                "game_id": game_id,
                "season": int(game_row["season"]),
                "game_date": safe_text(game_row["game_date"]),
                "home_abbr": safe_text(game_row["home_abbr"]),
                "away_abbr": safe_text(game_row["away_abbr"]),
                "games_loaded": 1,
                "players_loaded": 0,
                "play_by_play_loaded": 0,
                "team_loaded": 0,
                "player_loaded": 0,
                "fully_loaded": 0,
                "last_updated": now_text(),
                "error_message": "",
            }
        )

    if new_rows:
        status_df = pd.concat(
            [status_df, pd.DataFrame(new_rows, columns=STATUS_COLUMNS)],
            ignore_index=True,
        )

    target_game_map = {safe_text(row["game_id"]): row for _, row in target_games_df.iterrows()}
    for index, row in status_df.iterrows():
        game_id = safe_text(row["game_id"])
        if game_id not in target_game_map:
            continue
        game_row = target_game_map[game_id]
        status_df.loc[index, "season"] = int(game_row["season"])
        status_df.loc[index, "game_date"] = safe_text(game_row["game_date"])
        status_df.loc[index, "home_abbr"] = safe_text(game_row["home_abbr"])
        status_df.loc[index, "away_abbr"] = safe_text(game_row["away_abbr"])
        status_df.loc[index, "games_loaded"] = 1

    return recompute_fully_loaded(status_df)


def get_status_row(status_df: pd.DataFrame, game_id: str) -> pd.Series:
    # 获取单场状态。
    normalized_game_id = normalize_game_id(game_id)
    row_df = status_df.loc[status_df["game_id"].astype(str) == normalized_game_id]
    if row_df.empty:
        raise ValueError(f"Missing status row for game {game_id}")
    return row_df.iloc[0]


def mark_stage_success(status_df: pd.DataFrame, game_id: str, stage_column: str) -> pd.DataFrame:
    # 标记阶段完成。
    normalized_game_id = normalize_game_id(game_id)
    mask = status_df["game_id"].astype(str) == normalized_game_id
    status_df.loc[mask, stage_column] = 1
    status_df.loc[mask, "last_updated"] = now_text()
    status_df.loc[mask, "error_message"] = ""
    return recompute_fully_loaded(status_df)


def mark_stage_error(status_df: pd.DataFrame, game_id: str, error_message: str) -> pd.DataFrame:
    # 记录阶段错误。
    normalized_game_id = normalize_game_id(game_id)
    mask = status_df["game_id"].astype(str) == normalized_game_id
    status_df.loc[mask, "last_updated"] = now_text()
    status_df.loc[mask, "error_message"] = error_message
    return recompute_fully_loaded(status_df)


def load_team_map() -> Tuple[pd.DataFrame, Dict[str, int], Dict[int, str]]:
    # 读取球队字典，并建立本地缩写与内部 ID 映射。
    teams_df = pd.read_csv(get_file_path("teams.csv"))
    team_id_map = {
        safe_text(row["team_abbr"]): int(row["team_id"])
        for _, row in teams_df.iterrows()
    }
    team_abbr_by_nba_id: Dict[int, str] = {}
    return teams_df, team_id_map, team_abbr_by_nba_id


def fetch_league_gamefinder_df(
    season_text: str,
    season_type: str,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    # 调 leaguegamefinder 读取指定赛季类型和日期范围的比赛。
    endpoint = leaguegamefinder.LeagueGameFinder(
        player_or_team_abbreviation="T",
        season_nullable=season_text,
        season_type_nullable=season_type,
        date_from_nullable=start_date.strftime("%m/%d/%Y"),
        date_to_nullable=end_date.strftime("%m/%d/%Y"),
        timeout=60,
    )
    data_frames = endpoint.get_data_frames()
    if not data_frames:
        return pd.DataFrame()
    return data_frames[0]


def parse_team_minutes_to_total(minutes_value) -> int:
    # 将球队分钟格式转成总分钟数，用来判断是否加时。
    text = safe_text(minutes_value)
    if text == "":
        return 240
    if ":" in text:
        minute_text = text.split(":", 1)[0]
        return safe_int(minute_text, 240)
    return safe_int(text, 240)


def compute_overtime_from_minutes(minutes_value) -> int:
    # 根据球队总分钟数推算加时次数。
    total_minutes = parse_team_minutes_to_total(minutes_value)
    if total_minutes <= 240:
        return 0
    return max((total_minutes - 240) // 25, 0)


def build_games_from_gamefinder(
    gamefinder_df: pd.DataFrame,
    season_start_year: int,
    game_type_value: int,
    team_id_map: Dict[str, int],
) -> List[dict]:
    # 将 leaguegamefinder 的双行球队结果整理成单行比赛记录。
    if gamefinder_df.empty:
        return []

    gamefinder_df = gamefinder_df.copy()
    gamefinder_df["GAME_ID"] = gamefinder_df["GAME_ID"].astype(str)
    gamefinder_df["GAME_DATE"] = pd.to_datetime(gamefinder_df["GAME_DATE"], errors="coerce")

    games: List[dict] = []
    grouped = list(gamefinder_df.groupby("GAME_ID", sort=False))
    total_games = len(grouped)
    for index, (_, game_rows) in enumerate(grouped, start=1):
        print_progress(index, total_games, "整理比赛进度")
        if len(game_rows) < 2:
            continue

        home_candidates = game_rows[
            game_rows["MATCHUP"].astype(str).str.contains("vs\\.", regex=True)
        ]
        away_candidates = game_rows[
            game_rows["MATCHUP"].astype(str).str.contains("@", regex=False)
        ]
        if home_candidates.empty or away_candidates.empty:
            continue

        home_row = home_candidates.iloc[0]
        away_row = away_candidates.iloc[0]

        home_abbr = safe_text(home_row.get("TEAM_ABBREVIATION"))
        away_abbr = safe_text(away_row.get("TEAM_ABBREVIATION"))
        game_date = home_row.get("GAME_DATE")

        if (
            home_abbr == ""
            or away_abbr == ""
            or home_abbr not in team_id_map
            or away_abbr not in team_id_map
            or pd.isna(game_date)
        ):
            continue

        home_score = safe_int(home_row.get("PTS"))
        away_score = safe_int(away_row.get("PTS"))
        games.append(
            {
                "game_id": normalize_game_id(home_row.get("GAME_ID")),
                "season": int(season_start_year),
                "game_date": game_date.strftime("%Y-%m-%d"),
                "game_datetime": f"{game_date.strftime('%Y-%m-%d')}T00:00:00",
                "game_type": int(game_type_value),
                "home_team_id": int(team_id_map[home_abbr]),
                "home_abbr": home_abbr,
                "away_team_id": int(team_id_map[away_abbr]),
                "away_abbr": away_abbr,
                "home_score": home_score,
                "away_score": away_score,
                "home_win": 1 if home_score > away_score else 0,
                "overtime": compute_overtime_from_minutes(home_row.get("MIN")),
            }
        )
    return games


def build_supplemental_regular_games(
    season_start_year: int,
    start_date: date,
    end_date: date,
    team_id_map: Dict[str, int],
) -> List[dict]:
    # 补充 LeagueGameFinder 漏掉的特殊常规赛，例如中立场/NBA Cup 场次。
    supplemental_games = []
    for raw_game in SUPPLEMENTAL_REGULAR_SEASON_GAMES.get(season_start_year, []):
        game_date = pd.to_datetime(raw_game["game_date"], errors="coerce")
        if pd.isna(game_date):
            continue
        game_date_value = game_date.date()
        if not (start_date <= game_date_value <= end_date):
            continue

        home_abbr = safe_text(raw_game["home_abbr"])
        away_abbr = safe_text(raw_game["away_abbr"])
        if home_abbr not in team_id_map or away_abbr not in team_id_map:
            print_section(
                f"跳过补充比赛 {raw_game['game_id']}，球队缩写无法匹配："
                f"{away_abbr} @ {home_abbr}"
            )
            continue

        home_score = safe_int(raw_game["home_score"])
        away_score = safe_int(raw_game["away_score"])
        supplemental_games.append(
            {
                "game_id": normalize_game_id(raw_game["game_id"]),
                "season": int(season_start_year),
                "game_date": game_date_value.strftime("%Y-%m-%d"),
                "game_datetime": f"{game_date_value.strftime('%Y-%m-%d')}T00:00:00",
                "game_type": 1,
                "home_team_id": int(team_id_map[home_abbr]),
                "home_abbr": home_abbr,
                "away_team_id": int(team_id_map[away_abbr]),
                "away_abbr": away_abbr,
                "home_score": home_score,
                "away_score": away_score,
                "home_win": 1 if home_score > away_score else 0,
                "overtime": 0,
            }
        )

    if supplemental_games:
        print_section(f"补充特殊常规赛 {len(supplemental_games)} 场")
    return supplemental_games


def print_regular_season_integrity_check(games_df: pd.DataFrame, season_start_year: int) -> None:
    # 打印当前本地常规赛完整性检查，正常完整赛季应为 1230 场、每队 82 场。
    if games_df.empty:
        return
    check_df = games_df.copy()
    check_df["game_id"] = check_df["game_id"].apply(normalize_game_id)
    check_df["season"] = pd.to_numeric(check_df["season"], errors="coerce")
    regular_df = check_df[
        (check_df["season"] == int(season_start_year))
        & (check_df["game_id"].astype(str).str.startswith("002"))
    ].copy()
    if regular_df.empty:
        return

    team_counts: Dict[str, int] = {}
    for _, row in regular_df.iterrows():
        home_abbr = safe_text(row.get("home_abbr"))
        away_abbr = safe_text(row.get("away_abbr"))
        if home_abbr:
            team_counts[home_abbr] = team_counts.get(home_abbr, 0) + 1
        if away_abbr:
            team_counts[away_abbr] = team_counts.get(away_abbr, 0) + 1

    incomplete_teams = {
        team: count
        for team, count in sorted(team_counts.items())
        if count != 82
    }
    print_section(f"常规赛完整性检查：season={season_start_year}, games={len(regular_df)}")
    if incomplete_teams:
        print_section(f"仍有球队不是 82 场：{incomplete_teams}")
    else:
        print_section("常规赛完整性检查通过：所有球队均为 82 场")


def update_games_table(new_games: List[dict]) -> pd.DataFrame:
    # 更新本地 games.csv，并返回本次目标比赛。
    initialize_csv("games.csv", GAMES_COLUMNS)
    existing_df = pd.read_csv(get_file_path("games.csv"), dtype=str)
    new_df = pd.DataFrame(new_games, columns=GAMES_COLUMNS) if new_games else pd.DataFrame(columns=GAMES_COLUMNS)

    if existing_df.empty:
        updated_df = new_df
    else:
        updated_df = pd.concat([existing_df, new_df], ignore_index=True)

    if not updated_df.empty:
        updated_df["game_id"] = updated_df["game_id"].apply(normalize_game_id)
        updated_df = updated_df.drop_duplicates(subset=["game_id"], keep="first")
        updated_df = updated_df.sort_values(
            by=["game_date", "game_datetime", "game_id"],
            ascending=[False, False, False],
        )

    save_local_df(updated_df, "games.csv", GAMES_COLUMNS, "games.csv")
    return updated_df


def build_target_games_df(season_start_year: int, start_month: int, end_month: int) -> pd.DataFrame:
    # 根据赛季和月份区间获取目标比赛，并写入 games.csv。
    season_text = build_season_text(season_start_year)
    start_date, end_date = resolve_date_range(season_start_year, start_month, end_month)
    print_section(
        f"开始更新 games.csv，season={season_text}, range={start_date.isoformat()} to {end_date.isoformat()}"
    )

    _, team_id_map, _ = load_team_map()
    regular_df = fetch_league_gamefinder_df(season_text, REGULAR_SEASON_TYPE, start_date, end_date)
    playoff_df = fetch_league_gamefinder_df(season_text, PLAYOFF_TYPE, start_date, end_date)

    target_games = []
    target_games.extend(
        build_games_from_gamefinder(regular_df, season_start_year, 1, team_id_map)
    )
    target_games.extend(
        build_supplemental_regular_games(season_start_year, start_date, end_date, team_id_map)
    )
    target_games.extend(
        build_games_from_gamefinder(playoff_df, season_start_year, 0, team_id_map)
    )

    target_games_df = pd.DataFrame(target_games, columns=GAMES_COLUMNS)
    if not target_games_df.empty:
        target_games_df = target_games_df.sort_values(
            by=["game_date", "game_datetime", "game_id"],
            ascending=[False, False, False],
        )
    updated_games_df = update_games_table(target_games)
    print_regular_season_integrity_check(updated_games_df, season_start_year)
    print_section(f"结束更新 games.csv，本次目标比赛共 {len(target_games_df)} 场")
    return target_games_df


def update_model_team_stats_from_gamefinder(
    season_start_year: int,
    start_month: int,
    end_month: int,
    target_games_df: pd.DataFrame,
    status_df: pd.DataFrame,
) -> pd.DataFrame:
    """Bulk-load the regular-season team stats required by the model."""
    season_text = build_season_text(season_start_year)
    start_date, end_date = resolve_date_range(season_start_year, start_month, end_month)
    regular_df = fetch_league_gamefinder_df(
        season_text,
        REGULAR_SEASON_TYPE,
        start_date,
        end_date,
    )
    if regular_df.empty:
        raise ValueError(f"No regular-season team rows returned for {season_text}")

    game_map = {
        normalize_game_id(row["game_id"]): row
        for _, row in target_games_df.loc[target_games_df["game_type"].eq(1)].iterrows()
    }
    rows: List[dict] = []
    grouped = list(regular_df.groupby(regular_df["GAME_ID"].apply(normalize_game_id)))
    for index, (game_id, game_rows) in enumerate(grouped, start=1):
        print_progress(index, len(grouped), "批量整理模型球队数据")
        if game_id not in game_map or len(game_rows) < 2:
            continue
        game = game_map[game_id]
        by_abbr = {
            safe_text(row.get("TEAM_ABBREVIATION")): row
            for _, row in game_rows.iterrows()
        }
        for team_abbr, is_home in (
            (safe_text(game["home_abbr"]), 1),
            (safe_text(game["away_abbr"]), 0),
        ):
            opponent_abbr = (
                safe_text(game["away_abbr"])
                if is_home == 1
                else safe_text(game["home_abbr"])
            )
            row = by_abbr.get(team_abbr)
            opponent_row = by_abbr.get(opponent_abbr)
            if row is None or opponent_row is None:
                continue

            fgm = safe_int(row.get("FGM"))
            fga = safe_int(row.get("FGA"))
            fg3m = safe_int(row.get("FG3M"))
            fg3a = safe_int(row.get("FG3A"))
            ftm = safe_int(row.get("FTM"))
            fta = safe_int(row.get("FTA"))
            oreb = safe_int(row.get("OREB"))
            tov = safe_int(row.get("TOV"))
            points = safe_int(row.get("PTS"))
            opponent_points = safe_int(opponent_row.get("PTS"))
            possessions = fga + 0.44 * fta - oreb + tov
            opponent_possessions = (
                safe_int(opponent_row.get("FGA"))
                + 0.44 * safe_int(opponent_row.get("FTA"))
                - safe_int(opponent_row.get("OREB"))
                + safe_int(opponent_row.get("TOV"))
            )
            off_rating = 100 * points / possessions if possessions > 0 else 0.0
            def_rating = (
                100 * opponent_points / opponent_possessions
                if opponent_possessions > 0
                else 0.0
            )
            rows.append(
                {
                    "game_id": game_id,
                    "season": int(season_start_year),
                    "team_id": safe_int(
                        game["home_team_id"] if is_home == 1 else game["away_team_id"]
                    ),
                    "team_abbr": team_abbr,
                    "opponent_team_id": safe_int(
                        game["away_team_id"] if is_home == 1 else game["home_team_id"]
                    ),
                    "opponent_abbr": opponent_abbr,
                    "is_home": is_home,
                    "team_win": 1 if points > opponent_points else 0,
                    "minutes": safe_text(row.get("MIN")),
                    "points": points,
                    "fgm": fgm,
                    "fga": fga,
                    "fg3m": fg3m,
                    "fg3a": fg3a,
                    "ftm": ftm,
                    "fta": fta,
                    "oreb": oreb,
                    "dreb": safe_int(row.get("DREB")),
                    "reb": safe_int(row.get("REB")),
                    "ast": safe_int(row.get("AST")),
                    "stl": safe_int(row.get("STL")),
                    "blk": safe_int(row.get("BLK")),
                    "tov": tov,
                    "pf": safe_int(row.get("PF")),
                    "fast_break_points": 0,
                    "points_in_paint": 0,
                    "second_chance_points": 0,
                    "largest_lead": 0,
                    "lead_changes": 0,
                    "times_tied": 0,
                    "fg_pct": fgm / fga if fga > 0 else 0.0,
                    "fg3_pct": fg3m / fg3a if fg3a > 0 else 0.0,
                    "ft_pct": ftm / fta if fta > 0 else 0.0,
                    "efg_pct": (fgm + 0.5 * fg3m) / fga if fga > 0 else 0.0,
                    "ts_pct": (
                        points / (2 * (fga + 0.44 * fta))
                        if (fga + 0.44 * fta) > 0
                        else 0.0
                    ),
                    "pace": (possessions + opponent_possessions) / 2,
                    "possessions": possessions,
                    "off_rating": off_rating,
                    "def_rating": def_rating,
                    "net_rating": off_rating - def_rating,
                }
            )

    expected_games = len(game_map)
    new_df = pd.DataFrame(rows, columns=TEAM_GAME_STATS_COLUMNS)
    counts = new_df.groupby("game_id").size() if not new_df.empty else pd.Series(dtype=int)
    complete_game_ids = set(counts.loc[counts.eq(2)].index.astype(str))
    if len(complete_game_ids) != expected_games:
        missing = sorted(set(game_map) - complete_game_ids)
        raise ValueError(
            f"Expected {expected_games} complete regular games, found "
            f"{len(complete_game_ids)}; missing examples: {missing[:5]}"
        )

    existing_df = load_local_df(
        "team_game_stats.csv",
        TEAM_GAME_STATS_COLUMNS,
        "team_game_stats.csv",
    )
    existing_df = existing_df.loc[
        ~existing_df["game_id"].astype(str).isin(complete_game_ids)
    ].copy()
    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
    save_local_df(
        updated_df,
        "team_game_stats.csv",
        TEAM_GAME_STATS_COLUMNS,
        "team_game_stats.csv",
    )

    mask = status_df["game_id"].astype(str).isin(complete_game_ids)
    status_df.loc[mask, "team_loaded"] = 1
    status_df.loc[mask, "last_updated"] = now_text()
    status_df.loc[mask, "error_message"] = ""
    save_status_df(status_df)
    print_section(
        f"模型球队数据批量更新完成：season={season_text}, games={expected_games}"
    )
    return updated_df


def convert_iso_duration_to_clock(duration_text: str) -> str:
    # 将 PT25M01.00S 这种 ISO 时长转成 25:01。
    text = safe_text(duration_text)
    if text == "":
        return "00:00"

    match = re.search(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", text)
    if not match:
        return text

    hours = safe_int(match.group(1), 0)
    minutes = safe_int(match.group(2), 0)
    seconds = safe_int(float(match.group(3)) if match.group(3) else 0, 0)
    total_minutes = hours * 60 + minutes
    return f"{total_minutes:02d}:{seconds:02d}"


def call_boxscoretraditionalv3(game_id: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # 读取传统 box score v3，作为单场基础球员/球队数据的主来源。
    endpoint = boxscoretraditionalv3.BoxScoreTraditionalV3(
        game_id=game_id,
        start_period=1,
        end_period=10,
        start_range=0,
        end_range=0,
        range_type=0,
        timeout=60,
    )
    player_df = endpoint.player_stats.get_data_frame()
    team_df = endpoint.team_stats.get_data_frame()
    return player_df, team_df


def call_boxscoreadvancedv3(game_id: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # 读取高级 box score v3；球员表为空时允许继续，稍后用 0 补齐。
    endpoint = boxscoreadvancedv3.BoxScoreAdvancedV3(
        game_id=game_id,
        start_period=1,
        end_period=10,
        start_range=0,
        end_range=0,
        range_type=0,
        timeout=60,
    )
    player_df = endpoint.player_stats.get_data_frame()
    team_df = endpoint.team_stats.get_data_frame()
    return player_df, team_df


def call_playbyplayv3(game_id: str) -> pd.DataFrame:
    # 读取 play-by-play v3。
    endpoint = playbyplayv3.PlayByPlayV3(
        game_id=game_id,
        start_period=1,
        end_period=10,
        timeout=60,
    )
    return endpoint.get_data_frames()[0]


def normalize_traditional_player_rows(player_df: pd.DataFrame) -> pd.DataFrame:
    # 将 traditional boxscore 的球员数据整理成统一 DataFrame。
    rows: List[dict] = []
    for _, row in player_df.iterrows():
        starter_text = safe_text(row.get("starter") or row.get("STARTER"))
        rows.append(
            {
                "PLAYER_ID": safe_text(row.get("personId") or row.get("PLAYER_ID")),
                "PLAYER_NAME": safe_text(row.get("playerName") or row.get("name") or row.get("PLAYER_NAME")),
                "TEAM_ID": safe_int(row.get("teamId") or row.get("TEAM_ID")),
                "TEAM_ABBREVIATION": safe_text(row.get("teamTricode") or row.get("TEAM_ABBREVIATION")),
                "MIN": convert_iso_duration_to_clock(row.get("minutes") or row.get("MIN")),
                "PTS": safe_int(row.get("points") or row.get("PTS")),
                "FGM": safe_int(row.get("fieldGoalsMade") or row.get("FGM")),
                "FGA": safe_int(row.get("fieldGoalsAttempted") or row.get("FGA")),
                "FG_PCT": safe_float(row.get("fieldGoalsPercentage") or row.get("FG_PCT")),
                "FG3M": safe_int(row.get("threePointersMade") or row.get("FG3M")),
                "FG3A": safe_int(row.get("threePointersAttempted") or row.get("FG3A")),
                "FG3_PCT": safe_float(row.get("threePointersPercentage") or row.get("FG3_PCT")),
                "FTM": safe_int(row.get("freeThrowsMade") or row.get("FTM")),
                "FTA": safe_int(row.get("freeThrowsAttempted") or row.get("FTA")),
                "FT_PCT": safe_float(row.get("freeThrowsPercentage") or row.get("FT_PCT")),
                "OREB": safe_int(row.get("reboundsOffensive") or row.get("OREB")),
                "DREB": safe_int(row.get("reboundsDefensive") or row.get("DREB")),
                "REB": safe_int(row.get("reboundsTotal") or row.get("REB")),
                "AST": safe_int(row.get("assists") or row.get("AST")),
                "STL": safe_int(row.get("steals") or row.get("STL")),
                "BLK": safe_int(row.get("blocks") or row.get("BLK")),
                "TO": safe_int(row.get("turnovers") or row.get("TO")),
                "PF": safe_int(row.get("foulsPersonal") or row.get("PF")),
                "PLUS_MINUS": safe_float(row.get("plusMinusPoints") or row.get("PLUS_MINUS")),
                "START_POSITION": safe_text(row.get("position") or row.get("START_POSITION")) if starter_text in {"1", "Y", "Yes", "True", "true"} else "",
                "COMMENT": safe_text(row.get("comment") or row.get("COMMENT")),
                "STARTER_FLAG": 1 if starter_text in {"1", "Y", "Yes", "True", "true"} else 0,
            }
        )
    return pd.DataFrame(rows)


def normalize_traditional_team_rows(team_df: pd.DataFrame) -> pd.DataFrame:
    # 将 traditional boxscore 的球队数据整理成统一 DataFrame。
    rows: List[dict] = []
    for _, row in team_df.iterrows():
        rows.append(
            {
                "TEAM_ID": safe_int(row.get("teamId") or row.get("TEAM_ID")),
                "TEAM_ABBREVIATION": safe_text(row.get("teamTricode") or row.get("TEAM_ABBREVIATION")),
                "MIN": convert_iso_duration_to_clock(row.get("minutes") or row.get("MIN")),
                "PTS": safe_int(row.get("points") or row.get("PTS")),
                "FGM": safe_int(row.get("fieldGoalsMade") or row.get("FGM")),
                "FGA": safe_int(row.get("fieldGoalsAttempted") or row.get("FGA")),
                "FG_PCT": safe_float(row.get("fieldGoalsPercentage") or row.get("FG_PCT")),
                "FG3M": safe_int(row.get("threePointersMade") or row.get("FG3M")),
                "FG3A": safe_int(row.get("threePointersAttempted") or row.get("FG3A")),
                "FG3_PCT": safe_float(row.get("threePointersPercentage") or row.get("FG3_PCT")),
                "FTM": safe_int(row.get("freeThrowsMade") or row.get("FTM")),
                "FTA": safe_int(row.get("freeThrowsAttempted") or row.get("FTA")),
                "FT_PCT": safe_float(row.get("freeThrowsPercentage") or row.get("FT_PCT")),
                "OREB": safe_int(row.get("reboundsOffensive") or row.get("OREB")),
                "DREB": safe_int(row.get("reboundsDefensive") or row.get("DREB")),
                "REB": safe_int(row.get("reboundsTotal") or row.get("REB")),
                "AST": safe_int(row.get("assists") or row.get("AST")),
                "STL": safe_int(row.get("steals") or row.get("STL")),
                "BLK": safe_int(row.get("blocks") or row.get("BLK")),
                "TO": safe_int(row.get("turnovers") or row.get("TO")),
                "PF": safe_int(row.get("foulsPersonal") or row.get("PF")),
                "FAST_BREAK_POINTS": safe_int(row.get("pointsFastBreak") or row.get("FAST_BREAK_POINTS")),
                "POINTS_IN_PAINT": safe_int(row.get("pointsInThePaint") or row.get("POINTS_IN_PAINT")),
                "SECOND_CHANCE_POINTS": safe_int(row.get("pointsSecondChance") or row.get("SECOND_CHANCE_POINTS")),
                "LARGEST_LEAD": safe_int(row.get("biggestLead") or row.get("LARGEST_LEAD")),
                "LEAD_CHANGES": safe_int(row.get("leadChanges") or row.get("LEAD_CHANGES")),
                "TIMES_TIED": safe_int(row.get("timesTied") or row.get("TIMES_TIED")),
                "EFG_PCT_LIVE": safe_float(row.get("fieldGoalsEffectiveAdjusted") or row.get("EFG_PCT_LIVE")),
                "TS_PCT_LIVE": safe_float(row.get("trueShootingPercentage") or row.get("TS_PCT_LIVE")),
            }
        )
    return pd.DataFrame(rows)


def fetch_game_payloads(game_id: str) -> Dict[str, object]:
    # 一次性读取单场比赛需要的所有端点。
    print_section(f"开始读取比赛 {game_id} 的 NBA 官方数据")
    try:
        player_traditional_raw_df, team_traditional_raw_df = call_boxscoretraditionalv3(game_id)
        player_traditional_df = normalize_traditional_player_rows(player_traditional_raw_df)
        team_traditional_df = normalize_traditional_team_rows(team_traditional_raw_df)
    except Exception as exc:
        raise RuntimeError(f"boxscoretraditionalv3 failed: {type(exc).__name__}: {exc}") from exc

    try:
        player_advanced_df, team_advanced_df = call_boxscoreadvancedv3(game_id)
    except Exception as exc:
        raise RuntimeError(f"boxscoreadvancedv3 failed: {type(exc).__name__}: {exc}") from exc

    try:
        pbp_v3_df = call_playbyplayv3(game_id)
    except Exception as exc:
        raise RuntimeError(f"playbyplayv3 failed: {type(exc).__name__}: {exc}") from exc

    print_section(f"结束读取比赛 {game_id} 的 NBA 官方数据")
    return {
        "player_traditional_df": player_traditional_df,
        "team_traditional_df": team_traditional_df,
        "player_advanced_df": player_advanced_df,
        "team_advanced_df": team_advanced_df,
        "pbp_v3_df": pbp_v3_df,
    }


def parse_birth_date(value) -> str:
    # 规范化球员生日。
    text = safe_text(value)
    if text == "":
        return ""
    try:
        return pd.to_datetime(text, errors="coerce").strftime("%Y-%m-%d")
    except Exception:
        return text[:10]


def process_players_for_game(
    game_row: pd.Series,
    players_df: pd.DataFrame,
    player_traditional_df: pd.DataFrame,
) -> pd.DataFrame:
    # 读取单场球员并补全 players.csv。
    existing_nba_ids = set(players_df["nba_id"].astype(str)) if not players_df.empty else set()
    candidate_ids = sorted(
        {
            safe_text(value)
            for value in player_traditional_df["PLAYER_ID"].dropna().tolist()
            if safe_text(value) != ""
        }
    )
    missing_nba_ids = [nba_id for nba_id in candidate_ids if nba_id not in existing_nba_ids]

    if not missing_nba_ids:
        return players_df

    next_player_id = 0
    if not players_df.empty:
        next_player_id = safe_int(pd.to_numeric(players_df["player_id"], errors="coerce").max(), 0) + 1

    new_rows = []
    total_missing = len(missing_nba_ids)
    print_section(f"开始补充 players.csv，共 {total_missing} 名新球员")
    for index, nba_id in enumerate(missing_nba_ids, start=1):
        print_progress(index, total_missing, "读取球员主信息进度")
        endpoint = commonplayerinfo.CommonPlayerInfo(player_id=nba_id, timeout=60)
        data_frames = endpoint.get_data_frames()
        if not data_frames or data_frames[0].empty:
            continue
        row = data_frames[0].iloc[0]
        new_rows.append(
            {
                "player_id": next_player_id,
                "nba_id": safe_text(row.get("PERSON_ID")),
                "full_name": safe_text(row.get("DISPLAY_FIRST_LAST")),
                "first_name": safe_text(row.get("FIRST_NAME")),
                "last_name": safe_text(row.get("LAST_NAME")),
                "birth_date": parse_birth_date(row.get("BIRTHDATE")),
                "position": safe_text(row.get("POSITION")),
                "height": safe_text(row.get("HEIGHT")),
                "weight": safe_text(row.get("WEIGHT")),
                "college": safe_text(row.get("SCHOOL")),
                "country": safe_text(row.get("COUNTRY")),
                "draft_year": safe_text(row.get("DRAFT_YEAR")),
            }
        )
        next_player_id += 1

    if new_rows:
        players_df = pd.concat(
            [players_df, pd.DataFrame(new_rows, columns=PLAYERS_COLUMNS)],
            ignore_index=True,
        )
        players_df = players_df.drop_duplicates(subset=["nba_id"], keep="first")
        # 统一按数值 player_id 排序，避免 CSV 读入后字符串/整数混排导致报错。
        players_df["_player_id_sort"] = pd.to_numeric(players_df["player_id"], errors="coerce")
        players_df = players_df.sort_values(by=["_player_id_sort"], ascending=[True], na_position="last")
        players_df["player_id"] = players_df["_player_id_sort"].fillna(-1).astype(int).astype(str)
        players_df = players_df.drop(columns=["_player_id_sort"])
        save_local_df(players_df, "players.csv", PLAYERS_COLUMNS, "players.csv")
    return players_df


def build_player_lookup(players_df: pd.DataFrame) -> Dict[str, dict]:
    # 建立 nba_id -> 本地 player 记录映射。
    if players_df.empty:
        return {}
    return {
        safe_text(row["nba_id"]): row.to_dict()
        for _, row in players_df.iterrows()
        if safe_text(row.get("nba_id")) != ""
    }


def parse_clock_to_minutes_seconds(clock_text: str) -> Tuple[int, int]:
    # 解析 NBA PBP 的时钟字段。
    text = safe_text(clock_text)
    if text == "":
        return 0, 0

    iso_match = re.search(r"PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", text)
    if iso_match:
        minutes = safe_int(iso_match.group(1), 0)
        seconds = safe_int(float(iso_match.group(2)) if iso_match.group(2) else 0, 0)
        return minutes, seconds

    if ":" in text:
        minute_text, second_text = text.split(":", 1)
        return safe_int(minute_text), safe_int(second_text)

    return 0, 0


def parse_score_margin(score_home: int, score_away: int) -> int:
    # 统一输出主队视角的分差。
    return score_home - score_away


def parse_free_throw_numbers(description: str) -> Tuple[int, int]:
    # 从描述中解析罚球序号。
    text = safe_text(description).upper()
    match = re.search(r"FREE THROW\s+(\d+)\s+OF\s+(\d+)", text)
    if not match:
        return 0, 0
    return safe_int(match.group(1)), safe_int(match.group(2))


def infer_rebound_type(description: str) -> str:
    # 从描述中判断篮板类型。
    text = safe_text(description).lower()
    if "off" in text and "rebound" in text:
        return "offensive"
    if "def" in text and "rebound" in text:
        return "defensive"
    return ""


def infer_three_point_attempt(description: str, sub_type: str) -> int:
    # 判断是否为三分出手。
    text = f"{safe_text(description)} {safe_text(sub_type)}".upper()
    return 1 if "3PT" in text or "THREE" in text else 0


def infer_shot_value(is_field_goal: int, is_three_point_attempt: int, points_scored: int, is_free_throw_attempt: int) -> int:
    # 推断单个事件的出手分值。
    if is_free_throw_attempt == 1:
        return 1
    if is_field_goal == 1:
        return 3 if is_three_point_attempt == 1 else 2
    if points_scored in {1, 2, 3}:
        return points_scored
    return 0


def build_play_by_play_rows(game_row: pd.Series, pbp_v3_df: pd.DataFrame) -> List[dict]:
    # 构建本地 play_by_play 表。
    rows: List[dict] = []
    for _, row in pbp_v3_df.iterrows():
        description = safe_text(row.get("description"))
        action_type = safe_text(row.get("actionType"))
        sub_type = safe_text(row.get("subType"))
        points_scored = safe_int(row.get("pointsTotal"))
        score_home = safe_int(row.get("scoreHome"))
        score_away = safe_int(row.get("scoreAway"))
        player_id = safe_text(row.get("personId"))
        player_name = safe_text(row.get("playerName"))
        team_abbr = safe_text(row.get("teamTricode"))

        clock_minutes, clock_seconds = parse_clock_to_minutes_seconds(safe_text(row.get("clock")))
        is_field_goal_attempt = bool_flag(row.get("isFieldGoal"))
        is_field_goal_made = 1 if safe_text(row.get("shotResult")).lower() == "made" else 0
        is_three_point_attempt = infer_three_point_attempt(description, sub_type)
        is_free_throw_attempt = 1 if action_type.lower() == "freethrow" or "FREE THROW" in description.upper() else 0
        is_free_throw_made = 1 if is_free_throw_attempt == 1 and "MISS" not in description.upper() else 0
        rebound_type = infer_rebound_type(description)
        foul_type = sub_type if action_type.lower() == "foul" else ""
        turnover_type = sub_type if action_type.lower() == "turnover" else ""
        free_throw_num, free_throw_total = parse_free_throw_numbers(description)

        rows.append(
            {
                "action_id": safe_text(row.get("actionId") or row.get("actionNumber")),
                "game_id": safe_text(game_row["game_id"]),
                "season": int(game_row["season"]),
                "period": safe_int(row.get("period")),
                "period_type": "OT" if safe_int(row.get("period")) > 4 else safe_text(row.get("periodType") or "REG"),
                "clock_minutes_remaining": clock_minutes,
                "clock_seconds_remaining": clock_seconds,
                "home_team_id": safe_int(game_row["home_team_id"]),
                "home_abbr": safe_text(game_row["home_abbr"]),
                "away_team_id": safe_int(game_row["away_team_id"]),
                "away_abbr": safe_text(game_row["away_abbr"]),
                "team_id": resolve_internal_team_id(game_row, team_abbr),
                "team_abbr": team_abbr,
                "possession_team_abbr": team_abbr,
                "action_type": action_type,
                "sub_type": sub_type,
                "description": description,
                "qualifiers": ",".join(row.get("qualifiers", [])) if isinstance(row.get("qualifiers"), list) else safe_text(row.get("qualifiers")),
                "player_id": player_id,
                "player_name": player_name,
                "assist_player_id": "",
                "assist_player_name": "",
                "block_player_id": "",
                "block_player_name": "",
                "steal_player_id": "",
                "steal_player_name": "",
                "points_scored": points_scored,
                "score_home": score_home,
                "score_away": score_away,
                "score_margin": parse_score_margin(score_home, score_away),
                "shot_type": sub_type if is_field_goal_attempt == 1 else "",
                "shot_result": safe_text(row.get("shotResult")),
                "shot_value": infer_shot_value(
                    is_field_goal_attempt,
                    is_three_point_attempt,
                    points_scored,
                    is_free_throw_attempt,
                ),
                "shot_distance": safe_int(row.get("shotDistance")),
                "x": safe_int(row.get("xLegacy")),
                "y": safe_int(row.get("yLegacy")),
                "foul_type": foul_type,
                "turnover_type": turnover_type,
                "rebound_type": rebound_type,
                "free_throw_num": free_throw_num,
                "free_throw_total": free_throw_total,
                "jump_ball_won_player_id": safe_text(row.get("jumpBallWonPersonId")),
                "jump_ball_won_player_name": safe_text(row.get("jumpBallWonPlayerName")),
                "is_field_goal_attempt": is_field_goal_attempt,
                "is_field_goal_made": is_field_goal_made,
                "is_three_point_attempt": is_three_point_attempt,
                "is_free_throw_attempt": is_free_throw_attempt,
                "is_free_throw_made": is_free_throw_made,
                "is_rebound": 1 if action_type.lower() == "rebound" else 0,
                "is_offensive_rebound": 1 if rebound_type == "offensive" else 0,
                "is_defensive_rebound": 1 if rebound_type == "defensive" else 0,
                "is_turnover": 1 if action_type.lower() == "turnover" else 0,
                "is_steal": 0,
                "is_block": 0,
                "is_foul": 1 if action_type.lower() == "foul" else 0,
                "is_timeout": 1 if action_type.lower() == "timeout" else 0,
                "is_substitution": 1 if action_type.lower() == "substitution" else 0,
                "is_jump_ball": 1 if action_type.lower() == "jumpball" else 0,
            }
        )
    return rows


def process_play_by_play_for_game(game_row: pd.Series, play_by_play_df: pd.DataFrame, pbp_v3_df: pd.DataFrame) -> pd.DataFrame:
    # 更新单场 play_by_play。
    game_id = safe_text(game_row["game_id"])
    if not play_by_play_df.empty:
        play_by_play_df = play_by_play_df[play_by_play_df["game_id"].astype(str) != game_id].copy()
    new_rows = build_play_by_play_rows(game_row, pbp_v3_df)
    if new_rows:
        play_by_play_df = pd.concat(
            [play_by_play_df, pd.DataFrame(new_rows, columns=PLAY_BY_PLAY_COLUMNS)],
            ignore_index=True,
        )
    save_local_df(play_by_play_df, "play_by_play.csv", PLAY_BY_PLAY_COLUMNS, "play_by_play.csv")
    return play_by_play_df


def find_team_opponent_meta(game_row: pd.Series, team_abbr: str) -> Tuple[int, str, int]:
    # 根据比赛行推断球队主客场和对手。
    home_abbr = safe_text(game_row["home_abbr"])
    away_abbr = safe_text(game_row["away_abbr"])
    if team_abbr == home_abbr:
        return 1, away_abbr, safe_int(game_row["away_team_id"])
    return 0, home_abbr, safe_int(game_row["home_team_id"])


def resolve_internal_team_id(game_row: pd.Series, team_abbr: str) -> int:
    # 将球队缩写映射到本地内部 team_id。
    if team_abbr == safe_text(game_row["home_abbr"]):
        return safe_int(game_row["home_team_id"])
    if team_abbr == safe_text(game_row["away_abbr"]):
        return safe_int(game_row["away_team_id"])
    return 0


def process_team_game_stats_for_game(
    game_row: pd.Series,
    team_game_stats_df: pd.DataFrame,
    team_traditional_df: pd.DataFrame,
    team_advanced_df: pd.DataFrame,
) -> pd.DataFrame:
    # 更新单场 team_game_stats。
    game_id = safe_text(game_row["game_id"])
    if not team_game_stats_df.empty:
        team_game_stats_df = team_game_stats_df[team_game_stats_df["game_id"].astype(str) != game_id].copy()

    advanced_map = {
        safe_int(row["teamId"]): row
        for _, row in team_advanced_df.iterrows()
    }

    new_rows = []
    for _, row in team_traditional_df.iterrows():
        nba_team_id = safe_int(row.get("TEAM_ID"))
        team_abbr = safe_text(row.get("TEAM_ABBREVIATION"))
        is_home, opponent_abbr, opponent_team_id = find_team_opponent_meta(game_row, team_abbr)
        advanced_row = advanced_map.get(nba_team_id, {})

        points = safe_int(row.get("PTS"))
        opponent_points = safe_int(game_row["away_score"]) if is_home == 1 else safe_int(game_row["home_score"])
        team_win = 1 if points > opponent_points else 0

        new_rows.append(
            {
                "game_id": game_id,
                "season": int(game_row["season"]),
                "team_id": safe_int(game_row["home_team_id"]) if is_home == 1 else safe_int(game_row["away_team_id"]),
                "team_abbr": team_abbr,
                "opponent_team_id": opponent_team_id,
                "opponent_abbr": opponent_abbr,
                "is_home": is_home,
                "team_win": team_win,
                "minutes": safe_text(row.get("MIN")),
                "points": points,
                "fgm": safe_int(row.get("FGM")),
                "fga": safe_int(row.get("FGA")),
                "fg3m": safe_int(row.get("FG3M")),
                "fg3a": safe_int(row.get("FG3A")),
                "ftm": safe_int(row.get("FTM")),
                "fta": safe_int(row.get("FTA")),
                "oreb": safe_int(row.get("OREB")),
                "dreb": safe_int(row.get("DREB")),
                "reb": safe_int(row.get("REB")),
                "ast": safe_int(row.get("AST")),
                "stl": safe_int(row.get("STL")),
                "blk": safe_int(row.get("BLK")),
                "tov": safe_int(row.get("TO")),
                "pf": safe_int(row.get("PF")),
                "fast_break_points": safe_int(row.get("FAST_BREAK_POINTS")),
                "points_in_paint": safe_int(row.get("POINTS_IN_PAINT")),
                "second_chance_points": safe_int(row.get("SECOND_CHANCE_POINTS")),
                "largest_lead": safe_int(row.get("LARGEST_LEAD")),
                "lead_changes": safe_int(row.get("LEAD_CHANGES")),
                "times_tied": safe_int(row.get("TIMES_TIED")),
                "fg_pct": safe_float(row.get("FG_PCT")),
                "fg3_pct": safe_float(row.get("FG3_PCT")),
                "ft_pct": safe_float(row.get("FT_PCT")),
                "efg_pct": safe_float(advanced_row.get("effectiveFieldGoalPercentage") or row.get("EFG_PCT_LIVE")),
                "ts_pct": safe_float(advanced_row.get("trueShootingPercentage") or row.get("TS_PCT_LIVE")),
                "pace": safe_float(advanced_row.get("pace")),
                "possessions": safe_float(advanced_row.get("possessions")),
                "off_rating": safe_float(advanced_row.get("offensiveRating")),
                "def_rating": safe_float(advanced_row.get("defensiveRating")),
                "net_rating": safe_float(advanced_row.get("netRating")),
            }
        )

    if new_rows:
        team_game_stats_df = pd.concat(
            [team_game_stats_df, pd.DataFrame(new_rows, columns=TEAM_GAME_STATS_COLUMNS)],
            ignore_index=True,
        )
    save_local_df(team_game_stats_df, "team_game_stats.csv", TEAM_GAME_STATS_COLUMNS, "team_game_stats.csv")
    return team_game_stats_df


def process_player_game_stats_for_game(
    game_row: pd.Series,
    player_game_stats_df: pd.DataFrame,
    player_traditional_df: pd.DataFrame,
    player_advanced_df: pd.DataFrame,
    players_lookup: Dict[str, dict],
) -> pd.DataFrame:
    # 更新单场 player_game_stats。
    game_id = safe_text(game_row["game_id"])
    if not player_game_stats_df.empty:
        player_game_stats_df = player_game_stats_df[player_game_stats_df["game_id"].astype(str) != game_id].copy()

    advanced_map = {
        safe_text(row["personId"]): row
        for _, row in player_advanced_df.iterrows()
    }

    new_rows = []
    for _, row in player_traditional_df.iterrows():
        nba_id = safe_text(row.get("PLAYER_ID"))
        if nba_id == "" or nba_id not in players_lookup:
            continue
        if safe_text(row.get("COMMENT")) != "" and safe_text(row.get("MIN")) == "":
            continue

        local_player = players_lookup[nba_id]
        team_abbr = safe_text(row.get("TEAM_ABBREVIATION"))
        is_home, opponent_abbr, opponent_team_id = find_team_opponent_meta(game_row, team_abbr)
        advanced_row = advanced_map.get(nba_id, {})

        new_rows.append(
            {
                "game_id": game_id,
                "season": int(game_row["season"]),
                "player_id": safe_int(local_player["player_id"]),
                "full_name": safe_text(local_player["full_name"]),
                "position": safe_text(local_player["position"]) or safe_text(row.get("START_POSITION")),
                "team_id": safe_int(game_row["home_team_id"]) if is_home == 1 else safe_int(game_row["away_team_id"]),
                "team_abbr": team_abbr,
                "opponent_team_id": opponent_team_id,
                "opponent_abbr": opponent_abbr,
                "is_home": is_home,
                "starter": safe_int(row.get("STARTER_FLAG")),
                "minutes": safe_text(row.get("MIN")),
                "points": safe_int(row.get("PTS")),
                "fgm": safe_int(row.get("FGM")),
                "fga": safe_int(row.get("FGA")),
                "fg3m": safe_int(row.get("FG3M")),
                "fg3a": safe_int(row.get("FG3A")),
                "ftm": safe_int(row.get("FTM")),
                "fta": safe_int(row.get("FTA")),
                "oreb": safe_int(row.get("OREB")),
                "dreb": safe_int(row.get("DREB")),
                "reb": safe_int(row.get("REB")),
                "ast": safe_int(row.get("AST")),
                "stl": safe_int(row.get("STL")),
                "blk": safe_int(row.get("BLK")),
                "tov": safe_int(row.get("TO")),
                "pf": safe_int(row.get("PF")),
                "plus_minus": safe_int(row.get("PLUS_MINUS")),
                "fg_pct": safe_float(row.get("FG_PCT")),
                "fg3_pct": safe_float(row.get("FG3_PCT")),
                "ft_pct": safe_float(row.get("FT_PCT")),
                "efg_pct": round(
                    (safe_int(row.get("FGM")) + 0.5 * safe_int(row.get("FG3M"))) / safe_int(row.get("FGA")),
                    4,
                ) if safe_int(row.get("FGA")) > 0 else 0.0,
                "ts_pct": round(
                    safe_int(row.get("PTS")) / (2 * (safe_int(row.get("FGA")) + 0.44 * safe_int(row.get("FTA")))),
                    4,
                ) if (safe_int(row.get("FGA")) + 0.44 * safe_int(row.get("FTA"))) > 0 else 0.0,
                "usg_pct": safe_float(advanced_row.get("usagePercentage")),
                "ast_pct": safe_float(advanced_row.get("assistPercentage")),
                "reb_pct": safe_float(advanced_row.get("reboundPercentage")),
                "off_rating": safe_float(advanced_row.get("offensiveRating")),
                "def_rating": safe_float(advanced_row.get("defensiveRating")),
                "net_rating": safe_float(advanced_row.get("netRating")),
                "pace": safe_float(advanced_row.get("pace")),
                "possessions": safe_float(advanced_row.get("possessions")),
            }
        )

    if new_rows:
        player_game_stats_df = pd.concat(
            [player_game_stats_df, pd.DataFrame(new_rows, columns=PLAYER_GAME_STATS_COLUMNS)],
            ignore_index=True,
        )
    save_local_df(player_game_stats_df, "player_game_stats.csv", PLAYER_GAME_STATS_COLUMNS, "player_game_stats.csv")
    return player_game_stats_df


def main() -> None:
    # NBA 总入口：输入赛季与月份区间，逐场更新全部表。
    try:
        require_nba_api()

        parser = argparse.ArgumentParser(description="Update local NBA data")
        parser.add_argument(
            "--model-data-only",
            action="store_true",
            help="Only update games.csv and the regular-season team stats used by models",
        )
        parser.add_argument(
            "--reconcile-play-by-play-status",
            action="store_true",
            help="Reconcile play-by-play status flags with game IDs present in the CSV",
        )
        args = parser.parse_args()

        if args.reconcile_play_by_play_status:
            reconcile_play_by_play_status()
            return

        season_start_year = prompt_for_season()
        start_month = prompt_for_month("start")
        end_month = prompt_for_month("end")

        target_games_df = build_target_games_df(season_start_year, start_month, end_month)
        if target_games_df.empty:
            print_section("当前月份范围内没有可处理的已结束比赛")
            return

        status_df = load_status_df()
        status_df = ensure_status_rows(status_df, target_games_df)
        save_status_df(status_df)

        if args.model_data_only:
            update_model_team_stats_from_gamefinder(
                season_start_year,
                start_month,
                end_month,
                target_games_df,
                status_df,
            )
            print_section("本次 NBA 模型数据更新已全部结束")
            return

        players_df = load_local_df("players.csv", PLAYERS_COLUMNS, "players.csv")
        play_by_play_df = load_local_df("play_by_play.csv", PLAY_BY_PLAY_COLUMNS, "play_by_play.csv")
        team_game_stats_df = load_local_df("team_game_stats.csv", TEAM_GAME_STATS_COLUMNS, "team_game_stats.csv")
        player_game_stats_df = load_local_df("player_game_stats.csv", PLAYER_GAME_STATS_COLUMNS, "player_game_stats.csv")

        total_games = len(target_games_df)
        print_section(f"开始逐场更新 NBA 数据，共 {total_games} 场比赛")
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

            try:
                payloads = fetch_game_payloads(game_id)

                if safe_int(game_status["players_loaded"]) != 1:
                    players_df = process_players_for_game(
                        game_row,
                        players_df,
                        payloads["player_traditional_df"],
                    )
                    status_df = mark_stage_success(status_df, game_id, "players_loaded")
                    save_status_df(status_df)

                players_lookup = build_player_lookup(players_df)
                game_status = get_status_row(status_df, game_id)

                if safe_int(game_status["play_by_play_loaded"]) != 1:
                    play_by_play_df = process_play_by_play_for_game(
                        game_row,
                        play_by_play_df,
                        payloads["pbp_v3_df"],
                    )
                    status_df = mark_stage_success(status_df, game_id, "play_by_play_loaded")
                    save_status_df(status_df)

                game_status = get_status_row(status_df, game_id)
                if safe_int(game_status["team_loaded"]) != 1:
                    team_game_stats_df = process_team_game_stats_for_game(
                        game_row,
                        team_game_stats_df,
                        payloads["team_traditional_df"],
                        payloads["team_advanced_df"],
                    )
                    status_df = mark_stage_success(status_df, game_id, "team_loaded")
                    save_status_df(status_df)

                game_status = get_status_row(status_df, game_id)
                if safe_int(game_status["player_loaded"]) != 1:
                    player_game_stats_df = process_player_game_stats_for_game(
                        game_row,
                        player_game_stats_df,
                        payloads["player_traditional_df"],
                        payloads["player_advanced_df"],
                        players_lookup,
                    )
                    status_df = mark_stage_success(status_df, game_id, "player_loaded")
                    save_status_df(status_df)

                save_status_df(status_df)
                print_section(f"比赛 {game_id} 已完成全部更新")
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                status_df = mark_stage_error(status_df, game_id, error_message)
                save_status_df(status_df)
                print_section(f"比赛 {game_id} 更新失败，已记录错误：{error_message}")
                continue

        print_section("本次 NBA 数据更新已全部结束")
    except Exception as exc:
        print(f"Failed to run NBA update pipeline: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
