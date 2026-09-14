from flask import Flask, render_template, request
from pathlib import Path
from dotenv import load_dotenv
from auth import init_auth

from timetable_service import (
    load_trains,
    time_to_minutes,
    return_time_to_minutes,
    select_outbound_trains,
    select_return_trains,
    sort_outbound_trains_for_display,
    calculate_timeline_range,
    generate_time_ticks,
    calculate_x_position,
    is_valid_search_time,
    build_train_diagram_points,
    build_train_diagram_stops,
    stack_overlapping_stops,
)


# =========================================================
# 行きダイヤで表示する駅
# 快速停車駅を中心に表示
# =========================================================
OUTBOUND_STATIONS = [
    {
        "name": "茨木",
        "arrival_key": None,
        "departure_key": "茨木発",
    },
    {
        "name": "新大阪",
        "arrival_key": "新大阪着",
        "departure_key": "新大阪発",
    },
    {
        "name": "大阪",
        "arrival_key": "大阪着",
        "departure_key": "大阪発",
    },
    {
        "name": "尼崎",
        "arrival_key": "尼崎着",
        "departure_key": "尼崎発",
    },
    {
        "name": "西宮",
        "arrival_key": None,
        "departure_key": "西宮発",
    },
    {
        "name": "芦屋",
        "arrival_key": "芦屋着",
        "departure_key": "芦屋発",
    },
    {
        "name": "住吉",
        "arrival_key": None,
        "departure_key": "住吉発",
    },
    {
        "name": "六甲道",
        "arrival_key": None,
        "departure_key": "六甲道発",
    },
    {
        "name": "三ノ宮",
        "arrival_key": None,
        "departure_key": "三ノ宮発",
    },
    {
        "name": "元町",
        "arrival_key": None,
        "departure_key": "元町発",
    },
    {
        "name": "神戸",
        "arrival_key": None,
        "departure_key": "神戸発",
    },
]


RETURN_STATIONS = list(reversed(OUTBOUND_STATIONS))


