"""GET /items."""

from __future__ import annotations

from fastapi.testclient import TestClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ITEMS = "/api/v1/items"

ACCOUNT = {"email": "rafael@example.com", "password": "a good password"}
OTHER = {"email": "someone@example.com", "password": "another password"}


def sign_in(client: TestClient, account: dict[str, str]) -> dict[str, str]:
    client.post(REGISTER, json=account)
    response = client.post(LOGIN, json=account)
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def add(client: TestClient, headers: dict[str, str], name: str, **rest: str) -> None:
    client.post(ITEMS, headers=headers, json={"name": name, **rest})


def test_lists_the_items(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    add(client, headers, "GitHub", username="rafael")

    response = client.get(ITEMS, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "GitHub"


def test_no_secret_field_appears(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    add(client, headers, "GitHub", password="K7#mQ2vX!pL9", notes="a note")

    body = client.get(ITEMS, headers=headers).json()

    assert set(body["data"][0]) == {
        "id",
        "name",
        "username",
        "url",
        "created_at",
        "updated_at",
    }


def test_it_is_sorted_by_name(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    for name in ["Zulip", "AWS", "GitHub"]:
        add(client, headers, name)

    body = client.get(ITEMS, headers=headers).json()
    names = [row["name"] for row in body["data"]]

    assert names == ["AWS", "GitHub", "Zulip"]


def test_the_meta_block_counts_everything(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    for number in range(7):
        add(client, headers, f"service-{number}")

    body = client.get(ITEMS, headers=headers, params={"per_page": 3}).json()

    assert body["meta"] == {"page": 1, "per_page": 3, "total": 7, "pages": 3}
    assert len(body["data"]) == 3


def test_paging_neither_repeats_nor_drops_an_item(client: TestClient) -> None:
    """Items sharing a name are the case the id tiebreak exists for."""
    headers = sign_in(client, ACCOUNT)
    for _ in range(5):
        add(client, headers, "GitHub")

    seen = []
    for page in (1, 2, 3):
        body = client.get(ITEMS, headers=headers, params={"page": page, "per_page": 2}).json()
        seen.extend(row["id"] for row in body["data"])

    assert len(seen) == 5
    assert len(set(seen)) == 5


def test_a_page_past_the_end_is_empty_not_an_error(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    add(client, headers, "GitHub")

    response = client.get(ITEMS, headers=headers, params={"page": 9})

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_an_empty_list_reports_zero(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)

    body = client.get(ITEMS, headers=headers).json()

    assert body["data"] == []
    assert body["meta"]["total"] == 0
    assert body["meta"]["pages"] == 0


def test_search_matches_name_and_username(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    add(client, headers, "GitHub", username="rafael")
    add(client, headers, "AWS", username="git-user")
    add(client, headers, "Zulip", username="someone")

    body = client.get(ITEMS, headers=headers, params={"q": "git"}).json()
    names = {row["name"] for row in body["data"]}

    assert names == {"GitHub", "AWS"}
    assert body["meta"]["total"] == 2


def test_a_percent_in_the_search_is_a_character_not_a_wildcard(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    add(client, headers, "GitHub")
    add(client, headers, "100% legit")

    body = client.get(ITEMS, headers=headers, params={"q": "%"}).json()
    names = [row["name"] for row in body["data"]]

    assert names == ["100% legit"]


def test_another_users_items_are_invisible(client: TestClient) -> None:
    mine = sign_in(client, ACCOUNT)
    theirs = sign_in(client, OTHER)
    add(client, mine, "GitHub")
    add(client, theirs, "Their Bank")

    body = client.get(ITEMS, headers=mine).json()
    names = [row["name"] for row in body["data"]]

    assert names == ["GitHub"]
    assert body["meta"]["total"] == 1


def test_without_a_token_it_is_unauthenticated(client: TestClient) -> None:
    response = client.get(ITEMS)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_page_zero_is_rejected(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)

    response = client.get(ITEMS, headers=headers, params={"page": 0})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_an_oversized_page_is_rejected(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)

    response = client.get(ITEMS, headers=headers, params={"per_page": 500})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
