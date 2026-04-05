# 同人小说（Fan Fiction）支持设计方案

> 日期：2026-04-05
> 状态：已确认，待实施

## 背景

webnovel-writer 当前仅支持原创小说。本方案将同人小说创作能力融入现有流程，重点支持：
- **原作类型**：网文/小说（用户提供 TXT 文件）
- **同人类型**：AU/衍生（借用原作角色，可改变世界观）
- **资料提取**：AI 自动解析原作 TXT
- **架构策略**：融入现有流程，在 init 时选择模式

---

## 一、同人创作需要的资料体系

### 第一层：原作基准资料（Canon Baseline）

| 资料类型 | 内容 | 用途 |
|----------|------|------|
| 角色档案 | 姓名、性格核心、口头禅/说话风格、行为模式、人际关系、能力设定 | OOC 检查基准线 |
| 力量体系 | 等级划分、能力规则、升级条件、硬限制 | 设定一致性检查 |
| 世界观骨架 | 地理结构、势力格局、社会规则、核心矛盾 | 世界观改造起点 |
| 关系网络 | 角色间亲缘/师徒/敌对/暧昧等关系 | 关系重构参照 |

### 第二层：Canon 偏离管理

- **保留清单**：哪些原作设定保持不变（如角色性格内核）
- **修改清单**：哪些设定被有意改变（如世界背景、力量体系）
- **新增设定**：为 AU 新创造的设定（新角色、新势力、新规则）

### 第三层：同人专属创作资料

- 原创主角与原作世界的融合方案
- 原作角色在 AU 中的重新定位
- Canon 合理性红线

---

## 二、流程设计

### 原创 vs 同人流程对比

```
原创: Step1(故事核心) → Step2(角色) → Step3(金手指) → Step4(世界观) → Step5(约束) → Step6(确认)
同人: Step0(导入原作TXT) → Step1(AI解析提取) → Step2(Canon偏离声明) → Step3(同人故事核心) → Step4(角色重塑/新增) → Step5(确认生成)
```

### 同人 init 流程详述

#### Step 0：导入原作
- 用户提供原作 TXT 文件路径
- 输入原作名称、主要题材

#### Step 1：AI 解析提取
- 调用 `canon_parser.py` 对 TXT 分段解析
- 提取：主要角色（前 N 名）、力量体系、世界观结构、关系网络
- 输出到 `.webnovel/canon/` 目录

#### Step 2：Canon 偏离声明
- 用户声明保留/修改/新增
- 生成 `设定集/Canon偏离声明.md`

#### Step 3：同人故事核心
- 复用部分原创 Step1 逻辑（书名、核心冲突、目标字数）
- 增加：同人卖点（对原作的什么进行再创作）

#### Step 4：角色重塑/新增
- 复用原作角色 → 基于 canon 档案修改
- 新增角色 → 使用标准主角卡模板

#### Step 5：确认生成
- 生成全套项目文件（含 canon 参照目录）

---

## 三、新增/修改文件

### 新增文件

| 文件 | 说明 |
|------|------|
| `scripts/canon_parser.py` | 原作 TXT 解析脚本，提取角色、设定、世界观 |
| `templates/output/设定集-Canon偏离声明.md` | 偏离声明模板 |
| `templates/output/设定集-原作角色卡.md` | 原作角色档案模板（复用主角卡结构 + canon 标记） |
| `templates/output/设定集-原作世界观.md` | 原作世界观快照模板 |
| `genres/fan-fiction/` | 同人写作专用指导（canon 还原技巧、AU 改造方法论） |

### 修改文件

| 文件 | 改动 |
|------|------|
| `skills/webnovel-init/SKILL.md` | 加入同人分支流程（Step 0 选择模式） |
| `scripts/init_project.py` | 支持 `--mode fan_fiction` 参数、canon 目录创建、state.json 扩展 |
| `agents/ooc-checker.md` | 增加 canon 对照检查层 |
| `agents/consistency-checker.md` | 区分 canon 设定 vs AU 改造设定 |

---

## 四、数据结构扩展

### state.json 新增字段

```json
{
  "project_info": {
    "mode": "fan_fiction",
    "canon_source": "斗破苍穹",
    "canon_type": "AU"
  },
  "fan_fiction_meta": {
    "canon_retained": ["力量体系-斗气等级", "角色-萧炎性格内核"],
    "canon_modified": ["世界背景-现代都市化"],
    "canon_added": ["新角色-xxx"]
  }
}
```

### 项目目录结构（同人模式）

```
我的同人小说/
├── .webnovel/
│   ├── state.json
│   ├── canon/                    # 新增：原作资料
│   │   ├── characters/           # 原作角色档案
│   │   │   ├── 萧炎.md
│   │   │   └── 萧薰儿.md
│   │   ├── world.md              # 原作世界观快照
│   │   ├── power_system.md       # 原作力量体系
│   │   └── relationships.md      # 原作关系网络
│   ├── index.db
│   └── ...
├── 设定集/
│   ├── Canon偏离声明.md           # 新增
│   ├── 世界观.md                  # AU 版世界观
│   ├── 力量体系.md
│   ├── 主角卡.md
│   └── 角色库/
├── 大纲/
├── 正文/
└── ...
```

---

## 五、Checker 增强

### OOC Checker 增强
- 对 canon 角色：同时对照 `.webnovel/canon/characters/` 和 `设定集/角色库/`
- 区分「canon 性格偏离」（严重）和「AU 合理改造」（已声明则放行）

### Consistency Checker 增强
- 读取 `fan_fiction_meta.canon_retained` → 严格检查
- 读取 `fan_fiction_meta.canon_modified` → 跳过或用 AU 版设定检查
- 新增实体标记 `canon_source: true/false`