def index():

    # =====================================================
    # 画面共通
    # =====================================================
    direction = "outbound"
    target_time = ""

    selected_trains = []
    error_message = None


    # =====================================================
    # 新ダイヤグラム用
    # =====================================================
    diagram_trains = []

    diagram_start_minutes = None
    diagram_end_minutes = None

    # 基本倍率での1分あたりの横幅
    diagram_pixels_per_minute = 18

    # 一番上の駅までの余白
    diagram_top_margin = 50

    # 駅と駅の縦方向の間隔
    diagram_station_spacing = 78

    diagram_width = 0
    diagram_height = 0

    # 希望到着時刻の縦線位置
    diagram_target_x = None

    # 5分刻みの時間軸
    time_ticks = []


    # =====================================================
    # POSTされたときだけ検索
    # =====================================================
    if request.method == "POST":

        # [] ではなく get() を使うことで、
        # 万が一フォーム値が送られてこなくても
        # BadRequestKeyError にしない
        direction = request.form.get(
            "direction",
            "outbound"
        )

        target_time = request.form.get(
            "target_time",
            ""
        )


        # =================================================
        # 行き
        # =================================================
        if direction == "outbound":

            trains = load_trains(
                "to-kobe.csv"
            )


            # ---------------------------------------------
            # 検索時刻の範囲チェック
            # ---------------------------------------------
            if not is_valid_search_time(
                direction="outbound",
                target_time=target_time,
                trains=trains,
            ):

                error_message = (
                    "行きの希望到着時刻は、"
                    "始発から9:30までを指定してください。"
                )


            else:

                # -----------------------------------------
                # 希望到着時刻の
                # 前7本 + 後3本を取得
                # -----------------------------------------
                selected_trains = (
                    select_outbound_trains(
                        trains,
                        target_time
                    )
                )


                # -----------------------------------------
                # 神戸時刻の早い順に並べる
                # -----------------------------------------
                selected_trains = (
                    sort_outbound_trains_for_display(
                        selected_trains
                    )
                )


        # =================================================
        # 帰り
        # =================================================
        elif direction == "return":

            trains = load_trains(
                "to-ibaraki.csv"
            )


            # ---------------------------------------------
            # 15:00～終電の範囲チェック
            # ---------------------------------------------
            if not is_valid_search_time(
                direction="return",
                target_time=target_time,
                trains=trains,
            ):

                error_message = (
                    "帰りの希望出発時刻は、"
                    "15:00から終電までを指定してください。"
                )


            else:

                # 指定時刻以降の10本
                selected_trains = (
                    select_return_trains(
                        trains,
                        target_time
                    )
                )


        # =================================================
        # directionに想定外の値が来た場合
        # =================================================
        else:

            direction = "outbound"

            error_message = (
                "行き・帰りを選択してください。"
            )


    diagram_stations = RETURN_STATIONS if direction == "return" else OUTBOUND_STATIONS
    time_converter = return_time_to_minutes if direction == "return" else time_to_minutes
    if selected_trains:
        # -----------------------------------------
        # ダイヤ全体の時間範囲
        # -----------------------------------------
        (
            diagram_start_minutes,
            diagram_end_minutes
        ) = calculate_timeline_range(
            selected_trains, time_converter=time_converter
        )


        diagram_start_minutes = min(diagram_start_minutes, (time_converter(target_time) // 5) * 5)

        # -----------------------------------------
        # 5分刻みの時間軸
        # -----------------------------------------
        time_ticks = generate_time_ticks(
            diagram_start_minutes,
            diagram_end_minutes
        )


        # -----------------------------------------
        # 希望到着時刻の縦線位置
        # -----------------------------------------
        diagram_target_x = (
            calculate_x_position(
                time_text=target_time,
                time_converter=time_converter,
                start_minutes=diagram_start_minutes,
                pixels_per_minute=(
                    diagram_pixels_per_minute
                ),
            )
        )


        # -----------------------------------------
        # 10本分のSVG描画データを作る
        # -----------------------------------------
        for train in selected_trains:

            # 列車の折れ線を描くための点
            points = (
                build_train_diagram_points(
                    train=train,
                    time_converter=time_converter,
                    stations=diagram_stations,
                    start_minutes=(
                        diagram_start_minutes
                    ),
                    pixels_per_minute=(
                        diagram_pixels_per_minute
                    ),
                    top_margin=(
                        diagram_top_margin
                    ),
                    station_spacing=(
                        diagram_station_spacing
                    ),
                )
            )


            # 各駅の情報ボックス用
            #
            # 例：
            # 着 8:22
            #   大阪
            #   発 8:25
            stops = (
                build_train_diagram_stops(
                    train=train,
                    time_converter=time_converter,
                    stations=diagram_stations,
                    start_minutes=(
                        diagram_start_minutes
                    ),
                    pixels_per_minute=(
                        diagram_pixels_per_minute
                    ),
                    top_margin=(
                        diagram_top_margin
                    ),
                    station_spacing=(
                        diagram_station_spacing
                    ),
                )
            )


            diagram_trains.append({
                "train_type": (
                    train["train_type"]
                ),
                "kobe_time": (
                    train["神戸発"]
                ),
                "points": points,
                "stops": stops,
            })

        diagram_trains = stack_overlapping_stops(diagram_trains)


        # -----------------------------------------
        # SVGの横幅
        # -----------------------------------------
        diagram_width = (
            (
                diagram_end_minutes
                - diagram_start_minutes
            )
            * diagram_pixels_per_minute
        )


        # -----------------------------------------
        # SVGの高さ
        # -----------------------------------------
        diagram_height = (
            diagram_top_margin * 2
            + (
                len(diagram_stations) - 1
            )
            * diagram_station_spacing
        )



    # =====================================================
    # HTMLへ渡す
    # =====================================================
    return render_template(
        "index.html",

        direction=direction,
        target_time=target_time,

        selected_trains=selected_trains,
        error_message=error_message,

        time_ticks=time_ticks,

        diagram_trains=diagram_trains,

        diagram_start_minutes=(
            diagram_start_minutes
        ),

        diagram_end_minutes=(
            diagram_end_minutes
        ),

        diagram_pixels_per_minute=(
            diagram_pixels_per_minute
        ),

        diagram_top_margin=(
            diagram_top_margin
        ),

        diagram_station_spacing=(
            diagram_station_spacing
        ),

        diagram_width=diagram_width,
        diagram_height=diagram_height,

        diagram_target_x=(
            diagram_target_x
        ),

        diagram_stations=(
            diagram_stations
        ),
    )


def create_app():
    load_dotenv(Path(__file__).with_name(".env"), override=False, encoding="utf-8-sig")
    application = Flask(__name__)
    init_auth(application)
    application.add_url_rule("/", "index", index, methods=["GET", "POST"])
    return application


app = create_app()

if __name__ == "__main__":
    app.run()
