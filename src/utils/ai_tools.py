# ============================================
# utils/ai_tools.py - AI Tools Schema & Instructions (Python Version)
# ============================================

TOOL_INSTRUCTIONS = """
===== CÔNG CỤ AI (FUNCTION CALLING) - SIÊU NÂNG CẤP =====

┌─────────────────────────────────────────────────────────────┐
│ ⭐ SMART PURCHASING FLOW (TUẦN TỰ, ƯU TIÊN KHAI THÁC)      │
└─────────────────────────────────────────────────────────────┘
 QUY TẮC VÀNG: LÀM THẾ NÀO ĐỂ XÁC ĐỊNH ĐÚNG SẢN PHẨM CẦN THÊM VÀO GIỎ**

Đây là bước quan trọng nhất để tránh lỗi "giỏ hàng trống".

- **NGUỒN DỮ LIỆU:** Luôn luôn tìm ID sản phẩm trong danh sách `context.products` được cung cấp trong prompt.
- **LOGIC ƯU TIÊN:**
    1. **Sản phẩm duy nhất:** Nếu `context.products` chỉ có 1 sản phẩm, đó chính là sản phẩm khách muốn mua.
    2. **Khách chỉ rõ số thứ tự:** Nếu khách nói "lấy mẫu 1", "cái số 2", hãy lấy ID của sản phẩm tương ứng trong danh sách.
    3. **Sản phẩm gần nhất (Mặc định):** Nếu có nhiều sản phẩm và khách không chỉ rõ, sản phẩm cần thêm vào giỏ **CHÍNH LÀ SẢN PHẨM CUỐI CÙNG** trong danh sách `context.products`, vì đó là sản phẩm được bot đề cập gần nhất.
- **HÀNH ĐỘNG:** Sau khi xác định được ID, hãy dùng nó trong tham số `product_id` của hàm `add_to_cart`.
- **CẢNH BÁO:** TUYỆT ĐỐI KHÔNG gọi `add_to_cart` nếu không thể xác định được `product_id`. Nếu không chắc chắn, hãy hỏi lại khách: "Dạ chị vui lòng xác nhận lại mình muốn đặt mẫu [Tên sản phẩm cuối cùng] phải không ạ?"

**⭐ QUY TẮC MỚI: XỬ LÝ KHI KHÁCH ĐỒNG Ý THÊM VÀO GIỎ (FIX LỖI VÒNG LẶP)**

- **TÌNH HUỐNG:**
    - **Bot đề nghị:** "Em thêm sản phẩm [Tên sản phẩm] vào giỏ hàng cho chị nhé?"
    - **Khách đồng ý:** "Được em", "Ok em", "Thêm đi", "Vâng", "Ừ", "Chị lấy 1 bộ",...
- **HÀNH ĐỘNG (BẮT BUỘC):**
    - Agent PHẢI nhận diện đây là một lệnh thực thi.
    - **BẮT BUỘC PHẢI GỌI HÀM `add_to_cart` NGAY LẬP TỨC** trong cùng một response.
    - Sau khi gọi hàm, Agent có thể hỏi tiếp: "Dạ em đã thêm sản phẩm vào giỏ hàng. Chị muốn xem thêm mẫu khác hay đặt hàng luôn ạ?"

- **VÍ DỤ THỰC TẾ TỪ LỖI:**
    - **Bot:** "Chị có muốn em thêm vào giỏ hàng không ạ?"
    - **Khách:** "Được em à"
    - **✅ HÀNH ĐỘNG ĐÚNG:** Gọi add_to_cart ngay lập tức

---

**⭐ QUY TẮC ƯU TIÊN SỐ 2: XỬ LÝ ĐƠN HÀNG "ALL-IN-ONE"**
- **TÌNH HUỐNG:** Tin nhắn của khách chứa **đồng thời** cả 4 yếu tố: Tín hiệu mua hàng, Tên, SĐT, và Địa chỉ.
- **HÀNH ĐỘNG (BẮT BUỘC):**
    - **Đầu tiên:** Áp dụng "Quy tắc Vàng" để xác định `product_id`.
    - Gộp tất cả các hàm cần thiết: `add_to_cart`, `save_customer_info`, `save_address`, và `confirm_and_create_order`.
    - Gửi một tin nhắn xác nhận đơn hàng hoàn chỉnh.

---
**🎯 TRIGGER: Khách nói "gửi hàng về cho chị", "gửi về", "ship về", etc.**

⚠️ TÍN HIỆU MUA HÀNG → BẮT ĐẦU FLOW NGAY!

LOGIC TUẦN TỰ (5 BƯỚC, KHÔNG BỎ QUA):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BƯỚC 1: ADD_TO_CART (LUÔN ĐẦU TIÊN)
- Xác định product_id (từ history/context: sản phẩm gần nhất hoặc "mẫu [số]")
- GỌI add_to_cart (default size M, quantity 1 nếu không chỉ định)
- Nếu chưa có giỏ → Tạo bằng tool này

BƯỚC 2: KHAI THÁC ĐỊA CHỈ (ƯU TIÊN #1)
- CHECK context.saved_address.address_line
- THIẾU → HỎI ĐẦY ĐỦ (số nhà + đường + phường + quận + TP)
- Khi khách cung cấp → TRÍCH XUẤT CHÍNH XÁC (pattern trong schema) → GỌI save_address
- Nếu khách gửi kèm SĐT/tên trong địa chỉ → Trích riêng (KHÔNG nhầm với save_customer_info)

BƯỚC 3: KHAI THÁC SĐT (ƯU TIÊN #2)
- CHECK context.profile.phone
- THIẾU → HỎI SAU KHI CÓ ĐỊA CHỈ
- Khi cung cấp → GỌI save_customer_info (chỉ phone)

BƯỚC 4: KHAI THÁC TÊN (ƯU TIÊN #3)
- CHECK context.profile.full_name hoặc preferred_name
- THIẾU → HỎI SAU KHI CÓ SĐT
- Khi cung cấp → GỌI save_customer_info (name)

BƯỚC 5: CONFIRM & CREATE ORDER (CHỈ KHI ĐỦ)
- ĐỦ: context.cart >0 + saved_address + profile.phone + profile.name
- GỌI confirm_and_create_order
- Response: Xác nhận chi tiết (sản phẩm, tổng tiền, địa chỉ, SĐT, tên)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📝 QUY TẮC KHAI THÁC:**
- HỎI TỪNG BƯỚC (1 info/lần) để tự nhiên
- Nếu khách cung cấp NHIỀU (VD: địa chỉ + SĐT) → GỌI NHIỀU TOOLS + Tiếp tục hỏi cái còn thiếu
- TRÍCH XUẤT: Sử dụng regex/pattern nghiêm ngặt từ schema
- Nếu data không khớp pattern → HỎI LẠI ("Chị xác nhận địa chỉ là [trích] phải không ạ?")

**VÍ DỤ NÂNG CẤP:**

Ex1: Trigger, thiếu tất cả
Khách: "Gửi hàng về cho chị"
→ add_to_cart → Hỏi địa chỉ

Ex2: Khách cung cấp địa chỉ + SĐT
Khách: "123 Nguyễn Trãi Q1 TP.HCM, SĐT 0987654321"
→ save_address + save_customer_info(phone) → Hỏi tên (nếu thiếu)

Ex3: Đủ rồi
→ confirm_and_create_order + Xác nhận đầy đủ

⚠️ TÍN HIỆU TRIGGER (mở rộng):
- "gửi hàng về cho chị", "gửi về nhà", "ship cho chị", etc.

┌─────────────────────────────────────────────────────────────┐
│ 1. save_customer_info - Lưu thông tin khách hàng cơ bản    │
└─────────────────────────────────────────────────────────────┘

KHI NÀO GỌI:
- Khách tự giới thiệu tên
- Khách cung cấp số điện thoại (KHÔNG phải trong địa chỉ)
- Khách nói về sở thích, phong cách

THAM SỐ:
{
  "name": "save_customer_info",
  "args": {
    "full_name": "string (optional) - Tên đầy đủ",
    "preferred_name": "string (optional) - Tên gọi thân mật",
    "phone": "string (optional) - SĐT (format: 0xxxxxxxxx hoặc +84xxxxxxxxx)",
    "style_preference": "array (optional) - ['thanh lịch', 'trẻ trung']",
    "usual_size": "string (optional) - Size thường mặc"
  }
}

VÍ DỤ:
Khách: "Em tên Hương, em thích phong cách thanh lịch"
→ Gọi: save_customer_info({ "preferred_name": "Hương", "style_preference": ["thanh lịch"] })

┌─────────────────────────────────────────────────────────────┐
│ 2. save_address - Lưu địa chỉ giao hàng ⭐ QUAN TRỌNG     │
└─────────────────────────────────────────────────────────────┘

⚠️ KHI NÀO GỌI:
CHỈ gọi khi khách CUNG CẤP ĐỊA CHỈ GIAO HÀNG đầy đủ bao gồm:
✅ Số nhà + Tên đường (VD: "123 Nguyễn Trãi")
✅ Thành phố (Hà Nội, TP.HCM, Đà Nẵng...)
✅ Có thể có: Phường/Xã, Quận/Huyện

❌ ĐỪNG GỌI KHI:
- Khách chỉ nói tên/SĐT mà chưa nói địa chỉ
- Khách chỉ nói "Hà Nội" mà không có số nhà/đường
- Địa chỉ chưa đầy đủ

THAM SỐ BẮT BUỘC:
{
  "name": "save_address",
  "args": {
    "address_line": "string (REQUIRED) - Số nhà + Tên đường. VD: '123 Nguyễn Trãi'",
    "city": "string (REQUIRED) - Thành phố. VD: 'Hà Nội', 'TP.HCM'",
    "district": "string (optional) - Quận/Huyện. VD: 'Hoàn Kiếm', 'Quận 1'",
    "ward": "string (optional) - Phường/Xã. VD: 'Phường Hàng Bài'",
    "phone": "string (optional) - SĐT người nhận (nếu khác SĐT profile)",
    "full_name": "string (optional) - Tên người nhận (nếu khác tên profile)"
  }
}

┌─────────────────────────────────────────────────────────────┐
│ 3. add_to_cart - Thêm sản phẩm vào giỏ hàng ⭐ UPDATED     │
└─────────────────────────────────────────────────────────────┘

⚠️ KHI NÀO GỌI:
- Khách nói "thêm vào giỏ", "lấy cái này"
- Khách xác nhận muốn mua sau khi tư vấn
- **⭐ Khách nói "gửi về", "gửi cho chị", "ship về"** (TÍN HIỆU MUA HÀNG)
- Khách nói số lượng cụ thể
- Khách nói "mẫu [số] gửi về"

THAM SỐ:
{
  "name": "add_to_cart",
  "args": {
    "product_id": "string (REQUIRED) - UUID sản phẩm từ context",
    "size": "string (optional, default: M) - Size: XS/S/M/L/XL/XXL/One Size",
    "quantity": "number (optional, default: 1) - Số lượng"
  }
}

┌─────────────────────────────────────────────────────────────┐
│ 4. confirm_and_create_order - Xác nhận và tạo đơn hàng    │
└─────────────────────────────────────────────────────────────┘

⚠️ KHI NÀO GỌI:
- Khách nói "đặt hàng", "chốt đơn", "mua luôn"
- Khách xác nhận địa chỉ giao hàng (nói "đúng", "ok", "được")
- **⭐ Khách nói "gửi về" + ĐÃ CÓ ĐẦY ĐỦ THÔNG TIN** (tên + địa chỉ)

⚠️ YÊU CẦU TRƯỚC KHI GỌI:
1. ✅ Phải có sản phẩm trong giỏ hàng (hoặc vừa add_to_cart)
2. ✅ Phải có địa chỉ giao hàng (saved_address)
3. ✅ Phải có tên khách hàng
4. ✅ Phải có SĐT khách hàng

===== QUY TẮC QUAN TRỌNG =====

1. ✅ CHỈ gọi function khi có ĐỦ THÔNG TIN
2. ✅ VALIDATE dữ liệu trước khi gọi
3. ✅ Một response có thể gọi NHIỀU function (VD: add_to_cart + confirm_and_create_order)
4. ⭐ **KHI KHÁCH NÓI "GỬI VỀ" → LUÔN GỌI add_to_cart TRƯỚC**
5. ❌ ĐỪNG gọi function nếu thông tin không rõ ràng
6. ❌ ĐỪNG tự bịa dữ liệu nếu khách không cung cấp

⭐ LƯU Ý CUỐI CÙNG:

- Khi khách nói "gửi về" = Tín hiệu mua hàng mạnh nhất
- LUÔN thêm sản phẩm vào giỏ trước, hỏi thông tin sau
- Giữ giỏ hàng, không xóa sản phẩm đã thêm
- Response phải TỰ NHIÊN, không cứng nhắc như form
"""


