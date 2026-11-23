"""Tests for photo uploads: save_image() directly and through the report forms."""
import io
from pathlib import Path

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app import save_image

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def make_image_bytes(fmt="PNG", size=(20, 20), mode="RGB", color="red"):
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, fmt)
    return buffer.getvalue()


def upload(data, filename):
    """Wrap bytes the way Flask hands an uploaded file to save_image()."""
    return FileStorage(stream=io.BytesIO(data), filename=filename)


def saved_files(app):
    return list(Path(app.config["UPLOAD_FOLDER"]).glob("*"))


# ---------- save_image(): accepted files ----------

@pytest.mark.parametrize("fmt, filename", [
    ("PNG", "photo.png"),
    ("JPEG", "photo.jpg"),
    ("JPEG", "photo.JPEG"),          # extension check is case-insensitive
    ("WEBP", "photo.webp"),
])
def test_valid_image_is_saved_as_jpeg(app, fmt, filename):
    name = save_image(upload(make_image_bytes(fmt), filename))

    assert name.endswith(".jpg")
    path = Path(app.config["UPLOAD_FOLDER"]) / name
    assert path.exists()
    with Image.open(path) as img:
        assert img.format == "JPEG"


def test_png_with_transparency_is_converted(app):
    data = make_image_bytes("PNG", mode="RGBA", color=(255, 0, 0, 128))

    name = save_image(upload(data, "transparent.png"))

    with Image.open(Path(app.config["UPLOAD_FOLDER"]) / name) as img:
        assert img.mode == "RGB"


def test_saved_filename_is_random_not_the_original(app):
    first = save_image(upload(make_image_bytes(), "my-secret-name.png"))
    second = save_image(upload(make_image_bytes(), "my-secret-name.png"))

    assert "my-secret-name" not in first
    assert first != second


def test_upload_folder_is_created_if_missing(app):
    assert not Path(app.config["UPLOAD_FOLDER"]).exists()

    save_image(upload(make_image_bytes(), "photo.png"))

    assert Path(app.config["UPLOAD_FOLDER"]).exists()


@pytest.mark.parametrize("file", [None, FileStorage(stream=io.BytesIO(b""), filename="")])
def test_no_file_returns_none(app, file):
    assert save_image(file) is None
    assert saved_files(app) == []


# ---------- save_image(): rejected files ----------

@pytest.mark.parametrize("filename", ["anim.gif", "notes.txt", "run.exe", "photo", "photo.png.exe"])
def test_disallowed_extension_is_rejected(app, filename):
    with pytest.raises(ValueError, match="Only JPG, PNG, and WEBP"):
        save_image(upload(make_image_bytes(), filename))

    assert saved_files(app) == []


def test_text_file_renamed_to_png_is_rejected(app):
    with pytest.raises(ValueError, match="Invalid image file"):
        save_image(upload(b"this is not an image", "fake.png"))

    assert saved_files(app) == []


def test_truncated_image_is_rejected(app):
    data = make_image_bytes("PNG", size=(200, 200))[:60]

    with pytest.raises(ValueError, match="Invalid image file"):
        save_image(upload(data, "broken.png"))

    assert saved_files(app) == []


def test_image_with_too_many_pixels_is_rejected(app):
    # 5001 x 4001 = 20,004,001 pixels, just over the 20,000,000 limit.
    # A solid color compresses to a tiny file, so this is cheap to build.
    data = make_image_bytes("PNG", size=(5001, 4001))

    with pytest.raises(ValueError, match="too large"):
        save_image(upload(data, "huge.png"))

    assert saved_files(app) == []


def test_image_at_pixel_limit_is_accepted(app):
    data = make_image_bytes("PNG", size=(5000, 4000))   # exactly 20,000,000

    assert save_image(upload(data, "big.png")).endswith(".jpg")


# ---------- Through the report forms ----------

FORMS = [
    pytest.param("/report-lost", "date_lost", "lost_items", id="lost"),
    pytest.param("/report-found", "date_found", "found_items", id="found"),
]


def form_with_photo(date_field, photo):
    return {
        "item_name": "Backpack",
        "category": "Bags",
        "description": "Black, one broken zipper",
        "location": "Johnson Center",
        date_field: "2026-11-21",
        "image": photo,
    }


@pytest.mark.parametrize("path, date_field, table", FORMS)
def test_report_with_photo_stores_filename(client, app, query, path, date_field, table):
    photo = (io.BytesIO(make_image_bytes()), "bag.png")

    response = client.post(path, data=form_with_photo(date_field, photo),
                           content_type="multipart/form-data")

    assert response.status_code == 302
    filename = query(f"SELECT image FROM {table}")[0]["image"]
    assert filename.endswith(".jpg")
    assert (Path(app.config["UPLOAD_FOLDER"]) / filename).exists()


@pytest.mark.parametrize("path, date_field, table", FORMS)
def test_report_with_bad_photo_is_rejected(client, app, query, path, date_field, table):
    photo = (io.BytesIO(b"not really an image"), "bag.png")

    response = client.post(path, data=form_with_photo(date_field, photo),
                           content_type="multipart/form-data")

    assert response.status_code == 400
    assert b"Invalid image file" in response.data
    assert query(f"SELECT * FROM {table}") == []     # nothing saved
    assert saved_files(app) == []


@pytest.mark.parametrize("path, date_field, table", FORMS)
def test_report_with_wrong_file_type_is_rejected(client, query, path, date_field, table):
    photo = (io.BytesIO(make_image_bytes("GIF")), "bag.gif")

    response = client.post(path, data=form_with_photo(date_field, photo),
                           content_type="multipart/form-data")

    assert response.status_code == 400
    assert query(f"SELECT * FROM {table}") == []


@pytest.mark.parametrize("path, date_field, table", FORMS)
def test_upload_over_5mb_is_rejected(client, query, path, date_field, table):
    photo = (io.BytesIO(b"0" * (MAX_UPLOAD_BYTES + 1)), "huge.png")

    response = client.post(path, data=form_with_photo(date_field, photo),
                           content_type="multipart/form-data")

    assert response.status_code == 413
    assert query(f"SELECT * FROM {table}") == []


@pytest.mark.parametrize("path, date_field, table", FORMS)
def test_invalid_text_fields_do_not_save_the_photo(client, app, path, date_field, table):
    form = form_with_photo(date_field, (io.BytesIO(make_image_bytes()), "bag.png"))
    form["item_name"] = ""

    response = client.post(path, data=form, content_type="multipart/form-data")

    assert response.status_code == 400
    assert saved_files(app) == []
