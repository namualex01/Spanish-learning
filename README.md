# Spanish-learning

learning Spanish in a much easier and costomized way

## Quizlet 单词抓取脚本

仓库新增了一个脚本，可以从 Quizlet 单词集页面提取“单词-释义”并导出。

### 文件

- `scripts/scrape_quizlet_vocab.py`

### 用法

```bash
python scripts/scrape_quizlet_vocab.py \
  "https://quizlet.com/cn/40125686/%E7%8E%B0%E4%BB%A3%E8%A5%BF%E7%8F%AD%E7%89%99%E8%AF%AD1-4%E5%86%8C%E5%8D%95%E8%AF%8D%E4%B8%80-flash-cards/" \
  --output data/modern_spanish_1_4.csv \
  --format csv
```

### 可选参数

- `--output/-o`：输出文件路径（默认 `data/quizlet_words.csv`）
- `--format/-f`：`csv` / `json` / `txt`（默认 `csv`）

## index.html 新增能力（册数 + 单元 + 外部 JSON）

- 现在 `index.html` 支持加载外部 JSON 词库（本地文件或 URL）。
- 如果词条包含 `book`（册数）和 `unit`（单元）字段，页面会自动启用「册数选择 + 单元选择」联动筛选。

推荐 JSON 词条格式示例：

```json
[
  {
    "word": "hola",
    "meaning": "你好",
    "book": "第1册",
    "unit": "第1单元",
    "pos": "interj.",
    "example": "Hola, ¿cómo estás?"
  }
]
```

### 注意

- Quizlet 可能会触发登录限制、地区限制或反爬机制。
- 如果你看到“未提取到词条”，请在本地网络环境重试，或登录后再运行。
