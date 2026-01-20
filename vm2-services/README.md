# 🔧 VM2 Recovery Services

Сервисы для управления VM1 с VM2 когда VM1 недоступна.

## 🚨 Экстренная перезагрузка VM1

### Вариант 1: Oracle Console (если ничего не работает)
```
1. https://cloud.oracle.com
2. Menu → Compute → Instances  
3. Найти VM (92.5.72.169)
4. Actions → Reboot
```

### Вариант 2: VM Controller API (после установки)
```bash
# Мягкая перезагрузка через SSH
curl -X POST "http://158.180.56.74:5100/vm1/reboot/soft?key=vm-controller-2026"

# Жёсткая перезагрузка через OCI CLI
curl -X POST "http://158.180.56.74:5100/vm1/reboot/hard?key=vm-controller-2026"
```

### Вариант 3: SSH напрямую на VM2
```bash
ssh ubuntu@158.180.56.74
ssh ubuntu@92.5.72.169 "sudo reboot"
```

## 📦 Установка VM Controller на VM2

### Быстрая установка:
```bash
ssh ubuntu@158.180.56.74
curl -sL https://raw.githubusercontent.com/tikserziku/vm2-infrastructure/main/vm2-services/setup_recovery.sh | bash
```

### Ручная установка:
```bash
# 1. Скачать
curl -sL https://raw.githubusercontent.com/tikserziku/vm2-infrastructure/main/vm2-services/vm_controller.py -o ~/vm_controller.py

# 2. Установить зависимости
pip3 install flask requests --break-system-packages

# 3. Запустить
python3 ~/vm_controller.py
```

## ⚙️ Настройка OCI CLI для жёсткой перезагрузки

OCI CLI позволяет перезагрузить VM даже когда она полностью зависла.

### 1. Установка OCI CLI
```bash
pip3 install oci-cli --break-system-packages
```

### 2. Настройка
```bash
oci setup config
```
Потребуется:
- User OCID (Oracle Console → Profile → User Settings)
- Tenancy OCID (Oracle Console → Profile → Tenancy)
- Region (например eu-frankfurt-1)

### 3. Добавить API Key в Oracle Console
```bash
cat ~/.oci/oci_api_key_public.pem
```
Скопировать и добавить в: Oracle Console → Profile → API Keys → Add API Key

### 4. Получить Instance OCID
Oracle Console → Compute → Instances → твоя VM → OCID (Copy)

### 5. Добавить в сервис
```bash
sudo systemctl edit vm-controller
```
Добавить:
```
[Service]
Environment=VM1_INSTANCE_OCID=ocid1.instance.oc1.eu-frankfurt-1.xxxxx
```

### 6. Перезапустить
```bash
sudo systemctl restart vm-controller
```

## 🔗 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/vm1/ping` | GET | Check if VM1 is alive |
| `/vm1/status` | GET | VM1 services status |
| `/vm1/ssh` | POST | Execute command on VM1 |
| `/vm1/reboot/soft` | POST | SSH reboot |
| `/vm1/reboot/hard` | POST | OCI CLI reboot |
| `/vm1/oci-action` | POST | OCI action (STOP/START/RESET) |

## 📊 Архитектура

```
┌─────────────────┐     ┌─────────────────┐
│   Claude/User   │     │  Oracle Console │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│           VM2 (158.180.56.74)           │
│  ┌─────────────────────────────────┐    │
│  │     VM Controller (:5100)       │    │
│  │  - SSH to VM1                   │    │
│  │  - OCI CLI commands             │    │
│  └─────────────────────────────────┘    │
└─────────────────┬───────────────────────┘
                  │ SSH / OCI API
                  ▼
┌─────────────────────────────────────────┐
│           VM1 (92.5.72.169)             │
│         24 grok-* services              │
└─────────────────────────────────────────┘
```

## 🔐 Безопасность

- API защищён ключом: `X-API-Key` header или `?key=` параметр
- Опасные команды заблокированы
- Только grok-* сервисы можно перезапускать

---
*Created for AGI Infrastructure resilience*
