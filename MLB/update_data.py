import os
import sys
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

import get_batter_game_stats
import get_games
import get_pitch_by_pitch
import get_pitcher_game_stats
import get_players
import get_team_game_stats

STATUS_COLUMNS = [
    "game_id",
    "season",
    "game_date",
    "home_abbr",
    "away_abbr",
    "games_loaded",
    "players_loaded",
    "batter_loaded",
    "pitcher_loaded",
    "pitch_by_pitch_loaded",
    "team_loaded",
    "fully_loaded",
    "last_updated",
    "error_message",
]
STAGE_COLUMNS = [
    "games_loaded",
    "players_loaded",
    "batter_loaded",
    "pitcher_loaded",
    "pitch_by_pitch_loaded",
    "team_loaded",
]


def print_section(message: str) -> None:
    # 统一打印 pipeline 的关键执行步骤。
    print(f"[pipeline] {message}")


def get_data_dir() -> str:
    # 获取 MLB data 目录。
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "data")


def get_status_file_path() -> str:
    # 返回逐场更新状态表路径。
    return os.path.join(get_data_dir(), "game_update_status.csv")


def now_text() -> str:
    # 生成写入状态表的更新时间文本。
    return datetime.now().isoformat(timespec="seconds")


def prompt_for_inputs():
    # 统一在总管线入口读取日期范围和可选球队过滤条件。
    return get_games.resolve_date_range()


def initialize_status_table() -> None:
    # 初始化逐场更新状态表。
    file_path = get_status_file_path()
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print_section("开始初始化 game_update_status.csv")
        pd.DataFrame(columns=STATUS_COLUMNS).to_csv(file_path, index=False)
        print_section("结束初始化 game_update_status.csv")


def load_status_df() -> pd.DataFrame:
    # 读取已有的逐场更新状态表。
    initialize_status_table()
    file_path = get_status_file_path()
    print_section("开始读取 game_update_status.csv")
    status_df = pd.read_csv(file_path)

    if status_df.empty:
        print_section("结束读取 game_update_status.csv，当前为空表")
        return pd.DataFrame(columns=STATUS_COLUMNS)

    status_df["game_id"] = pd.to_numeric(status_df["game_id"], errors="coerce").astype("Int64")
    for column in STAGE_COLUMNS + ["fully_loaded"]:
        status_df[column] = pd.to_numeric(status_df[column], errors="coerce").fillna(0).astype(int)

    print_section(f"结束读取 game_update_status.csv，共加载 {len(status_df)} 条记录")
    return status_df


def save_status_df(status_df: pd.DataFrame) -> None:
    # 将更新后的逐场状态写回本地。
    print_section("开始写入 game_update_status.csv")
    status_df = status_df[STATUS_COLUMNS]
    status_df = status_df.sort_values(
        by=["fully_loaded", "game_date", "game_id"],
        ascending=[True, False, False],
    )
    status_df.to_csv(get_status_file_path(), index=False)
    print_section(f"结束写入 game_update_status.csv，共 {len(status_df)} 条记录")


def build_target_games_df(start_date: str, end_date: str, team_filter: Optional[str]) -> pd.DataFrame:
    # 先抓取本次请求范围内的比赛，再写入 games.csv，同时返回本次目标比赛集合。
    print_section("开始更新 games.csv")
    get_games.initialize_games_table()
    team_abbr_map = get_games.load_team_abbr_map()
    target_games = get_games.fetch_completed_games(
        start_date=start_date,
        end_date=end_date,
        team_abbr_map=team_abbr_map,
        team_filter=team_filter,
    )
    get_games.save_games(target_games)

    if not target_games:
        print_section("当前日期范围内没有符合条件的已完赛比赛")
        return pd.DataFrame(columns=get_games.GAMES_COLUMNS)

    target_games_df = pd.DataFrame(target_games, columns=get_games.GAMES_COLUMNS)
    target_games_df = target_games_df.sort_values(
        by=["game_date", "game_datetime", "game_id"],
        ascending=[False, False, False],
    )
    print_section(f"结束更新 games.csv，本次目标比赛共 {len(target_games_df)} 场")
    return target_games_df


