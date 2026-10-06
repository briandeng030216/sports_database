import os
import sys
from typing import Dict, List, Optional, Set

import pandas as pd
import requests
from pybaseball import playerid_reverse_lookup

MLB_LIVE_FEED_URL_TEMPLATE = "https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
MLB_PERSON_URL_TEMPLATE = "https://statsapi.mlb.com/api/v1/people/{mlb_id}"
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


def print_section(message):
    # 统一打印 players 脚本的关键执行步骤。
    print(f"[players] {message}")


def print_progress(current, total, label):
    # 批量读取比赛、逐球数据、球员主信息或 Fangraphs 映射时按固定步长打印进度。
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


def initialize_players_table() -> None:
    # 初始化空的 players.csv，保证后续读取和写入不会因为文件不存在而报错。
    file_path = get_players_file_path()
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print_section("开始初始化 players.csv")
        pd.DataFrame(columns=PLAYERS_COLUMNS).to_csv(file_path, index=False)
        print_section("结束初始化 players.csv")


def load_games_df() -> pd.DataFrame:
    # 读取 games.csv，作为后续逐场抓取 pitch_by_pitch 的比赛索引。
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
    # 读取现有 players.csv，用于判断哪些球员已经分配过内部 player_id。
    initialize_players_table()
    file_path = get_players_file_path()
    print_section("开始读取 players.csv")
    players_df = pd.read_csv(file_path)

    if players_df.empty:
        print_section("结束读取 players.csv，当前为空表")
        return pd.DataFrame(columns=PLAYERS_COLUMNS)

    total_rows = len(players_df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, "读取已有球员进度")

    players_df["player_id"] = players_df["player_id"].astype(int)
    players_df["mlb_id"] = players_df["mlb_id"].astype(int)
    players_df["fangraphs_id"] = pd.to_numeric(
        players_df["fangraphs_id"],
        errors="coerce",
    ).astype("Int64")
    print_section(f"结束读取 players.csv，共加载 {total_rows} 名球员")
    return players_df


