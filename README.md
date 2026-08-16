# 灵活公交仿真平台

> **项目状态**: 🟢 Web 平台 + 核心算法 + 轨迹回放 + 完整评价体系已实现，持续开发中  
> **最后更新**: 2026-08-16 (v0.3.0)  
> **运行环境**: Python 3.9+ / Windows / conda 环境位于 `.conda/`

---

## 1. 项目背景

**云公交（灵活公交）**——公交车像打车一样，有单子就去接送乘客。  
多辆公交车在路上运营，有订单时需要智能派单，选择更近或更顺路的车辆接单。

### 1.1 建设目标（来自需求文档）

1. 确定车辆数需求
2. 确定订单池请求合并策略
3. 确定算法参数，发现算法问题
4. 确定调度策略
5. 新区域初始参数确定
6. 提升测试效率

---

## 2. 核心算法

派单引擎基于 **网约车/出租车派单算法** 设计，核心为 **带权二分图匹配**：

| 策略 | 说明 | 实现状态 |
|------|------|----------|
| 延迟集中分单（Batch Matching） | 收集时间窗口内的订单和车辆，集中求解全局最优 | ✅ 已实现 |
| KM 算法（Kuhn-Munkres） | 求解带权二分图最优匹配，最小化全局接驾成本 | ✅ 已实现 |
| 贪心匹配 | 简单"就近派单"模式，作为对比基线 | ✅ 已实现 |
| 三层优先级派单 | P1:保障车内乘客 P2:缩短候车 P3:控制空载 | ✅ 已实现 |
| 方向夹角约束 | 车辆行进方向与订单上车点夹角过大时不接单 | ✅ 已实现 |
| 连环派单 | 即将完成当前任务的车辆优先接新单 | ✅ 评分中体现 |
| 供需预测 | 预测未来区域供需，提前调度 | ❌ 未实现 |

### 评分公式（三层优先级）

```
综合匹配分 = 0.50 × f(车内乘客保障 + 顺路程度)    # 第一优先级
           + 0.35 × f(接驾距离/候车时间)          # 第二优先级
           + 0.15 × f(空载控制)                    # 第三优先级
           × (1 - 负载均衡惩罚因子)
```

---

## 3. 项目结构

```
模拟仿真/
├── main.py                  # 仿真主入口（Demo 场景）
├── config/
│   └── settings.py          # 全局配置（SimConfig, CityConfig）
├── core/                    # 核心数据模型
│   ├── vehicle.py           # 车辆模型（状态机 + dataclass）
│   ├── order.py             # 订单模型（状态机 + dataclass）
│   └── stop.py              # 站点模型
├── dispatch/                # 派单引擎
│   ├── dispatcher.py        # 派单调度器（完整派单流程编排）
│   ├── matcher.py           # 二分图匹配（KM算法 + 贪心）
│   └── scorer.py            # 司乘评分计算（4维加权）
├── simulation/              # 仿真引擎
│   ├── engine.py            # 离散事件仿真引擎（PEDS）
│   ├── event.py             # 事件定义（EventType + Event）
│   └── order_generator.py   # 订单生成器（随机/历史回放）
├── utils/                   # 工具模块
│   ├── geo.py               # 地理计算（Haversine距离、方位角）
│   ├── navigation.py        # 高德路径规划 API（多 Key 池）
│   ├── distance_matrix.py   # 距离矩阵预计算
│   └── logger.py            # 日志工具
├── data/                    # 输入数据与查询脚本
│   ├── od_loader.py         # OD CSV 加载器
│   ├── top200_od_query.sql  # 区域内 Top200 OD 查询
│   └── station_region_query.sql  # 区域内站点筛选
├── web/                     # Web 平台（FastAPI + 高德地图）
│   ├── app.py               # FastAPI 主入口
│   ├── routers/
│   │   ├── upload.py        # 数据上传 API
│   │   └── simulation.py    # 仿真运行 API
│   └── static/
│       ├── index.html       # 主页面
│       ├── css/style.css    # 样式
│       └── js/
│           ├── app.js       # 前端主逻辑
│           ├── map.js       # 地图初始化
│           └── replay.js    # 轨迹回放
├── output/                  # 仿真结果输出
├── tests/                   # 测试脚本
└── README.md
```

---

## 4. 运行指南

### 4.1 环境准备

```bash
cd c:\Users\52566\Desktop\GJY
.conda\python.exe main.py
```

**依赖包**: numpy, scipy

### 4.2 运行 Demo

```bash
cd c:\Users\52566\Desktop\GJY\模拟仿真
python main.py
```

### 4.3 启动 Web 平台

```bash
cd c:\Users\52566\Desktop\GJY\模拟仿真
& "c:\Users\52566\Desktop\GJY\.conda\python.exe" web/app.py
```

访问: `http://localhost:8001`

---

## 5. 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 仿真框架 | 自研 PEDS | 需求明确不使用 SimPy 等重框架 |
| 匹配算法 | KM (scipy) | 滴滴验证过的全局最优方案 |
| 距离计算 | Haversine + 导航距离可选 | 支持直线距离和高德导航两种模式 |
| 车辆速度 | 固定 30km/h | 需求明确暂不考虑交通流 |
| 订单生成 | 泊松过程 | 经典排队论假设，可替换为历史回放 |

---

## License

MIT
