# Phase 2 Week 1 Testing Guide
**如何测试现有成果，无需继续开发**

---

## 测试方法总览

| 测试类型 | 工具 | 耗时 | 适用场景 |
|---------|------|------|---------|
| ✅ 自动化测试 | test_phase2_manual.py | 5秒 | 快速验证所有场景 |
| 🔍 交互式测试 | Python REPL | 自定义 | 探索性测试，自定义场景 |
| 📊 历史数据对比 | 手动对比 | 10分钟 | 对比Phase 1 vs Phase 2输出 |
| 🗄️ 数据库测试 | Railway环境 | 5分钟 | 验证migration脚本 |

---

## ✅ 方法1：自动化测试套件（推荐）

### 已完成 ✓

```bash
python test_phase2_manual.py
```

**测试覆盖：**
- ✅ Test 1: 6个典型模式定义验证（11 sectors, 范围校验）
- ✅ Test 2: 2026-03-20历史场景（伊朗战争+石油危机）
- ✅ Test 3: 利率冲击场景（Fed hawkish）
- ✅ Test 4: Risk-off场景（信用危机）
- ✅ Test 5: 多模式叠加（油价战争 = supply_shock + war）
- ✅ Test 6: 无匹配场景（常规企业新闻）

**关键结果：**
```
Test 2: 2026-03-20 Iran War Scenario
  ✓ XLE should be strong winner: +1.00 (clipped from 1.75)
  ✓ XLY should be strong loser: -1.00 (clipped from -1.45)
  ✓ XLI should benefit (defense): +1.00
  ✓ XLK should be hurt (growth): -0.95

Test 5: Multiple Pattern Blending
  ✓ XLE: +1.00 (amplified by both patterns)
  ✓ XLI: +1.00 (amplified by both patterns)
  ✓ XLY: -1.00 (very negative)
```

---

## 🔍 方法2：交互式测试（Python REPL）

### 启动Python交互环境

```bash
python
```

### 测试1：加载传导规则

```python
from app.pipeline.transmission_rules import (
    match_event_to_pattern,
    detect_event_type,
    format_transmission_context,
    CANONICAL_TRANSMISSIONS
)

# 查看所有模式
print(f"已定义 {len(CANONICAL_TRANSMISSIONS)} 个模式:")
for name in CANONICAL_TRANSMISSIONS:
    print(f"  - {name}")
```

### 测试2：自定义场景测试

```python
# 场景：美联储降息
key_events = ["Fed cuts rates 50bps", "Powell dovish", "QE announced"]
reasoning = "Fed pivots to easing with emergency rate cut and QE..."

transmission = match_event_to_pattern(key_events, reasoning)

# 查看结果
for sector, strength in sorted(transmission.items(), key=lambda x: -x[1]):
    print(f"{sector}: {strength:+.2f}")
```

### 测试3：格式化输出（Step 2 prompt用）

```python
# 格式化为Step 2 prompt可用的文本
formatted = format_transmission_context(transmission)
print(formatted)
```

**预期输出：**
```
## MACRO EVENT TRANSMISSION (Phase 2 Prior)
The following sector biases are derived from macro event analysis:
  XLRE: LONG 0.80
  XLK: LONG 0.70
  XLU: LONG 0.70
  ...

INSTRUCTION: Use these as STARTING POINTS, then refine with ticker-level news.
```

### 测试4：事件类型检测

```python
event_type = detect_event_type(key_events, reasoning)
print(f"检测到的事件类型: {event_type}")
# 输出: fed_dovish_easing
```

### 测试5：对比不同模式

```python
# 对比供给冲击 vs 需求冲击对XLE的影响
patterns = ["supply_shock_oil", "recession_demand_collapse"]

for pattern_name in patterns:
    vector = CANONICAL_TRANSMISSIONS[pattern_name]["vector"]
    print(f"\n{pattern_name}:")
    print(f"  XLE (Energy): {vector['XLE']:+.2f}")
    print(f"  XLY (Consumer): {vector['XLY']:+.2f}")
```

