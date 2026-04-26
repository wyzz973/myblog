# PageHelper 分页失效踩坑指南

> 适用框架：MyBatis + PageHelper（RuoYi / SpringBoot 项目常见）

---

## 一、PageHelper 工作原理

PageHelper 是 MyBatis 最常用的分页插件，核心机制是 **ThreadLocal + MyBatis 拦截器**。

### 执行流程

```
PageHelper.startPage(pageNum, pageSize)
        │
        ▼
┌──────────────────────────────────┐
│  在当前线程 ThreadLocal 中存入     │
│  分页参数 {pageNum, pageSize}     │
└──────────────────────────────────┘
        │
        ▼
   等待下一个 MyBatis SQL 执行
        │
        ▼
┌──────────────────────────────────┐
│  拦截器检测到 ThreadLocal 有参数   │
│  → 改写 SQL，追加 LIMIT/OFFSET   │
│  → 同时执行 COUNT 查询获取总数     │
└──────────────────────────────────┘
        │
        ▼
   执行完毕，立即清除 ThreadLocal
   （一次性消费，用完即销毁）
```

### 关键规则

**PageHelper 只对 `startPage()` 之后的第一个 MyBatis 查询生效，用完自动失效。**

---

## 二、经典踩坑场景

### 场景：startPage() 和业务查询之间插入了其他 SQL

```java
// ❌ 错误写法
startPage();                          // ① 设置分页参数

if (isCourseManagerOnly()) {          // ② 内部调用了 roleService.selectRolesByUserId()
    // ...                            //    这是一个 MyBatis 查询！
}                                     //    PageHelper 拦截了这条 SQL → 分页被消耗

list = scheduleService.selectList();  // ③ 真正的业务查询 → ThreadLocal 已空
                                      //    没有 LIMIT → 返回全部数据！
```

**发生了什么：**

| 步骤 | 操作 | ThreadLocal 状态 |
|------|------|------------------|
| ① | `startPage(1, 20)` | `{pageNum:1, pageSize:20}` |
| ② | `roleService.selectRolesByUserId()` | **被消耗，变为空** |
| ③ | `scheduleService.selectList()` | 空，不分页 |

### 为什么难发现？

- **管理员账号测试正常**：管理员判断走内存（`userId == 1`），不触发 SQL，所以分页没被消耗
- **普通用户才出问题**：角色判断需要查数据库，SQL 插入到了 `startPage()` 和业务查询之间

---

## 三、正确写法

### 核心原则：`startPage()` 必须紧贴业务查询，中间不能有任何 MyBatis SQL

```java
// ✅ 正确写法：所有可能触发 SQL 的操作放在 startPage() 之前
boolean superAdmin = isSuperAdmin();
boolean collegeAdmin = isCollegeAdmin();       // SQL 查询角色 → 这里随便查
boolean courseManager = isCourseManagerOnly();  // SQL 查询角色 → 这里也随便查
Long teacherId = getCurrentTeacherId();        // SQL 查询教师 → 没问题

startPage();  // ← 此后到业务查询之间，不能有任何 MyBatis 操作

List<Schedule> list = scheduleService.selectList(query);  // ← PageHelper 正确拦截
return getDataTable(list);
```

---

## 四、其他常见失效场景

### 4.1 条件判断中触发查询

```java
// ❌ 错误
startPage();
if (userService.checkPermission(userId)) {  // 触发了 SQL
    list = orderService.selectList(query);   // 分页已失效
}
```

### 4.2 在循环或 try-catch 中 startPage 后没有执行查询

```java
// ❌ 错误：异常导致查询未执行，ThreadLocal 残留到下一个请求
startPage();
try {
    // 这里抛异常了，查询没执行
    validate(param);  // throws Exception
    list = service.selectList(query);
} catch (Exception e) {
    return error();  // ThreadLocal 没被消费，泄漏到下次请求
}
```

### 4.3 多次查询只有第一个被分页

```java
// ❌ 错误：只有第一个查询被分页
startPage();
List<Order> orders = orderService.selectList(query);    // ← 被分页
List<User> users = userService.selectByIds(userIds);    // ← 不会被分页（已消费）
```

---

## 五、排查清单

当分页不生效时，按以下步骤排查：

- [ ] `startPage()` 和业务查询之间是否有其他 MyBatis 查询？
- [ ] 是否存在条件分支导致 `startPage()` 后查询未执行？
- [ ] 是否有 AOP 切面（如 `@DataScope`）在中间插入了 SQL？
- [ ] 是否在 Service 层内部有额外查询（如校验、日志记录）？
- [ ] 确认 `startPage()` 只对紧接着的**第一个** Mapper 方法生效

---

## 六、最佳实践总结

| 规则 | 说明 |
|------|------|
| `startPage()` 紧贴查询 | 中间不插入任何可能触发 SQL 的代码 |
| 预计算所有条件 | 把角色判断、权限校验等提前到 `startPage()` 之前 |
| 用变量缓存结果 | 避免在 if/else 分支中重复调用可能触发 SQL 的方法 |
| 注意隐藏的 SQL | AOP 切面、拦截器、懒加载都可能偷偷执行 SQL |
| 异常时清理 | 在 finally 中调用 `PageHelper.clearPage()` 防止 ThreadLocal 泄漏 |

---

*记录时间：2026-02-09 | 来源：Ecomatrix 课程管理系统实际 bug 复盘*
