"""Tests for reporting and listing lost / found items."""
import pytest

# Everything that differs between the lost and found versions of each route.
KINDS = [
    pytest.param(
        dict(report="/report-lost", listing="/lost-items", table="lost_items",
             date_field="date_lost", list_template="lost_items.html"),
        id="lost",
    ),
    pytest.param(
        dict(report="/report-found", listing="/found-items", table="found_items",
             date_field="date_found", list_template="found_items.html"),
        id="found",
    ),
]


def valid_form(kind, **overrides):
    form = {
        "item_name": "Blue Water Bottle",
        "category": "Personal Items",
        "description": "Dented, with a GMU sticker",
        "location": "Fenwick Library",
        kind["date_field"]: "2026-11-20",
    }
    form.update(overrides)
    return form


@pytest.mark.parametrize("kind", KINDS)
def test_report_form_page_loads(client, kind):
    assert client.get(kind["report"]).status_code == 200


@pytest.mark.parametrize("kind", KINDS)
def test_listing_page_loads_when_empty(client, kind):
    assert client.get(kind["listing"]).status_code == 200


# ---------- Valid reports ----------

@pytest.mark.parametrize("kind", KINDS)
def test_valid_report_is_saved(client, query, kind):
    response = client.post(kind["report"], data=valid_form(kind))

    assert response.status_code == 302
    assert response.headers["Location"].endswith(kind["listing"])

    rows = query(f"SELECT * FROM {kind['table']}")
    assert len(rows) == 1
    row = rows[0]
    assert row["item_name"] == "Blue Water Bottle"
    assert row["category"] == "Personal Items"
    assert row["description"] == "Dented, with a GMU sticker"
    assert row["location"] == "Fenwick Library"
    assert row[kind["date_field"]] == "2026-11-20"
    assert row["status"] == "Open"
    assert row["image"] is None              # photo is optional


@pytest.mark.parametrize("kind", KINDS)
def test_text_fields_are_trimmed(client, query, kind):
    client.post(kind["report"], data=valid_form(
        kind, item_name="  Keys  ", description=" On a red lanyard ", location=" JC "))

    row = query(f"SELECT * FROM {kind['table']}")[0]
    assert (row["item_name"], row["description"], row["location"]) == (
        "Keys", "On a red lanyard", "JC")


@pytest.mark.parametrize("kind", KINDS)
def test_lost_and_found_tables_are_separate(client, query, kind):
    client.post(kind["report"], data=valid_form(kind))

    other = "found_items" if kind["table"] == "lost_items" else "lost_items"
    assert query(f"SELECT * FROM {other}") == []


@pytest.mark.parametrize("kind", KINDS)
def test_sql_injection_text_is_stored_literally(client, query, kind):
    nasty = "x'); DROP TABLE lost_items; --"
    client.post(kind["report"], data=valid_form(kind, item_name=nasty))

    assert query(f"SELECT item_name FROM {kind['table']}")[0]["item_name"] == nasty
    query("SELECT * FROM lost_items")        # tables still exist
    query("SELECT * FROM found_items")


# ---------- Invalid reports ----------

@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("field", ["item_name", "description", "location"])
def test_blank_required_text_field_is_rejected(client, query, kind, field):
    response = client.post(kind["report"], data=valid_form(kind, **{field: "   "}))

    assert response.status_code == 400
    assert query(f"SELECT * FROM {kind['table']}") == []


@pytest.mark.parametrize("kind", KINDS)
def test_blank_date_is_rejected(client, query, kind):
    response = client.post(kind["report"], data=valid_form(kind, **{kind["date_field"]: ""}))

    assert response.status_code == 400
    assert query(f"SELECT * FROM {kind['table']}") == []


@pytest.mark.parametrize("kind", KINDS)
def test_missing_form_field_is_rejected(client, query, kind):
    form = valid_form(kind)
    del form["category"]

    response = client.post(kind["report"], data=form)

    assert response.status_code == 400
    assert query(f"SELECT * FROM {kind['table']}") == []


# ---------- Listing pages ----------

@pytest.mark.parametrize("kind", KINDS)
def test_listing_shows_newest_first(client, templates, kind):
    for name in ("First", "Second", "Third"):
        client.post(kind["report"], data=valid_form(kind, item_name=name))

    response = client.get(kind["listing"])

    assert response.status_code == 200
    template_name, context = templates[-1]
    assert template_name == kind["list_template"]
    assert [item["item_name"] for item in context["items"]] == ["Third", "Second", "First"]


# ---------- Login protection ----------
# These routes are currently public. This test describes the behavior you would
# want if reporting should require login. It is marked xfail so the suite stays
# green today; when you add login checks it will start to "pass unexpectedly",
# which (strict=True) fails the run as a reminder to delete the marker.

@pytest.mark.xfail(strict=True, reason="report/list routes do not require login yet")
@pytest.mark.parametrize("path", [
    "/report-lost", "/report-found", "/lost-items", "/found-items",
])
def test_item_pages_require_login(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
