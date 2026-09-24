# LoomLot-01 · 染坊缸染与色牢度抽检

靛蓝染坊台：按 **染坊 → 染缸 → 染程 → 色牢度** 工序推进，聚焦缸染调度与抽检，不是库存出入库系统。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Backend | FastAPI + SQLAlchemy 2 + Pydantic v2 + Postgres + JWT |
| Frontend | Svelte 4 + Vite + svelte-spa-router |
| 部署 | docker-compose（db + backend + frontend/nginx） |

## 端口

| 服务 | 端口 |
| --- | --- |
| 前端 | **3600** |
| 后端 API | **8600** |
| PostgreSQL | **5439** |

数据库账号：`loomlot` / `loomlot` / 库名 `loomlot`。

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 染坊主管 |
| `dyer` | `123456` | 染程操作员 |

容器启动时 entrypoint 自动建表并 seed。

## 快速启动

```bash
cd D:\work\document\bytecode\claudeCodePro\LoomLot\LoomLot-01
docker compose up -d --build
```

浏览器：http://localhost:3600  
API：http://localhost:8600/api/health

停止：

```bash
docker compose down
```

## 业务实体

1. **DyeHouse** — `name`, `waterNote`, `notes`
2. **Vat** — `dyeHouseId`, `vatCode`, `fiberType`, `capacityL`, `status` ∈ `ready|dyeing|drain`
3. **DyeLot** — `vatId`, `recipeName`, `fabricKg`, `startedAt`, `operatorName`
4. **FastnessCheck** — `dyeLotId`, `checkedAt`, `washFastness`(1–5), `rubFastness`(>0), `tempC`, `notes`
5. **SampleSlot**（留样格位）— `dyeHouseId`, `slotCode`, `capacity`(正整数), `storedCount`(默认 0), `isActive`；同坊格位码唯一
6. **SampleBinding**（入格记录）— `slotId`, `fastnessCheckId`(唯一，一条色牢度只能入一次), `boundAt`

### 规则

- 仅当染缸状态为 `ready` 或 `dyeing` 时可新建染程，否则 409
- 新建染程后，染缸状态自动设为 `dyeing`
- 可选接口：`POST /api/vats/{id}/drain` 将染缸置为 `drain`
- **新建染程布重上限默认 100 千克**。
- **留样占位降限**：当某染坊**所有启用格位的 `storedCount` 合计大于 0** 时，该坊染缸上新建染程的布重上限降为 **50 千克**；超限返回 400 并提示「因留样占位」。待该坊启用格位留样全部取出、已存合计清零后，恢复为 100 千克。停用格位不计入合计。
- **入格**：`POST /api/sample-slots/{id}/bindings` 绑定一条色牢度，`storedCount` 加一；格满（`storedCount >= capacity`）返回 409；一条色牢度只能入一次（重复入格 409）；只能绑定本坊染程所属色牢度（跨坊 409，入格与色牢度互证）；停用格位不能入格。操作员（dyer）即可入格 / 取出。
- **停用格位**需染坊主管（admin），且该格位 `storedCount` 必须为 0，否则 409。
- 删除已入格的色牢度会同步取出其留样并将格位已存减一；已入格色牢度不允许改挂染程。

## 主要 API

- `POST /api/auth/login`（OAuth2 表单）
- `GET /api/auth/me`
- `GET/POST/PUT/DELETE /api/dye-houses`
- `GET/POST/PUT/DELETE /api/vats` · `POST /api/vats/{id}/drain`
- `GET/POST/PUT/DELETE /api/dye-lots`
- `GET/POST/PUT/DELETE /api/fastness-checks`
- `GET/POST/PUT/DELETE /api/sample-slots`（**停用**需主管；删除要求已存为 0）
  - `POST /api/sample-slots/{id}/bindings`（入格，操作员可执行）
  - `GET /api/sample-slots/bindings`（可按 `slotId` / `fastnessCheckId` 过滤）
  - `DELETE /api/sample-slots/bindings/{id}`（取出留样，已存减一）
- `GET /api/dashboard/stats`（含 `occupiedSlotCount`：已存条数大于 0 的格位数）

除登录外需 `Authorization: Bearer <token>`。字段对外为 camelCase。

## 目录

```
LoomLot-01/
├── docker-compose.yml
├── backend/          # FastAPI
├── frontend/         # Svelte 4 + Vite + nginx
└── README.md
```

## 本地开发

### 数据库

```bash
docker compose up -d db
```

### 后端

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
$env:DATABASE_URL="postgresql+psycopg2://loomlot:loomlot@127.0.0.1:5439/loomlot"
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
uvicorn app.main:app --reload --port 8600
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

开发态 Vite 将 `/api` 代理到 `http://127.0.0.1:8600`。
