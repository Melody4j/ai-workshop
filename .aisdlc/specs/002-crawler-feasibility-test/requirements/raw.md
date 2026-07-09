# 爬虫方案可行性验证

## 目标

验证当前技术方案中 httpx + html2text + 规则去噪（不用 LLM）的爬虫可行性，针对以下竞品网站进行最小 MVP 测试：

| 网站 | URL | 特殊处理 |
|---|---|---|
| ihuiwa.com | https://www.ihuiwa.com/ | 正常方式无法爬取时，使用 JS 注入方式爬取（当获取的 markdown 数据小于 3 行时，使用 JS 注入） |
| x-design.com | https://www.x-design.com/ | 正常爬取 |
| piccopilot.com | https://www.piccopilot.com/ | 正常爬取 |
| weshop.ai | https://www.weshop.ai/ | 正常爬取 |
| bandy.ai | https://bandy.ai/ | 正常爬取 |
| thenewblack.ai | https://thenewblack.ai/ | 正常爬取 |
| lovable.dev | https://lovable.dev/ | 正常爬取 |

## 要求

1. 使用 httpx 优先爬取 HTML
2. 使用 html2text 转换为 Markdown
3. 使用规则去噪（BeautifulSoup 去除 nav/footer/script/style 等），不使用 LLM
4. 当 httpx 获取的 markdown 小于 3 行时，降级使用 Playwright（JS 注入）重新爬取
5. 去噪后的 MD 文件存储在 /Users/melody/Desktop/ai-workshop-test 目录下
6. 每个网站一个 .md 文件，文件名以域名命名
