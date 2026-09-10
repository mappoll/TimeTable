import unittest

from timetable_service import (
    time_to_minutes,
    return_time_to_minutes,
    select_outbound_trains,
    select_return_trains,
    sort_outbound_trains_for_display,
    calculate_top,
    calculate_timeline_range,
    generate_time_ticks,
    build_train_lane,
    is_valid_search_time,
    calculate_x_position,
    build_train_diagram_points,
    build_train_diagram_stops,
)

class TimeToMinutesTest(unittest.TestCase):

    def test_5_06を分に変換できる(self):
        result = time_to_minutes("5:06")

        self.assertEqual(306, result)

    def test_9_15を分に変換できる(self):
        result = time_to_minutes("9:15")

        self.assertEqual(555, result)

    def test_15_03を分に変換できる(self):
        result = time_to_minutes("15:03")

        self.assertEqual(903, result)

class SelectOutboundTrainsTest(unittest.TestCase):

    def test_希望到着時刻の前7本と後3本を取得できる(self):
        trains = [
            {"name": "A", "神戸発": "8:45"},
            {"name": "B", "神戸発": "8:50"},
            {"name": "C", "神戸発": "9:00"},
            {"name": "D", "神戸発": "9:10"},
            {"name": "E", "神戸発": "9:05"},
            {"name": "F", "神戸発": "9:15"},
            {"name": "G", "神戸発": "9:12"},
            {"name": "H", "神戸発": "9:14"},
            {"name": "I", "神戸発": "9:20"},
            {"name": "J", "神戸発": "9:18"},
            {"name": "K", "神戸発": "9:25"},
            {"name": "L", "神戸発": "9:30"},
        ]

        result = select_outbound_trains(trains, "9:15")

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["B", "C", "D", "E", "F", "G", "H", "I", "J", "K"],
            result_names
        )

    def test_前の列車が7本未満なら後ろから補充して10本取得できる(self):
        trains = [
            {"name": "A", "神戸発": "8:50"},
            {"name": "B", "神戸発": "9:00"},
            {"name": "C", "神戸発": "9:10"},
            {"name": "D", "神戸発": "9:15"},
            {"name": "E", "神戸発": "9:18"},
            {"name": "F", "神戸発": "9:20"},
            {"name": "G", "神戸発": "9:22"},
            {"name": "H", "神戸発": "9:24"},
            {"name": "I", "神戸発": "9:26"},
            {"name": "J", "神戸発": "9:28"},
            {"name": "K", "神戸発": "9:30"},
            {"name": "L", "神戸発": "9:32"},
        ]

        result = select_outbound_trains(trains, "9:15")

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
            result_names
        )

    def test_後ろの列車が3本未満なら前から補充して10本取得できる(self):
        trains = [
            {"name": "A", "神戸発": "8:30"},
            {"name": "B", "神戸発": "8:40"},
            {"name": "C", "神戸発": "8:50"},
            {"name": "D", "神戸発": "9:00"},
            {"name": "E", "神戸発": "9:05"},
            {"name": "F", "神戸発": "9:08"},
            {"name": "G", "神戸発": "9:10"},
            {"name": "H", "神戸発": "9:12"},
            {"name": "I", "神戸発": "9:14"},
            {"name": "J", "神戸発": "9:15"},
            {"name": "K", "神戸発": "9:20"},
        ]

        result = select_outbound_trains(trains, "9:15")

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["B", "C", "D", "E", "F", "G", "H", "I", "J", "K"],
            result_names
        )

    def test_神戸時刻が空欄の列車は検索対象から除外される(self):
        trains = [
            {"name": "A", "神戸発": "9:00"},
            {"name": "B", "神戸発": ""},
            {"name": "C", "神戸発": "9:05"},
            {"name": "D", "神戸発": "9:10"},
            {"name": "E", "神戸発": "9:15"},
            {"name": "F", "神戸発": ""},
            {"name": "G", "神戸発": "9:18"},
            {"name": "H", "神戸発": "9:20"},
            {"name": "I", "神戸発": "9:22"},
        ]

        result = select_outbound_trains(trains, "9:15")

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["A", "C", "D", "E", "G", "H", "I"],
            result_names
        )

