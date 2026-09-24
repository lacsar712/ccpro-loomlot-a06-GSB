# LoomLot-01 · 染坊缸染与色牢度抽检

靛蓝染坊台：按 **染坊 → 染缸 → 染程 → 色牢度 → 留样格** 工序推进，聚焦缸染调度、抽检与留样占位，不是库存出入库系统。

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
4. **FastnessCheck** — `dyeLotId`, `checkedAt`, `washFastness`(1–5), `rubFastness`(>0), `tempC`, `notes`, `sampleSlotId`（入格绑定，可空）
5. **SampleSlot（留样格）** — `dyeHouseId`, `slotCode`, `capacity`（可存条数，正整数）, `storedCount`（已存条数，默认 0）, `enabled`（启用与否）；同坊 `slotCode` 唯一

### 规则

- 仅当染缸状态为 `ready` 或 `dyeing` 时可新建染程，否则 409
- 新建染程后，染缸状态自动设为 `dyeing`
- 可选接口：`POST /api/vats/{id}/drain` 将染缸置为 `drain`

#### 留样格与入格

- 同坊格位码唯一（重复返回 400）；可存条数必须为正整数（`< 1` 返回 400）。
- 入格：`POST /api/sample-slots/{id}/store`，绑定一条色牢度，`storedCount` 加一。
  - 操作员（dyer）即可入格；停用中的格位不能入格（409）。
  - 一条色牢度只能入一次（重复入格 409）；满格再入返回 409。
- 出格：`POST /api/sample-slots/{id}/unstore`，解除绑定、`storedCount` 减一。
- **停用格位需染坊主管（admin）**，且该格位已存必须为 0，否则分别返回 403 / 409。
- 删除格位同样要求已存为 0（409）。

#### 留样占位 → 染程布重降限（核心联动）

- 当某染坊**所有启用格位的已存条数合计大于 0** 时，该坊各染缸上**新建染程的布重上限降为 50 千克**；提交 `fabricKg > 50` 返回 **400**，并提示「因留样占位」。
- 判定按染坊隔离，且只统计**启用**格位：他坊留样不影响本坊；停用格位中的存量不计入。
- 待该坊启用格位已存全部清零（留样全部取出）后，恢复原布重规则（不再设 50kg 上限）。
- 染程改挂染缸 / 修改布重时同样按目标染坊当前占位状态校验。
- 该联动在后端 `POST/PUT /api/dye-lots` 强制执行，前端仅作提示，故「格位与布重上限互不影响」的实现不过关。
- 看板 `sampleSlotsOccupied` 展示**已存大于 0 的格位数**，与留样格列表统计口径一致。
- 种子数据含一格已存（一号坊 `R-01`，已存 1 条并绑定一条色牢度），因此初始状态下一号坊新建染程布重上限为 50kg。

## 主要 API

- `POST /api/auth/login`（OAuth2 表单）
- `GET /api/auth/me`
- `GET/POST/PUT/DELETE /api/dye-houses`
- `GET/POST/PUT/DELETE /api/vats` · `POST /api/vats/{id}/drain`
- `GET/POST/PUT/DELETE /api/dye-lots`
- `GET/POST/PUT/DELETE /api/fastness-checks`
- `GET/POST/PUT/DELETE /api/sample-slots` · `POST /api/sample-slots/{id}/store` · `POST /api/sample-slots/{id}/unstore`
- `GET /api/dashboard/stats`

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
