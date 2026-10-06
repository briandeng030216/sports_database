import os

import pandas as pd
import requests

MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
PROGRESS_STEP = 10


def print_section(message):
    # 统一输出主要步骤，方便在终端里快速定位当前执行阶段。
    print(f"[teams] {message}")


def print_progress(current, total, label):
    # 批量读取时按固定步长打印进度，同时确保最后一条一定会显示。
    if total == 0:
        return
    if current == 1 or current % PROGRESS_STEP == 0 or current == total:
        print_section(f"{label}: {current}/{total}")


def fetch_mlb_teams():
    # 从 MLB 官方接口读取球队字典，并只保留大联盟球队。
    print_section("开始读取 MLB 球队数据")
    response = requests.get(MLB_TEAMS_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    raw_teams = data.get("teams", [])
    total_teams = len(raw_teams)
    print_section(f"检测到 {total_teams} 条原始球队记录")

    teams = []

    for index, team in enumerate(raw_teams, start=1):
        print_progress(index, total_teams, "读取球队进度")

        # 只保留 MLB 球队，过滤掉其他联盟或层级的数据。
        if team.get("sport", {}).get("id") != 1:
            continue

        team_info = {
            # 直接使用 MLB 官方 team_id，后续其他表都引用这个值。
            "team_id": team["id"],
            "team_abbr": team["abbreviation"],
            "team_name": team["name"],
            "league": "AL" if team["league"]["name"] == "American League" else "NL",
        }
        teams.append(team_info)

    print_section(f"结束读取 MLB 球队数据，共保留 {len(teams)} 支球队")
    return teams


def save_to_csv(teams):
    # 将球队数据写入 data/teams.csv。
    print_section("开始写入 teams.csv")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    file_path = os.path.join(data_dir, "teams.csv")
    df = pd.DataFrame(teams)
    df.to_csv(file_path, index=False)

    print_section(f"结束写入 teams.csv，共写入 {len(df)} 条记录")
    print(f"Saved to: {file_path}")


if __name__ == "__main__":
    # 主入口：先读取球队，再写入本地 CSV。
    teams = fetch_mlb_teams()
    save_to_csv(teams)
