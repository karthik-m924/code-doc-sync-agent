import os

from dotenv import load_dotenv
from openai import AuthenticationError, OpenAI, OpenAIError


def main() -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key or api_key == "replace_with_your_project_api_key":
        raise SystemExit("OPENAI_API_KEY is missing from the local .env file.")

    client = OpenAI(api_key=api_key)

    try:
        client.models.list()
    except AuthenticationError:
        raise SystemExit("OpenAI authentication failed. Check or rotate the project API key.")
    except OpenAIError as error:
        raise SystemExit(f"OpenAI connection failed: {type(error).__name__}") from None

    print("OpenAI authentication succeeded. The project key is ready.")


if __name__ == "__main__":
    main()
