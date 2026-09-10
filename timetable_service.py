import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def load_trains(csv_filename="to-kobe.csv"):
    trains = []

    csv_path = DATA_DIR / csv_filename

    with csv_path.open(
        mode="r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            if row.get("train_type"):
                trains.append(row)

    return trains


def time_to_minutes(time_text):
    hour, minute = map(int, time_text.split(":"))

    return hour * 60 + minute

def return_time_to_minutes(time_text):
    minutes = time_to_minutes(time_text)

    # 深夜帯（0〜2時台）だけを翌日として扱う。
    # CSVに含まれる14時台などの昼の列車を翌日に回さない。
    if minutes < 3 * 60:
        minutes += 24 * 60

    return minutes

def is_valid_search_time(direction, target_time, trains):

    # 時刻が入力されていない場合
    if not target_time:
        return False

    # 行き：CSV上の最も早い神戸時刻 ～ 9:30
    if direction == "outbound":
        kobe_times = []

        for train in trains:
            kobe_time = train.get("神戸発")

            if not kobe_time:
                continue

            kobe_times.append(
                time_to_minutes(kobe_time)
            )

        if not kobe_times:
            return False

        first_train_minutes = min(kobe_times)
        target_minutes = time_to_minutes(target_time)
        limit_minutes = time_to_minutes("9:30")

        return first_train_minutes <= target_minutes <= limit_minutes

    # 帰り：15:00 ～ CSV上の終電
    if direction == "return":
        kobe_times = []

        for train in trains:
            kobe_time = train.get("神戸発")

            if not kobe_time:
                continue

            kobe_times.append(
                return_time_to_minutes(kobe_time)
            )

        if not kobe_times:
            return False

        start_minutes = return_time_to_minutes("15:00")
        last_train_minutes = max(kobe_times)
        target_minutes = return_time_to_minutes(target_time)

        return start_minutes <= target_minutes <= last_train_minutes

    return False

def select_outbound_trains(trains, target_time):
    target_minutes = time_to_minutes(target_time)

    before_trains = []
    after_trains = []

    for index, train in enumerate(trains):
        kobe_time = train.get("神戸発")

        # 神戸時刻が空欄の列車は検索対象外
        if not kobe_time:
            continue

        kobe_minutes = time_to_minutes(kobe_time)

        train_info = {
            "index": index,
            "minutes": kobe_minutes,
            "train": train
        }

        # 希望到着時刻ちょうどは「前側」に含める
        if kobe_minutes <= target_minutes:
            before_trains.append(train_info)
        else:
            after_trains.append(train_info)

    # 希望到着時刻に近い順に並べる
    before_trains.sort(
        key=lambda item: item["minutes"],
        reverse=True
    )

    after_trains.sort(
        key=lambda item: item["minutes"]
    )

    # 基本は「前7本 + 後3本」
    selected_before = before_trains[:7]
    selected_after = after_trains[:3]

    # 10本に足りない本数
    shortage = 10 - (
        len(selected_before) + len(selected_after)
    )

    if shortage > 0:

        # 前側が7本未満なら、後側から追加
        if len(selected_before) < 7:
            start = len(selected_after)

            selected_after += after_trains[
                start:start + shortage
            ]

        # 後側が3本未満なら、前側から追加
        elif len(selected_after) < 3:
            start = len(selected_before)

            selected_before += before_trains[
                start:start + shortage
            ]

    selected = selected_before + selected_after

    # B案では後発列車ほど右側にしたいので
    # 最後にCSV上の元の順番へ戻す
    selected.sort(key=lambda item: item["index"])

    return [item["train"] for item in selected]

def select_return_trains(trains, target_time):
    target_minutes = return_time_to_minutes(target_time)

    candidates = []

    for index, train in enumerate(trains):
        kobe_time = train.get("神戸発")

        # 神戸時刻が空欄なら対象外
        if not kobe_time:
            continue

        kobe_minutes = return_time_to_minutes(kobe_time)

        # 指定時刻以降だけ対象
        if kobe_minutes >= target_minutes:
            candidates.append({
                "index": index,
                "minutes": kobe_minutes,
                "train": train
            })

    # 神戸出発時刻の早い順
    candidates.sort(
        key=lambda item: item["minutes"]
    )

    # 最大10本
    selected = candidates[:10]

    return [item["train"] for item in selected]

def sort_outbound_trains_for_display(trains):

    return sorted(
        trains,
        key=lambda train: time_to_minutes(train["神戸発"])
    )

def calculate_top(time_text, start_minutes, pixels_per_minute):
    time_minutes = time_to_minutes(time_text)

    difference = time_minutes - start_minutes

    return difference * pixels_per_minute

def calculate_x_position(time_text, start_minutes, pixels_per_minute, time_converter=time_to_minutes):
    time_minutes = time_converter(time_text)

    return (
        time_minutes - start_minutes
    ) * pixels_per_minute

def build_train_diagram_points(
    train,
    stations,
    start_minutes,
    pixels_per_minute,
    top_margin,
    station_spacing,
    time_converter=time_to_minutes,
):
    points = []

    for index, station in enumerate(stations):
        y = top_margin + (index * station_spacing)

        arrival_key = station["arrival_key"]
        departure_key = station["departure_key"]

        # 到着時刻がある場合
        if arrival_key:
            arrival_time = train.get(arrival_key)

            if arrival_time:
                points.append({
                    "station": station["name"],
                    "event": "arrival",
                    "time": arrival_time,
                    "x": calculate_x_position(
                        time_text=arrival_time,
                        start_minutes=start_minutes,
                        pixels_per_minute=pixels_per_minute,
                        time_converter=time_converter,
                    ),
                    "y": y,
                })

        # 発車時刻がある場合
        if departure_key:
            departure_time = train.get(departure_key)

            if departure_time:
                points.append({
                    "station": station["name"],
                    "event": "departure",
                    "time": departure_time,
                    "x": calculate_x_position(
                        time_text=departure_time,
                        start_minutes=start_minutes,
                        pixels_per_minute=pixels_per_minute,
                        time_converter=time_converter,
                    ),
                    "y": y,
                })

    return points

def build_train_diagram_stops(
    train,
    stations,
    start_minutes,
    pixels_per_minute,
    top_margin,
    station_spacing,
    time_converter=time_to_minutes,
):
    stops = []

    for index, station in enumerate(stations):
        y = top_margin + (index * station_spacing)

        arrival = ""
        departure = ""

        arrival_key = station["arrival_key"]
        departure_key = station["departure_key"]

        if arrival_key:
            arrival = train.get(arrival_key, "") or ""

        if departure_key:
            departure = train.get(departure_key, "") or ""

        # 到着・発車の両方が空欄なら、
        # この列車はその駅に停車しないので箱を作らない
        if not arrival and not departure:
            continue

        arrival_x = None
        departure_x = None

        if arrival:
            arrival_x = calculate_x_position(
                time_text=arrival,
                start_minutes=start_minutes,
                pixels_per_minute=pixels_per_minute,
                time_converter=time_converter,
            )

        if departure:
            departure_x = calculate_x_position(
                time_text=departure,
                start_minutes=start_minutes,
                pixels_per_minute=pixels_per_minute,
                time_converter=time_converter,
            )

        # 箱の中心位置
        if arrival_x is not None and departure_x is not None:
            x = (arrival_x + departure_x) / 2

        elif arrival_x is not None:
            x = arrival_x

        else:
            x = departure_x

        stops.append({
            "station": station["name"],
            "arrival": arrival,
            "departure": departure,
            "arrival_x": arrival_x,
            "departure_x": departure_x,
            "x": x,
            "y": y,
        })

    return stops

def calculate_timeline_range(trains, time_converter=time_to_minutes):
    all_times = []

    for train in trains:
        for key, value in train.items():

            # 時刻ではない項目は除外
            if key in ("name", "train_type"):
                continue

            # 空欄は除外
            if not value:
                continue

            all_times.append(
                time_converter(value)
            )

    min_minutes = min(all_times)
    max_minutes = max(all_times)

    # 開始時刻は直前の5分単位へ切り下げ
    start_minutes = (min_minutes // 5) * 5

    # 終了時刻は直後の5分単位へ切り上げ
    end_minutes = ((max_minutes + 4) // 5) * 5

    return start_minutes, end_minutes

def generate_time_ticks(start_minutes, end_minutes):
    ticks = []

    current_minutes = start_minutes

    while current_minutes <= end_minutes:
        hour = current_minutes // 60
        minute = current_minutes % 60

        ticks.append({
            "minutes": current_minutes,
            "label": ("翌日 " if hour >= 24 else "") + f"{hour % 24}:{minute:02d}"
        })

        current_minutes += 5

    return ticks

def build_train_lane(
    train,
    stations,
    start_minutes,
    pixels_per_minute,
):
    lane = []

    for station in stations:
        arrival_key = station["arrival_key"]
        departure_key = station["departure_key"]

        arrival = ""
        departure = ""

        if arrival_key:
            arrival = train.get(arrival_key, "") or ""

        if departure_key:
            departure = train.get(departure_key, "") or ""

        # 到着・発車の両方が空欄なら、
        # この列車はその駅に停まらないので表示しない
        if not arrival and not departure:
            continue

        # 時間軸上の位置は
        # 到着時刻があれば到着時刻、
        # なければ発車時刻を使う
        position_time = arrival or departure

        top = calculate_top(
            time_text=position_time,
            start_minutes=start_minutes,
            pixels_per_minute=pixels_per_minute,
        )

        lane.append({
            "station": station["name"],
            "arrival": arrival,
            "departure": departure,
            "top": top,
        })

    return lane

def stack_overlapping_stops(diagram_trains, stack_step=34):
    """
    同じ駅・同じ時刻の stop が重なる場合、
    縦方向に少しずらして表示するための offset_y を付ける。

    判定ルール：
    - arrival があれば arrival を優先
    - arrival が無ければ departure を使う
    """

    # まず全stopに offset_y = 0 を入れておく
    for train in diagram_trains:
        for stop in train["stops"]:
            stop["offset_y"] = 0

    grouped = {}

    # 同じ駅・同じ時刻でグループ化
    for train_index, train in enumerate(diagram_trains):
        for stop_index, stop in enumerate(train["stops"]):
            compare_time = stop.get("arrival") or stop.get("departure")

            if not compare_time:
                continue

            key = (stop["station"], compare_time)

            grouped.setdefault(key, []).append({
                "train_index": train_index,
                "stop_index": stop_index,
                "stop": stop,
            })

    # 重なるグループだけ縦に並べる
    for items in grouped.values():
        if len(items) <= 1:
            continue

        # 左から右の順に並べる
        items.sort(key=lambda item: item["train_index"])

        count = len(items)

        # 例:
        # 2個 -> [-17, 17]
        # 3個 -> [-34, 0, 34]
        # 4個 -> [-51, -17, 17, 51]
        start = -((count - 1) / 2) * stack_step

        for i, item in enumerate(items):
            offset_y = int(start + i * stack_step)
            item["stop"]["offset_y"] = offset_y

    return diagram_trains
