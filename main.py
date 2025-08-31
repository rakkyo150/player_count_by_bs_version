import sys
from typing import Any, Tuple
import time
import requests
from collections import Counter
from packaging.version import parse as parse_version
from tqdm import tqdm
import re
import demjson3

def remove_section_from_readme(marker) -> None:
  filepath="README.md" 
  with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

  # マーカーがある行以降を削除
  new_lines = []
  for line in lines:
    if marker in line:
        break
    new_lines.append(line)

  with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

def version_key(x) -> Tuple[Any, Any]:
  count, key = x[1], x[0]
  if ',' in key:
    version_part = key.split(',')[1]
    version_parsed = parse_version(version_part)
    return (count, version_parsed)
  else:
    # コンマなしは最後尾に回すため、バージョンを非常に小さくする
    return (count, parse_version("0"))
  
def calc_percentage(total: float, part: float) -> float:
  """
  合計(total)に対する部分(part)の割合を計算し、
  小数点2桁まで四捨五入して返す。
  """
  if total == 0:
      return 0.0
  percentage = (part / total) * 100
  return round(percentage, 2)


def fetch_player_ids(player_id_list: list, page: int) -> Tuple[list, Any] :
  try:
    url_players = f"https://api.beatleader.com/players?countries=jp&page={page}"
    response = requests.get(url_players)
    response_json = response.json()
    players = response_json.get("data")
  except (requests.RequestException, ValueError) as e:
    print(f"ページ {page} の情報取得に失敗しました\nError: {e}")
    return player_id_list, None

  if not players:
    return player_id_list, response_json

  now_timestamp = int(time.time())
  one_month_seconds = 30 * 24 * 60 * 60

  for player in players:
    score_state = player.get("scoreStats")
    if score_state is None:
      continue
    target_timestamp = score_state.get('lastScoreTime')
    if target_timestamp is None:
      continue

    diff_seconds = abs(now_timestamp - target_timestamp)
    if diff_seconds >= one_month_seconds:
        continue

    player_id = player.get('id')
    if not player_id:
        continue
    player_id_list.append(player_id)

  return player_id_list, response_json

def fetch_hmds_dict() -> Any:
  url = "https://raw.githubusercontent.com/BeatLeader/beatleader-website/master/src/utils/beatleader/format.js"
  response = requests.get(url)
  response.raise_for_status()
  content = response.text

  pattern = r"export const HMDs\s*=\s*({.*?});"
  match = re.search(pattern, content, re.DOTALL)

  if match:
    hmds_str = match.group(1)
    try:
      hmds_dict = demjson3.decode(hmds_str)
      return hmds_dict
    except demjson3.JSONDecodeError as e:
      print("demjson3でのデコードエラー:", e)
      return None
  else:
    print("HMDsの定義が見つかりませんでした。")
    return None

# 1. プレイヤー取得（日本のプレイヤー）
limit_pages = 1
per_page = 50
player_id_list=[]
platform_game_version_counter = Counter()
platform_counter = Counter()
game_version_counter = Counter()
hmd_counter = Counter()

hmd_dict = fetch_hmds_dict()
time.sleep(2)

player_id_list, response_json = fetch_player_ids(player_id_list, 1)
time.sleep(2)
if response_json == None:
  print("1ページ目のresponse_jsonがNoneです。処理を中断します。")
  sys.exit(1)

total_data = response_json.get("metadata").get("total")
all_pages = (total_data + per_page - 1) // per_page

for page in tqdm(range(2, all_pages + 1), desc="Processing pages"):
  print(page)
  player_id_list, _ = fetch_player_ids(player_id_list, page)
  time.sleep(2)

# 2. 各プレイヤースコア取得
print(f"プレイヤーID総数：{len(player_id_list)}")
for player_id in tqdm(player_id_list, desc="Processing players"):
  try:
    url_scores = f"https://api.beatleader.com/player/{player_id}/scores"
    scores_response = requests.get(url_scores)
    scores = scores_response.json()
  except(requests.RequestException, ValueError) as e:
    print(f"player_id {player_id} の情報取得に失敗しました\nError: {e}")
    time.sleep(2)
    continue

  if not scores:
    continue

  # 3. 一番新しいスコアのplatform取得（newest firstなら一番目）
  data = scores.get("data")
  if data is None or len(data) == 0:
    time.sleep(2)
    continue
  platform = data[0].get('platform')
  if platform is None:
    time.sleep(2)
    continue
  hmd_id = data[0].get('hmd')
  if hmd_id is None:
    time.sleep(2)
    continue
  
  hmd_counter[hmd_id] += 1

  if platform:
    simple_platform=platform.split('_')[0]
    
    # simpler_platformについて、コンマが２つある場合は２つ目のコンマ以降を削除する
    parts = simple_platform.split(',')
    if len(parts) > 2:
      simple_platform = ','.join(parts[:2])
    
    platform_game_version_counter[simple_platform] += 1
    
    parts = simple_platform.split(',')
    if len(parts) == 2:
      front, back = parts
      platform_counter[front] += 1
      game_version_counter[back] += 1
    elif len(parts) == 1:
      # コンマなしの場合は前だけカウント
      platform_counter[parts[0]] += 1
  time.sleep(2)

sorted_by_count_hmd_counter = hmd_counter.most_common()
sorted_by_count_front_counter = platform_counter.most_common()
sorted_by_version_back_counter = sorted(game_version_counter.items(), key=lambda x: parse_version(x[0]), reverse=True)
sorted_by_count_version_counter = sorted(
    platform_game_version_counter.items(),
    key=version_key,
    reverse=True
)
# 4. 集計結果作成
marker="プレイヤーのゲームバージョン統計結果"

remove_section_from_readme(marker)

result_text = f"\n## {marker}\n"

sum = sum(platform_game_version_counter.values())

result_text += f"過去1ヶ月以内にプレイがあり、BeatLeaderのModを導入している、BeatLeaderのランク上位{sum}人の日本で登録しているプレイヤーが対象\n"
result_text += "\n### プラットフォームのみ\n"
result_text += "| プラットフォーム | 人数 | 割合 |\n| ---- | ---- | ---- |\n"
for platform, count in sorted_by_count_front_counter:
  result_text += f"| {platform} | {count} | {calc_percentage(sum, count)}% |\n"

result_text += "\n### ゲームバージョンのみ\n"
result_text += "| バージョン | 人数 | 割合 |\n| ---- | ---- | ---- |\n"
for game_version, count in sorted_by_version_back_counter:
  result_text += f"| {game_version} | {count} | {calc_percentage(sum, count)}% |\n"
    
result_text += "\n### HMD\n"
result_text += "| HMD | 人数 | 割合 |\n| ---- | ---- | ---- |\n"
for hmd_id, count in sorted_by_count_hmd_counter:
  result_text += f"| {hmd_dict.get(hmd_id, {}).get('name')} | {count} | {calc_percentage(sum, count)}% |\n"
    
result_text += "\n### プラットフォームとゲームバージョンの両方\n"
result_text += "| プラットフォームとバージョン | 人数 | 割合 |\n| ---- | ---- | ---- |\n"
for version, count in sorted_by_count_version_counter:
  result_text += f"| {version} | {count} | {calc_percentage(sum, count)}% |\n"

# 5. README.mdに追加
with open("README.md", "a", encoding="utf-8") as f:
  f.write(result_text)
  
print("finish!")