def fetch_live_feed(game_id: int) -> dict:
    # 按比赛读取 live feed，这里包含逐球级别的打者和投手信息。
    response = requests.get(
        MLB_LIVE_FEED_URL_TEMPLATE.format(game_id=game_id),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def extract_player_ids_from_live_feed(live_feed: dict) -> Set[int]:
    # 从单场比赛的逐球数据里提取所有实际出现在 matchup 中的 batter / pitcher。
    player_ids = set()
    all_plays = live_feed.get("liveData", {}).get("plays", {}).get("allPlays", [])

    for play in all_plays:
        matchup = play.get("matchup", {})
        batter_id = matchup.get("batter", {}).get("id")
        pitcher_id = matchup.get("pitcher", {}).get("id")

        if batter_id is not None:
            player_ids.add(int(batter_id))
        if pitcher_id is not None:
            player_ids.add(int(pitcher_id))

    return player_ids


def collect_missing_mlb_ids(games_df: pd.DataFrame, players_df: pd.DataFrame) -> Set[int]:
    # 按 games.csv 逐场读取逐球数据，汇总所有 batter / pitcher 的 MLB ID。
    known_mlb_ids = set()
    if not players_df.empty:
        known_mlb_ids = set(players_df["mlb_id"].astype(int))

    total_games = len(games_df)
    raw_pitch_matchups = 0
    all_pitch_player_ids = set()

    print_section(f"开始按比赛读取 pitch_by_pitch，共 {total_games} 场")

    for index, (_, game_row) in enumerate(games_df.iterrows(), start=1):
        print_progress(index, total_games, "读取逐球比赛进度")

        game_id = int(game_row["game_id"])
        live_feed = fetch_live_feed(game_id)
        all_plays = live_feed.get("liveData", {}).get("plays", {}).get("allPlays", [])
        raw_pitch_matchups += len(all_plays)
        all_pitch_player_ids.update(extract_player_ids_from_live_feed(live_feed))

    missing_mlb_ids = all_pitch_player_ids.difference(known_mlb_ids)

    print_section(
        f"结束按比赛读取 pitch_by_pitch，累计扫描 {raw_pitch_matchups} 个打席对位，"
        f"去重后共有 {len(all_pitch_player_ids)} 名投打球员，"
        f"其中 {len(missing_mlb_ids)} 名需要新增"
    )
    return missing_mlb_ids


def fetch_person(mlb_id: int) -> Optional[dict]:
    # 读取单个球员的基础身份信息，用来构造 players.csv 的一行记录。
    response = requests.get(
        MLB_PERSON_URL_TEMPLATE.format(mlb_id=mlb_id),
        timeout=30,
    )
    response.raise_for_status()
    people = response.json().get("people", [])
    return people[0] if people else None


def fetch_fangraphs_map(mlb_ids: Set[int]) -> Dict[int, int]:
    # 用 pybaseball 批量反查 Fangraphs ID，作为 players.csv 的外部映射字段。
    if not mlb_ids:
        return {}

    sorted_ids = sorted(mlb_ids)
    total_ids = len(sorted_ids)
    print_section(f"开始读取 Fangraphs 映射，共 {total_ids} 名球员")

    lookup_df = playerid_reverse_lookup(
        [str(player_id) for player_id in sorted_ids],
        key_type="mlbam",
    )
    if lookup_df.empty:
        print_section("结束读取 Fangraphs 映射，未查到可用结果")
        return {}

    fangraphs_map = {}
    total_rows = len(lookup_df)

    for index, (_, row) in enumerate(lookup_df.iterrows(), start=1):
        print_progress(index, total_rows, "读取 Fangraphs 映射进度")

        mlbam_value = row.get("key_mlbam")
        fangraphs_value = row.get("key_fangraphs")

        if pd.isna(mlbam_value) or pd.isna(fangraphs_value):
            continue

        fangraphs_map[int(mlbam_value)] = int(fangraphs_value)

    print_section(f"结束读取 Fangraphs 映射，共得到 {len(fangraphs_map)} 条映射")
    return fangraphs_map


def get_next_player_id(players_df: pd.DataFrame) -> int:
    # 获取下一个可分配的内部 player_id，空表时从 0 开始。
    if players_df.empty:
        return 0
    return int(players_df["player_id"].max()) + 1


def build_player_core_record(
    mlb_id: int,
    next_player_id: int,
) -> Optional[dict]:
    # 先只根据 MLB 官方接口构造球员主信息，fangraphs_id 后续再补。
    person = fetch_person(mlb_id)
    if not person:
        return None

    name = person.get("fullName")
    birth_date = person.get("birthDate")
    primary_position = person.get("primaryPosition", {}).get("abbreviation")
    bats = person.get("batSide", {}).get("code")
    throws = person.get("pitchHand", {}).get("code")

    required_values = [name, birth_date, primary_position, bats, throws]
    if any(value is None for value in required_values):
        return None

    return {
        "player_id": next_player_id,
        "mlb_id": mlb_id,
        "fangraphs_id": None,
        "name": name,
        "birth_date": birth_date,
        "primary_position": primary_position,
        "bats": bats,
        "throws": throws,
    }


def append_new_players_from_mlb(
    players_df: pd.DataFrame,
    missing_mlb_ids: Set[int],
) -> pd.DataFrame:
    # 先根据缺失的 mlb_id 批量补全 MLB 官方球员主信息。
    if not missing_mlb_ids:
        print_section("没有检测到需要新增的球员")
        return players_df

    print_section(f"开始读取 MLB 球员主信息，共 {len(missing_mlb_ids)} 名")
    next_player_id = get_next_player_id(players_df)
    new_players = []
    total_missing = len(missing_mlb_ids)

    for index, mlb_id in enumerate(sorted(missing_mlb_ids), start=1):
        print_progress(index, total_missing, "读取 MLB 球员主信息进度")

        player_record = build_player_core_record(mlb_id, next_player_id)
        if player_record is None:
            continue

        new_players.append(player_record)
        next_player_id += 1

    if not new_players:
        print_section("结束读取 MLB 球员主信息，新增 0 名球员")
        return players_df

    new_players_df = pd.DataFrame(new_players, columns=PLAYERS_COLUMNS)
    players_df = pd.concat([players_df, new_players_df], ignore_index=True)
    players_df = players_df.drop_duplicates(subset=["mlb_id"], keep="first")
    players_df = players_df.sort_values(by=["player_id"], ascending=[True])

    print_section(f"结束读取 MLB 球员主信息，新增 {len(new_players)} 名球员")
    return players_df


def fill_missing_fangraphs_ids(players_df: pd.DataFrame) -> pd.DataFrame:
    # 在同一个脚本里继续补 fangraphs_id，只更新当前仍缺失映射的球员。
    if players_df.empty:
        print_section("players.csv 当前为空，无需补 Fangraphs ID")
        return players_df

    missing_mask = players_df["fangraphs_id"].isna()
    missing_fangraphs_df = players_df[missing_mask].copy()

    if missing_fangraphs_df.empty:
        print_section("所有球员都已经有 Fangraphs ID")
        return players_df

    missing_mlb_ids = set(missing_fangraphs_df["mlb_id"].astype(int))
    print_section(f"开始补充 Fangraphs ID，共 {len(missing_mlb_ids)} 名球员待补")
    fangraphs_map = fetch_fangraphs_map(missing_mlb_ids)

    if not fangraphs_map:
        print_section("本次未补到任何 Fangraphs ID")
        return players_df

    players_df["mlb_id"] = players_df["mlb_id"].astype(int)
    players_df["fangraphs_id"] = players_df["fangraphs_id"].astype("Int64")

    total_missing = len(missing_mlb_ids)
    for index, mlb_id in enumerate(sorted(missing_mlb_ids), start=1):
        print_progress(index, total_missing, "补 Fangraphs ID 进度")

        fangraphs_id = fangraphs_map.get(mlb_id)
        if fangraphs_id is None:
            continue

        players_df.loc[players_df["mlb_id"] == mlb_id, "fangraphs_id"] = int(fangraphs_id)

    filled_count = players_df["fangraphs_id"].notna().sum()
    print_section(f"结束补充 Fangraphs ID，目前共有 {filled_count} 名球员带 Fangraphs ID")
    return players_df


def filter_players_ready_to_save(players_df: pd.DataFrame) -> pd.DataFrame:
    # players.csv 现在允许 fangraphs_id 暂时为空，但 MLB 主信息仍必须完整。
    if players_df.empty:
        return players_df

    required_columns = [
        "player_id",
        "mlb_id",
        "name",
        "birth_date",
        "primary_position",
        "bats",
        "throws",
    ]
    ready_df = players_df.dropna(subset=required_columns).copy()
    dropped_count = len(players_df) - len(ready_df)

    if dropped_count > 0:
        print_section(f"有 {dropped_count} 名球员因 MLB 主信息不完整而暂不写入 players.csv")

    ready_df["player_id"] = ready_df["player_id"].astype(int)
    ready_df["mlb_id"] = ready_df["mlb_id"].astype(int)
    ready_df["fangraphs_id"] = pd.to_numeric(
        ready_df["fangraphs_id"],
        errors="coerce",
    ).astype("Int64")
    return ready_df


def save_players_df(players_df: pd.DataFrame) -> None:
    # 将更新后的球员字典写回 players.csv。
    print_section("开始写入 players.csv")
    players_df = players_df[PLAYERS_COLUMNS]
    players_df = players_df.sort_values(by=["player_id"], ascending=[True])
    players_df.to_csv(get_players_file_path(), index=False)
    print_section(f"结束写入 players.csv，共 {len(players_df)} 条记录")


def main() -> None:
    # 主入口：先按 games.csv 抓逐球数据，再补全 players.csv。
    try:
        games_df = load_games_df()
        players_df = load_players_df()
        missing_mlb_ids = collect_missing_mlb_ids(games_df, players_df)
        players_df = append_new_players_from_mlb(players_df, missing_mlb_ids)
        players_df = fill_missing_fangraphs_ids(players_df)
        players_df = filter_players_ready_to_save(players_df)
        save_players_df(players_df)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Initialization failed: {exc}")
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Failed to fetch MLB players: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Failed to update players.csv: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
