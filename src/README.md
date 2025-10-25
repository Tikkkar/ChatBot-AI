# Mô tả thư mục `src`

Tệp này giải thích cấu trúc và mục đích của các tệp và thư mục trong thư mục `src`.

## Tệp

- `__init__.py`: Đánh dấu thư mục `src` là một Python package, cho phép import các mô-đun từ bên trong nó.
- `main.py`: Điểm khởi đầu chính của ứng dụng. Tệp này chịu trách nhiệm khởi tạo và chạy ứng dụng (ví dụ: khởi động máy chủ web).

## Thư mục

- `agent/`: Chứa logic cốt lõi của chatbot agent. Điều này bao gồm cách agent xử lý thông tin, đưa ra quyết định và tạo phản hồi.

- `config/`: Chứa các tệp cấu hình cho ứng dụng. Ví dụ: khóa API, thông tin kết nối cơ sở dữ liệu, và các cài đặt khác.

- `handlers/`: Xử lý các sự kiện hoặc tác vụ cụ thể. Ví dụ, nó có thể chứa logic để xử lý các kết nối WebSocket, các webhook, hoặc các sự kiện không đồng bộ khác.

- `routes/`: Định nghĩa các điểm cuối (endpoints) API của ứng dụng web. Nó ánh xạ các URL tới các hàm xử lý cụ thể, thường nằm trong thư mục `handlers` hoặc `services`.

- `services/`: Chứa logic nghiệp vụ (business logic) của ứng dụng. Các service này được gọi bởi các `routes` để thực hiện các tác vụ chính, tách biệt logic khỏi lớp giao diện web.

- `utils/`: Chứa các hàm và công cụ tiện ích được sử dụng chung trong toàn bộ ứng dụng để tránh lặp lại mã.

## Chi tiết các thư mục con

### `agent/`
- `agent_service.py`: Chứa logic triển khai cốt lõi của agent chatbot, bao gồm xử lý đầu vào người dùng, tương tác với các dịch vụ khác và tạo phản hồi.

### `config/`
- `__init__.py`: Đánh dấu thư mục `config` là một Python package.
- `env.py`: Xử lý các biến môi trường và cài đặt cấu hình ứng dụng.

### `handlers/`
- `__init__.py`: Đánh dấu thư mục `handlers` là một Python package.
- `message_handler.py`: Xử lý các tin nhắn đến, có thể từ nhiều nền tảng khác nhau (ví dụ: Facebook, web).
- `order_handler.py`: Quản lý các tương tác và logic liên quan đến đơn hàng.

### `routes/`
- `__init__.py`: Đánh dấu thư mục `routes` là một Python package.
- `chat.py`: Định nghĩa các điểm cuối API dành riêng cho các chức năng trò chuyện.

### `services/`
- `__init__.py`: Đánh dấu thư mục `services` là một Python package.
- `address_extraction_service.py`: Trích xuất thông tin địa chỉ từ văn bản.
- `address_service.py`: Quản lý các hoạt động liên quan đến địa chỉ.
- `cart_service.py`: Xử lý logic giỏ hàng.
- `chatbot_order_service.py`: Quản lý quy trình đặt hàng dành riêng cho chatbot.
- `context_service.py`: Quản lý ngữ cảnh hội thoại của chatbot.
- `customer_profile_service.py`: Quản lý dữ liệu hồ sơ khách hàng.
- `embedding_service.py`: Cung cấp các chức năng tạo embedding cho văn bản.
- `facebook_service.py`: Tích hợp với nền tảng Facebook (ví dụ: Messenger).
- `memory_service.py`: Quản lý bộ nhớ hoặc trạng thái của chatbot.

### `utils/`
- `connect_supabase.py`: Tiện ích để kết nối với cơ sở dữ liệu Supabase.
- `formatters.py`: Chứa các hàm để định dạng dữ liệu.

# Method 1: Dùng Invoke-RestMethod
