from dataclasses import dataclass

import httpx


GITHUB_CREATE_REPOSITORY_URL = "https://api.github.com/user/repos"


@dataclass
class GithubRepositoryData:
    github_repository_id: int
    name: str


class GithubApiError(Exception):
    pass


async def create_repository(
    access_token: str,
    name: str,
    private: bool = True,
    description: str | None = None,
) -> GithubRepositoryData:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "name": name,
        "private": private,
        "auto_init": True,
    }

    if description is not None:
        payload["description"] = description

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=GITHUB_CREATE_REPOSITORY_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise GithubApiError("Failed to create GitHub repository") from exc

    response_data = response.json()
    github_repository_id = response_data.get("id")
    repository_name = response_data.get("name")

    if github_repository_id is None or repository_name is None:
        raise GithubApiError("GitHub did not return repository data")

    return GithubRepositoryData(
        github_repository_id=github_repository_id,
        name=repository_name,
    )
