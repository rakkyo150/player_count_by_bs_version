import time
import requests
from collections import Counter
from packaging.version import parse as parse_version
from tqdm import tqdm

def remove_section_from_readme(marker):
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

def version_key(x):
  count, key = x[1], x[0]
  if ',' in key:
    version_part = key.split(',')[1]
    version_parsed = parse_version(version_part)
    return (count, version_parsed)
  else:
    # コンマなしは最後尾に回すため、バージョンを非常に小さくする
    return (count, parse_version("0"))

# 1. プレイヤー取得（日本のプレイヤー）
pages=50
player_id_list=[]

for page in tqdm(range(1, pages + 1), desc="Processing pages"):
  url_players = f"https://api.beatleader.xyz/players?countries=jp&page={page}"
  response = requests.get(url_players)
  response_json = response.json()
  players = response_json.get("data")

  version_counter = Counter()
  front_counter = Counter()
  back_counter = Counter()

  for player in players:
    target_timestamp = player.get("scoreStats").get('lastScoreTime')
    # 現在時刻のUnixタイムスタンプを取得
    now_timestamp = int(time.time())

    # 現在時刻と比較対象の差を計算（秒）
    diff_seconds = abs(now_timestamp - target_timestamp)

    # 1ヶ月を30日として秒数に換算
    one_month_seconds = 30 * 24 * 60 * 60

    # 1ヶ月差があるかどうか判定
    if diff_seconds >= one_month_seconds:
      continue

    player_id = player.get('id')
    if not player_id:
      continue
    player_id_list.append(player_id)
    
  time.sleep(2)

# 2. 各プレイヤースコア取得
print(f"プレイヤーID総数：{len(player_id_list)}")
for player_id in tqdm(player_id_list, desc="Processing players"):
  url_scores = f"https://api.beatleader.xyz/player/{player_id}/scores"
  scores_response = requests.get(url_scores)
  scores = scores_response.json()

  if not scores:
    continue

  # 3. 一番新しいスコアのplatform取得（newest firstなら一番目）
  platform = scores.get("data")[0].get('platform')

  if platform:
    simple_platform=platform.split('_')[0]
    
    # simpler_platformについて、コンマが２つある場合は２つ目のコンマ以降を削除する
    parts = simple_platform.split(',')
    if len(parts) > 2:
      simple_platform = ','.join(parts[:2])
    
    version_counter[simple_platform] += 1
    
    parts = simple_platform.split(',')
    if len(parts) == 2:
      front, back = parts
      front_counter[front] += 1
      back_counter[back] += 1
    elif len(parts) == 1:
      # コンマなしの場合は前だけカウント
      front_counter[parts[0]] += 1
  time.sleep(2)

sorted_by_count_front_counter = front_counter.most_common()
sorted_by_version_back_counter = sorted(back_counter.items(), key=lambda x: parse_version(x[0]), reverse=True)
sorted_by_count_version_counter = sorted(
    version_counter.items(),
    key=version_key,
    reverse=True
)
# 4. 集計結果作成
marker="プレイヤーのゲームバージョン統計結果"

remove_section_from_readme(marker)

result_text = f"\n## {marker}\n"

result_text += f"\n過去1ヶ月以内にプレイがあり、BeatLeaderのModを導入している、BeatLeaderのランク上位{sum(version_counter.values())}人の日本で登録しているプレイヤーが対象\n"
result_text += "\n### プラットフォームのみ\n"
for platform, count in sorted_by_count_front_counter:
  result_text += f"{platform}: {count}人\n"

result_text += "\n### ゲームバージョンのみ\n"
for game_version, count in sorted_by_version_back_counter:
  result_text += f"{game_version}: {count}人\n"
    
result_text += "\n### プラットフォームとゲームバージョンの両方\n"
for version, count in sorted_by_count_version_counter:
  result_text += f"- {version}: {count}人\n"

# 5. README.mdに追加
with open("README.md", "a", encoding="utf-8") as f:
  f.write(result_text)
  
print("finish!")