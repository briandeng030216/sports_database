import os
import sys
from typing import Dict, List, Set, Tuple

import pandas as pd
import requests

MLB_BOXSCORE_URL_TEMPLATE = "https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
PROGRESS_STEP = 10

PLAYERS_COLUMNS = [
    "player_id",
    "mlb_id",
    "fangraphs_id",
    "name",
    "birth_date",
    "primary_position",
    "bats",
    "throws",
]

BATTER_GAME_STATS_COLUMNS = [
    "game_id",
    "season",
    "player_id",
    "player_name",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "batting_order",
    "pa",
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
]


def print_section(message):
    # 统一打印 batter 脚本的关键执行步骤。
    print(f"[batter] {message}")


def print_progress(current, total, label):
    # 批量读取比赛、球员字典或 boxscore 时按固定步长显示进度。
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


def get_players_file_path() -> str:
    # 返回 players.csv 的完整路径。
    return os.path.join(get_data_dir(), "players.csv")


def get_batter_game_stats_file_path() -> str:
    # 返回 batter_game_stats.csv 的完整路径。
    return os.path.join(get_data_dir(), "batter_game_stats.csv")


def initialize_csv(file_path: str, columns: List[str]) -> None:
    # 初始化空 CSV，保证后续读取和写入不会因为文件不存在而报错。
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print_section(f"开始初始化 {os.path.basename(file_path)}")
        pd.DataFrame(columns=columns).to_csv(file_path, index=False)
        print_section(f"结束初始化 {os.path.basename(file_path)}")


def load_games_df() -> pd.DataFrame:
    # 读取 games.csv，作为后续补打者逐场数据的比赛索引。
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


def load_players_df() -> pd.DataFrame:
    # 读取 players.csv，建立 mlb_id -> (player_id, player_name) 的内部映射。
    file_path = get_players_file_path()
    initialize_csv(file_path, PLAYERS_COLUMNS)
    print_section("开始读取 players.csv")
    players_df = pd.read_csv(file_path)

    if players_df.empty:
        raise ValueError("players.csv is empty. Please populate players.csv first.")

    total_rows = len(players_df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, "读取球员字典进度")

    players_df["player_id"] = players_df["player_id"].astype(int)
    players_df["mlb_id"] = players_df["mlb_id"].astype(int)
    print_section(f"结束读取 players.csv，共加载 {total_rows} 名球员")
    return players_df


def load_batter_game_stats_df() -> pd.DataFrame:
    # 读取已有的 batter_game_stats.csv，用于判断哪些逐场记录已经存在。
    file_path = get_batter_game_stats_file_path()
    initialize_csv(file_path, BATTER_GAME_STATS_COLUMNS)
    print_section("开始读取 batter_game_stats.csv")
    batter_df = pd.read_csv(file_path)

    if batter_df.empty:
        print_section("结束读取 batter_game_stats.csv，当前为空表")
        return pd.DataFrame(columns=BATTER_GAME_STATS_COLUMNS)

    total_rows = len(batter_df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, "读取已有打者数据进度")

    for column in ["game_id", "player_id", "team_id"]:
        batter_df[column] = batter_df[column].astype(int)

    print_section(f"结束读取 batter_game_stats.csv，共加载 {total_rows} 条记录")
    return batter_df


def fetch_boxscore(game_id: int) -> dict:
    # 按比赛读取 boxscore，这里会拿到球队、打者和逐场统计明细。
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


def resolve_team_abbr(team_data: dict, fallback_abbr: str) -> str:
    # 先用 boxscore 里的缩写，缺失时回退到 games.csv 中已有的缩写。
    team = team_data.get("team", {})
    return team.get("abbreviation") or fallback_abbr


def extract_batter_rows_for_team(
    game_row: pd.Series,
    team_data: dict,
    team_abbr_fallback: str,
    opponent_team_id: int,
    opponent_abbr: str,
    is_home: int,
    mlb_to_player_info: Dict[int, Dict[str, object]],
    existing_keys: Set[Tuple[int, int, int]],
) -> List[dict]:
    # 从单支球队的 boxscore 中提取所有打者的逐场统计。
    team = team_data.get("team", {})
    team_id = team.get("id")
    team_abbr = resolve_team_abbr(team_data, team_abbr_fallback)
    batters = team_data.get("batters", [])
    players = team_data.get("players", {})

    if team_id is None or team_abbr is None:
        return []

    rows = []
    skipped_missing_players = 0
    total_batters = len(batters)

    for index, batter_mlb_id in enumerate(batters, start=1):
        print_progress(index, total_batters, f"读取球队 {team_abbr} 打者进度")

        player_payload = players.get(f"ID{batter_mlb_id}", {})
        stats = player_payload.get("stats", {}).get("batting", {})
        batting_order = player_payload.get("battingOrder")
        player_info = mlb_to_player_info.get(int(batter_mlb_id))

        if player_info is None:
            skipped_missing_players += 1
            continue

        if batting_order is None:
            continue

        player_id = int(player_info["player_id"])
        player_name = str(player_info["player_name"])

        unique_key = (int(game_row["game_id"]), player_id, int(team_id))
        if unique_key in existing_keys:
            continue

        row = {
            "game_id": int(game_row["game_id"]),
            "season": int(game_row["season"]),
            "player_id": player_id,
            "player_name": player_name,
            "team_id": int(team_id),
            "team_abbr": team_abbr,
            "opponent_team_id": int(opponent_team_id),
            "opponent_abbr": opponent_abbr,
            "is_home": int(is_home),
            "batting_order": int(str(batting_order)[0]),
            "pa": safe_int(stats.get("plateAppearances")),
            "ab": safe_int(stats.get("atBats")),
            "r": safe_int(stats.get("runs")),
            "h": safe_int(stats.get("hits")),
            "doubles": safe_int(stats.get("doubles")),
            "triples": safe_int(stats.get("triples")),
            "hr": safe_int(stats.get("homeRuns")),
            "rbi": safe_int(stats.get("rbi")),
            "bb": safe_int(stats.get("baseOnBalls")),
            "ibb": safe_int(stats.get("intentionalWalks")),
            "so": safe_int(stats.get("strikeOuts")),
            "hbp": safe_int(stats.get("hitByPitch")),
            "sf": safe_int(stats.get("sacFlies")),
            "sh": safe_int(stats.get("sacBunts")),
            "gidp": safe_int(stats.get("groundIntoDoublePlay")),
            "sb": safe_int(stats.get("stolenBases")),
            "cs": safe_int(stats.get("caughtStealing")),
        }
        rows.append(row)
        existing_keys.add(unique_key)

    if skipped_missing_players > 0:
        print_section(
            f"球队 {team_abbr} 有 {skipped_missing_players} 名打者未在 players.csv 中找到，已跳过"
        )

    return rows


