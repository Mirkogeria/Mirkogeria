"""Scarica il calendario dei contributi GitHub in data/contributions.json.

Usa l'API GraphQL di GitHub con il token in GH_TOKEN (nella Action e il
GITHUB_TOKEN automatico, oppure il secret PROFILE_TOKEN se lo crei).
Solo libreria standard, nessuna dipendenza.
"""

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "contributions.json"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Manca GH_TOKEN: impossibile leggere i contributi.")
    body = json.dumps({"query": QUERY, "variables": {"login": PROFILE["username"]}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "readme-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise SystemExit(f"Errore GraphQL: {payload['errors']}")

    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [
        {"date": d["date"], "count": d["contributionCount"]}
        for w in cal["weeks"]
        for d in w["contributionDays"]
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "total": cal["totalContributions"],
                "days": days,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{len(days)} giorni, {cal['totalContributions']} contributi -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
