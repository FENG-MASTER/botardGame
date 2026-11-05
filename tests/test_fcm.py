from copy import deepcopy
import unittest
from boardgame.core import GameError
from boardgame.games.fcm.engine import FCM
from boardgame.games.fcm import board as geo


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.g = FCM()
        self.s = self.g.create(["a", "b"], {"scenario": {"board": geo.generated(2, 11)}}, 11)
        for pid, pos in [("a", [3, 0]), ("b", [8, 0])]:
            self.g.place_restaurant(
                self.s, pid, {"position": pos, "entrance": 0}, setup=True
            )
        self.s.update(
            phase="work",
            queue=["a", "b"],
            order=["a", "b"],
            reserves={"a": 100, "b": 100},
        )
        self.p = self.s["players"]["a"]

    def add(self, kind, active=False, pid="a"):
        eid = self.g.employee(self.s, pid, kind)
        if active:
            self.s["players"][pid]["active"].append(eid)
        return eid

    def do(self, **data):
        return self.g.apply(self.s, "a", {"type": "work", **data})

    def reject(self, action):
        with self.assertRaises(GameError):
            self.g.apply(deepcopy(self.s), "a", action)

    def test_recruit_and_train_new_employee(self):
        trainer = self.add("trainer", True)
        self.do(
            hire=[{"recruiter": "a:ceo", "kind": "kitchen_trainee"}],
            train=[{"trainer": trainer, "hire_index": 0, "path": ["burger_cook"]}],
        )
        self.assertTrue(any(e["kind"] == "burger_cook" for e in self.p["employees"]))
        self.assertIn("first_train", self.p["milestones"])
        self.assertEqual(self.g.salary(self.p), 0)

    def test_empty_round_advances_to_next_real_choice(self):
        self.g.apply(self.s, "a", {"type": "work"})
        events = self.g.apply(self.s, "b", {"type": "work"})
        self.assertEqual(self.s["round"], 2)
        self.assertEqual(self.s["phase"], "order")
        automated = [e for e in events if e["type"] == "decision_automated"]
        self.assertEqual(len(automated), 6)  # Two salaries, cleanups, structures.
        actor = self.g.actors(self.s)[0]
        events = self.g.apply(self.s, actor, {"type": "choose_order", "position": 1})
        self.assertEqual(self.s["phase"], "work")
        self.assertEqual(self.s["order"][1], actor)
        self.assertTrue(any(e.get("reason") == "only_position" for e in events))

    def test_cleanup_automates_forced_discard_but_keeps_freezer_choice(self):
        self.p["inventory"]["burger"] = 3
        other = self.s["players"]["b"]
        other["inventory"]["pizza"] = 2
        other["milestones"].append("first_discard")
        self.g.apply(self.s, "a", {"type": "work"})
        events = self.g.apply(self.s, "b", {"type": "work"})
        self.assertEqual(self.s["phase"], "cleanup")
        self.assertEqual(self.g.actors(self.s), ["b"])
        self.assertEqual(self.p["inventory"]["burger"], 0)
        self.assertIn("first_discard", self.p["milestones"])
        self.assertTrue(any(e.get("reason") == "no_freezer" for e in events))
        self.g.apply(self.s, "b", {"type": "cleanup", "keep": {"pizza": 1}})
        self.assertEqual(other["inventory"]["pizza"], 1)
        self.assertEqual(self.s["round"], 2)

    def test_zero_salary_keeps_optional_firing_and_tips_without_food(self):
        waitress = self.add("waitress", True)
        self.g.apply(self.s, "a", {"type": "work"})
        self.g.apply(self.s, "b", {"type": "work"})
        self.assertEqual(self.p["cash"], 3)
        self.assertEqual(self.s["phase"], "payday")
        self.assertEqual(self.g.actors(self.s), ["a"])
        self.assertEqual(self.g.salary(self.p), 0)
        self.g.apply(self.s, "a", {"type": "payday", "fire": [waitress]})
        self.assertEqual(self.s["round"], 2)

    def test_busy_marketer_salary_can_automate_only_when_affordable(self):
        self.add("campaign_manager")
        self.p["employees"][-1]["busy"] = "7"
        self.s["phase"] = "payday"
        self.assertIsNone(self.g.automatic_action(self.s, "a"))
        self.p["cash"] = 10
        before = self.s["bank"]
        self.g.advance_automatic(self.s)
        self.assertEqual(self.p["cash"], 5)
        self.assertEqual(self.s["bank"], before + 5)
        self.assertEqual(self.s["round"], 2)

    def test_automatic_cleanup_still_expires_campaigns(self):
        marketer = self.add("marketing_trainee")
        self.p["employees"][-1]["busy"] = "11"
        self.s["campaigns"] = [dict(id="11", kind="billboard", cells=[[1, 3]],
            player="a", employee=marketer, product="burger", remaining=1, eternal=False)]
        self.g.apply(self.s, "a", {"type": "work"})
        self.g.apply(self.s, "b", {"type": "work"})
        self.assertEqual(self.s["campaigns"], [])
        self.assertIsNone(self.p["employees"][-1]["busy"])
        self.assertEqual(self.s["phase"], "restructure")
        self.assertEqual(self.g.actors(self.s), ["a"])

    def test_introductory_auto_cleanup_and_finished_game_stop(self):
        self.s["introductory"] = True
        self.g.apply(self.s, "a", {"type": "work"})
        self.g.apply(self.s, "b", {"type": "work"})
        self.assertEqual(self.s["round"], 2)
        self.s.update(phase="work", queue=["a", "b"], bank=1)
        self.add("waitress", True)
        self.g.apply(self.s, "a", {"type": "work"})
        self.g.apply(self.s, "b", {"type": "work"})
        self.assertEqual(self.s["phase"], "finished")
        self.assertEqual(self.s["round"], 2)

    def test_out_of_stock_intermediate(self):
        trainer = self.add("trainer", True)
        self.s["stock"]["kitchen_trainee"] = 0
        self.do(
            hire=[{"recruiter": "a:ceo", "kind": "kitchen_trainee"}],
            train=[{"trainer": trainer, "hire_index": 0, "path": ["burger_cook"]}],
        )
        self.assertEqual(self.s["stock"]["kitchen_trainee"], 0)

    def test_stock_debt_must_be_trained(self):
        self.s["stock"]["kitchen_trainee"] = 0
        self.reject(
            {
                "type": "work",
                "hire": [{"recruiter": "a:ceo", "kind": "kitchen_trainee"}],
            }
        )

    def test_training_and_recruitment_limits(self):
        t = self.add("trainer", True)
        e = self.add("kitchen_trainee")
        self.reject(
            {
                "type": "work",
                "train": [
                    {
                        "trainer": t,
                        "employee": e,
                        "path": ["burger_cook", "burger_chef"],
                    }
                ],
            }
        )
        self.reject(
            {"type": "work", "hire": [{"recruiter": "a:ceo", "kind": "waitress"}] * 2}
        )
        self.reject(
            {
                "type": "work",
                "train": [{"trainer": t, "employee": t, "path": ["coach"]}],
            }
        )

    def test_coach_two_steps(self):
        t = self.add("coach", True)
        e = self.add("kitchen_trainee")
        self.s["stock"]["burger_cook"] = 0
        self.do(
            train=[
                {"trainer": t, "employee": e, "path": ["burger_cook", "burger_chef"]}
            ]
        )
        self.assertEqual(
            next(v["kind"] for v in self.p["employees"] if v["id"] == e), "burger_chef"
        )

    def test_unique_positions(self):
        self.add("guru")
        self.s["stock"]["guru"] = 1
        with self.assertRaises(GameError):
            self.add("guru")

    def test_unknown_fields_and_types(self):
        self.reject({"type": "work", "cash": 999})
        self.reject({"type": "work", "hire": "waitress"})
        self.reject({"type": "work", "hire": [{"recruiter": [], "kind": "waitress"}]})
        self.reject({"type": "work", "produce": [{"employee": "fake"}]})

    def test_same_round_milestones_and_close(self):
        self.g.grant(self.s, "a", "first_waitress")
        self.g.grant(self.s, "b", "first_waitress")
        self.assertIn("first_waitress", self.s["players"]["b"]["milestones"])
        self.g.new_round(self.s)
        self.assertIn("first_waitress", self.s["closed_milestones"])

    def test_production_bonus_is_on_beach(self):
        e = self.add("kitchen_trainee", True)
        self.do(produce=[{"employee": e, "product": "burger"}])
        self.assertEqual(self.p["inventory"]["burger"], 1)
        cook = next(v for v in self.p["employees"] if v["kind"] == "burger_cook")
        self.assertNotIn(cook["id"], self.p["active"])

    def test_secret_restructure_reveals_together(self):
        e = self.add("waitress")
        self.add("waitress", pid="b")  # Both players have an actual decision.
        self.s["phase"] = "restructure"
        self.s["pending"] = {}
        self.g.apply(self.s, "a", {"type": "restructure", "structure": {e: "a:ceo"}})
        view = self.g.observe(self.s, "b")
        self.assertEqual(view["pending"], {})
        self.assertNotIn(e, view["players"]["a"]["active"])
        self.g.apply(self.s, "b", {"type": "restructure", "structure": {}})
        self.assertIn(e, self.g.observe(self.s, "b")["players"]["a"]["active"])
        self.assertIn("first_waitress", self.p["milestones"])

    def test_structure_overflow_and_manager_nesting(self):
        es = [self.add("waitress") for _ in range(4)]
        self.s["phase"] = "restructure"
        self.g.apply(
            self.s,
            "a",
            {"type": "restructure", "structure": dict.fromkeys(es, "a:ceo")},
        )
        self.assertEqual(self.p["active"], ["a:ceo"])

    def test_first_placement_pass_second_forward(self):
        s = self.g.create(["a", "b", "c"], {}, 1)
        initial = list(s["order"])
        for pid in reversed(initial):
            self.g.apply(s, pid, {"type": "pass"})
        self.assertEqual(s["queue"], initial)
        self.assertEqual(s["placement_pass"], 2)
        with self.assertRaises(GameError):
            self.g.apply(s, initial[0], {"type": "pass"})

    def test_marketeer_busy_and_eternal(self):
        e = self.add("marketing_trainee", True)
        self.do(
            market=[
                {
                    "employee": e,
                    "campaign_id": "11",
                    "product": "burger",
                    "duration": 1,
                    "position": [4, 3],
                }
            ]
        )
        campaign = self.s["campaigns"][0]
        self.assertTrue(campaign["eternal"])
        self.assertIsNone(campaign["remaining"])
        self.assertEqual(
            next(v for v in self.p["employees"] if v["id"] == e)["busy"], "11"
        )
        self.assertIn("first_burger_marketed", self.p["milestones"])
        self.assertIn("first_billboard", self.p["milestones"])

    def test_marketing_after_dinner_and_caps(self):
        h = self.s["board"]["houses"][0]
        h["demand"] = ["pizza", "pizza"]
        self.s["campaigns"] = [
            dict(
                id="1",
                kind="radio",
                cells=[[1, 3]],
                player="a",
                employee="gone",
                product="burger",
                remaining=1,
                eternal=False,
            )
        ]
        self.p["milestones"].append("first_radio")
        self.g.marketing(self.s)
        self.assertEqual(h["demand"], ["pizza", "pizza", "burger"])
        self.assertEqual(self.s["campaigns"], [])

    def test_freezer_not_immediate(self):
        self.p["inventory"]["burger"] = 4
        with self.assertRaises(GameError):
            self.g.cleanup(self.s, "a", {"keep": {"burger": 1}})
        self.g.cleanup(self.s, "a", {"keep": {}})
        self.assertIn("first_discard", self.p["milestones"])
        self.assertEqual(sum(self.p["inventory"].values()), 0)
        self.p["inventory"]["burger"] = 4
        self.g.cleanup(self.s, "a", {"keep": {"burger": 4}})
        self.assertEqual(self.p["inventory"]["burger"], 4)

    def test_salary_discount_firing_and_bank(self):
        self.add("coach")
        self.add("burger_cook")
        self.p["cash"] = 20
        before = self.s["bank"]
        self.g.payday(self.s, "a", {"fire": []})
        self.assertEqual(self.p["cash"], 10)
        self.assertEqual(self.s["bank"], before + 10)

    def test_unaffordable_busy_firing(self):
        e = self.add("campaign_manager")
        self.p["employees"][-1]["busy"] = "7"
        t = self.add("coach")
        with self.assertRaises(GameError):
            self.g.payday(self.s, "a", {"fire": [e]})
        self.g.payday(self.s, "a", {"fire": [e, t]})
        self.assertEqual(len(self.p["employees"]), 1)

    def test_recruitment_discount_survives_firing(self):
        e = self.add("recruiting_manager", True)
        self.add("trainer")
        self.do()
        self.assertEqual(self.p["hire_discount"], 10)
        self.s["log"] = []
        self.g.payday(self.s, "a", {"fire": [e]})
        self.assertEqual(self.p["cash"], 0)

    def test_dinner_all_demand_required(self):
        h = self.s["board"]["houses"][0]
        h["demand"] = ["burger", "pizza"]
        self.p["inventory"]["burger"] = 1
        self.g.dinner(self.s)
        self.assertEqual(h["demand"], ["burger", "pizza"])
        self.assertEqual(self.p["cash"], 0)

    def test_price_distance_tie_waitress_and_garden(self):
        h = self.s["board"]["houses"][0]
        h["garden"] = True
        h["demand"] = ["burger"]
        self.p["inventory"]["burger"] = 1
        self.p["milestones"].append("first_burger_marketed")
        self.g.dinner(self.s)
        self.assertEqual(self.p["cash"], 25)
        self.assertEqual(h["demand"], [])
        self.assertIn("first_twenty", self.p["milestones"])

    def test_cfo_rounding_and_hundred_delayed(self):
        self.add("cfo", True)
        self.add("waitress", True)
        self.g.dinner(self.s)
        self.assertEqual(self.p["cash"], 5)  # 3 + ceil(1.5)
        self.s["log"] = []
        self.p["employees"] = [v for v in self.p["employees"] if v["kind"] != "cfo"]
        self.p["cash"] = 99
        self.g.dinner(self.s)
        self.assertEqual(self.p["cash"], 102)
        self.assertIn("first_hundred", self.p["milestones"])

    def test_second_bank_break_finishes_before_salary(self):
        self.s["bank"] = 1
        self.s["bank_breaks"] = 1
        self.add("waitress", True)
        self.add("trainer")
        self.g.dinner(self.s)
        self.assertEqual(self.s["phase"], "finished")
        self.assertEqual(self.p["cash"], 3)

    def test_reserve_tie_prefers_more_slots_next_round(self):
        self.s["reserves"] = {"a": 100, "b": 300}
        self.s["bank"] = 1
        self.g.pay(self.s, "a", 2)
        self.assertEqual(self.s["bank"], 399)
        self.assertEqual(self.s["ceo_slots"], 3)
        self.assertEqual(self.s["next_ceo_slots"], 4)

    def test_road_distance_counts_tile_borders(self):
        b = self.s["board"]
        self.assertEqual(geo.distance(b, [[3, 0]], [[0, 0], [1, 0], [0, 1], [1, 1]]), 0)
        self.assertEqual(geo.distance(b, [[8, 0]], [[0, 0], [1, 0], [0, 1], [1, 1]]), 1)

    def test_bridge_cannot_turn(self):
        b = {"width": 5, "height": 5, "cells": [["empty"] * 5 for _ in range(5)]}
        for i in range(5):
            b["cells"][2][i] = "road"
            b["cells"][i][2] = "road"
        b["cells"][2][2] = "bridge"
        d = geo.distances(b, [[0, 1]])
        self.assertIn((4, 2, ""), d)
        self.assertNotIn((2, 0, ""), d)

    def test_buyer_no_uturn(self):
        e = self.add("cart_operator", True)
        self.reject(
            {
                "type": "work",
                "produce": [{"employee": e, "route": [[2, 0], [2, 1], [2, 0]]}],
            }
        )

    def test_expansions_rejected(self):
        with self.assertRaises(GameError):
            self.g.create(["a", "b"], {"coffee": True}, 0)

    def test_introductory_finishes_on_first_break(self):
        self.s["introductory"] = True
        self.s["bank"] = 1
        self.add("waitress", True)
        self.g.dinner(self.s)
        self.assertTrue(self.s["finished"])
        self.assertEqual(self.s["bank_breaks"], 1)
        breaks = [e for e in self.s["log"] if e["type"] == "bank_broken"]
        self.assertEqual(len(breaks), 1)

    def test_competition_uses_unit_price_not_total(self):
        h = self.s["board"]["houses"][0]
        h["demand"] = ["burger"] * 3
        for p in self.s["players"].values():
            p["inventory"]["burger"] = 3
        # b is one tile farther away; discount manager makes its price 7.
        self.add("discount_manager", True, "b")
        self.g.dinner(self.s)
        self.assertEqual(self.p["inventory"]["burger"], 3)
        self.assertEqual(self.s["players"]["b"]["cash"], 21)

    def test_build_house_and_local_restaurant_delay(self):
        self.g.develop(self.s, {"position": [3, 4], "new_house_id": 1})
        house = next(h for h in self.s["board"]["houses"] if h["id"] == 1)
        self.assertTrue(house["garden"])
        self.g.place_restaurant(
            self.s, "a", {"position": [8, 5], "entrance": 0}, manager="local_manager"
        )
        self.assertFalse(self.p["restaurants"][-1]["open"])
        self.g.new_round(self.s)
        self.assertTrue(self.p["restaurants"][-1]["open"])
