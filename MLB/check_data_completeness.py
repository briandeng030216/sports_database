import os
import sys
from typing import List

import pandas as pd

PROGRESS_STEP = 10

REPORT_COLUMNS = [
    "game_id",
    "season",
    "game_date",
    "home_abbr",
    "away_abbr",
    "batter_row_count",
    "pitcher_row_count",
    "batter_complete",
    "pitcher_complete",
    "overall_complete",
]


def print_section(message):
    # 统一打印检查脚本的关键执行步骤。
    print(f"[check] {message}")


def print_progress(current, total, label):
    # 批量读取比赛或报告时按固定步长显示进度。
    if total == 0:
        return
    if current == 1 or current % PROGRESS_STEP == 0 or current == total:
        print_section(f"{label}: {current}/{total}")


def get_data_dir() -> str:
    # 获取 data 目录。
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "data")


def get_games_file_path() -> str:
    # 返回 games.csv 的完整路径。
    return os.path.join(get_data_dir(), "games.csv")


def get_batter_game_stats_file_path() -> str:
    # 返回 batter_game_stats.csv 的完整路径。
    return os.path.join(get_data_dir(), "batter_game_stats.csv")


def get_pitcher_game_stats_file_path() -> str:
    # 返回 pitcher_game_stats.csv 的完整路径。
    return os.path.join(get_data_dir(), "pitcher_game_stats.csv")


def get_report_file_path() -> str:
    # 返回完整性检查报告路径。
    return os.path.join(get_data_dir(), "data_completeness_report.csv")


def load_csv(file_path: str, label: str) -> pd.DataFrame:
    # 读取通用 CSV；文件不存在或为空时返回空表。
    print_section(f"开始读取 {label}")

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print_section(f"结束读取 {label}，文件不存在或为空")
        return pd.DataFrame()

    df = pd.read_csv(file_path)
    if df.empty:
        print_section(f"结束读取 {label}，当前为空表")
        return df

    total_rows = len(df)
    for index in range(1, total_rows + 1):
        print_progress(index, total_rows, f"读取 {label} 进度")

    print_section(f"结束读取 {label}，共加载 {total_rows} 条记录")
    return df


def build_game_report_rows(
    games_df: pd.DataFrame,
    batter_df: pd.DataFrame,
    pitcher_df: pd.DataFrame,
) -> List[dict]:
    # 基于 games.csv 检查每场比赛在 batter / pitcher 表中是否都有记录。
    report_rows: List[dict] = []
    total_games = len(games_df)

    batter_counts = {}
    if not batter_df.empty:
        batter_counts = (
            batter_df.groupby("game_id").size().astype(int).to_dict()
        )

    pitcher_counts = {}
    if not pitcher_df.empty:
        pitcher_counts = (
            pitcher_df.groupby("game_id").size().astype(int).to_dict()
        )

    print_section(f"开始检查数据完整性，共 {total_games} 场比赛")

    for index, (_, game_row) in enumerate(games_df.iterrows(), start=1):
        print_progress(index, total_games, "检查比赛进度")

        game_id = int(game_row["game_id"])
        batter_row_count = int(batter_counts.get(game_id, 0))
        pitcher_row_count = int(pitcher_counts.get(game_id, 0))
        batter_complete = 1 if batter_row_count > 0 else 0
        pitcher_complete = 1 if pitcher_row_count > 0 else 0
        overall_complete = 1 if batter_complete and pitcher_complete else 0

        report_rows.append(
            {
                "game_id": game_id,
                "season": int(game_row["season"]),
                "game_date": str(game_row["game_date"]),
                "home_abbr": str(game_row["home_abbr"]),
                "away_abbr": str(game_row["away_abbr"]),
                "batter_row_count": batter_row_count,
                "pitcher_row_count": pitcher_row_count,
                "batter_complete": batter_complete,
                "pitcher_complete": pitcher_complete,
                "overall_complete": overall_complete,
            }
        )

    return report_rows


def save_report_df(report_df: pd.DataFrame) -> None:
    # 将完整性检查结果写入报告文件。
    print_section("开始写入 data_completeness_report.csv")
    report_df = report_df[REPORT_COLUMNS]
    report_df.to_csv(get_report_file_path(), index=False)
    print_section(f"结束写入 data_completeness_report.csv，共 {len(report_df)} 条记录")


def print_summary(report_df: pd.DataFrame) -> None:
    # 在终端打印高层总结，方便快速判断哪些比赛缺失。
    total_games = len(report_df)
    complete_games = int(report_df["overall_complete"].sum()) if total_games else 0
    incomplete_games = total_games - complete_games

    print_section(
        f"完整性检查完成：共 {total_games} 场，完整 {complete_games} 场，不完整 {incomplete_games} 场"
    )

    if incomplete_games == 0:
        return

    batter_missing_games = int((report_df["batter_complete"] == 0).sum())
    pitcher_missing_games = int((report_df["pitcher_complete"] == 0).sum())

    print_section(f"batter_game_stats 缺失比赛数：{batter_missing_games}")
    print_section(f"pitcher_game_stats 缺失比赛数：{pitcher_missing_games}")


def main() -> None:
    # 主入口：只基于本地 CSV 检查 batter / pitcher 逐场表是否覆盖了 games.csv。
    try:
        games_df = load_csv(get_games_file_path(), "games.csv")
        if games_df.empty:
            raise ValueError("games.csv is empty.")

        batter_df = load_csv(get_batter_game_stats_file_path(), "batter_game_stats.csv")
        pitcher_df = load_csv(get_pitcher_game_stats_file_path(), "pitcher_game_stats.csv")

        report_rows = build_game_report_rows(games_df, batter_df, pitcher_df)
        report_df = pd.DataFrame(report_rows, columns=REPORT_COLUMNS)
        report_df = report_df.sort_values(
            by=["overall_complete", "game_date", "game_id"],
            ascending=[True, False, False],
        )
        save_report_df(report_df)
        print_summary(report_df)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Initialization failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Failed to check MLB data completeness: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
