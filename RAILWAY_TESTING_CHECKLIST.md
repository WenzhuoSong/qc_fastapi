# Railway Environment Testing Checklist
**Phase 2 Week 1 - Database Migration & Validation**

---

## 前提条件

- [x] Week 1代码已推送到GitHub (commit 7013bab)
- [x] Railway自动部署完成
- [ ] 有Railway环境访问权限
- [ ] 有DATABASE_URL环境变量

---

## 步骤1：连接Railway环境

### 方法A：Railway CLI（推荐）

```bash
# 1. 安装Railway CLI（如果未安装）
# macOS:
brew install railway

# 2. 登录
railway login

# 3. 链接到项目
railway link

# 4. 运行migration
railway run python migrate_phase2.py
```

### 方法B：Railway Web Console

1. 访问 https://railway.app
2. 进入qc_fastapi项目
3. 点击 Web Service
4. 进入 "Deployments" 标签
5. 找到最新部署（commit 7013bab）
6. 点击 "View Logs" 查看部署状态

### 方法C：本地连接Railway数据库

```bash
# 1. 获取DATABASE_URL
railway variables

# 2. 导出到本地环境
export DATABASE_URL="postgresql://..."

# 3. 运行migration
python migrate_phase2.py
```

---

## 步骤2：运行Database Migration

### 执行migration脚本

```bash
railway run python migrate_phase2.py
```

**预期输出：**
```
=== Phase 2 Migration: Event Transmission Table ===
Creating event_transmission table...
✓ event_transmission table created successfully
✓ Table verification passed

Table schema:
  - id: INTEGER
  - date: DATE
  - event_id: VARCHAR(100)
  - event_type: VARCHAR(50)
  - event_description: TEXT
  - confidence: INTEGER
  - transmission_vector: JSONB
  - validated: BOOLEAN
  - accuracy_score: DOUBLE_PRECISION
  - created_at: TIMESTAMP

=== Phase 2 Migration Complete ===
```

### 如果表已存在

```
✓ event_transmission table already exists, skipping creation
```

### 如果出错

**常见错误1：无法连接数据库**
```
Error: could not connect to server
```
解决：检查DATABASE_URL环境变量

**常见错误2：权限不足**
```
Error: permission denied to create table
```
解决：检查数据库用户权限（Railway默认用户应该有权限）

---

## 步骤3：验证表创建（SQL查询）

### 连接到Railway PostgreSQL

```bash
# 方法A：Railway CLI
railway connect postgres

# 方法B：使用psql（需要DATABASE_URL）
psql $DATABASE_URL
```

### 验证表存在

```sql
-- 检查表是否存在
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name = 'event_transmission'
);
-- 预期: t (true)

-- 查看表结构
\d event_transmission

-- 查看所有表
\dt

-- 预期看到：
-- daily_decisions
-- daily_holdings
-- daily_news_digest
-- decision_log
-- ticker_news_library
-- sector_news_library
-- event_transmission  ← 新表
```

### 验证索引

```sql
-- 查看索引
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'event_transmission';

-- 预期：
-- event_transmission_pkey (PRIMARY KEY on id)
-- ix_event_transmission_date (INDEX on date)
-- ix_event_transmission_event_id (UNIQUE INDEX on event_id)
-- ix_event_transmission_event_type (INDEX on event_type)
```

---

## 步骤4：插入测试数据

### 测试数据1：2026-03-20 Iran War

```sql
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector,
    validated
) VALUES (
    '2026-03-20',
    'macro_2026-03-20',
    'supply_shock_oil',
    'Iran war escalation with Strait of Hormuz closure threat causing oil supply disruption',
    85,
    '{"XLE": 1.0, "XLY": -1.0, "XLI": 1.0, "XLK": -0.95, "XLF": -0.8, "XLB": 1.0, "XLP": -0.7, "XLV": -0.55, "XLU": -0.9, "XLC": -0.75, "XLRE": -1.0}'::jsonb,
    false
);

-- 验证插入
SELECT * FROM event_transmission WHERE date = '2026-03-20';
```

### 测试数据2：模拟Fed Rate Hike

