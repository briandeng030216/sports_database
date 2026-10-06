import os
import sys
from typing import List, Set, Tuple

import pandas as pd
import requests

MLB_BOXSCORE_URL_TEMPLATE = "https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
PROGRESS_STEP = 10

TEAM_GAME_STATS_COLUMNS = [
    "game_id",
    "season",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "team_win",
    "ab",
    "r",
    "h",
    "doubles",
    "triples",
    "hr",
    "rbi",
    "bb",
    "ibb",
    "so",
    "hbp",
    "sf",
    "sh",
    "gidp",
    "sb",
    "cs",
    "lob",
    "ip",
    "outs",
    "h_allowed",
    "r_allowed",
    "er",
    "bb_allowed",
    "ibb_allowed",
    "so_pitched",
    "hr_allowed",
    "hbp_allowed",
    "wp",
    "pitches",
    "strikes",
    "errors",
    "dp",
]


def print_section(message):
    # 统一打印 team 脚本的关键执行步骤。
    print(f"[team] {message}")


def print_progress(current, total, label):
    # 批量读取比赛索引、已有数据或 boxscore 时按固定步长显示进度。
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


def get_team_game_stats_file_path() -> str:
    # 返回 team_game_stats.csv 的完整路径。
    return os.path.join(get_data_dir(), "team_game_stats.csv")


def initialize_csv(file_path: str, columns: List[str]) -> None:
    # 初始化空 CSV，保证后续读取和写入不会因为文件不存在而报错。
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print_section(f"开始初始化 {os.path.basename(file_path)}")
        pd.DataFrame(columns=columns).to_csv(file_path, index=False)
        print_section(f"结束初始化 {os.path.basename(file_path)}")


def load_games_df() -> pd.DataFrame:
    # 读取 games.csv，作为后续补球队逐场数据的比赛索引。
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


def load_team_game_stats_df() -> pd.DataFrame:
    # 读取已有的 team_game_stats.csv，用于判断哪些逐场记录已经存在。
    file_path = get_team_game_stats_file_path()
    initialize_csv(file_path, TEAM_GAME_STATS_COLUMNS)
    print_section("开始读取 team_game_stats.csv")
    team_df = pd.read_csv(file_path)

    if team_df.empty:
        print_section("结束读取 team_game_stats.csv，当前为空表")
        return pd.DataFrame(columns=TEAM_GAME_STATS_COLUMNS)

    total_rows = len(team_df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, "读取已有球队数据进度")

    for column in ["game_id", "team_id"]:
        team_df[column] = team_df[column].astype(int)

    print_section(f"结束读取 team_game_stats.csv，共加载 {total_rows} 条记录")
    return team_df


