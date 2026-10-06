import os
import sys
from typing import Dict, List, Set, Tuple

import pandas as pd
import requests

MLB_BOXSCORE_URL_TEMPLATE = "https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
MLB_LIVE_FEED_URL_TEMPLATE = "https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
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

PITCHER_GAME_STATS_COLUMNS = [
    "game_id",
    "season",
    "player_id",
    "player_name",
    "team_id",
    "team_abbr",
    "opponent_team_id",
    "opponent_abbr",
    "is_home",
    "enter_inning",
    "ip",
    "outs",
    "bf",
    "pitches",
    "strikes",
    "h",
    "r",
    "er",
    "bb",
    "ibb",
    "so",
    "hr",
    "hbp",
    "wp",
    "win",
    "loss",
    "save",
    "hold",
    "blown_save",
]


def print_section(message):
    # 统一打印 pitcher 脚本的关键执行步骤。
    print(f"[pitcher] {message}")


def print_progress(current, total, label):
    # 批量读取比赛、球员字典、boxscore 或 live feed 时按固定步长显示进度。
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


def get_pitcher_game_stats_file_path() -> str:
    # 返回 pitcher_game_stats.csv 的完整路径。
    return os.path.join(get_data_dir(), "pitcher_game_stats.csv")


def initialize_csv(file_path: str, columns: List[str]) -> None:
    # 初始化空 CSV，保证后续读取和写入不会因为文件不存在而报错。
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print_section(f"开始初始化 {os.path.basename(file_path)}")
        pd.DataFrame(columns=columns).to_csv(file_path, index=False)
        print_section(f"结束初始化 {os.path.basename(file_path)}")


def load_games_df() -> pd.DataFrame:
    # 读取 games.csv，作为后续补投手逐场数据的比赛索引。
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


def load_pitcher_game_stats_df() -> pd.DataFrame:
    # 读取已有的 pitcher_game_stats.csv，用于判断哪些逐场记录已经存在。
    file_path = get_pitcher_game_stats_file_path()
    initialize_csv(file_path, PITCHER_GAME_STATS_COLUMNS)
    print_section("开始读取 pitcher_game_stats.csv")
    pitcher_df = pd.read_csv(file_path)

    if pitcher_df.empty:
        print_section("结束读取 pitcher_game_stats.csv，当前为空表")
        return pd.DataFrame(columns=PITCHER_GAME_STATS_COLUMNS)

    total_rows = len(pitcher_df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, "读取已有投手数据进度")

    for column in ["game_id", "player_id", "team_id"]:
        pitcher_df[column] = pitcher_df[column].astype(int)

    print_section(f"结束读取 pitcher_game_stats.csv，共加载 {total_rows} 条记录")
    return pitcher_df


