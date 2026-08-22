# Travel Categories for AI Travel Chatbot

Bộ category này được thiết kế cho bài toán **AI Travel Chatbot / Travel Planner**, dùng một lớp category nghiệp vụ du lịch ở phía trên và ánh xạ xuống `canonicalId` của Mapbox.

Mục tiêu:

- Không đưa toàn bộ hàng trăm category Mapbox trực tiếp cho LLM.
- Giúp chatbot hiểu nhu cầu người dùng theo ngữ nghĩa du lịch.
- Chuẩn hóa việc chọn category khi gọi Mapbox `category_search`.
- Hỗ trợ recommendation, tìm địa điểm, tạo itinerary và trợ lý trong chuyến đi.

---

## 1. ATTRACTION — Điểm tham quan

Dùng cho các intent như:

- Có gì chơi ở Đà Nẵng?
- Những điểm tham quan nổi tiếng ở Hà Nội?
- Có chỗ check-in nào đẹp gần đây?
- Nên đi đâu vào buổi sáng?
- Nếu người dùng không nói đến loại địa điểm nào thì mặc định là có ATTRACTION

### Mapbox categories

```text
tourist_attraction
historic_site
monument
museum
art_gallery
public_artwork
outdoor_sculpture
viewpoint
bridge
plaza
tourist_information
```

---

## 2. NATURE — Thiên nhiên & ngoài trời

Dùng cho:

- Tôi thích thiên nhiên.
- Có bãi biển nào đẹp không?
- Tìm chỗ ngắm cảnh.
- Có núi, thác, hang động nào gần đây?
- Tôi muốn đi nơi ít đông, gần thiên nhiên.

### Mapbox categories

```text
outdoors
park
beach
mountain
forest
island
lake
river
waterfall
nature_reserve
cave
garden
trailhead
viewpoint
```

---

## 3. FOOD — Ăn uống

Dùng cho:

- Ăn gì ở Đà Nẵng?
- Quán ăn ngon gần đây?
- Tìm quán cà phê.
- Tìm đồ ăn nhanh.
- Tìm nhà hàng Việt Nam.

### Core categories

```text
food_and_drink
food
restaurant
cafe
coffee_shop
bakery
fast_food
food_court
food_truck
dessert_shop
ice_cream
teahouse
snack_bar
```

### Cuisine subcategories

```text
vietnamese_restaurant
chinese_restaurant
japanese_restaurant
korean_restaurant
asian_restaurant
thai_restaurant
indian_restaurant
italian_restaurant
french_restaurant
mexican_restaurant
american_restaurant
seafood_restaurant
sushi_restaurant
ramen_restaurant
barbeque_restaurant
breakfast_restaurant
brunch_restaurant
buffet_restaurant
noodle_restaurant
```

### Gợi ý domain model

```json
{
  "domain": "FOOD",
  "category": "restaurant",
  "cuisine": "vietnamese"
}
```

---

## 4. ACCOMMODATION — Lưu trú

Dùng cho:

- Tìm khách sạn gần biển.
- Có hostel giá rẻ không?
- Tìm resort.
- Tìm chỗ ở gần trung tâm.

### Mapbox categories

```text
lodging
hotel
hostel
resort
motel
bed_and_breakfast
vacation_rental
campground
mountain_hut
apartment_or_condo
```

---

## 5. TRANSPORT — Di chuyển

Dùng cho:

- Sân bay gần nhất ở đâu?
- Tìm bến xe.
- Ga tàu gần đây.
- Thuê xe ở đâu?
- Tìm bãi đỗ xe.
- Có trạm xăng gần đây không?

### Mapbox categories

```text
transportation
airport
airport_terminal
public_transportation_station
bus_station
bus_stop
railway_station
train
taxi
car_rental
bike_rental
boat_or_ferry
marina
parking_lot
gas_station
charging_station
cable_car
```

---

## 6. ENTERTAINMENT — Vui chơi giải trí

Dùng cho:

- Có khu vui chơi nào?
- Đi đâu với trẻ em?
- Có công viên nước không?
- Tối nay xem phim ở đâu?
- Có khu giải trí nào gần đây?

### Mapbox categories

```text
entertainment
theme_park
theme_park_attraction
water_park
cinema
theatre
music_venue
concert_hall
arcade
bowling_alley
zoo
aquarium
```

---

## 7. CULTURE — Văn hóa, lịch sử & tâm linh

Dùng cho:

- Có chùa nào nổi tiếng?
- Tìm địa điểm văn hóa.
- Điểm lịch sử gần đây?
- Có bảo tàng nào không?
- Tìm nhà thờ, đền, chùa.

### Mapbox categories

```text
place_of_worship
temple
buddhist_temple
church
mosque
historic_site
monument
museum
art_gallery
public_artwork
```

> Một POI có thể thuộc nhiều domain.  
> Ví dụ `museum` có thể thuộc cả `ATTRACTION` và `CULTURE`.

---

## 8. NIGHTLIFE — Hoạt động buổi tối

Dùng cho:

- Tối ở Đà Nẵng có gì chơi?
- Tìm quán bar.
- Có pub nào gần đây?
- Đi đâu sau 10 giờ tối?
- Tìm nơi nghe nhạc.

### Mapbox categories

