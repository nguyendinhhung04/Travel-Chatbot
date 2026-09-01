import type { PlaceRecommendation } from "@/types/chat";

const MOCK_RECOMMENDATIONS: Record<string, PlaceRecommendation[]> = {
  hue: [
    {
      mapboxId: "mock-hue-imperial-city",
      name: "Đại Nội Huế",
      category: "Di tích lịch sử",
      distance: "1,2 km",
      longitude: 107.579,
      latitude: 16.469,
      accent: "sunset",
    },
    {
      mapboxId: "mock-hue-thien-mu",
      name: "Chùa Thiên Mụ",
      category: "Tâm linh",
      distance: "4,8 km",
      longitude: 107.552,
      latitude: 16.453,
      accent: "river",
    },
    {
      mapboxId: "mock-hue-dong-ba",
      name: "Chợ Đông Ba",
      category: "Ẩm thực / mua sắm",
      distance: "2,1 km",
      longitude: 107.586,
      latitude: 16.471,
      accent: "garden",
    },
  ],
  "da nang": [
    {
      mapboxId: "mock-da-nang-son-tra",
      name: "Bán đảo Sơn Trà",
      category: "Thiên nhiên",
      distance: "9,4 km",
      longitude: 108.277,
      latitude: 16.106,
      accent: "garden",
    },
    {
      mapboxId: "mock-da-nang-my-khe",
      name: "Bãi biển Mỹ Khê",
      category: "Biển",
      distance: "2,3 km",
      longitude: 108.247,
      latitude: 16.061,
      accent: "river",
    },
    {
      mapboxId: "mock-da-nang-marble-mountains",
      name: "Ngũ Hành Sơn",
      category: "Văn hóa",
      distance: "8,7 km",
      longitude: 108.263,
      latitude: 15.995,
      accent: "sunset",
    },
  ],
  "hoi an": [
    {
      mapboxId: "mock-hoi-an-old-town",
      name: "Phố cổ Hội An",
      category: "Di sản",
      distance: "0,8 km",
      longitude: 108.326,
      latitude: 15.88,
      accent: "sunset",
    },
    {
      mapboxId: "mock-hoi-an-an-bang",
      name: "Biển An Bàng",
      category: "Biển",
      distance: "4,1 km",
      longitude: 108.338,
      latitude: 15.914,
      accent: "river",
    },
    {
      mapboxId: "mock-hoi-an-tra-que",
      name: "Làng rau Trà Quế",
      category: "Trải nghiệm",
      distance: "3,2 km",
      longitude: 108.333,
      latitude: 15.906,
      accent: "garden",
    },
  ],
};

function normalizeQuestion(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("vi-VN")
    .replace(/đ/g, "d");
}

export function getMockRecommendations(question: string) {
  const normalizedQuestion = normalizeQuestion(question);
  const destination = Object.keys(MOCK_RECOMMENDATIONS).find((key) =>
    normalizedQuestion.includes(key),
  );

  return destination ? MOCK_RECOMMENDATIONS[destination] : [];
}