def ensure_status_rows(status_df: pd.DataFrame, target_games_df: pd.DataFrame) -> pd.DataFrame:
    # 确保本次目标比赛在状态表中都有一行。
    if target_games_df.empty:
        return status_df

    existing_game_ids = set()
    if not status_df.empty:
        existing_game_ids = set(status_df["game_id"].dropna().astype(int))

    new_rows = []
    for _, game_row in target_games_df.iterrows():
        game_id = int(game_row["game_id"])
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
                "batter_loaded": 0,
                "pitcher_loaded": 0,
                "pitch_by_pitch_loaded": 0,
                "team_loaded": 0,
                "fully_loaded": 0,
                "last_updated": now_text(),
                "error_message": "",
            }
        )

    if new_rows:
        status_df = pd.concat([status_df, pd.DataFrame(new_rows, columns=STATUS_COLUMNS)], ignore_index=True)

    if status_df.empty:
        return status_df

    # 对已存在的比赛也刷新基础元信息，避免显示过时。
    target_games_map = {
        int(row["game_id"]): row for _, row in target_games_df.iterrows()
    }
    for row_index, status_row in status_df.iterrows():
        game_id = status_row.get("game_id")
        if pd.isna(game_id):
            continue
        game_id = int(game_id)
        if game_id not in target_games_map:
            continue
        game_row = target_games_map[game_id]
        status_df.loc[row_index, "season"] = int(game_row["season"])
        status_df.loc[row_index, "game_date"] = str(game_row["game_date"])
        status_df.loc[row_index, "home_abbr"] = str(game_row["home_abbr"])
        status_df.loc[row_index, "away_abbr"] = str(game_row["away_abbr"])
        status_df.loc[row_index, "games_loaded"] = 1

    return recompute_fully_loaded(status_df)


def recompute_fully_loaded(status_df: pd.DataFrame) -> pd.DataFrame:
    # 当所有阶段都完成时，将 fully_loaded 标为 1。
    if status_df.empty:
        return status_df

    status_df["fully_loaded"] = (
        status_df["games_loaded"].astype(int)
        & status_df["players_loaded"].astype(int)
        & status_df["batter_loaded"].astype(int)
        & status_df["pitcher_loaded"].astype(int)
        & status_df["pitch_by_pitch_loaded"].astype(int)
        & status_df["team_loaded"].astype(int)
    ).astype(int)
    return status_df


def get_game_status_row(status_df: pd.DataFrame, game_id: int) -> pd.Series:
    # 读取单场比赛的状态行。
    game_rows = status_df.loc[status_df["game_id"].astype(int) == int(game_id)]
    if game_rows.empty:
        raise ValueError(f"Missing status row for game_id={game_id}")
    return game_rows.iloc[0]


def mark_stage_success(status_df: pd.DataFrame, game_id: int, stage_column: str) -> pd.DataFrame:
    # 将某个阶段标记为成功完成。
    status_df.loc[status_df["game_id"].astype(int) == int(game_id), stage_column] = 1
    status_df.loc[status_df["game_id"].astype(int) == int(game_id), "last_updated"] = now_text()
    status_df.loc[status_df["game_id"].astype(int) == int(game_id), "error_message"] = ""
    return recompute_fully_loaded(status_df)


def mark_stage_error(status_df: pd.DataFrame, game_id: int, error_message: str) -> pd.DataFrame:
    # 记录单场比赛的失败原因，方便下次继续。
    status_df.loc[status_df["game_id"].astype(int) == int(game_id), "last_updated"] = now_text()
    status_df.loc[status_df["game_id"].astype(int) == int(game_id), "error_message"] = error_message
    return recompute_fully_loaded(status_df)


def build_single_game_df(game_row: pd.Series) -> pd.DataFrame:
    # 将单场比赛包装成 DataFrame，便于复用现有子脚本函数。
    return pd.DataFrame([game_row.to_dict()], columns=get_games.GAMES_COLUMNS)


def process_players_for_game(single_game_df: pd.DataFrame, players_df: pd.DataFrame) -> pd.DataFrame:
    # 只为当前这场比赛补全 players.csv，且不在总管线里尝试补 Fangraphs。
    missing_mlb_ids = get_players.collect_missing_mlb_ids(single_game_df, players_df)
    players_df = get_players.append_new_players_from_mlb(players_df, missing_mlb_ids)
    players_df = get_players.filter_players_ready_to_save(players_df)
    get_players.save_players_df(players_df)
    return players_df


def process_batter_for_game(
    single_game_df: pd.DataFrame,
    players_df: pd.DataFrame,
    batter_df: pd.DataFrame,
) -> pd.DataFrame:
    # 只为当前这场比赛补全打者逐场表。
    batter_df = get_batter_game_stats.build_batter_game_stats(
        single_game_df,
        players_df,
        batter_df,
    )
    get_batter_game_stats.save_batter_game_stats_df(batter_df)
    return batter_df


def process_pitcher_for_game(
    single_game_df: pd.DataFrame,
    players_df: pd.DataFrame,
    pitcher_df: pd.DataFrame,
) -> pd.DataFrame:
    # 只为当前这场比赛补全投手逐场表。
    pitcher_df = get_pitcher_game_stats.build_pitcher_game_stats(
        single_game_df,
        players_df,
        pitcher_df,
    )
    get_pitcher_game_stats.save_pitcher_game_stats_df(pitcher_df)
    return pitcher_df


def process_pitch_by_pitch_for_game(
    single_game_df: pd.DataFrame,
    pitch_df: pd.DataFrame,
) -> pd.DataFrame:
    # 只为当前这场比赛补全逐球表。
    pitch_df = get_pitch_by_pitch.build_pitch_by_pitch(single_game_df, pitch_df)
    get_pitch_by_pitch.save_pitch_by_pitch_df(pitch_df)
    return pitch_df


