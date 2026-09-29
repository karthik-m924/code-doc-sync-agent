import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN is missing from the local .env file.")

    request = Request(
        "https://api.github.com/repos/karthik-m924/code-doc-sync-demo/commits/a13740a",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "code-doc-sync-agent",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            commit = json.load(response)
    except HTTPError as error:
        raise SystemExit(f"GitHub request failed with HTTP {error.code}.") from None
    except URLError:
        raise SystemExit("GitHub connection failed before receiving a response.") from None

    message = commit["commit"]["message"].splitlines()[0]
    print(f"GitHub access succeeded: {commit['sha'][:7]} - {message}")


if __name__ == "__main__":
    main()