```text
nightlife
bar
pub
nightclub
cocktail_bar
lounge
wine_bar
sports_bar
karaoke_bar
music_venue
```

---

## 9. SHOPPING — Mua sắm

Dùng cho:

- Mua quà ở đâu?
- Có chợ nào gần đây?
- Tìm trung tâm thương mại.
- Có cửa hàng tiện lợi không?

### Mapbox categories

```text
shopping
shopping_mall
market
supermarket
convenience_store
gift_shop
boutique
department_store
duty_free_shop
```

---

## 10. ESSENTIAL — Tiện ích thiết yếu trong chuyến đi

Nhóm này phục vụ trợ lý **during-trip**.

### 10.1. Medical

```text
hospital
pharmacy
medical_clinic
emergency_room
```

Dùng cho:

- Hiệu thuốc gần tôi?
- Có bệnh viện nào gần đây?
- Tôi cần phòng cấp cứu.

### 10.2. Safety

```text
police_station
fire_station
```

### 10.3. Finance

```text
atm
bank
currency_exchange
```

### 10.4. Daily Needs

```text
supermarket
convenience_store
grocery
```

### 10.5. Vehicle Support

```text
gas_station
charging_station
auto_repair
```

---

# Recommended V1 Taxonomy

V1 nên ưu tiên 5 nhóm chính:

```text
ATTRACTION
FOOD
ACCOMMODATION
NATURE
TRANSPORT
```

Sau đó bổ sung:

```text
ENTERTAINMENT
CULTURE
NIGHTLIFE
SHOPPING
ESSENTIAL
```

---

# Suggested Architecture

Không nên để LLM chọn trực tiếp trong toàn bộ taxonomy Mapbox.

Nên dùng:

```text
User Query
    ↓
Intent / Semantic Analysis
    ↓
Travel Domain
    ↓
Category Resolver
    ↓
Mapbox canonicalId[]
    ↓
Mapbox category_search
```

Ví dụ:

```text
User:
"Tôi muốn tìm chỗ chill ngắm hoàng hôn gần biển"

Travel domains:
NATURE
ATTRACTION

Mapbox categories:
viewpoint
beach
park
```

Structured output:

```json
{
  "user_need": "chill, ngắm hoàng hôn",
  "travel_domains": [
    "NATURE",
    "ATTRACTION"
  ],
  "mapbox_categories": [
    "viewpoint",
    "beach",
    "park"
  ]
}
```

---

# Suggested Category Mapping Object

Có thể lưu taxonomy trong backend dưới dạng:

```json
{
  "ATTRACTION": [
    "tourist_attraction",
    "historic_site",
    "monument",
    "museum",
    "art_gallery",
    "viewpoint",
    "bridge",
    "plaza"
  ],
  "NATURE": [
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
    "viewpoint"
  ],
  "FOOD": [
    "restaurant",
    "cafe",
    "coffee_shop",
    "bakery",
    "fast_food",
    "food_court",
    "food_truck"
  ],
  "ACCOMMODATION": [
    "lodging",
    "hotel",
    "hostel",
    "resort",
    "motel",
    "bed_and_breakfast",
    "vacation_rental",
    "campground"
  ],
  "TRANSPORT": [
    "airport",
    "bus_station",
    "bus_stop",
    "railway_station",
    "taxi",
    "car_rental",
    "bike_rental",
    "boat_or_ferry",
    "parking_lot",
    "gas_station"
  ],
  "ENTERTAINMENT": [
    "theme_park",
    "theme_park_attraction",
    "water_park",
    "cinema",
    "theatre",
    "zoo",
    "aquarium",
    "arcade"
  ],
  "CULTURE": [
    "place_of_worship",
    "temple",
    "buddhist_temple",
    "church",
    "historic_site",
    "monument",
    "museum",
    "art_gallery"
  ],
  "NIGHTLIFE": [
    "nightlife",
    "bar",
    "pub",
    "nightclub",
    "cocktail_bar",
    "lounge",
    "music_venue"
  ],
  "SHOPPING": [
    "market",
    "shopping_mall",
    "gift_shop",
    "supermarket",
    "convenience_store"
  ],
  "ESSENTIAL": [
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
    "auto_repair"
  ]
}
```

---

# Design Notes

1. **Travel category không đồng nghĩa với Mapbox category.**  
   Travel category là domain abstraction của hệ thống.

2. **Một travel category ánh xạ tới nhiều Mapbox category.**

3. **Một Mapbox category có thể xuất hiện trong nhiều travel domain.**  
   Ví dụ `viewpoint` có thể thuộc cả `ATTRACTION` và `NATURE`.

4. **Không cần expose toàn bộ taxonomy Mapbox cho LLM.**

5. **LLM nên xác định nhu cầu/ngữ nghĩa**, còn backend/category resolver chịu trách nhiệm ánh xạ sang `canonicalId`.

6. Với V1, whitelist khoảng **50–70 category liên quan du lịch** là đủ tốt hơn so với dùng toàn bộ hàng trăm category.

---

# Source

Bộ category trên được lọc và tổ chức từ danh sách `canonicalId` Mapbox trong response Category List API do dự án cung cấp, sau đó nhóm lại theo domain phục vụ bài toán AI Travel Chatbot.
