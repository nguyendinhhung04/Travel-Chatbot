from django.test import SimpleTestCase

from chatbot.intent import TravelIntent
from chatbot.intent_routing.factory import build_intent_router
from chatbot.intent_routing.handlers import (
    BudgetQAHandler,
    ContextFollowUpHandler,
    DestinationDiscoveryHandler,
    GeneralChatHandler,
    ItineraryAdviceHandler,
    ItineraryManagementHandler,
    ItineraryMakingHandler,
    PlaceDetailsHandler,
    PlaceSearchHandler,
    TravelQAHandler,
    TransportationQAHandler,
    UnsupportedCapabilityHandler,
)


class IntentRouterFactoryTests(SimpleTestCase):
    def test_factory_registers_one_concrete_handler_per_intent(self):
        router = build_intent_router(object(), object(), max_tool_calls=4)

        self.assertEqual(set(router.handlers), set(TravelIntent))
        self.assertEqual(
            {type(handler) for handler in router.handlers.values()},
            {
                BudgetQAHandler,
                ContextFollowUpHandler,
                DestinationDiscoveryHandler,
                GeneralChatHandler,
                ItineraryAdviceHandler,
                ItineraryManagementHandler,
                ItineraryMakingHandler,
                PlaceDetailsHandler,
                PlaceSearchHandler,
                TravelQAHandler,
                TransportationQAHandler,
                UnsupportedCapabilityHandler,
            },
        )
