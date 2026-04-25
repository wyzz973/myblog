// Post data + site data for Wang Yang's blog
window.SITE = {
  handle: "wangyang",
  name: "汪洋",
  nameEn: "Wang Yang",
  role: "Backend / AI Full-Stack Engineer",
  tagline: "Backends that don't flinch. Models that ship.",
  bio: "I build backend systems and AI agents. Java · Python · PyTorch · Agents · Deep Learning · Image Segmentation.",
  location: "Hangzhou, CN",
  uptime: "3y 142d",
  commits52w: 1384,
  posts: 47,
  words: 98240,
  email: "hi@wangyang.dev",
  github: "wangyang",
};

window.POSTS = [
  {
    id: "termius-utf8",
    n: "042",
    title: "Termius 中文乱码解决方案",
    subtitle: "UTF-8 编码配置指南",
    tag: "devtools",
    date: "2026-04-12",
    read: "6 min",
    lang: "zh",
    summary: "Termius 里 vim、ls、tmux 都吐方块——根因不是字体，是 locale。一路从客户端 env 传到服务端 /etc/locale.conf 的完整 checklist。",
    tldr: "Set LANG + LC_ALL to en_US.UTF-8 on both sides; push via SendEnv/AcceptEnv; install glibc-langpack if on minimal images.",
    body: [
      { t: "p", c: "在 Termius 里连上一台新装的 CentOS，`ls` 出来一排方块，`vim` 打开 .md 直接糊脸。第一反应是字体——但换了 JetBrains Mono 也没用。问题在 locale。" },
      { t: "h2", c: "1. 客户端：让 Termius 发对 env" },
      { t: "p", c: "Termius → Settings → Terminal → Send Locale Environment Variables。打开后它会把 LANG / LC_* 一路 forward 过去。" },
      { t: "code", c: "# 本机 shell\necho $LANG\n# en_US.UTF-8   <- 应该是这个" },
      { t: "h2", c: "2. 服务端：确认 sshd 接受" },
      { t: "code", c: "# /etc/ssh/sshd_config\nAcceptEnv LANG LC_*\n\nsudo systemctl reload sshd" },
      { t: "h2", c: "3. 服务端：locale 得真装了" },
      { t: "p", c: "很多最小化镜像压根没装语言包。`locale -a` 如果看不到 en_US.utf8，就是它。" },
      { t: "code", c: "# Debian/Ubuntu\nsudo apt install locales\nsudo locale-gen en_US.UTF-8\n\n# CentOS / Rocky\nsudo dnf install glibc-langpack-en" },
      { t: "h2", c: "4. 写进 profile，永久生效" },
      { t: "code", c: "# ~/.bashrc 或 /etc/locale.conf\nexport LANG=en_US.UTF-8\nexport LC_ALL=en_US.UTF-8" },
      { t: "p", c: "重连一次，方块消失。后面三个月没再犯过。" },
    ],
  },
  {
    id: "pagehelper",
    n: "041",
    title: "PageHelper 分页失效踩坑指南",
    subtitle: "MyBatis + Spring Boot 的静默 bug",
    tag: "backend",
    date: "2026-04-03",
    read: "9 min",
    lang: "zh",
    summary: "PageHelper.startPage() 明明调了，SQL 里却没 LIMIT——八种常见死法一次列清，附一个能在启动时自检的小拦截器。",
    tldr: "startPage must be immediately followed by the query; no extra Mapper calls in between; watch reasonable=true silently eating your bounds.",
    body: [
      { t: "p", c: "看见一个 10w 行的表在列表页全量回来，前端又懒得做虚拟滚动——查了半天，PageHelper 没生效。" },
      { t: "h2", c: "Top 8 死法" },
      { t: "p", c: "1) startPage 后面紧跟的不是目标查询；2) 中间夹了一个 count；3) Mapper 返回值不是 List；4) 插件版本和 MyBatis 不兼容；5) reasonable=true 静默把越界 pageNum 改成 1；6) 子查询里用了 order by 被优化掉；7) 使用了 @Transactional(propagation=NEVER) 导致 ThreadLocal 错位；8) 在 async 里调用——ThreadLocal 不会传过去。" },
      { t: "code", c: "// 启动自检：确保插件链里有 PageInterceptor\n@PostConstruct\nvoid verifyPageHelperLoaded() {\n  List<Interceptor> chain = sqlSessionFactory\n    .getConfiguration().getInterceptors();\n  if (chain.stream().noneMatch(i ->\n      i.getClass().getSimpleName().equals(\"PageInterceptor\")))\n    throw new IllegalStateException(\"PageHelper not wired\");\n}" },
    ],
  },
  {
    id: "vpn-setup",
    n: "040",
    title: "科学上网搭建教程",
    subtitle: "一台 VPS，30 分钟，稳定到能开视频会议",
    tag: "infra",
    date: "2026-03-19",
    read: "12 min",
    lang: "zh",
    summary: "从挑机房、装 BBR、配 TLS 到客户端分流规则——不讲玄学，只讲每一步为什么这么做。",
    tldr: "Pick a low-latency POP, enable BBR, terminate TLS properly, keep rules simple: block CN + direct LAN, proxy everything else.",
    body: [
      { t: "p", c: "这篇是给『我想自己搞一下但文档全是复制粘贴』的朋友写的。每一步我都解释为什么。" },
      { t: "h2", c: "机房选择" },
      { t: "p", c: "国内到境外最舒服的路径目前是 HKT / 日本 IIJ / 新加坡 StarHub。挑一个 ping 值稳定在 40-80ms、jitter 低于 5ms 的就行。" },
      { t: "h2", c: "内核：打开 BBR" },
      { t: "code", c: "echo 'net.core.default_qdisc=fq' >> /etc/sysctl.conf\necho 'net.ipv4.tcp_congestion_control=bbr' >> /etc/sysctl.conf\nsysctl -p" },
    ],
  },
  {
    id: "agent-memory",
    n: "039",
    title: "Designing long-term memory for agents",
    subtitle: "Vector stores are necessary but not sufficient",
    tag: "ai",
    date: "2026-03-02",
    read: "14 min",
    lang: "en",
    summary: "A working agent needs three memories: episodic (what happened), semantic (what's true), procedural (how I do it). Most stacks only give you one.",
    tldr: "Split memory by write semantics, not read semantics. Summaries are lossy — store both the summary AND the raw trace.",
    body: [
      { t: "p", c: "Everyone ships an agent with a single pgvector table labeled 'memory' and wonders why it forgets birthdays and remembers bug reports." },
    ],
  },
  {
    id: "seg-loss",
    n: "038",
    title: "A quiet bug in my segmentation loss",
    subtitle: "Dice + BCE, and the `reduction` that ate my gradient",
    tag: "ml",
    date: "2026-02-11",
    read: "7 min",
    lang: "en",
    summary: "Training loss looked great, val IoU was garbage. The villain: `reduction='sum'` on one side of a compound loss.",
    body: [],
  },
  {
    id: "pytorch-profiler",
    n: "037",
    title: "PyTorch profiler, in 15 minutes",
    subtitle: "Find the op that's secretly on CPU",
    tag: "ml",
    date: "2026-01-28",
    read: "8 min",
    lang: "en",
    summary: "A minimal wrapper I paste into every training script on day one. Surfaces H2D copies, sync points, and the one `.item()` call burning 30% of your epoch.",
    body: [],
  },
  {
    id: "spring-startup",
    n: "036",
    title: "Spring Boot 冷启动从 18s 压到 3s",
    subtitle: "Lazy init, class data sharing, AOT",
    tag: "backend",
    date: "2026-01-09",
    read: "11 min",
    lang: "zh",
    summary: "一个 120-bean 的服务，从部署到 healthy 原来要 18 秒。分三步砍到 3.1 秒，线上滚动发布从此不再需要预热脚本。",
    body: [],
  },
  {
    id: "idempotency",
    n: "035",
    title: "幂等键的五种写法，哪种适合你",
    subtitle: "Token / natural-key / fingerprint / 状态机 / 乐观锁",
    tag: "backend",
    date: "2025-12-22",
    read: "10 min",
    lang: "zh",
    summary: "每个做支付的人都写过幂等，但很少有人把这五种策略的适用边界画清楚。一张决策树，一张对比表。",
    body: [],
  },
  {
    id: "docker-cache",
    n: "034",
    title: "Dockerfile 缓存，你可能一直写反了",
    subtitle: "为什么 COPY . . 永远应该在最后",
    tag: "devtools",
    date: "2025-12-05",
    read: "5 min",
    lang: "zh",
    summary: "构建慢的罪魁祸首通常不是网络，是你的 layer 顺序。",
    body: [],
  },
  {
    id: "cuda-oom",
    n: "033",
    title: "Debugging phantom CUDA OOMs",
    subtitle: "When nvidia-smi says you have memory, but torch says you don't",
    tag: "ml",
    date: "2025-11-18",
    read: "9 min",
    lang: "en",
    summary: "Fragmentation, caching allocator, and the flag that fixed it.",
    body: [],
  },
  {
    id: "rag-eval",
    n: "032",
    title: "Stop A/B-testing your RAG with vibes",
    subtitle: "A 50-line eval harness that actually catches regressions",
    tag: "ai",
    date: "2025-10-30",
    read: "13 min",
    lang: "en",
    summary: "Golden set + faithfulness + answer-relevance, run on every PR. You can build it in an afternoon.",
    body: [],
  },
  {
    id: "terminal-setup",
    n: "031",
    title: "我的终端，2026 版",
    subtitle: "Ghostty + zsh + starship + atuin + zoxide",
    tag: "devtools",
    date: "2025-10-12",
    read: "6 min",
    lang: "zh",
    summary: "每年更新一次的 terminal dotfiles，今年终于离开 iTerm2。",
    body: [],
  },
];

