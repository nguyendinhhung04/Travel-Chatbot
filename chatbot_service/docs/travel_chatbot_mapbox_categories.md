# Các category quan trọng cho chatbot du lịch

Nguồn: danh sách category trong response Mapbox được cung cấp.

## Mục tiêu

Không nên đưa toàn bộ category Mapbox vào intent/tool schema. Với chatbot du lịch, nên gom các category quan trọng thành nhóm nghiệp vụ để:

- phân loại intent đơn giản hơn;
- giảm số category LLM phải lựa chọn;
- dễ mapping câu hỏi tự nhiên sang `poi_category`;
- dễ mở rộng về sau mà không làm prompt/tool schema quá lớn.

## Danh sách đề xuất

### 1. Điểm tham quan & trải nghiệm

| canonicalId | Mapbox name |
|---|---|
| `tourist_attraction` | Tourist Attraction |
| `historic_site` | Historic Site |
| `monument` | Monument |
| `museum` | Museum |
| `art_gallery` | Art Gallery |
| `public_artwork` | Public Artwork |
| `outdoor_sculpture` | Outdoor Sculpture |
| `exhibit` | Exhibit |
| `viewpoint` | Viewpoint |
| `plaza` | Plaza |
| `theme_park` | Theme Park |
| `theme_park_attraction` | Theme Park Attraction |
| `zoo` | Zoo |
| `aquarium` | Aquarium |
| `planetarium` | Planetarium |
| `observatory` | Observatory |
| `tours` | Tours |
| `tourist_information` | Tourist Information Center |

### 2. Thiên nhiên & ngoài trời

| canonicalId | Mapbox name |
|---|---|
| `outdoors` | Outdoors |
| `park` | Park |
| `garden` | Garden |
| `nature_reserve` | Nature Reserve |
| `forest` | Forest |
| `mountain` | Mountain |
| `lake` | Lake |
| `river` | River |
| `waterfall` | Waterfall |
| `beach` | Beach |
| `island` | Island |
| `cave` | Cave |
| `trailhead` | Trailhead |
| `campground` | Campground |
| `mountain_hut` | Mountain Hut |
| `picnic_shelter` | Picnic Shelter |
| `surf_spot` | Surf Spot |
| `rafting_spot` | Rafting Spot |
| `marina` | Marina |
| `pier` | Pier |
| `boat_launch` | Boat Launch |

### 3. Ăn uống

| canonicalId | Mapbox name |
|---|---|
| `food_and_drink` | Food and Drink |
| `food` | Food |
| `restaurant` | Restaurant |
| `cafe` | Café |
| `coffee_shop` | Coffee Shop |
| `bakery` | Bakery |
| `fast_food` | Fast Food Restaurant |
| `food_court` | Food Court |
| `food_truck` | Food Truck |
| `breakfast_restaurant` | Breakfast Restaurant |
| `brunch_restaurant` | Brunch Restaurant |
| `buffet_restaurant` | Buffet Restaurant |
| `dessert_shop` | Confectionary |
| `ice_cream` | Ice Cream Store |
| `vietnamese_restaurant` | Vietnamese Restaurant |
| `asian_restaurant` | Asian Food |
| `seafood_restaurant` | Fish Restaurant |

### 4. Lưu trú

| canonicalId | Mapbox name |
|---|---|
| `lodging` | Lodging |
| `hotel` | Hotel |
| `hostel` | Hostel |
| `motel` | Motel |
| `resort` | Resort |
| `bed_and_breakfast` | Bed and Breakfast |
| `vacation_rental` | Vacation Rental |
| `campground` | Campground |
| `mountain_hut` | Mountain Hut |
| `apartment_or_condo` | Apartment Or Condo |

### 5. Giao thông & di chuyển

| canonicalId | Mapbox name |
|---|---|
| `transportation` | Transportation |
| `airport` | Airport |
| `airport_terminal` | Airport Terminal |
| `bus_stop` | Bus Stop |
| `bus_station` | Bus Station |
| `public_transportation_station` | Public Transit Station |
| `railway_station` | Train Station |
| `light_rail_station` | Light Rail Station |
| `taxi` | Taxi |
| `boat_or_ferry` | Boat Or Ferry |
| `cable_car` | Cable Car |
| `bike_rental` | Bike Rental |
| `car_rental` | Car Rental |
| `parking_lot` | Parking |
| `gas_station` | Gas Station |
| `charging_station` | Charging Station |
| `rest_area` | Rest Area |
| `service_area` | Service Area |

### 6. Mua sắm & nhu yếu phẩm

| canonicalId | Mapbox name |
|---|---|
| `shopping` | Shopping |
| `shopping_mall` | Shopping Mall |
| `market` | Market |
| `supermarket` | Supermarket |
| `grocery` | Grocery |
| `convenience_store` | Convenience Store |
| `gift_shop` | Gift Shop |
| `book_store` | Bookstore |
| `clothing_store` | Clothes Store |
| `department_store` | Department Store |
| `duty_free_shop` | Duty Free Shop |
| `luggage_store` | Luggage Store |

### 7. Y tế & khẩn cấp

| canonicalId | Mapbox name |
|---|---|
| `health_services` | Health Services |
| `hospital` | Hospital |
| `emergency_room` | Emergency Room |
| `medical_clinic` | Medical Clinic |
| `doctors_office` | Doctor's Office |
| `pharmacy` | Pharmacy |
| `police_station` | Police |
| `fire_station` | Fire Station |

### 8. Tài chính & tiện ích

