"""Tests for reporting and listing lost / found items, and the category filter."""
import pytest

from conftest import redirect_path

# Everything that differs between the lost and found versions of each route.
KINDS = [
    pytest.param(
        dict(report="/report-lost", listing="/lost-items", table="lost_items",
             date_field="date_lost", list_template="lost_items.html",
             after_post="/lost-items"),
        id="lost",
    ),
    pytest.param(
        dict(report="/report-found", listing="/found-items", table="found_items",
             date_field="date_found", list_template="found_items.html",
             after_post="/main"),            # found reports go back to the main page
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


@pytest.fixture(autouse=True)
def _logged_in(log_in):
    """/report-found requires login, so log in for every test in this file.
    (The login-protection tests at the bottom use a fresh client instead.)"""
    log_in()


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
    assert redirect_path(response) == kind["after_post"]

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


# ---------- Category filter (?category=...) ----------

@pytest.fixture
def three_items(add_item):
    def run(table):
        add_item(table, item_name="A", category="Bags")
        add_item(table, item_name="B", category="Keys")
        add_item(table, item_name="C", category="Bags")
    return run


def shown(templates):
    """(item names, selected_category) from the most recently rendered page."""
    _, context = templates[-1]
    return [i["item_name"] for i in context["items"]], context["selected_category"]


@pytest.mark.parametrize("kind", KINDS)
def test_category_filter_keeps_only_matching_items(client, templates, three_items, kind):
    three_items(kind["table"])

    client.get(kind["listing"], query_string={"category": "Bags"})

    assert shown(templates) == (["C", "A"], "Bags")      # newest first


@pytest.mark.parametrize("kind", KINDS)
def test_no_category_shows_everything(client, templates, three_items, kind):
    three_items(kind["table"])

    client.get(kind["listing"])

    assert shown(templates) == (["C", "B", "A"], "")


@pytest.mark.parametrize("kind", KINDS)
def test_empty_category_shows_everything(client, templates, three_items, kind):
    three_items(kind["table"])

    client.get(kind["listing"], query_string={"category": ""})

    assert shown(templates) == (["C", "B", "A"], "")


@pytest.mark.parametrize("kind", KINDS)
def test_unknown_category_shows_nothing(client, templates, three_items, kind):
    three_items(kind["table"])

    client.get(kind["listing"], query_string={"category": "Spaceships"})

    assert shown(templates) == ([], "Spaceships")


@pytest.mark.parametrize("kind", KINDS)
def test_category_filter_is_safe_from_sql_injection(client, templates, three_items, kind):
    three_items(kind["table"])

    client.get(kind["listing"], query_string={"category": "' OR '1'='1"})

    assert shown(templates)[0] == []         # treated as plain text, matches nothing


# ---------- Login protection ----------
# report-found already redirects to the login page when logged out, so these
# pass today. The other pages are public right now; the xfail tests describe
# what you would want if every page should need login. strict=True: when you
# add the checks they will "unexpectedly pass", which fails the run until you
# delete the xfail marker.

@pytest.mark.parametrize("method", ["get", "post"])
def test_report_found_requires_login(app, query, method):
    fresh_client = app.test_client()                    # not logged in

    response = getattr(fresh_client, method)("/report-found", data=valid_form(KINDS[1].values[0]))

    assert redirect_path(response) == "/"
    assert query("SELECT * FROM found_items") == []


@pytest.mark.xfail(strict=True, reason="these routes do not require login yet")
@pytest.mark.parametrize("path", ["/report-lost", "/lost-items", "/found-items"])
def test_other_item_pages_require_login(app, path):
    response = app.test_client().get(path)           # not logged in

    assert response.status_code == 302
    assert redirect_path(response) == "/"
