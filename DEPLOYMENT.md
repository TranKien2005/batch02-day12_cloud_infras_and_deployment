# Deployment Information

## Public URL
https://production-agent-day12-production.up.railway.app

## Platform
Railway

## Test Commands

### Health Check
```bash
curl https://production-agent-day12-production.up.railway.app/health
# Expected: {"status": "ok"}
```

### API Test (with authentication)
```bash
curl -X POST https://production-agent-day12-production.up.railway.app/ask \
  -H "X-API-Key: my-super-secret-key-999" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is cloud deployment?"}'
```

## Environment Variables Set
- `PORT`: `8000` (Assigned dynamically or configured manually for internal routing)
- `AGENT_API_KEY`: `my-super-secret-key-999` (API authorization key)
- `ENVIRONMENT`: `production` (Activates production-ready configurations and checks)
- `JWT_SECRET`: `my-super-secret-jwt-secret-999` (JSON Web Token signature key)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png) *(Vui lòng chụp ảnh màn hình dashboard Railway của bạn, tạo thư mục `screenshots` và lưu ảnh vào đó với tên `dashboard.png`)*
- [Service running](screenshots/running.png) *(Vui lòng chụp ảnh màn hình logs của container đang hiển thị trạng thái `ready`)*
- [Test results](screenshots/test.png) *(Vui lòng chụp ảnh kết quả chạy cURL kiểm thử API ở trên)*