```sql
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector,
    validated
) VALUES (
    '2026-03-15',
    'macro_2026-03-15',
    'rate_shock_hawkish',
    'Fed hikes 75bps to 5.5%, Powell signals higher for longer',
    90,
    '{"XLF": 0.7, "XLE": 0.3, "XLB": 0.2, "XLI": 0.1, "XLV": 0.1, "XLP": -0.1, "XLC": -0.4, "XLY": -0.5, "XLU": -0.6, "XLK": -0.8, "XLRE": -0.9}'::jsonb,
    false
);
```

### 测试数据3：Risk-Off Credit Stress

```sql
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector,
    validated
) VALUES (
    '2026-03-10',
    'macro_2026-03-10',
    'risk_off_credit_stress',
    'Regional bank failures trigger credit stress, VIX spikes to 45',
    80,
    '{"XLV": 0.85, "XLP": 0.8, "XLU": 0.7, "XLV": 0.3, "XLB": -0.4, "XLI": -0.4, "XLRE": -0.6, "XLC": -0.5, "XLF": -0.7, "XLK": -0.7, "XLY": -0.85}'::jsonb,
    false
);
```

---

## 步骤5：JSONB查询性能测试

### 查询1：查找所有能源受益事件

```sql
SELECT
    date,
    event_type,
    confidence,
    transmission_vector->>'XLE' as xle_strength,
    event_description
FROM event_transmission
WHERE (transmission_vector->>'XLE')::float > 0.8
ORDER BY date DESC;

-- 预期结果：
-- 2026-03-20, supply_shock_oil, XLE=1.0
```

### 查询2：查找所有科技受损事件

```sql
SELECT
    date,
    event_type,
    transmission_vector->>'XLK' as xlk_strength
FROM event_transmission
WHERE (transmission_vector->>'XLK')::float < -0.5
ORDER BY date DESC;

-- 预期结果：
-- 2026-03-20, supply_shock_oil, XLK=-0.95
-- 2026-03-15, rate_shock_hawkish, XLK=-0.8
-- 2026-03-10, risk_off_credit_stress, XLK=-0.7
```

### 查询3：统计事件类型分布

```sql
SELECT
    event_type,
    COUNT(*) as count,
    AVG(confidence) as avg_confidence
FROM event_transmission
GROUP BY event_type
ORDER BY count DESC;
```

### 查询4：查找多个sector同时受益/受损的事件

```sql
-- 查找XLE和XLI同时强受益的事件（oil war场景）
SELECT
    date,
    event_type,
    transmission_vector->>'XLE' as xle,
    transmission_vector->>'XLI' as xli
FROM event_transmission
WHERE (transmission_vector->>'XLE')::float > 0.8
  AND (transmission_vector->>'XLI')::float > 0.8;
```

### 性能优化：创建GIN索引

```sql
-- 为JSONB字段创建GIN索引（如果数据量大）
CREATE INDEX idx_transmission_vector
ON event_transmission
USING GIN (transmission_vector);

-- 验证索引创建
\d event_transmission
```

---

## 步骤6：集成测试（与现有表关联）

### 测试1：关联daily_decisions表

```sql
-- 查看是否有对应日期的decision记录
SELECT
    dd.date,
    dd.status,
    et.event_type,
    et.confidence,
    et.transmission_vector->>'XLE' as xle_transmission
FROM daily_decisions dd
LEFT JOIN event_transmission et ON dd.date = et.date
WHERE dd.date >= '2026-03-10'
ORDER BY dd.date DESC
LIMIT 5;

-- 如果event_transmission有数据但daily_decisions没有，说明还未运行pipeline
```

### 测试2：关联daily_news_digest表

```sql
-- 对比macro_regime和event_type
SELECT
    dnd.date,
    dnd.macro_regime,
    dnd.confidence,
    et.event_type,
    et.confidence as event_confidence
FROM daily_news_digest dnd
LEFT JOIN event_transmission et ON dnd.date = et.date
WHERE dnd.date >= '2026-03-10'
ORDER BY dnd.date DESC;
```

---

## 步骤7：数据完整性检查

### 检查1：验证JSONB格式正确

```sql
-- 检查transmission_vector是否包含所有11个sector
SELECT
    date,
    event_id,
    jsonb_object_keys(transmission_vector) as sector
FROM event_transmission
WHERE date = '2026-03-20';

-- 预期返回11行：XLE, XLF, XLV, XLI, XLP, XLU, XLY, XLK, XLC, XLRE, XLB
```

### 检查2：验证值范围