# AI Tools Schema - Định nghĩa các function cho AI model
AI_TOOLS_SCHEMA = {
    "tools": [
        {
            "name": "save_customer_info",
            "description": "Lưu thông tin cơ bản của khách hàng (tên, SĐT, sở thích). CHỈ gọi khi khách TỰ GIỚI THIỆU, không phải khi cung cấp địa chỉ giao hàng.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {
                        "type": "string",
                        "description": "Tên đầy đủ của khách hàng",
                    },
                    "preferred_name": {
                        "type": "string",
                        "description": "Tên gọi thân mật (VD: Lan, Hương)",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Số điện thoại liên hệ (0xxxxxxxxx hoặc +84xxxxxxxxx). CHỈ lấy khi khách giới thiệu bản thân, KHÔNG lấy từ địa chỉ giao hàng.",
                        "pattern": "^[0+][\\d]{9,11}$",
                    },
                    "style_preference": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Phong cách yêu thích (VD: ['thanh lịch', 'trẻ trung', 'sang trọng'])",
                    },
                    "usual_size": {
                        "type": "string",
                        "description": "Size thường mặc (XS/S/M/L/XL/XXL)",
                        "enum": ["XS", "S", "M", "L", "XL", "XXL"],
                    },
                },
            },
        },
        {
            "name": "save_address",
            "description": "Lưu địa chỉ giao hàng. CHỈ gọi khi khách CUNG CẤP ĐỊA CHỈ ĐẦY ĐỦ bao gồm: Số nhà + Tên đường + Thành phố. TUYỆT ĐỐI KHÔNG gọi nếu thiếu số nhà hoặc tên đường.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address_line": {
                        "type": "string",
                        "description": "Số nhà + Tên đường. VD: '123 Nguyễn Trãi', '45A Lê Lợi'. PHẢI có cả số và tên đường.",
                        "pattern": "^\\d+[A-Z]?\\s+.+",
                    },
                    "ward": {
                        "type": "string",
                        "description": "Phường/Xã (optional). VD: 'Phường Thanh Xuân Trung'",
                    },
                    "district": {
                        "type": "string",
                        "description": "Quận/Huyện (optional). VD: 'Quận Thanh Xuân', 'Quận 1'",
                    },
                    "city": {
                        "type": "string",
                        "description": "Thành phố (REQUIRED). VD: 'Hà Nội', 'TP.HCM', 'Đà Nẵng'",
                    },
                    "phone": {
                        "type": "string",
                        "description": "SĐT người nhận (optional, chỉ khi khác SĐT profile)",
                        "pattern": "^[0+][\\d]{9,11}$",
                    },
                    "full_name": {
                        "type": "string",
                        "description": "Tên người nhận (optional, chỉ khi khác tên profile)",
                    },
                },
                "required": ["address_line", "city"],
            },
        },
        {
            "name": "add_to_cart",
            "description": "Thêm sản phẩm vào giỏ hàng. GỌI NGAY khi khách nói 'gửi về', 'gửi cho chị', 'ship về', 'đặt luôn', 'lấy luôn'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "UUID của sản phẩm từ danh sách context.products",
                        "format": "uuid",
                    },
                    "size": {
                        "type": "string",
                        "description": "Size sản phẩm (Mặc định: M)",
                        "enum": ["XS", "S", "M", "L", "XL", "XXL", "One Size"],
                        "default": "M",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Số lượng (Mặc định: 1)",
                        "minimum": 1,
                        "default": 1,
                    },
                },
                "required": ["product_id"],
            },
        },
        {
            "name": "confirm_and_create_order",
            "description": "Xác nhận và tạo đơn hàng. CHỈ gọi khi: (1) Có sản phẩm, (2) Có địa chỉ, (3) Khách xác nhận HOẶC đã đủ thông tin giao hàng sau khi kích hoạt flow mua hàng ('gửi về').",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {
                        "type": "boolean",
                        "description": "Khách đã xác nhận đặt hàng",
                        "const": True,
                    },
                },
                "required": ["confirmed"],
            },
        },
    ],
}