class SelectReturnTrainsTest(unittest.TestCase):

    def test_指定出発時刻以降の10本を取得できる(self):
        trains = [
            {"name": "A", "神戸発": "17:50"},
            {"name": "B", "神戸発": "17:55"},
            {"name": "C", "神戸発": "18:00"},
            {"name": "D", "神戸発": "18:03"},
            {"name": "E", "神戸発": "18:07"},
            {"name": "F", "神戸発": "18:10"},
            {"name": "G", "神戸発": "18:14"},
            {"name": "H", "神戸発": "18:18"},
            {"name": "I", "神戸発": "18:22"},
            {"name": "J", "神戸発": "18:27"},
            {"name": "K", "神戸発": "18:31"},
            {"name": "L", "神戸発": "18:35"},
            {"name": "M", "神戸発": "18:40"},
        ]

        result = select_return_trains(trains, "18:00")

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["C", "D", "E", "F", "G", "H", "I", "J", "K", "L"],
            result_names
        )

    def test_神戸時刻が空欄の列車は検索対象から除外される(self):
        trains = [
            {"name": "A", "神戸発": "17:55"},
            {"name": "B", "神戸発": ""},
            {"name": "C", "神戸発": "18:00"},
            {"name": "D", "神戸発": "18:05"},
            {"name": "E", "神戸発": ""},
            {"name": "F", "神戸発": "18:10"},
        ]

        result = select_return_trains(trains, "18:00")

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["C", "D", "F"],
            result_names
        )

    def test_指定時刻以降が10本未満なら存在する列車だけ取得できる(self):
        trains = [
            {"name": "A", "神戸発": "17:50"},
            {"name": "B", "神戸発": "18:00"},
            {"name": "C", "神戸発": "18:05"},
            {"name": "D", "神戸発": "18:10"},
            {"name": "E", "神戸発": "18:15"},
        ]

        result = select_return_trains(trains, "18:00")

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["B", "C", "D", "E"],
            result_names
        )

    def test_列車は神戸出発時刻の早い順に並ぶ(self):
        trains = [
            {"name": "A", "神戸発": "18:17"},
            {"name": "B", "神戸発": "18:02"},
            {"name": "C", "神戸発": "18:13"},
            {"name": "D", "神戸発": "18:04"},
            {"name": "E", "神戸発": "18:08"},
        ]

        result = select_return_trains(trains, "18:00")

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["B", "D", "E", "C", "A"],
            result_names
        )

    def test_日付をまたぐ終電帯を正しい順番で取得できる(self):
        trains = [
            {"name": "A", "神戸発": "23:50"},
            {"name": "B", "神戸発": "23:55"},
            {"name": "C", "神戸発": "0:02"},
            {"name": "D", "神戸発": "0:08"},
            {"name": "E", "神戸発": "0:15"},
        ]

        result = select_return_trains(trains, "23:55")

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["B", "C", "D", "E"],
            result_names
        )

class SortOutboundTrainsForDisplayTest(unittest.TestCase):

    def test_神戸到着時刻の早い順に並ぶ(self):
        trains = [
            {
                "name": "A",
                "茨木発": "8:10",
                "新大阪発": "8:22",
                "大阪発": "8:27",
                "神戸発": "9:05",
            },
            {
                "name": "B",
                "茨木発": "",
                "新大阪発": "8:18",
                "大阪発": "8:23",
                "神戸発": "8:55",
            },
            {
                "name": "C",
                "茨木発": "",
                "新大阪発": "",
                "大阪発": "8:25",
                "神戸発": "9:10",
            },
            {
                "name": "D",
                "茨木発": "8:05",
                "新大阪発": "8:17",
                "大阪発": "8:22",
                "神戸発": "9:00",
            },
        ]

        result = sort_outbound_trains_for_display(trains)

        result_names = [train["name"] for train in result]

        self.assertEqual(
            ["B", "D", "A", "C"],
            result_names
        )

class CalculateTopTest(unittest.TestCase):

    def test_開始時刻からの差をピクセル位置に変換できる(self):
        result = calculate_top(
            time_text="9:15",
            start_minutes=540,
            pixels_per_minute=8,
        )

        self.assertEqual(120, result)

