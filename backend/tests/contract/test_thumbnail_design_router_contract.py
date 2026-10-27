"""画像生成・素材入出力・テンプレートエラーの公開契約。"""

from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import pytest
import structlog

from splat_replay.application.services.editing.thumbnail_generator import (
    ThumbnailGenerator,
)
from splat_replay.application.services.editing.thumbnail_design_service import (
    ThumbnailDesignService,
)
from splat_replay.infrastructure.adapters.image.image_drawer import ImageDrawer
from splat_replay.infrastructure.adapters.image.thumbnail_assets import (
    ThumbnailAssets,
)
from splat_replay.infrastructure.adapters.image.thumbnail_rule_image_resolver import (
    ThumbnailRuleImageResolver,
)
from splat_replay.infrastructure.adapters.system.cross_cutting import (
    FileSystemPathsAdapter,
    LocalFileSystemAdapter,
)
from splat_replay.interface.web.routers.thumbnail_design import (
    create_thumbnail_design_router,
)

pytestmark = pytest.mark.contract


def test_design_catalog_render_validation_and_asset_lifecycle(
    tmp_path: Path,
) -> None:
    assets = ThumbnailAssets(tmp_path / "assets", tmp_path / "settings.toml")
    generator = ThumbnailGenerator(
        structlog.get_logger(),
        FileSystemPathsAdapter(),
        ImageDrawer.select_brightest_image,
        LocalFileSystemAdapter(),
        ThumbnailRuleImageResolver(),
        assets,
    )
    app = FastAPI()
    app.include_router(
        create_thumbnail_design_router(
            ThumbnailDesignService(assets, generator)
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/thumbnail-design")
        assert response.status_code == 200
        catalog = response.json()
        design = catalog["default_design"]
        assert "RATE_LABEL" in catalog["variables"]
        assert any(asset["kind"] == "font" for asset in catalog["assets"])
        response = client.post(
            "/api/thumbnail-design/preview",
            json={"design": design, "scenario": "x"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert Image.open(BytesIO(response.content)).size == (1920, 1080)
        measured = client.post(
            "/api/thumbnail-design/preview",
            json={
                "design": design,
                "scenario": "regular",
                "include_layout": True,
            },
        )
        assert measured.status_code == 200
        assert measured.json()["image"].startswith("data:image/png;base64,")
        assert measured.json()["layout"]["win-lose"]["width"] > 0
        assert "rate" not in measured.json()["layout"]
        design["elements"][0]["template"] = "{UNKNOWN}"
        assert (
            client.post(
                "/api/thumbnail-design/preview", json={"design": design}
            ).status_code
            == 422
        )
        design = catalog["default_design"]
        design["elements"][0]["template"] = "{WIN} - {LOSE}"
        assert (
            client.post(
                "/api/thumbnail-design/assets", content=b"invalid"
            ).status_code
            == 422
        )
        buffer = BytesIO()
        Image.new("RGB", (160, 90), "red").save(buffer, "PNG")
        response = client.post(
            "/api/thumbnail-design/assets", content=buffer.getvalue()
        )
        assert response.status_code == 200
        asset_id = response.json()["id"]
        assert (
            client.get(f"/api/thumbnail-design/assets/{asset_id}").status_code
            == 200
        )
        design["background"] = {"source": "image", "asset": asset_id}
        assert (
            client.post(
                "/api/thumbnail-design/assets/delete",
                json={"asset_id": asset_id, "draft": design},
            ).status_code
            == 409
        )
        design["background"] = {"source": "result"}
        assert (
            client.post(
                "/api/thumbnail-design/assets/delete",
                json={"asset_id": asset_id, "draft": design},
            ).status_code
            == 200
        )
        assert (
            client.get(f"/api/thumbnail-design/assets/{asset_id}").status_code
            == 404
        )
        assert (
            client.post(
                "/api/thumbnail-design/assets/delete",
                json={"asset_id": "../settings.toml", "draft": design},
            ).status_code
            == 409
        )