def process_team_for_game(
    single_game_df: pd.DataFrame,
    team_df: pd.DataFrame,
) -> pd.DataFrame:
    # 只为当前这场比赛补全球队逐场表。
    team_df = get_team_game_stats.build_team_game_stats(single_game_df, team_df)
    get_team_game_stats.save_team_game_stats_df(team_df)
    return team_df


def main() -> None:
    # 总入口：先读取目标比赛，再逐场补齐所有依赖表，并为每场记录更新状态。
    try:
        start_date, end_date, team_filter = prompt_for_inputs()
        target_games_df = build_target_games_df(start_date, end_date, team_filter)

        if target_games_df.empty:
            return

        status_df = load_status_df()
        status_df = ensure_status_rows(status_df, target_games_df)
        save_status_df(status_df)

        players_df = get_players.load_players_df()
        batter_df = get_batter_game_stats.load_batter_game_stats_df()
        pitcher_df = get_pitcher_game_stats.load_pitcher_game_stats_df()
        pitch_df = get_pitch_by_pitch.load_pitch_by_pitch_df()
        team_df = get_team_game_stats.load_team_game_stats_df()

        total_games = len(target_games_df)
        print_section(f"开始逐场更新，共 {total_games} 场比赛")

        for index, (_, game_row) in enumerate(target_games_df.iterrows(), start=1):
            game_id = int(game_row["game_id"])
            print_section(
                f"开始处理比赛 {game_id} ({index}/{total_games}) "
                f"{game_row['away_abbr']} @ {game_row['home_abbr']}"
            )

            game_status = get_game_status_row(status_df, game_id)
            if int(game_status["fully_loaded"]) == 1:
                print_section(f"比赛 {game_id} 已全部完成，直接跳过")
                continue

            single_game_df = build_single_game_df(game_row)

            try:
                if int(game_status["players_loaded"]) != 1:
                    print_section(f"比赛 {game_id} 开始更新 players")
                    players_df = process_players_for_game(single_game_df, players_df)
                    status_df = mark_stage_success(status_df, game_id, "players_loaded")
                    save_status_df(status_df)
                    print_section(f"比赛 {game_id} 结束更新 players")

                game_status = get_game_status_row(status_df, game_id)
                if int(game_status["batter_loaded"]) != 1:
                    print_section(f"比赛 {game_id} 开始更新 batter_game_stats")
                    batter_df = process_batter_for_game(single_game_df, players_df, batter_df)
                    status_df = mark_stage_success(status_df, game_id, "batter_loaded")
                    save_status_df(status_df)
                    print_section(f"比赛 {game_id} 结束更新 batter_game_stats")

                game_status = get_game_status_row(status_df, game_id)
                if int(game_status["pitcher_loaded"]) != 1:
                    print_section(f"比赛 {game_id} 开始更新 pitcher_game_stats")
                    pitcher_df = process_pitcher_for_game(single_game_df, players_df, pitcher_df)
                    status_df = mark_stage_success(status_df, game_id, "pitcher_loaded")
                    save_status_df(status_df)
                    print_section(f"比赛 {game_id} 结束更新 pitcher_game_stats")

                game_status = get_game_status_row(status_df, game_id)
                if int(game_status["pitch_by_pitch_loaded"]) != 1:
                    print_section(f"比赛 {game_id} 开始更新 pitch_by_pitch")
                    pitch_df = process_pitch_by_pitch_for_game(single_game_df, pitch_df)
                    status_df = mark_stage_success(status_df, game_id, "pitch_by_pitch_loaded")
                    save_status_df(status_df)
                    print_section(f"比赛 {game_id} 结束更新 pitch_by_pitch")

                game_status = get_game_status_row(status_df, game_id)
                if int(game_status["team_loaded"]) != 1:
                    print_section(f"比赛 {game_id} 开始更新 team_game_stats")
                    team_df = process_team_for_game(single_game_df, team_df)
                    status_df = mark_stage_success(status_df, game_id, "team_loaded")
                    save_status_df(status_df)
                    print_section(f"比赛 {game_id} 结束更新 team_game_stats")

                status_df = recompute_fully_loaded(status_df)
                save_status_df(status_df)
                print_section(f"比赛 {game_id} 已完成全部更新")
            except requests.RequestException as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                status_df = mark_stage_error(status_df, game_id, error_message)
                save_status_df(status_df)
                print_section(f"比赛 {game_id} 更新失败，已记录错误：{error_message}")
                continue
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                status_df = mark_stage_error(status_df, game_id, error_message)
                save_status_df(status_df)
                print_section(f"比赛 {game_id} 更新失败，已记录错误：{error_message}")
                continue

        print_section("本次逐场数据更新已全部结束")
    except (FileNotFoundError, ValueError) as exc:
        print(f"Initialization failed: {exc}")
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Failed to update MLB pipeline data: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Failed to run MLB update pipeline: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
