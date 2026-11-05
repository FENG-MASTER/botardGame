"""Run with uv run --locked python -m examples.play_agents; two API agents complete a real game.
This intentionally simple policy hires waitresses and earns tips. It exercises the
whole turn loop and bank breaks, not a competitive FCM strategy.
"""

import argparse
import uuid
from boardgame.client import Client


def choose(identity, observation, options):
    s = observation["state"]
    p = s["players"][identity]
    phase = s["phase"]
    if phase == "setup_restaurants":
        return options["placements"][0]
    if phase == "reserve":
        return dict(type="choose_reserve", amount=options.get("reserve_choices", [100])[0])
    if phase == "restructure":
        employees = [e for e in p["employees"] if e["kind"] == "waitress"][
            : s["ceo_slots"]
        ]
        return dict(
            type="restructure",
            structure={e["id"]: identity + ":ceo" for e in employees},
        )
    if phase == "order":
        return dict(type="choose_order", position=options["available_positions"][0])
    if phase == "work":
        hire = (
            []
            if len(p["employees"]) >= 4 or s["stock"]["waitress"] <= 0
            else [dict(recruiter=identity + ":ceo", kind="waitress")]
        )
        return dict(type="work", hire=hire)
    if phase == "payday":
        return dict(type="payday", fire=[])
    if phase == "cleanup":
        return dict(type="cleanup", keep={})
    raise RuntimeError(phase)


def run(base):
    clients = [Client(base), Client(base)]
    identities = [c.register(f"Waitress agent {i + 1}") for i, c in enumerate(clients)]
    room = clients[0].request("POST", "/v1/rooms", dict(game="fcm", capacity=2, seed=7))
    rid = room["id"]
    clients[1].request(
        "POST", f"/v1/rooms/{rid}/join", dict(join_code=room["join_code"])
    )
    room = clients[0].observe(rid)
    clients[0].request(
        "POST",
        f"/v1/rooms/{rid}/start",
        dict(expected_version=room["version"]),
        uuid.uuid4().hex,
    )
    for _ in range(2000):
        progressed = False
        for c, identity in zip(clients, identities):
            obs = c.observe(rid)
            if obs["status"] == "finished":
                print(
                    f"Finished room {rid}, round {obs['state']['round']}, winner {obs['state']['winner']}"
                )
                print(
                    {
                        p: company["cash"]
                        for p, company in obs["state"]["players"].items()
                    }
                )
                return obs
            options = c.actions(rid)
            if options["can_act"]:
                c.submit(rid, options["version"], choose(identity["id"], obs, options))
                progressed = True
        if not progressed:
            raise RuntimeError("No agent can act")
    raise RuntimeError("Game did not finish within action budget")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    run(parser.parse_args().url)