| canonicalId | Mapbox name |
|---|---|
| `financial_services` | Financial Services |
| `bank` | Bank |
| `atm` | Atm |
| `currency_exchange` | Currency Exchange |
| `post_office` | Post Office |
| `laundry` | Laundry |
| `internet_cafe` | Internet Cafe |

### 9. Văn hóa, tôn giáo & cộng đồng

| canonicalId | Mapbox name |
|---|---|
| `place_of_worship` | Place Of Worship |
| `temple` | Temple |
| `buddhist_temple` | Buddhist Temple |
| `church` | Church |
| `mosque` | Mosque |
| `synagogue` | Synagogue |
| `community_center` | Community Center |

### 10. Giải trí & nightlife

| canonicalId | Mapbox name |
|---|---|
| `entertainment` | Entertainment |
| `nightlife` | Nightlife |
| `bar` | Bar |
| `pub` | Pub |
| `nightclub` | Nightclub |
| `karaoke_bar` | Karaoke Bar |
| `cinema` | Movie Theater |
| `theatre` | Theater |
| `music_venue` | Music Venue |
| `concert_hall` | Concert Hall |
| `arcade` | Arcade |
| `bowling_alley` | Bowling Alley |

### 11. Thể thao & hoạt động

| canonicalId | Mapbox name |
|---|---|
| `sports` | Sports |
| `sports_center` | Sports Center |
| `stadium` | Stadium |
| `swimming_pool` | Swimming Pool |
| `golf_course` | Golf Course |
| `climbing` | Climbing |
| `climbing_gym` | Climbing Gym |
| `fitness_center` | Gym |
| `yoga_studio` | Yoga Studio |
| `tennis_courts` | Tennis Court |
| `basketball_court` | Basketball Court |
| `ski_area` | Ski Area |

## Bộ category tối thiểu nên ưu tiên cho V1

| canonicalId | Ý nghĩa sử dụng trong chatbot |
|---|---|
| `tourist_attraction` | Điểm du lịch / nơi tham quan nói chung |
| `historic_site` | Di tích, địa điểm lịch sử |
| `museum` | Bảo tàng |
| `viewpoint` | Điểm ngắm cảnh |
| `park` | Công viên |
| `nature_reserve` | Khu bảo tồn thiên nhiên |
| `mountain` | Núi |
| `lake` | Hồ |
| `waterfall` | Thác nước |
| `beach` | Bãi biển |
| `restaurant` | Nhà hàng |
| `cafe` | Quán cà phê |
| `food_and_drink` | Ăn uống nói chung |
| `lodging` | Lưu trú nói chung |
| `hotel` | Khách sạn |
| `hostel` | Hostel |
| `transportation` | Giao thông nói chung |
| `airport` | Sân bay |
| `bus_station` | Bến xe |
| `railway_station` | Ga tàu |
| `taxi` | Taxi |
| `parking_lot` | Bãi đỗ xe |
| `shopping` | Mua sắm nói chung |
| `market` | Chợ |
| `supermarket` | Siêu thị |
| `hospital` | Bệnh viện |
| `pharmacy` | Nhà thuốc |
| `police_station` | Công an / cảnh sát |
| `atm` | ATM |
| `bank` | Ngân hàng |
| `tourist_information` | Trung tâm thông tin du lịch |

## Gợi ý mapping intent → category

| Intent người dùng | Category nên dùng |
|---|---|
| Tìm địa điểm du lịch / chỗ chơi | `tourist_attraction`, `historic_site`, `museum`, `viewpoint`, `park` |
| Tìm cảnh đẹp / thiên nhiên | `nature_reserve`, `mountain`, `lake`, `waterfall`, `beach`, `viewpoint` |
| Tìm chỗ ăn | `food_and_drink`, `restaurant` |
| Tìm quán cà phê | `cafe`, `coffee_shop` |
| Tìm khách sạn / chỗ ở | `lodging`, `hotel`, `hostel`, `resort`, `vacation_rental` |
| Tìm phương tiện / điểm trung chuyển | `transportation`, `airport`, `bus_station`, `railway_station`, `taxi` |
| Tìm chợ / nơi mua đồ | `shopping`, `market`, `supermarket`, `convenience_store` |
| Tìm bệnh viện / nhà thuốc | `hospital`, `medical_clinic`, `pharmacy`, `emergency_room` |
| Tìm ATM / đổi tiền | `atm`, `bank`, `currency_exchange` |
| Tìm hoạt động buổi tối | `nightlife`, `bar`, `pub`, `nightclub`, `karaoke_bar` |

## Khuyến nghị thiết kế chatbot

1. **Không expose hàng trăm category trực tiếp cho LLM.** Hãy tạo khoảng 8–12 nhóm nghiệp vụ như bảng trên.
2. LLM trước tiên chọn `intent_group`, sau đó backend mapping sang một hoặc nhiều `canonicalId` Mapbox.
3. Dùng category tổng quát khi câu hỏi mơ hồ, ví dụ `food_and_drink`, `lodging`, `transportation`, `shopping`.
4. Chỉ dùng category chi tiết khi người dùng nói rõ, ví dụ “quán ramen” → `ramen_restaurant`, “hostel” → `hostel`.
5. Với bài toán lên lịch trình, ưu tiên 5 nhóm chính: **attraction, food, lodging, transport, emergency/utility**.

### Ví dụ schema nội bộ đơn giản

```json
{
  "intent_group": "food",
  "categories": ["restaurant", "vietnamese_restaurant"],
  "location": "Hà Nội",
  "near": "Hồ Hoàn Kiếm"
}
```