class CalculateTimelineRangeTest(unittest.TestCase):

    def test_列車時刻から5分単位の表示範囲を計算できる(self):
        trains = [
            {
                "train_type": "普通",
                "茨木発": "7:54",
                "大阪発": "8:16",
                "神戸発": "8:59",
            },
            {
                "train_type": "快速",
                "茨木発": "8:31",
                "大阪発": "8:44",
                "神戸発": "9:17",
            },
            {
                "train_type": "普通",
                "茨木発": "8:19",
                "大阪発": "8:41",
                "神戸発": "9:27",
            },
        ]

        start_minutes, end_minutes = calculate_timeline_range(trains)

        self.assertEqual(470, start_minutes)  # 7:50
        self.assertEqual(570, end_minutes)    # 9:30

class GenerateTimeTicksTest(unittest.TestCase):

    def test_5分刻みの時間軸を作成できる(self):
        result = generate_time_ticks(
            start_minutes=470,  # 7:50
            end_minutes=490,    # 8:10
        )

        self.assertEqual(
            [
                {"minutes": 470, "label": "7:50"},
                {"minutes": 475, "label": "7:55"},
                {"minutes": 480, "label": "8:00"},
                {"minutes": 485, "label": "8:05"},
                {"minutes": 490, "label": "8:10"},
            ],
            result
        )

class BuildTrainLaneTest(unittest.TestCase):

    def test_列車を時間軸表示用データに変換できる(self):
        train = {
            "train_type": "普通",
            "茨木発": "7:54",
            "新大阪着": "8:09",
            "新大阪発": "8:10",
            "大阪着": "8:13",
            "大阪発": "8:16",
            "神戸発": "8:59",
        }

        stations = [
            {
                "name": "茨木",
                "arrival_key": None,
                "departure_key": "茨木発",
            },
            {
                "name": "大阪",
                "arrival_key": "大阪着",
                "departure_key": "大阪発",
            },
            {
                "name": "神戸",
                "arrival_key": None,
                "departure_key": "神戸発",
            },
        ]

        result = build_train_lane(
            train=train,
            stations=stations,
            start_minutes=470,       # 7:50
            pixels_per_minute=4,
        )

        self.assertEqual(
            [
                {
                    "station": "茨木",
                    "arrival": "",
                    "departure": "7:54",
                    "top": 16,
                },
                {
                    "station": "大阪",
                    "arrival": "8:13",
                    "departure": "8:16",
                    "top": 92,
                },
                {
                    "station": "神戸",
                    "arrival": "",
                    "departure": "8:59",
                    "top": 276,
                },
            ],
            result
        )

class ReturnTimeToMinutesTest(unittest.TestCase):

    def test_帰りの0時台を翌日として分に変換できる(self):
        self.assertEqual(
            900,
            return_time_to_minutes("15:00")
        )

        self.assertEqual(
            1439,
            return_time_to_minutes("23:59")
        )

        self.assertEqual(
            1442,
            return_time_to_minutes("0:02")
        )

        self.assertEqual(
            1458,
            return_time_to_minutes("0:18")
        )

class IsValidSearchTimeTest(unittest.TestCase):

    def test_行きは始発から9時30分まで指定できる(self):
        trains = [
            {"神戸発": "5:40"},
            {"神戸発": "8:00"},
            {"神戸発": "9:30"},
        ]

        self.assertTrue(
            is_valid_search_time(
                direction="outbound",
                target_time="5:40",
                trains=trains,
            )
        )

        self.assertTrue(
            is_valid_search_time(
                direction="outbound",
                target_time="9:30",
                trains=trains,
            )
        )

        self.assertFalse(
            is_valid_search_time(
                direction="outbound",
                target_time="5:39",
                trains=trains,
            )
        )

        self.assertFalse(
            is_valid_search_time(
                direction="outbound",
                target_time="9:31",
                trains=trains,
            )
        )


    def test_帰りは15時から終電まで指定できる(self):
        trains = [
            {"神戸発": "15:00"},
            {"神戸発": "23:55"},
            {"神戸発": "0:18"},
        ]

        self.assertTrue(
            is_valid_search_time(
                direction="return",
                target_time="15:00",
                trains=trains,
            )
        )

        self.assertTrue(
            is_valid_search_time(
                direction="return",
                target_time="23:59",
                trains=trains,
            )
        )

        self.assertTrue(
            is_valid_search_time(
                direction="return",
                target_time="0:18",
                trains=trains,
            )
        )

        self.assertFalse(
            is_valid_search_time(
                direction="return",
                target_time="14:59",
                trains=trains,
            )
        )

        self.assertFalse(
            is_valid_search_time(
                direction="return",
                target_time="0:19",
                trains=trains,
            )
        )