**预期对比：**
```
supply_shock_oil:
  XLE (Energy): +0.95  ← 供给冲击，能源受益
  XLY (Consumer): -0.75

recession_demand_collapse:
  XLE (Energy): -0.60  ← 需求崩溃，能源受损
  XLY (Consumer): -0.80
```

---

## 📊 方法3：历史数据对比（Phase 1 vs Phase 2）

### 步骤1：提取Phase 1输出（2026-03-20）

```bash
# 查看Git历史中Phase 1的输出
git show 08f4f27:logs/pipeline_2026_03_20.log
```

或者手动记录当时的sector scores（如果有保存的话）。

### 步骤2：模拟Phase 2输出

```python
from app.pipeline.transmission_rules import match_event_to_pattern

# 2026-03-20的实际key_events
key_events = [
    "Iran war escalation",
    "Strait of Hormuz threatened",
    "Oil supply disruption concerns"
]

reasoning = """
Military tensions in the Middle East have escalated with Iran threatening
to close the Strait of Hormuz, a critical chokepoint for global oil shipments.
This has created severe oil supply disruption fears, with crude prices surging
toward $200/barrel. Defense contractors are benefiting from increased military
spending, while consumer sectors face demand destruction from high energy costs.
"""

transmission = match_event_to_pattern(key_events, reasoning)

# 打印传导向量（这是Phase 2会传递给Step 2的先验）
print("Phase 2 Transmission Vector:")
for sector in sorted(transmission.keys()):
    print(f"  {sector}: {transmission[sector]:+.2f}")
```

### 步骤3：对比分析

**Phase 1（当前生产）：**
- Step 2完全依赖Macro Event Transmission Rules（硬编码在prompt）
- 没有量化的传导强度
- 无法处理多事件叠加

**Phase 2（Week 1实现）：**
- 传导向量量化：XLE=+1.00, XLY=-1.00
- 多模式自动叠加（oil + war → XLE超强）
- 可以在Step 2 prompt中作为先验使用

**预期改进：**
- ✅ 更精确的sector权重初始值
- ✅ 多事件情况下的累积效应建模
- ✅ 可追溯的因果链（macro event → transmission → sector score）

---

## 🗄️ 方法4：数据库Migration测试（Railway环境）

### 前提条件

需要在Railway环境中运行，因为本地可能没有PostgreSQL。

### 步骤1：连接Railway环境

```bash
# 方法A：通过Railway CLI（如果已安装）
railway run python migrate_phase2.py

# 方法B：SSH到Railway服务
# (需要Railway Pro账户)
```

### 步骤2：手动验证表创建

连接到Railway PostgreSQL：

```sql
-- 检查表是否存在
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_name = 'event_transmission'
);

-- 查看表结构
\d event_transmission

-- 预期输出：
-- Column                 | Type      | Nullable
-- -----------------------+-----------+---------
-- id                     | integer   | not null
-- date                   | date      | not null
-- event_id               | varchar   | not null
-- event_type             | varchar   |
-- event_description      | text      |
-- confidence             | integer   |
-- transmission_vector    | jsonb     |
-- validated              | boolean   |
-- accuracy_score         | float     |
-- created_at             | timestamp |
```

### 步骤3：插入测试数据

```sql
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector
) VALUES (
    '2026-03-20',
    'macro_2026-03-20',
    'supply_shock_oil',
    'Iran war escalation with Hormuz closure threat',
    85,
    '{"XLE": 1.0, "XLY": -1.0, "XLI": 1.0, "XLK": -0.95, "XLF": -0.8, "XLB": 1.0, "XLP": -0.7, "XLV": -0.55, "XLU": -0.9, "XLC": -0.75, "XLRE": -1.0}'::jsonb
);

-- 查询测试
SELECT
    date,
    event_type,
    confidence,
    transmission_vector->'XLE' as xle_strength,
    transmission_vector->'XLY' as xly_strength
FROM event_transmission
WHERE date = '2026-03-20';
```

**预期输出：**
```
    date    |   event_type     | confidence | xle_strength | xly_strength
------------+------------------+------------+--------------+-------------
 2026-03-20 | supply_shock_oil |         85 | 1.0          | -1.0
```