```sql
-- 检查是否有超出[-1.0, 1.0]范围的值
WITH sector_values AS (
    SELECT
        date,
        event_id,
        key as sector,
        value::text::float as strength
    FROM event_transmission,
    LATERAL jsonb_each(transmission_vector)
)
SELECT
    date,
    event_id,
    sector,
    strength
FROM sector_values
WHERE strength < -1.0 OR strength > 1.0;

-- 预期：空结果（无超出范围的值）
```

### 检查3：验证event_id唯一性

```sql
-- 检查是否有重复的event_id
SELECT event_id, COUNT(*)
FROM event_transmission
GROUP BY event_id
HAVING COUNT(*) > 1;

-- 预期：空结果（无重复）
```

---

## 步骤8：清理测试数据（可选）

如果需要清空测试数据重新开始：

```sql
-- 删除所有测试数据
DELETE FROM event_transmission;

-- 重置自增ID（PostgreSQL）
ALTER SEQUENCE event_transmission_id_seq RESTART WITH 1;

-- 验证表为空
SELECT COUNT(*) FROM event_transmission;
-- 预期：0
```

---

## 验收标准

### ✅ Migration成功标准

- [ ] migrate_phase2.py执行无错误
- [ ] event_transmission表存在
- [ ] 表包含10个列（id, date, event_id, event_type, event_description, confidence, transmission_vector, validated, accuracy_score, created_at）
- [ ] 有4个索引（PRIMARY KEY + 3个INDEX）

### ✅ 数据插入标准

- [ ] 可以成功插入测试数据（至少3条）
- [ ] JSONB字段可以正确存储和查询
- [ ] 每个transmission_vector包含11个sector
- [ ] 所有strength值在[-1.0, 1.0]范围内

### ✅ 查询性能标准

- [ ] 按date查询 < 10ms
- [ ] JSONB条件查询 < 50ms（无索引）
- [ ] JSONB条件查询 < 20ms（有GIN索引）

### ✅ 集成标准

- [ ] 可以与daily_decisions表LEFT JOIN
- [ ] 可以与daily_news_digest表LEFT JOIN
- [ ] event_id格式与daily_decisions.date匹配

---

## 问题排查

### 问题1：migration脚本找不到模块

```
ModuleNotFoundError: No module named 'sqlalchemy'
```

**解决：**
```bash
# 在Railway环境应该已安装，如果没有：
railway run pip install -r requirements.txt
```

### 问题2：数据库连接超时

```
could not connect to server: Connection timed out
```

**解决：**
- 检查Railway服务是否运行中
- 检查DATABASE_URL是否正确
- 检查网络连接

### 问题3：表已存在但结构不对

```
Table exists but missing columns
```

**解决：**
```sql
-- 删除旧表重建
DROP TABLE event_transmission;

-- 重新运行migration
railway run python migrate_phase2.py
```

### 问题4：JSONB查询很慢

**解决：**
```sql
-- 创建GIN索引
CREATE INDEX idx_transmission_vector ON event_transmission USING GIN (transmission_vector);

-- 如果还是慢，检查数据量
SELECT COUNT(*) FROM event_transmission;
-- 如果 < 1000行，不应该慢
```

---

## 完成后的截图/验证

请保存以下验证截图：

1. **Migration输出**
   ```bash
   railway run python migrate_phase2.py > migration_output.txt
   ```

2. **表结构**
   ```sql
   \d event_transmission > table_structure.txt
   ```

3. **测试查询结果**
   ```sql
   SELECT * FROM event_transmission LIMIT 5;
   -- 截图或保存结果
   ```

---

## 下一步

完成Railway测试后，可以选择：

1. **继续更多场景测试** - 添加更多历史事件数据
2. **开始Week 2集成** - 集成到Step 1和Step 2
3. **调优传导规则** - 根据测试结果调整strength值

---

**Checklist进度：**

- [ ] 步骤1：连接Railway环境
- [ ] 步骤2：运行migration脚本
- [ ] 步骤3：验证表创建（SQL查询）
- [ ] 步骤4：插入测试数据
- [ ] 步骤5：JSONB查询性能测试
- [ ] 步骤6：集成测试（与现有表关联）
- [ ] 步骤7：数据完整性检查
- [ ] 步骤8：清理测试数据（可选）

**预计耗时：** 15-30分钟

开始测试吧！有问题随时告诉我。