window.PROJECTS = [
  { name: "segformer-lite", desc: "Tiny, quant-friendly segmentation model. 3.2MB, runs on ESP32-S3.", lang: "Python", stars: 1240, status: "active" },
  { name: "agentkit-jvm", desc: "LangChain-style agent primitives, native Java. Zero Python in prod.", lang: "Java", stars: 812, status: "active" },
  { name: "pghelper-debug", desc: "Runtime diagnostic for PageHelper — tells you why your page didn't page.", lang: "Java", stars: 203, status: "maintained" },
  { name: "dotfiles", desc: "Terminal, editor, and kernel tunings I run on every box.", lang: "Shell", stars: 96, status: "active" },
  { name: "term-i18n", desc: "Lint your SSH/locale config across a fleet. Catches the Termius bug at scale.", lang: "Go", stars: 61, status: "active" },
];

window.TAGS = [
  { id: "all", label: "all", n: 47 },
  { id: "backend", label: "backend", n: 18 },
  { id: "ai", label: "ai", n: 11 },
  { id: "ml", label: "ml", n: 9 },
  { id: "devtools", label: "devtools", n: 6 },
  { id: "infra", label: "infra", n: 3 },
];

// Generate a plausible 52-week contribution grid
window.CONTRIB = (() => {
  const seed = 42;
  let s = seed;
  const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  const grid = [];
  for (let w = 0; w < 52; w++) {
    const col = [];
    for (let d = 0; d < 7; d++) {
      const r = rnd();
      // mild weekly pattern: more on weekdays
      const weekday = d > 0 && d < 6 ? 1.2 : 0.6;
      const v = r * weekday;
      let level = 0;
      if (v > 0.35) level = 1;
      if (v > 0.6) level = 2;
      if (v > 0.8) level = 3;
      if (v > 0.93) level = 4;
      col.push(level);
    }
    grid.push(col);
  }
  return grid;
})();
