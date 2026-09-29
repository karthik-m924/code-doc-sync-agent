import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


def get_json(url: str, email: str, token: str) -> dict:
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    load_dotenv()
    site_url = os.getenv("ATLASSIAN_SITE_URL", "").rstrip("/")
    email = os.getenv("ATLASSIAN_EMAIL", "")
    token = os.getenv("ATLASSIAN_API_TOKEN", "")

    if not all((site_url, email, token)):
        raise SystemExit("Atlassian settings are missing from the local .env file.")

    try:
        issue = get_json(
            f"{site_url}/rest/api/3/issue/SCRUM-5?fields=summary,status",
            email,
            token,
        )
        page = get_json(
            f"{site_url}/wiki/api/v2/pages/425985",
            email,
            token,
        )
    except HTTPError as error:
        raise SystemExit(f"Atlassian request failed with HTTP {error.code}.") from None
    except URLError:
        raise SystemExit("Atlassian connection failed before receiving a response.") from None

    print(f"Jira access succeeded: {issue['key']} - {issue['fields']['summary']}")
    print(f"Confluence access succeeded: page {page['id']} - {page['title']}")


if __name__ == "__main__":
    main()
