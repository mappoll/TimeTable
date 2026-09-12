import unittest

from timetable_service import build_train_diagram_stops, stack_overlapping_stops


class StopOverlapTest(unittest.TestCase):
    def trains(self, positions, station="大阪"):
        return [{"stops": [{"station": station, "x": x, "offset_y": 99}]} for x in positions]

    def offsets(self, trains):
        return [t["stops"][0]["offset_y"] for t in trains]

    def test_different_arrivals_with_same_midpoint(self):
        stations = [{"name": "大阪", "arrival_key": "大阪着", "departure_key": "大阪発"}]
        trains = []
        for arrival, departure in [("18:50", "18:55"), ("18:52", "18:53")]:
            stops = build_train_diagram_stops(
                {"大阪着": arrival, "大阪発": departure}, stations,
                start_minutes=18*60, pixels_per_minute=18, top_margin=50, station_spacing=78)
            trains.append({"stops": stops})
        self.assertEqual(945, trains[0]["stops"][0]["x"])
        self.assertEqual(trains[0]["stops"][0]["x"], trains[1]["stops"][0]["x"])
        self.assertEqual([-17, 17], self.offsets(stack_overlapping_stops(trains)))

    def test_separated_or_touching_boxes_stay_on_baseline(self):
        for gap in [34, 50]:
            with self.subTest(gap=gap):
                self.assertEqual([0, 0], self.offsets(stack_overlapping_stops(self.trains([100, 100+gap]))))

    def test_different_stations_are_independent(self):
        trains = self.trains([100]) + self.trains([100], "尼崎")
        self.assertEqual([0, 0], self.offsets(stack_overlapping_stops(trains)))

    def test_chain_of_three_is_sorted_by_x(self):
        trains = self.trains([160, 100, 130])
        self.assertEqual([34, -34, 0], self.offsets(stack_overlapping_stops(trains)))

    def test_identical_times_still_stack(self):
        trains = self.trains([100, 100])
        for t in trains:
            t["stops"][0].update(arrival="18:50", departure="18:50")
        self.assertEqual([-17, 17], self.offsets(stack_overlapping_stops(trains)))

    def test_separate_groups_and_isolated_box(self):
        trains = self.trains([100, 120, 200, 220, 300])
        self.assertEqual([-17, 17, -17, 17, 0], self.offsets(stack_overlapping_stops(trains)))

    def test_custom_width_and_step_and_repeat(self):
        trains = self.trains([100, 130, 160, 190])
        self.assertEqual([-60, -20, 20, 60], self.offsets(stack_overlapping_stops(trains, stack_step=40, box_width=31)))
        self.assertEqual([0, 0, 0, 0], self.offsets(stack_overlapping_stops(trains, box_width=30)))
        self.assertEqual([], stack_overlapping_stops([]))
