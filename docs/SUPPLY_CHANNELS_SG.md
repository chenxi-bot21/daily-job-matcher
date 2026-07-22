# 岗位供给渠道 · 新加坡/香港 — 注册与设置清单

建于 2026-07-22(研究见 WORKLOG 同日条目)。解决的问题:**投递量上不去不是因为不努力,
是补给线太窄**——此前只有 LinkedIn(Apify,额度已耗尽)+ MCF + Indeed。

**设计要点:所有渠道都开"邮件提醒",提醒信落进 qieyue2001@gmail.com,而每日流水线
会自动扫描求职 alert 邮件并分诊进 Notion。** 所以你只需注册一次,之后新岗位自己流进管道。
技术源见 [`JOB_SOURCES.md`](JOB_SOURCES.md);每日操作见 [`DAILY_PLAYBOOK.md`](DAILY_PLAYBOOK.md)。

---

## 第一批 · 今晚 30 分钟(按顺序做)

### ① eFinancialCareers 新加坡 —— 最大缺口,先做这个(10 分钟)
金融**专板**,岗位密度远高于综合站;猎头的单子也发在这里。
- 注册:**efinancialcareers.sg** → 建账号 → 传主简历(`Chenxi_Zhao_Resume.pdf`)
- **建 4 个 saved search,全部设"每日邮件提醒"**,地点都选 Singapore:
  1. `credit risk`
  2. `market risk` OR `quantitative`
  3. `risk analyst graduate`
  4. `data analyst` (finance)
- 可选:再开一组同样的搜索,地点 Hong Kong

### ② JobStreet SG(已合并 JobsDB,一个账号覆盖新港)(8 分钟)
综合站里量最大的。
- 注册:**sg.jobstreet.com** → 建 profile → 传简历
- **saved search + 邮件提醒**(每日):
  1. `risk analyst`
  2. `data analyst`
  3. `actuarial analyst`
  4. `graduate programme`

### ③ GradConnection SG(5 分钟)
应届 graduate program 专供——这是你签证最可能过的一类岗。
- 注册:**sg.gradconnection.com** → 开 program alerts(关键词 finance / data / risk)
- 顺手存下 **gradsingapore.com 的「SG100 百强雇主榜」** —— 那就是一份现成的官网投递目标清单

### ④ NYU 校友权益 —— 你完全没用过(5 分钟)
校友**终身**保留 Wasserman 权限;上面的岗是雇主专门投给 NYU 的,竞争小得多。
- 登录 **wasserman.nyu.edu** → 激活 alumni 身份 → **Handshake** 按 Singapore 筛 + 开提醒
- 同时用 **Violet Network** 搜在新加坡金融机构的 NYU 校友(接 `linkedin/07_ALUMNI_SPRINT.md` 的外联流程)

---

## 第二批 · 本周(单独留 1 小时)

### ⑤ 猎头中介注册 —— 这才是"一次动作、持续供给"
中介替你递简历,自带背书,还能碰到根本不公开的岗。**动作:官网传简历 + 顺手申请 2-3 个在招的
junior 岗**(这样才会触发顾问打电话给你,只传简历常常石沉大海)。

| 中介 | 为什么 |
|---|---|
| **Selby Jennings** | 纯金融猎头,风险/量化专精,最对口 |
| **Robert Walters SG** | 大所,银行与金融服务台,junior 也做 |
| **Morgan McKinley SG** | 中后台强(风险/合规/运营) |
| **Michael Page / Page Personnel** | Page Personnel 专做初级岗 |
| **Randstad SG** | 银行金融量大 |
| **Ambition SG** | 金融精品所,junior-mid 覆盖 |

暂时跳过:Kerry Consulting / Charterhouse / Argyll Scott(偏高端猎聘)、Adecco / PERSOLKELLY
(合约岗为主,合约岗基本不办签证)。

---

## 情报型渠道(不投递,但要看)

### ⑥ MyCareersFuture —— 改变用法 ⚠️
它需要 Singpass,**实际只对本地人/PR 开放申请**,你投不了。
**但它是签证情报金矿**:法规要求雇主在办 EP 前必须在 MCF 挂满 14 天——
**所以上面的岗 = 正在办签证流程的岗。** 用法:浏览(不用登录)→ 看到匹配的 → **去公司官网投**。

### ⑦ Telegram(低优先,当背景噪音看)
值得关注:**@internsg**(实习+应届,量最大)、**@sgcareers**、**@SGFTJ**(全职)。
其余杂牌求职频道以兼职/中介/诈骗为主——**永远不付费、不给陌生"猎头"发证件**。

---

## 一句话使用规则

**注册 = 一次性;之后每天你只需要看日报。** 各站的提醒邮件进邮箱 → 每日流水线扫描分诊 →
真匹配的进 Notion「To Apply」→ 你按 true-fit bar 投递。补给线从此不依赖任何单一渠道
(Apify 额度 08-02 重置后 LinkedIn 自动归队)。