### 步骤4：测试JSONB查询性能

```sql
-- 查询所有XLE受益的事件（strength > 0.8）
SELECT date, event_type, transmission_vector->'XLE' as xle_strength
FROM event_transmission
WHERE (transmission_vector->>'XLE')::float > 0.8
ORDER BY date DESC;

-- 如果数据量大，可以创建GIN索引：
CREATE INDEX idx_transmission_vector ON event_transmission USING GIN (transmission_vector);
```

---

## 🎯 测试成功标准

### ✅ Week 1验收标准

- [x] **模式定义完整性**：6个模式，每个覆盖11 sectors
- [x] **值范围有效性**：所有strength在[-1.0, 1.0]
- [x] **关键场景验证**：
  - [x] 2026-03-20 Iran war → XLE=1.0, XLY=-1.0 ✓
  - [x] Rate shock → XLF=0.7, XLK=-0.8, XLRE=-0.9 ✓
  - [x] Risk-off → XLV=0.85, XLP=0.80, XLY=-0.85 ✓
- [x] **多模式叠加**：oil + war → XLE=1.0 (clipped) ✓
- [x] **无误匹配**：常规新闻返回空dict ✓
- [x] **代码质量**：无语法错误，可导入 ✓

### 🔄 Week 2前置条件

在开始Week 2集成之前，确保：
- [ ] Railway数据库migration成功（event_transmission表存在）
- [ ] 所有Week 1测试通过
- [ ] 传导强度值经过人工review（当前值是否合理？）

---

## 📝 测试结果总结

### 执行过的测试

| 测试 | 状态 | 输出 |
|-----|------|------|
| 自动化测试套件 | ✅ PASS | 所有6个测试通过 |
| 模式定义验证 | ✅ PASS | 6个模式，各11 sectors |
| 2026-03-20场景 | ✅ PASS | XLE=1.0, XLY=-1.0 |
| 利率冲击场景 | ✅ PASS | XLF=0.7, XLK=-0.8 |
| Risk-off场景 | ✅ PASS | 防御性sector>0.7 |
| 多模式叠加 | ✅ PASS | XLE amplified to 1.0 |
| 无匹配场景 | ✅ PASS | 返回空dict |

### 待测试项

- [ ] 数据库migration（需要Railway环境）
- [ ] 与历史pipeline输出对比（需要找到Phase 1的logs）
- [ ] 边界情况测试（极端新闻，多语言关键词）

---

## 🚀 下一步建议

### 选项A：继续测试（不开发）

1. **在Railway部署Week 1代码**
   ```bash
   git push origin main  # 已完成
   # Railway自动部署
   ```

2. **运行数据库migration**
   ```bash
   # 在Railway环境
   python migrate_phase2.py
   ```

3. **手动插入测试数据**
   - 使用上面的SQL脚本
   - 验证JSONB查询性能

4. **对比历史输出**
   - 找到2026-03-20的Phase 1日志
   - 对比transmission vector vs 当时的sector scores

### 选项B：开始Week 2集成

如果Week 1测试全部满意，开始集成到Step 1和Step 2。

### 选项C：调优传导强度

如果觉得某些传导强度值不合理（如XLE=0.95是否过高？），现在可以调整`transmission_rules.py`中的值。

---

## 💬 反馈问题

1. **传导强度是否合理？**
   - supply_shock_oil: XLE=0.95, XLY=-0.75
   - war_geopolitical: XLI=0.90, XLE=0.80
   - 是否需要调整？

2. **关键词覆盖是否足够？**
   - 当前12-14个关键词/模式
   - 是否有遗漏的重要关键词？

3. **多模式叠加策略**
   - 当前：简单求和+clip到[-1.0, 1.0]
   - 是否需要加权平均或其他策略？

4. **最低匹配阈值**
   - 当前：min_keyword_matches=2
   - 是否需要调整？（1太松，3太严）

---

**总结：** Week 1测试全部通过，代码质量良好，可以选择：
1. 继续测试（Railway migration + 历史对比）
2. 开始Week 2集成
3. 调优传导强度值

请告知下一步？
