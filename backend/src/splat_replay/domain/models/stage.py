"""ステージの列挙型（代表的な数種類のみ）。"""

from __future__ import annotations

from enum import Enum


class Stage(Enum):
    """ゲーム内ステージ。"""

    SCORCH_GORGE = "ユノハナ大渓谷"
    EELTAIL_ALLEY = "ゴンズイ地区"
    HAGGLEFISH_MARKET = "ヤガラ市場"
    UNDERTOW_SPILLWAY = "マテガイ放水路"
    MINCEMEAT_METALWORKS = "ナメロウ金属"
    MAHI_MAHI_RESORT = "マヒマヒリゾート＆スパ"
    MUSEUM_D_ALFONSINO = "キンメダイ美術館"
    HAMMERHEAD_BRIDGE = "マサバ海峡大橋"
    INKBLOT_ART_ACADEMY = "海女美術大学"
    STURGEON_SHIPYARD = "チョウザメ造船"
    MAKO_MART = "ザトウマーケット"
    WAHOO_WORLD = "スメーシーワールド"
    FLOUNDER_HEIGHTS = "ヒラメが丘団地"
    BRINEWATER_SPRINGS = "クサヤ温泉"
    UMAMI_RUINS = "ナンプラー遺跡"
    MANTA_MARIA = "マンタマリア号"
    BARNACLE_AND_DIME = "タラポートショッピングパーク"
    HUMPBACK_PUMP_TRACK = "コンブトラック"
    CRABLEG_CAPITAL = "タカアシ経済特区"
    SHIPSHAPE_CARGO_CO = "オヒョウ海運"
    ROBO_ROM_EN = "バイガイ亭"
    BLUEFIN_DEPOT = "ネギトロ炭鉱"
    MARLIN_AIRPORT = "カジキ空港"
    LEMURIA_HUB = "リュウグウターミナル"
    URCHIN_UNDERPASS = "デカライン高架下"