def fetch_boxscore(game_id: int) -> dict:
    # 按比赛读取 boxscore，这里会拿到球队级别的 batting、pitching、fielding 汇总。
    response = requests.get(
        MLB_BOXSCORE_URL_TEMPLATE.format(game_id=game_id),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def safe_int(value) -> int:
    # 将接口里的空值统一转成 0，避免写入严格 schema 时出现缺失。
    if value is None or pd.isna(value) or value == "":
        return 0
    return int(value)


def safe_text(value) -> str:
    # 将空文本统一转成空字符串。
    if value is None or pd.isna(value):
        return ""
    return str(value)


def resolve_team_abbr(team_data: dict, fallback_abbr: str) -> str:
    # 先用 boxscore 里的缩写，缺失时回退到 games.csv 中已有的缩写。
    team = team_data.get("team", {})
    return team.get("abbreviation") or fallback_abbr


def innings_to_outs(ip_value) -> int:
    # 将棒球格式局数转换成出局数，例如 5.2 -> 17。
    ip_text = safe_text(ip_value).strip()
    if ip_text == "":
        return 0

    if "." not in ip_text:
        return safe_int(ip_text) * 3

    inning_text, outs_text = ip_text.split(".", 1)
    return safe_int(inning_text) * 3 + safe_int(outs_text)


def build_team_row(
    game_row: pd.Series,
    team_data: dict,
    fallback_abbr: str,
    opponent_team_id: int,
    opponent_abbr: str,
    is_home: int,
    team_win: int,
) -> dict:
    # 将单支球队的 boxscore 汇总整理成一行球队逐场记录。
    team = team_data.get("team", {})
    batting = team_data.get("teamStats", {}).get("batting", {})
    pitching = team_data.get("teamStats", {}).get("pitching", {})
    fielding = team_data.get("teamStats", {}).get("fielding", {})

    team_id = team.get("id")
    team_abbr = resolve_team_abbr(team_data, fallback_abbr)
    ip_value = safe_text(pitching.get("inningsPitched"))

    return {
        "game_id": int(game_row["game_id"]),
        "season": int(game_row["season"]),
        "team_id": safe_int(team_id),
        "team_abbr": team_abbr,
        "opponent_team_id": int(opponent_team_id),
        "opponent_abbr": opponent_abbr,
        "is_home": int(is_home),
        "team_win": int(team_win),
        "ab": safe_int(batting.get("atBats")),
        "r": safe_int(batting.get("runs")),
        "h": safe_int(batting.get("hits")),
        "doubles": safe_int(batting.get("doubles")),
        "triples": safe_int(batting.get("triples")),
        "hr": safe_int(batting.get("homeRuns")),
        "rbi": safe_int(batting.get("rbi")),
        "bb": safe_int(batting.get("baseOnBalls")),
        "ibb": safe_int(batting.get("intentionalWalks")),
        "so": safe_int(batting.get("strikeOuts")),
        "hbp": safe_int(batting.get("hitByPitch")),
        "sf": safe_int(batting.get("sacFlies")),
        "sh": safe_int(batting.get("sacBunts")),
        "gidp": safe_int(batting.get("groundIntoDoublePlay")),
        "sb": safe_int(batting.get("stolenBases")),
        "cs": safe_int(batting.get("caughtStealing")),
        "lob": safe_int(batting.get("leftOnBase")),
        "ip": ip_value,
        "outs": innings_to_outs(ip_value),
        "h_allowed": safe_int(pitching.get("hits")),
        "r_allowed": safe_int(pitching.get("runs")),
        "er": safe_int(pitching.get("earnedRuns")),
        "bb_allowed": safe_int(pitching.get("baseOnBalls")),
        "ibb_allowed": safe_int(pitching.get("intentionalWalks")),
        "so_pitched": safe_int(pitching.get("strikeOuts")),
        "hr_allowed": safe_int(pitching.get("homeRuns")),
        "hbp_allowed": safe_int(pitching.get("hitByPitch")),
        "wp": safe_int(pitching.get("wildPitches")),
        "pitches": safe_int(pitching.get("numberOfPitches")),
        "strikes": safe_int(pitching.get("strikes")),
        "errors": safe_int(fielding.get("errors")),
        "dp": safe_int(fielding.get("doublePlays")),
    }


def extract_team_rows_for_game(
    game_row: pd.Series,
    boxscore: dict,
    existing_keys: Set[Tuple[int, int]],
) -> List[dict]:
    # 从单场比赛的 boxscore 中提取主客队两行球队逐场统计。
    teams = boxscore.get("teams", {})
    home_data = teams.get("home", {})
    away_data = teams.get("away", {})

    home_team_id = safe_int(home_data.get("team", {}).get("id") or game_row["home_team_id"])
    away_team_id = safe_int(away_data.get("team", {}).get("id") or game_row["away_team_id"])
    home_abbr = resolve_team_abbr(home_data, safe_text(game_row["home_abbr"]))
    away_abbr = resolve_team_abbr(away_data, safe_text(game_row["away_abbr"]))
    home_win = safe_int(game_row["home_win"])

    rows = []
    candidate_rows = [
        build_team_row(
            game_row=game_row,
            team_data=home_data,
            fallback_abbr=safe_text(game_row["home_abbr"]),
            opponent_team_id=away_team_id,
            opponent_abbr=away_abbr,
            is_home=1,
            team_win=home_win,
        ),
        build_team_row(
            game_row=game_row,
            team_data=away_data,
            fallback_abbr=safe_text(game_row["away_abbr"]),
            opponent_team_id=home_team_id,
            opponent_abbr=home_abbr,
            is_home=0,
            team_win=1 - home_win,
        ),
    ]

    total_teams = len(candidate_rows)
    for index, row in enumerate(candidate_rows, start=1):
        print_progress(index, total_teams, f"读取比赛 {int(game_row['game_id'])} 球队进度")
        unique_key = (int(row["game_id"]), int(row["team_id"]))
        if unique_key in existing_keys:
            continue
        existing_keys.add(unique_key)
        rows.append(row)

    return rows


def build_team_game_stats(games_df: pd.DataFrame, team_df: pd.DataFrame) -> pd.DataFrame:
    # 以 games.csv 为索引，逐场补齐 team_game_stats.csv。
    existing_keys: Set[Tuple[int, int]] = set()
    if not team_df.empty:
        existing_keys = set(
            zip(team_df["game_id"].astype(int), team_df["team_id"].astype(int))
        )

    all_new_rows = []
    total_games = len(games_df)
    print_section(f"开始读取球队逐场数据，共 {total_games} 场比赛")

    for index, (_, game_row) in enumerate(games_df.iterrows(), start=1):
        print_progress(index, total_games, "读取比赛 boxscore 进度")
        game_id = int(game_row["game_id"])
        boxscore = fetch_boxscore(game_id)
        new_game_rows = extract_team_rows_for_game(game_row, boxscore, existing_keys)
        print_section(f"结束读取比赛 {game_id} 球队数据，共新增 {len(new_game_rows)} 条")
        all_new_rows.extend(new_game_rows)

    print_section(f"结束读取球队逐场数据，共新增 {len(all_new_rows)} 条记录")

    if not all_new_rows:
        return team_df

    new_team_df = pd.DataFrame(all_new_rows, columns=TEAM_GAME_STATS_COLUMNS)
    team_df = pd.concat([team_df, new_team_df], ignore_index=True)
    team_df = team_df.drop_duplicates(subset=["game_id", "team_id"], keep="first")
    team_df = team_df.sort_values(
        by=["season", "game_id", "is_home"],
        ascending=[False, False, False],
    )
    return team_df


def save_team_game_stats_df(team_df: pd.DataFrame) -> None:
    # 将更新后的球队逐场数据写回 team_game_stats.csv。
    print_section("开始写入 team_game_stats.csv")
    team_df = team_df[TEAM_GAME_STATS_COLUMNS]
    team_df.to_csv(get_team_game_stats_file_path(), index=False)
    print_section(f"结束写入 team_game_stats.csv，共 {len(team_df)} 条记录")


def main() -> None:
    # 主入口：依赖 games.csv，逐场抓取并补齐 team_game_stats.csv。
    try:
        games_df = load_games_df()
        team_df = load_team_game_stats_df()
        team_df = build_team_game_stats(games_df, team_df)
        save_team_game_stats_df(team_df)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Initialization failed: {exc}")
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Failed to fetch MLB team game stats: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Failed to update team_game_stats.csv: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