def build_batter_game_stats(
    games_df: pd.DataFrame,
    players_df: pd.DataFrame,
    batter_df: pd.DataFrame,
) -> pd.DataFrame:
    # 以 games.csv 为索引，逐场补齐 batter_game_stats.csv。
    mlb_to_player_info = {
        int(row["mlb_id"]): {
            "player_id": int(row["player_id"]),
            "player_name": row["name"],
        }
        for _, row in players_df.iterrows()
    }

    existing_keys = set()
    if not batter_df.empty:
        existing_keys = set(
            zip(
                batter_df["game_id"].astype(int),
                batter_df["player_id"].astype(int),
                batter_df["team_id"].astype(int),
            )
        )

    all_new_rows = []
    total_games = len(games_df)
    print_section(f"开始读取比赛 boxscore，共 {total_games} 场")

    for index, (_, game_row) in enumerate(games_df.iterrows(), start=1):
        print_progress(index, total_games, "读取比赛 boxscore 进度")

        game_id = int(game_row["game_id"])
        boxscore = fetch_boxscore(game_id)

        home_data = boxscore.get("teams", {}).get("home", {})
        away_data = boxscore.get("teams", {}).get("away", {})

        print_section(f"开始读取比赛 {game_id} 的主队打者数据")
        home_rows = extract_batter_rows_for_team(
            game_row=game_row,
            team_data=home_data,
            team_abbr_fallback=str(game_row["home_abbr"]),
            opponent_team_id=int(game_row["away_team_id"]),
            opponent_abbr=str(game_row["away_abbr"]),
            is_home=1,
            mlb_to_player_info=mlb_to_player_info,
            existing_keys=existing_keys,
        )
        print_section(f"结束读取比赛 {game_id} 的主队打者数据，共新增 {len(home_rows)} 条")

        print_section(f"开始读取比赛 {game_id} 的客队打者数据")
        away_rows = extract_batter_rows_for_team(
            game_row=game_row,
            team_data=away_data,
            team_abbr_fallback=str(game_row["away_abbr"]),
            opponent_team_id=int(game_row["home_team_id"]),
            opponent_abbr=str(game_row["home_abbr"]),
            is_home=0,
            mlb_to_player_info=mlb_to_player_info,
            existing_keys=existing_keys,
        )
        print_section(f"结束读取比赛 {game_id} 的客队打者数据，共新增 {len(away_rows)} 条")

        all_new_rows.extend(home_rows)
        all_new_rows.extend(away_rows)

    print_section(f"结束读取比赛 boxscore，共新增 {len(all_new_rows)} 条打者逐场记录")

    if not all_new_rows:
        return batter_df

    new_batter_df = pd.DataFrame(all_new_rows, columns=BATTER_GAME_STATS_COLUMNS)
    batter_df = pd.concat([batter_df, new_batter_df], ignore_index=True)
    batter_df = batter_df.drop_duplicates(
        subset=["game_id", "player_id", "team_id"],
        keep="first",
    )
    batter_df = batter_df.sort_values(
        by=["season", "game_id", "team_id", "batting_order", "player_id"],
        ascending=[False, False, True, True, True],
    )
    return batter_df


def save_batter_game_stats_df(batter_df: pd.DataFrame) -> None:
    # 将更新后的打者逐场统计写回 batter_game_stats.csv。
    print_section("开始写入 batter_game_stats.csv")
    batter_df = batter_df[BATTER_GAME_STATS_COLUMNS]
    batter_df.to_csv(get_batter_game_stats_file_path(), index=False)
    print_section(f"结束写入 batter_game_stats.csv，共 {len(batter_df)} 条记录")


def main() -> None:
    # 主入口：依赖现有 games.csv 和 players.csv，补齐 batter_game_stats.csv。
    try:
        games_df = load_games_df()
        players_df = load_players_df()
        batter_df = load_batter_game_stats_df()
        batter_df = build_batter_game_stats(games_df, players_df, batter_df)
        save_batter_game_stats_df(batter_df)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Initialization failed: {exc}")
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Failed to fetch MLB batter game stats: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Failed to update batter game stats: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
