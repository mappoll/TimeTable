import unittest
import os
from unittest.mock import patch

with patch.dict(os.environ, {"TIMETABLE_AUTH_ENABLED": "0"}):
    from app import create_app, RETURN_STATIONS
    app = create_app()
from timetable_service import (
    build_train_diagram_points, build_train_diagram_stops,
    calculate_timeline_range, generate_time_ticks, return_time_to_minutes,
)


class ReturnDiagramTest(unittest.TestCase):
    def test_midnight_coordinates_keep_travel_order_and_original_labels(self):
        train = {"train_type": "普通", "神戸発": "23:55",
                 "大阪着": "0:30", "大阪発": "0:32", "茨木発": "0:55"}
        start, end = calculate_timeline_range([train], return_time_to_minutes)
        self.assertEqual((1435, 1495), (start, end))
        args = dict(train=train, stations=RETURN_STATIONS, start_minutes=start,
                    pixels_per_minute=18, top_margin=50, station_spacing=78,
                    time_converter=return_time_to_minutes)
        points = build_train_diagram_points(**args)
        self.assertEqual([0, 630, 666, 1080], [p["x"] for p in points])
        stops = build_train_diagram_stops(**args)
        self.assertEqual(["神戸", "大阪", "茨木"], [s["station"] for s in stops])
        self.assertEqual("0:30", stops[1]["arrival"])
        self.assertEqual(648, stops[1]["x"])
        self.assertEqual("翌日 0:00", generate_time_ticks(start, end)[1]["label"])

    def test_return_renders_diagram_with_requested_time_before_first_train(self):
        train = {"train_type": "普通", "神戸発": "18:10", "茨木発": "19:00"}
        with patch("app.load_trains", return_value=[train]):
            response = app.test_client().post("/", data={"direction": "return", "target_time": "18:00"})
        self.assertEqual(200, response.status_code)
        html = response.get_data(as_text=True)
        self.assertIn('id="timetable-diagram"', html)
        self.assertIn("希望出発 18:00", html)
        self.assertIn('data-base-x="18"', html)
        self.assertLess(html.index('data-station="神戸"'), html.index('data-station="茨木"'))

    def test_real_data_evening_midnight_and_outbound_render(self):
        client = app.test_client()
        for direction, time in [("return", "18:00"), ("return", "23:10"),
                                ("return", "23:47"), ("outbound", "09:15")]:
            with self.subTest(direction=direction, time=time):
                response = client.post("/", data={"direction": direction, "target_time": time})
                self.assertEqual(200, response.status_code)
                self.assertIn('id="timetable-diagram"', response.get_data(as_text=True))

    def test_return_outside_service_range_shows_error(self):
        response = app.test_client().post("/", data={"direction": "return", "target_time": "14:59"})
        self.assertEqual(200, response.status_code)
        self.assertIn("15:00から終電", response.get_data(as_text=True))
        self.assertNotIn('id="timetable-diagram"', response.get_data(as_text=True))

    def test_daytime_is_not_mistaken_for_next_day_and_last_train_is_enforced(self):
        self.assertEqual(884, return_time_to_minutes("14:44"))
        for time in ["23:48", "00:00"]:
            response = app.test_client().post("/", data={"direction": "return", "target_time": time})
            self.assertNotIn('id="timetable-diagram"', response.get_data(as_text=True))
