"""Tests for deterministic travel-domain to Mapbox category resolution."""

import json
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from chatbot.category_resolver import (
    CATEGORY_WHITELIST,
    DOMAIN_CATEGORY_MAP,
    resolve_mapbox_categories,
)
from chatbot.intent import TravelIntent
from chatbot.semantic import (
    InterpretationStatus,
    SemanticAction,
    SemanticActionType,
    SemanticConstraints,
    SemanticEntities,
    SemanticInterpretation,
    TravelDomain,
)


class CategoryResolverTests(SimpleTestCase):
    def test_code_mapping_matches_the_documented_mapping_object(self):
        documented_mapping = self._load_documented_mapping()
        code_mapping = {
            domain.value: list(categories)
            for domain, categories in DOMAIN_CATEGORY_MAP.items()
        }

        self.assertEqual(code_mapping, documented_mapping)
        self.assertEqual(len(DOMAIN_CATEGORY_MAP), 10)
        self.assertEqual(len(CATEGORY_WHITELIST), 77)

    def test_explicit_place_type_is_selected_before_domain_defaults(self):
        interpretation = build_place_search(
            domains=[TravelDomain.FOOD],
            place_types=["quán cafe"],
        )

        categories = resolve_mapbox_categories(interpretation)

        self.assertEqual(categories, ("cafe", "coffee_shop", "restaurant"))

    def test_experience_tags_can_resolve_multiple_compatible_domains(self):
        interpretation = build_place_search(
            domains=[TravelDomain.NATURE, TravelDomain.ATTRACTION],
            experience_tags=["ngắm hoàng hôn"],
        )

        categories = resolve_mapbox_categories(interpretation)

        self.assertEqual(categories, ("viewpoint", "beach", "park"))

    def test_irrelevant_secondary_keyword_cannot_escape_the_main_domain(self):
        interpretation = build_place_search(
            domains=[TravelDomain.NIGHTLIFE],
            place_types=["cafe"],
            experience_tags=["chill lãng mạn mùa thu buổi tối"],
        )

        categories = resolve_mapbox_categories(interpretation)

        self.assertEqual(categories, ("nightlife", "bar", "music_venue"))
        self.assertTrue(
            set(categories).issubset(DOMAIN_CATEGORY_MAP[TravelDomain.NIGHTLIFE])
        )

    def test_vague_discovery_defaults_to_attraction_categories(self):
        interpretation = build_place_search(domains=[])

        categories = resolve_mapbox_categories(interpretation)

        self.assertEqual(
            categories,
            ("tourist_attraction", "viewpoint", "historic_site"),
        )

    def test_category_limit_is_validated_and_enforced(self):
        interpretation = build_place_search(
            domains=[TravelDomain.NATURE],
            experience_tags=["ngắm hoàng hôn"],
        )

        self.assertEqual(
            resolve_mapbox_categories(interpretation, max_categories=2),
            ("viewpoint", "beach"),
        )
        for value in (0, -1, True, "3"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    resolve_mapbox_categories(
                        interpretation,
                        max_categories=value,
                    )

    @staticmethod
    def _load_documented_mapping() -> dict[str, list[str]]:
        document_path = Path(settings.BASE_DIR) / "docs" / "travel_categories_mapbox.md"
        text = document_path.read_text(encoding="utf-8")
        match = re.search(
            r"# Suggested Category Mapping Object.*?```json\s*(\{.*?\})\s*```",
            text,
            flags=re.DOTALL,
        )
        if match is None:
            raise AssertionError("Documented category mapping object was not found")
        return json.loads(match.group(1))


def build_place_search(
    *,
    domains: list[TravelDomain],
    place_types: list[str] | None = None,
    experience_tags: list[str] | None = None,
) -> SemanticInterpretation:
    return SemanticInterpretation(
        primary_intent=TravelIntent.PLACE_SEARCH,
        normalized_query="Tìm địa điểm phù hợp",
        travel_domains=domains,
        entities=SemanticEntities(place_types=place_types or []),
        constraints=SemanticConstraints(
            experience_tags=experience_tags or [],
        ),
        actions=[SemanticAction(type=SemanticActionType.DISCOVER_PLACES)],
        status=InterpretationStatus.SUPPORTED,
    )
