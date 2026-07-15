import unittest

from src.combat.AbyssLogAnalyzer import format_trace_report, parse_abyss_traces


class TestAbyssLogAnalyzer(unittest.TestCase):
    def test_parses_baicang_route_until_return_switch(self):
        traces = parse_abyss_traces(
            [
                "2026-07-16 10:00:00,000 INFO planner:strict route locked: "
                "Baicang abyss opener / Sakiri groups enemies",
                "2026-07-16 10:00:00,100 INFO planner:planner action Sakiri -> Sakiri_skill, "
                "tags [], reason test",
                "2026-07-16 10:00:01,000 INFO planner:strict route skips optional step: "
                "Baicang abyss opener / Hania Q",
                "2026-07-16 10:00:02,000 INFO planner:strict route fulfilled: "
                "Baicang abyss opener",
                "2026-07-16 10:00:02,100 INFO planner:planner switch Daphneel -> Baicang, "
                "priority 1, reason switch request: return Baicang",
            ]
        )

        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].status, "fulfilled")
        self.assertEqual(traces[0].action_sequence(), ["Sakiri:Sakiri_skill"])
        self.assertEqual(sum(event.kind == "skip" for event in traces[0].events), 1)
        self.assertEqual(traces[0].diagnosis(), [])

    def test_parses_chiz_reactions_and_next_cycle(self):
        traces = parse_abyss_traces(
            [
                "2026-07-16 10:00:00,000 INFO planner:strict route locked: "
                "Chiz Yingxu abyss opener / Jiuyuan E",
                "2026-07-16 10:00:01,000 INFO planner:strict route completed entry reaction "
                "Zero -> Jiuyuan: Chiz Yingxu abyss opener / Creation",
                "2026-07-16 10:00:02,000 INFO planner:strict route completed entry reaction "
                "Zero -> Yi: Chiz Yingxu abyss opener / Delay",
                "2026-07-16 10:00:03,000 INFO planner:strict route fulfilled: "
                "Chiz Yingxu abyss opener",
                "2026-07-16 10:00:03,100 INFO planner:strict route locked: "
                "Chiz Yingxu abyss cycle / Zero Q",
            ]
        )

        self.assertEqual(len(traces), 2)
        self.assertEqual(traces[0].status, "fulfilled")
        self.assertEqual(traces[0].reaction_sequence(), ["Zero->Jiuyuan", "Zero->Yi"])
        self.assertEqual(traces[1].route, "Chiz Yingxu abyss cycle")
        self.assertIn("route status is pending", traces[1].diagnosis())
        self.assertIn("missing reaction Zero->Jiuyuan", traces[1].diagnosis())

    def test_expired_route_is_reported(self):
        traces = parse_abyss_traces(
            [
                "2026-07-16 10:00:00,000 INFO planner:strict route locked: "
                "Chiz Yingxu abyss cycle / Zero E",
                "2026-07-16 10:00:35,000 WARNING planner:strict route deadline expired, "
                "route unlocked: Chiz Yingxu abyss cycle / Zero E",
            ]
        )

        self.assertEqual(traces[0].status, "expired")
        self.assertIn("status: expired", format_trace_report(traces))
        self.assertIn("route status is expired", traces[0].diagnosis())

    def test_irrelevant_log_returns_empty_report(self):
        traces = parse_abyss_traces(["2026-07-16 10:00:00,000 INFO app:started"])

        self.assertEqual(format_trace_report(traces), "No abyss team route traces found.")


if __name__ == "__main__":
    unittest.main()
