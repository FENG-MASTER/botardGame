# 员工中文名称核对

以用户提供的 TTS 汉化包为准，不将这些名称声称为官方统一译名。

来源：`tts-audit/card-sheets.json` 第 6 张基础汉化卡面、第 2 张扩展员工卡面、第 4 张夜班经理卡面。原始缓存路径见该索引。基础卡面缩图见 [基础汉化卡面](employee-base-cn.jpg)，扩展见 [扩展员工卡面](employee-expansion-cn.jpg)。英文种类 ID 保持不变；API/MCP 的 `game.employees[id].name_zh` 提供中文名称。

统一约定：基础卡面的“匹萨”和扩展卡面的“披萨”统一为“披萨”；基础“后厨培训生”与扩展“后厨实习生”共用 kitchen_trainee，统一为“后厨培训生”。CFO 在 UI 展开为“财务总监”，CEO 保留缩写。其余按汉化卡面名称。市场培训生在两套卡面中一致，不沿用此前的“营销实习生”。

| API kind | 中文名称 |
| --- | --- |
| `ceo` | CEO |
| `waitress` | 服务员 |
| `management_trainee` | 管理培训生 |
| `junior_vice_president` | 初级副总裁 |
| `vice_president` | 中级副总裁 |
| `senior_vice_president` | 高级副总裁 |
| `executive_vice_president` | 执行副总裁 |
| `new_business_developer` | 业务拓展专员 |
| `local_manager` | 地方总经理 |
| `regional_manager` | 区域总经理 |
| `pricing_manager` | 物价经理 |
| `luxuries_manager` | 奢侈品经理 |
| `discount_manager` | 促销经理 |
| `cfo` | 财务总监 |
| `recruiting_girl` | 招聘员 |
| `recruiting_manager` | 招聘经理 |
| `hr_director` | 人力资源总监 |
| `trainer` | 培训师 |
| `coach` | 导师 |
| `guru` | 成功学大师 |
| `errand_boy` | 跑腿小弟 |
| `cart_operator` | 采购专员 |
| `truck_driver` | 货运司机 |
| `zeppelin_pilot` | 飞船驾驶员 |
| `marketing_trainee` | 市场培训生 |
| `campaign_manager` | 广告经理 |
| `brand_manager` | 品牌经理 |
| `brand_director` | 品牌总监 |
| `kitchen_trainee` | 后厨培训生 |
| `burger_cook` | 汉堡小厨 |
| `pizza_cook` | 披萨小厨 |
| `burger_chef` | 汉堡大厨 |
| `pizza_chef` | 披萨大厨 |
| `sushi_cook` | 寿司小厨 |
| `sushi_chef` | 寿司大厨 |
| `noodle_cook` | 面条小厨 |
| `noodle_chef` | 面条大厨 |
| `kimchi_master` | 泡菜大师 |
| `fry_chef` | 薯条大厨 |
| `night_shift_manager` | 夜班经理 |
| `mass_marketeer` | 大众营销商 |
| `rural_marketeer` | 农村营销商 |
| `gourmet_food_critic` | 美食评论家 |
| `b_movie_star` | 电影明星-B |
| `c_movie_star` | 电影明星-C |
| `d_movie_star` | 电影明星-D |
| `barista_trainee` | 实习咖啡师 |
| `barista` | 咖啡师 |
| `lead_barista` | 首席咖啡师 |
| `lobbyist` | 说客 |
