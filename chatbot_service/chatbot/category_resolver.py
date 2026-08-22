"""Map travel semantics to a small allowlist of Mapbox categories."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

from chatbot.semantic import SemanticInterpretation, TravelDomain


DOMAIN_CATEGORY_MAP: dict[TravelDomain, tuple[str, ...]] = {
    TravelDomain.ATTRACTION: (
        "tourist_attraction",
        "historic_site",
        "monument",
        "museum",
        "art_gallery",
        "viewpoint",
        "bridge",
        "plaza",
    ),
    TravelDomain.NATURE: (
        "park",
        "beach",
        "mountain",
        "forest",
        "island",
        "lake",
        "river",
        "waterfall",
        "nature_reserve",
        "cave",
        "garden",
        "trailhead",
        "viewpoint",
    ),
    TravelDomain.FOOD: (
        "restaurant",
        "cafe",
        "coffee_shop",
        "bakery",
        "fast_food",
        "food_court",
        "food_truck",
    ),
    TravelDomain.ACCOMMODATION: (
        "lodging",
        "hotel",
        "hostel",
        "resort",
        "motel",
        "bed_and_breakfast",
        "vacation_rental",
        "campground",
    ),
    TravelDomain.TRANSPORT: (
        "airport",
        "bus_station",
        "bus_stop",
        "railway_station",
        "taxi",
        "car_rental",
        "bike_rental",
        "boat_or_ferry",
        "parking_lot",
        "gas_station",
    ),
    TravelDomain.ENTERTAINMENT: (
        "theme_park",
        "theme_park_attraction",
        "water_park",
        "cinema",
        "theatre",
        "zoo",
        "aquarium",
        "arcade",
    ),
    TravelDomain.CULTURE: (
        "place_of_worship",
        "temple",
        "buddhist_temple",
        "church",
        "historic_site",
        "monument",
        "museum",
        "art_gallery",
    ),
    TravelDomain.NIGHTLIFE: (
        "nightlife",
        "bar",
        "pub",
        "nightclub",
        "cocktail_bar",
        "lounge",
        "music_venue",
    ),
    TravelDomain.SHOPPING: (
        "market",
        "shopping_mall",
        "gift_shop",
        "supermarket",
        "convenience_store",
    ),
    TravelDomain.ESSENTIAL: (
        "hospital",
        "pharmacy",
        "medical_clinic",
        "police_station",
        "atm",
        "bank",
        "supermarket",
        "convenience_store",
        "gas_station",
        "charging_station",
        "auto_repair",
    ),
}

CATEGORY_WHITELIST = frozenset(
    category
    for categories in DOMAIN_CATEGORY_MAP.values()
    for category in categories
)

DOMAIN_DEFAULT_CATEGORIES: dict[TravelDomain, tuple[str, ...]] = {
    TravelDomain.ATTRACTION: ("tourist_attraction", "viewpoint", "historic_site"),
    TravelDomain.NATURE: ("park", "beach", "viewpoint"),
    TravelDomain.FOOD: ("restaurant", "cafe", "coffee_shop"),
    TravelDomain.ACCOMMODATION: ("lodging", "hotel", "hostel"),
    TravelDomain.TRANSPORT: ("airport", "bus_station", "taxi"),
    TravelDomain.ENTERTAINMENT: ("theme_park", "cinema", "zoo"),
    TravelDomain.CULTURE: ("museum", "historic_site", "place_of_worship"),
    TravelDomain.NIGHTLIFE: ("nightlife", "bar", "music_venue"),
    TravelDomain.SHOPPING: ("market", "shopping_mall", "gift_shop"),
    TravelDomain.ESSENTIAL: ("hospital", "pharmacy", "atm"),
}

_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "diem tham quan": ("tourist_attraction",),
    "di tich": ("historic_site", "monument"),
    "bao tang": ("museum",),
    "trien lam": ("art_gallery",),
    "ngam canh": ("viewpoint",),
    "hoang hon": ("viewpoint", "beach", "park"),
    "cau": ("bridge",),
    "cong vien": ("park",),
    "bai bien": ("beach",),
    "bien": ("beach",),
    "nui": ("mountain",),
    "rung": ("forest",),
    "dao": ("island",),
    "ho": ("lake",),
    "song": ("river",),
    "thac": ("waterfall",),
    "hang dong": ("cave",),
    "vuon": ("garden",),
    "quan an": ("restaurant",),
    "nha hang": ("restaurant",),
    "an uong": ("restaurant",),
    "mi quang": ("restaurant",),
    "cafe": ("cafe", "coffee_shop"),
    "ca phe": ("cafe", "coffee_shop"),
    "coffee": ("coffee_shop", "cafe"),
    "tiem banh": ("bakery",),
    "do an nhanh": ("fast_food",),
    "khach san": ("hotel", "lodging"),
    "hostel": ("hostel",),
    "resort": ("resort",),
    "nha nghi": ("motel", "lodging"),
    "san bay": ("airport",),
    "ben xe": ("bus_station",),
    "tram xe buyt": ("bus_stop",),
    "ga tau": ("railway_station",),
    "taxi": ("taxi",),
    "thue xe": ("car_rental", "bike_rental"),
    "bai do xe": ("parking_lot",),
    "tram xang": ("gas_station",),
    "khu vui choi": ("theme_park", "arcade"),
    "cong vien nuoc": ("water_park",),
    "rap phim": ("cinema",),
    "so thu": ("zoo",),
    "thuy cung": ("aquarium",),
    "chua": ("buddhist_temple", "temple", "place_of_worship"),
    "nha tho": ("church", "place_of_worship"),
    "bar": ("bar", "nightlife"),
    "pub": ("pub", "nightlife"),
    "club": ("nightclub", "nightlife"),
    "cho dem": ("market", "nightlife"),
    "cho": ("market",),
    "trung tam thuong mai": ("shopping_mall",),
    "mua qua": ("gift_shop", "market"),
    "sieu thi": ("supermarket",),
    "benh vien": ("hospital",),
    "hieu thuoc": ("pharmacy",),
    "nha thuoc": ("pharmacy",),
    "phong kham": ("medical_clinic",),
    "cong an": ("police_station",),
    "atm": ("atm",),
    "ngan hang": ("bank",),
    "sac dien": ("charging_station",),
    "sua xe": ("auto_repair",),
}


def resolve_mapbox_categories(
    interpretation: SemanticInterpretation,
    *,
    max_categories: int = 3,
) -> tuple[str, ...]:
    """Resolve semantic place needs to allowlisted Mapbox category IDs."""
    if isinstance(max_categories, bool) or not isinstance(max_categories, int):
        raise ValueError("max_categories must be an integer")
    if max_categories <= 0:
        raise ValueError("max_categories must be greater than zero")

    domains = interpretation.travel_domains
    allowed_categories = (
        frozenset(
            category
            for domain in domains
            for category in DOMAIN_CATEGORY_MAP[domain]
        )
        if domains
        else CATEGORY_WHITELIST
    )
    semantic_terms = [
        *interpretation.entities.place_types,
        *interpretation.constraints.experience_tags,
        *interpretation.constraints.cuisines,
    ]

    resolved: list[str] = []
    for term in semantic_terms:
        normalized_term = _normalize_term(term)
        for alias, categories in _CATEGORY_ALIASES.items():
            if alias not in normalized_term:
                continue
            _append_allowed(categories, allowed_categories, resolved)
            if len(resolved) >= max_categories:
                return tuple(resolved[:max_categories])

    default_domains = domains or [TravelDomain.ATTRACTION]
    for domain in default_domains:
        _append_allowed(
            DOMAIN_DEFAULT_CATEGORIES[domain],
            allowed_categories,
            resolved,
        )
        if len(resolved) >= max_categories:
            break

    return tuple(resolved[:max_categories])


def _append_allowed(
    categories: Iterable[str],
    allowed_categories: frozenset[str],
    resolved: list[str],
) -> None:
    for category in categories:
        if category in allowed_categories and category not in resolved:
            resolved.append(category)


def _normalize_term(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    without_accents = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_accents.split())


__all__ = [
    "CATEGORY_WHITELIST",
    "DOMAIN_CATEGORY_MAP",
    "DOMAIN_DEFAULT_CATEGORIES",
    "resolve_mapbox_categories",
]