def fetch_boxscore(game_id: int) -> dict:
    # 按比赛读取 boxscore，这里会拿到球队、投手和逐场投球统计。
    response = requests.get(
        MLB_BOXSCORE_URL_TEMPLATE.format(game_id=game_id),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_live_feed(game_id: int) -> dict:
    # 按比赛读取 live feed，用来计算投手是在第几局几出局时登板。
    response = requests.get(
        MLB_LIVE_FEED_URL_TEMPLATE.format(game_id=game_id),
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


def format_baseball_inning(inning: int, outs: int) -> str:
    # 按棒球格式表达局数，例如 3.2 表示第 3 局 2 出局时。
    return f"{int(inning)}.{int(outs)}"


def build_pitcher_enter_inning_map(live_feed: dict) -> Dict[int, str]:
    # 从逐打席数据中计算每名投手第一次出现在比赛里的登板时点。
    enter_map: Dict[int, str] = {}
    all_plays = live_feed.get("liveData", {}).get("plays", {}).get("allPlays", [])
    previous_outs_by_half: Dict[Tuple[int, str], int] = {}

    total_plays = len(all_plays)
    for index, play in enumerate(all_plays, start=1):
        print_progress(index, total_plays, "读取逐打席进度")

        matchup = play.get("matchup", {})
        pitcher_id = matchup.get("pitcher", {}).get("id")
        about = play.get("about", {})
        inning = about.get("inning")
        half_inning = about.get("halfInning")
        count = play.get("count", {})
        outs_after_play = safe_int(count.get("outs"))

        if pitcher_id is None or inning is None or half_inning is None:
            continue

        half_key = (int(inning), str(half_inning))
        start_outs = previous_outs_by_half.get(half_key, 0)

        if int(pitcher_id) not in enter_map:
            enter_map[int(pitcher_id)] = format_baseball_inning(int(inning), start_outs)

        previous_outs_by_half[half_key] = outs_after_play

    return enter_map


def build_pitcher_decision_flags(live_feed: dict) -> Dict[int, Dict[str, int]]:
    # 直接从 live feed 的官方 decisions 读取胜投、败投、救援成功。
    decision_flags: Dict[int, Dict[str, int]] = {}
    decisions = live_feed.get("liveData", {}).get("decisions", {})

    winner_id = decisions.get("winner", {}).get("id")
    loser_id = decisions.get("loser", {}).get("id")
    save_id = decisions.get("save", {}).get("id")

    for pitcher_id, key in [
        (winner_id, "win"),
        (loser_id, "loss"),
        (save_id, "save"),
    ]:
        if pitcher_id is None:
            continue

        pitcher_id = int(pitcher_id)
        if pitcher_id not in decision_flags:
            decision_flags[pitcher_id] = {
                "win": 0,
                "loss": 0,
                "save": 0,
            }
        decision_flags[pitcher_id][key] = 1

    return decision_flags


def extract_pitcher_rows_for_team(
    game_row: pd.Series,
    team_data: dict,
    team_abbr_fallback: str,
    opponent_team_id: int,
    opponent_abbr: str,
    is_home: int,
    mlb_to_player_info: Dict[int, Dict[str, object]],
    enter_inning_map: Dict[int, str],
    decision_flags: Dict[int, Dict[str, int]],
    existing_keys: Set[Tuple[int, int, int]],
) -> List[dict]:
    # 从单支球队的 boxscore 中提取所有投手的逐场统计。
    team = team_data.get("team", {})
    team_id = team.get("id")
    team_abbr = resolve_team_abbr(team_data, team_abbr_fallback)
    pitchers = team_data.get("pitchers", [])
    players = team_data.get("players", {})

    if team_id is None or team_abbr is None:
        return []

    rows = []
    skipped_missing_players = 0
    total_pitchers = len(pitchers)

    for index, pitcher_mlb_id in enumerate(pitchers, start=1):
        print_progress(index, total_pitchers, f"读取球队 {team_abbr} 投手进度")

        player_payload = players.get(f"ID{pitcher_mlb_id}", {})
        stats = player_payload.get("stats", {}).get("pitching", {})
        player_info = mlb_to_player_info.get(int(pitcher_mlb_id))

        if player_info is None:
            skipped_missing_players += 1
            continue

        player_id = int(player_info["player_id"])
        player_name = str(player_info["player_name"])
        unique_key = (int(game_row["game_id"]), player_id, int(team_id))
        note_text = str(stats.get("note", ""))
        pitcher_decision = decision_flags.get(int(pitcher_mlb_id), {})

        if unique_key in existing_keys:
            continue

        # 只保留真正投过球的投手，避免把未投球但在名单里的球员写进去。
        outs = safe_int(stats.get("outs"))
        pitches = safe_int(stats.get("numberOfPitches"))
        if outs == 0 and pitches == 0:
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
            "enter_inning": enter_inning_map.get(int(pitcher_mlb_id)),
            "ip": str(stats.get("inningsPitched", "0.0")),
            "outs": outs,
            "bf": safe_int(stats.get("battersFaced")),
            "pitches": pitches,
            "strikes": safe_int(stats.get("strikes")),
            "h": safe_int(stats.get("hits")),
            "r": safe_int(stats.get("runs")),
            "er": safe_int(stats.get("earnedRuns")),
            "bb": safe_int(stats.get("baseOnBalls")),
            "ibb": safe_int(stats.get("intentionalWalks")),
            "so": safe_int(stats.get("strikeOuts")),
            "hr": safe_int(stats.get("homeRuns")),
            "hbp": safe_int(stats.get("hitByPitch")),
            "wp": safe_int(stats.get("wildPitches")),
            "win": int(pitcher_decision.get("win", 0)),
            "loss": int(pitcher_decision.get("loss", 0)),
            "save": int(pitcher_decision.get("save", 0)),
            "hold": 1 if "H," in note_text or note_text.startswith("H ") else 0,
            "blown_save": 1 if "BS," in note_text or note_text.startswith("BS ") else 0,
        }

        if row["enter_inning"] is None:
            # 如果逐打席里没算出登板时点，就至少回退成 1.0，避免空值写入。
            row["enter_inning"] = "1.0"

        rows.append(row)
        existing_keys.add(unique_key)

    if skipped_missing_players > 0:
        print_section(
            f"球队 {team_abbr} 有 {skipped_missing_players} 名投手未在 players.csv 中找到，已跳过"
        )

    return rows


def build_pitcher_game_stats(
    games_df: pd.DataFrame,
    players_df: pd.DataFrame,
    pitcher_df: pd.DataFrame,
) -> pd.DataFrame:
    # 以 games.csv 为索引，逐场补齐 pitcher_game_stats.csv。
    mlb_to_player_info = {
        int(row["mlb_id"]): {
            "player_id": int(row["player_id"]),
            "player_name": row["name"],
        }
        for _, row in players_df.iterrows()
    }

    existing_keys = set()
    if not pitcher_df.empty:
        existing_keys = set(
            zip(
                pitcher_df["game_id"].astype(int),
                pitcher_df["player_id"].astype(int),
                pitcher_df["team_id"].astype(int),
            )
        )

    all_new_rows = []
    total_games = len(games_df)
    print_section(f"开始读取比赛数据，共 {total_games} 场")

    for index, (_, game_row) in enumerate(games_df.iterrows(), start=1):
        print_progress(index, total_games, "读取比赛进度")

        game_id = int(game_row["game_id"])
        print_section(f"开始读取比赛 {game_id} 的 boxscore")
        boxscore = fetch_boxscore(game_id)
        print_section(f"结束读取比赛 {game_id} 的 boxscore")

        print_section(f"开始读取比赛 {game_id} 的 live feed")
        live_feed = fetch_live_feed(game_id)
        enter_inning_map = build_pitcher_enter_inning_map(live_feed)
        decision_flags = build_pitcher_decision_flags(live_feed)
        print_section(f"结束读取比赛 {game_id} 的 live feed，共识别 {len(enter_inning_map)} 名投手登板时点")

        home_data = boxscore.get("teams", {}).get("home", {})
        away_data = boxscore.get("teams", {}).get("away", {})

        print_section(f"开始读取比赛 {game_id} 的主队投手数据")
        home_rows = extract_pitcher_rows_for_team(
            game_row=game_row,
            team_data=home_data,
            team_abbr_fallback=str(game_row["home_abbr"]),
            opponent_team_id=int(game_row["away_team_id"]),
            opponent_abbr=str(game_row["away_abbr"]),
            is_home=1,
            mlb_to_player_info=mlb_to_player_info,
            enter_inning_map=enter_inning_map,
            decision_flags=decision_flags,
            existing_keys=existing_keys,
        )
        print_section(f"结束读取比赛 {game_id} 的主队投手数据，共新增 {len(home_rows)} 条")

        print_section(f"开始读取比赛 {game_id} 的客队投手数据")
        away_rows = extract_pitcher_rows_for_team(
            game_row=game_row,
            team_data=away_data,
            team_abbr_fallback=str(game_row["away_abbr"]),
            opponent_team_id=int(game_row["home_team_id"]),
            opponent_abbr=str(game_row["home_abbr"]),
            is_home=0,
            mlb_to_player_info=mlb_to_player_info,
            enter_inning_map=enter_inning_map,
            decision_flags=decision_flags,
            existing_keys=existing_keys,
        )
        print_section(f"结束读取比赛 {game_id} 的客队投手数据，共新增 {len(away_rows)} 条")

        all_new_rows.extend(home_rows)
        all_new_rows.extend(away_rows)

    print_section(f"结束读取比赛数据，共新增 {len(all_new_rows)} 条投手逐场记录")

    if not all_new_rows:
        return pitcher_df

    new_pitcher_df = pd.DataFrame(all_new_rows, columns=PITCHER_GAME_STATS_COLUMNS)
    pitcher_df = pd.concat([pitcher_df, new_pitcher_df], ignore_index=True)
    pitcher_df = pitcher_df.drop_duplicates(
        subset=["game_id", "player_id", "team_id"],
        keep="first",
    )
    pitcher_df = pitcher_df.sort_values(
        by=["season", "game_id", "team_id", "outs", "player_id"],
        ascending=[False, False, True, False, True],
    )
    return pitcher_df


def save_pitcher_game_stats_df(pitcher_df: pd.DataFrame) -> None:
    # 将更新后的投手逐场统计写回 pitcher_game_stats.csv。
    print_section("开始写入 pitcher_game_stats.csv")
    pitcher_df = pitcher_df[PITCHER_GAME_STATS_COLUMNS]
    pitcher_df.to_csv(get_pitcher_game_stats_file_path(), index=False)
    print_section(f"结束写入 pitcher_game_stats.csv，共 {len(pitcher_df)} 条记录")


def main() -> None:
    # 主入口：依赖现有 games.csv 和 players.csv，补齐 pitcher_game_stats.csv。
    try:
        games_df = load_games_df()
        players_df = load_players_df()
        pitcher_df = load_pitcher_game_stats_df()
        pitcher_df = build_pitcher_game_stats(games_df, players_df, pitcher_df)
        save_pitcher_game_stats_df(pitcher_df)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Initialization failed: {exc}")
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Failed to fetch MLB pitcher game stats: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Failed to update pitcher game stats: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
