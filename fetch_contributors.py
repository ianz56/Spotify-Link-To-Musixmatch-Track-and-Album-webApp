import json
import os
import sys

import requests


def fetch_contributors():
    token = os.environ.get("CROWDIN_PERSONAL_TOKEN")
    project_id = os.environ.get("CROWDIN_PROJECT_ID")

    if not token or not project_id:
        print(
            "Error: CROWDIN_PERSONAL_TOKEN or CROWDIN_PROJECT_ID not found in environment variables."
        )
        sys.exit(1)

    url = f"https://api.crowdin.com/api/v2/projects/{project_id}/members"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    contributors = []
    limit = 500
    offset = 0

    while True:
        params = {"limit": limit, "offset": offset}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            users = data.get("data", [])
            if not users:
                break

            for user_entry in users:
                user = user_entry.get("data", {})
                contributors.append(
                    {
                        "username": user.get("username"),
                        "full_name": user.get("fullName"),
                        "avatar_url": user.get("avatarUrl"),
                        "roles": user.get(
                            "roles", []
                        ),  # Might be useful to filter translators vs managers
                        # Note: Language detailed stats might require a different endpoint (reports),
                        # but simple member list is a good start.
                    }
                )

            if len(users) < limit:
                break

            offset += limit

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from Crowdin: {e}")
            sys.exit(1)

    # Save to JSON
    output_file = "contributors.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(contributors, f, indent=2, ensure_ascii=False)

    print(
        f"Successfully fetched {len(contributors)} contributors and saved to {output_file}"
    )


if __name__ == "__main__":
    fetch_contributors()