class CalculateXPositionTest(unittest.TestCase):

    def test_時刻から横方向の位置を計算できる(self):
        self.assertEqual(
            0,
            calculate_x_position(
                time_text="8:00",
                start_minutes=480,
                pixels_per_minute=10,
            )
        )

        self.assertEqual(
            100,
            calculate_x_position(
                time_text="8:10",
                start_minutes=480,
                pixels_per_minute=10,
            )
        )

        self.assertEqual(
            750,
            calculate_x_position(
                time_text="9:15",
                start_minutes=480,
                pixels_per_minute=10,
            )
        )

class BuildTrainDiagramPointsTest(unittest.TestCase):

    def test_列車をダイヤグラム用の点データに変換できる(self):
        train = {
            "茨木発": "8:00",
            "大阪着": "8:10",
            "大阪発": "8:12",
            "神戸発": "8:30",
        }

        stations = [
            {
                "name": "茨木",
                "arrival_key": None,
                "departure_key": "茨木発",
            },
            {
                "name": "大阪",
                "arrival_key": "大阪着",
                "departure_key": "大阪発",
            },
            {
                "name": "神戸",
                "arrival_key": None,
                "departure_key": "神戸発",
            },
        ]

        result = build_train_diagram_points(
            train=train,
            stations=stations,
            start_minutes=480,
            pixels_per_minute=10,
            top_margin=40,
            station_spacing=100,
        )

        self.assertEqual(
            [
                {
                    "station": "茨木",
                    "event": "departure",
                    "time": "8:00",
                    "x": 0,
                    "y": 40,
                },
                {
                    "station": "大阪",
                    "event": "arrival",
                    "time": "8:10",
                    "x": 100,
                    "y": 140,
                },
                {
                    "station": "大阪",
                    "event": "departure",
                    "time": "8:12",
                    "x": 120,
                    "y": 140,
                },
                {
                    "station": "神戸",
                    "event": "departure",
                    "time": "8:30",
                    "x": 300,
                    "y": 240,
                },
            ],
            result
        )

class BuildTrainDiagramStopsTest(unittest.TestCase):

    def test_駅ごとに到着時刻と発車時刻を1つのデータにまとめられる(self):
        train = {
            "茨木発": "8:00",
            "大阪着": "8:10",
            "大阪発": "8:12",
            "神戸発": "8:30",
        }

        stations = [
            {
                "name": "茨木",
                "arrival_key": None,
                "departure_key": "茨木発",
            },
            {
                "name": "大阪",
                "arrival_key": "大阪着",
                "departure_key": "大阪発",
            },
            {
                "name": "神戸",
                "arrival_key": None,
                "departure_key": "神戸発",
            },
        ]

        result = build_train_diagram_stops(
            train=train,
            stations=stations,
            start_minutes=480,
            pixels_per_minute=10,
            top_margin=40,
            station_spacing=100,
        )

        self.assertEqual(
            [
                {
                    "station": "茨木",
                    "arrival": "",
                    "departure": "8:00",
                    "arrival_x": None,
                    "departure_x": 0,
                    "x": 0,
                    "y": 40,
                },
                {
                    "station": "大阪",
                    "arrival": "8:10",
                    "departure": "8:12",
                    "arrival_x": 100,
                    "departure_x": 120,
                    "x": 110,
                    "y": 140,
                },
                {
                    "station": "神戸",
                    "arrival": "",
                    "departure": "8:30",
                    "arrival_x": None,
                    "departure_x": 300,
                    "x": 300,
                    "y": 240,
                },
            ],
            result
        )

if __name__ == "__main__":
    unittest.main()