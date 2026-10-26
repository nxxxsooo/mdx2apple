# mdx2apple

[English](README.md) · [简体中文](README_CN.md) · [项目网站](https://mjshao.fun/mdx2apple/)

将 MDict（`.mdx` / `.mdd`）词典转换为 macOS 原生词典，保留完整词条。

## 保留的内容

- 全部释义、例句、翻译、词性、习语和用法说明。
- 原始词头及别名，包括多级跳转和同形词。
- 原始 CSS、字体、插图和发音资源。
- 适配为原生词典引用的内部链接。

转换器复用 PyGlossary 的 MDX/MDD 读取器，直接生成 Apple Dictionary XML。
源词典脚本和事件处理器会被移除；声音链接改为标准音频控件，牛津词典的折叠说明
默认展开，插图放大使用原生 HTML 折叠组件。

**OALD 10 实测：**62,137 个完整词条正文及 279,100 个原始查询键均通过原生引擎验证。
旧版的「10 个义项、每个义项两条例句、500 字符回退」限制已移除。
[查看验证范围](docs/oald-native-audit.md)。

## 安装

需要 macOS、Python 3.12+ 及 Apple Dictionary Development Kit。

```bash
git clone https://github.com/nxxxsooo/mdx2apple.git
cd mdx2apple
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# 尚未安装 DDK 时，单独安装：
git clone https://github.com/ikey4u/macddk.git \
  "$HOME/Library/Developer/Dictionary-Development-Kit"
```

部分旧 MDX 使用 LZO 压缩，需要额外安装 `python-lzo`。OALD 10 使用 zlib，无需安装。

## 转换并安装

使用新的输出目录。转换器会在 MDX 旁边查找同名 `.mdd`、`.1.mdd`、`.2.mdd` 等资源包。
被词条或样式引用的同目录资源文件优先于资源包中的版本。

```bash
python mdx2apple.py /path/to/dictionary.mdx \
  --name "我的词典" \
  --output ./output/my-dictionary \
  --keep-resources \
  --install
```

安装后，在「词典 → 设置」中勾选新词典。安装成功不会自动修改已选择的词典。

| 参数 | 说明 |
|---|---|
| `--name` | 设置列表中的完整词典名称 |
| `--short-name` | 顶部 tab 的简称，默认使用全称 |
| `--copyright` | 原词典版权声明 |
| `--publisher` | 原词典出版方 |
| `--credits` | 显示在版权声明下方的转换署名 |
| `--output`、`-o` | 新的输出目录，默认 `./output` |
| `--identifier` | 唯一 Bundle ID，例如 `com.example.dictionary` |
| `--keep-resources` | 包含图片、音频及其他资源包文件 |
| `--install` | 编译并安装到 `~/Library/Dictionaries/` |

不传 `--keep-resources` 时仍会保留 CSS 和字体；需要完整媒体功能时应传入该参数。
转换不会修改源 MDX、MDD 或同目录文件。

也可以先转换，再手动编译、安装：

```bash
make -C output/my-dictionary
make -C output/my-dictionary install
```

DDK 在隔离的编译目录中运行，再由 `ditto` 加入 `OtherResources`，避免大量资源触发
命令行参数长度限制。无需手动移动资源或在安装后执行 `rsync`。

## 诊断与限制

- `conversion-report.json` 记录词条数、正文保留检查、链接和媒体适配情况、无法解析的
  源链接、循环跳转及缺失文件。
- 无法解析的内部链接保留文字，但不可点击；转换器不会补造缺失文章。
- MP3/WAV 使用原生 HTML 音频控件，其他编码取决于 macOS WebKit，转换器不负责转码。
- 不执行词典自带脚本；高度依赖交互脚本的词典可能需要专门的适配器。
- 先导入词典原始样式，再应用转换器的兼容性适配。Dictionary.app 和系统「查询」
  的显示可能不同，需要分别验收。
- 牛津词条的正文、音标、例句和说明框使用专门的暗色配色，插图保留原始颜色。

[OALD 审计报告](docs/oald-native-audit.md) 记录了整库验证，以及原生引擎、WebKit 和
Dictionary.app 界面验证的边界。

## 按词典定制排版

个人字体和阅读排版属于单个词典的覆盖样式。`assets/dictionary.css` 是共享兼容性层，
不应将某本词典的个人偏好设为所有转换的默认值。

Dictionary.app 可能跳过用户安装的字体，即使独立 WebKit 预览能正确使用它。已经验证
可行的方式是将字体及许可证放入该词典的 `OtherResources`，通过本地 `@font-face` URL
加载，并保留中文、音标后备字体和相对字号。CSS 计算出的字体族名称不能证明实际绘制
字形的字体；应检查原生应用或其辅助功能字体信息。
[OALD 审计](docs/oald-native-audit.md#typography-customization-and-native-verification)
记录了原生验证证据和当前定制样式的拆分状态。

## 更新已有安装

工具通过源码安装，需要手动更新：

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
python mdx2apple.py /path/to/dictionary.mdx \
  --output ./output/my-dictionary-updated \
  --keep-resources --install
```

在已有 `mdx2apple` 仓库目录中执行。使用新的输出目录，并重新传入此前自定义的
`--name`、`--short-name`、`--identifier`、`--copyright`、`--publisher` 和 `--credits`。
拉取代码不会自动更新已安装词典，需要重新转换、安装，再退出并重新打开「词典」。

卸载时，退出「词典」，将生成的 `.dictionary` 包移出 `~/Library/Dictionaries/`。
保留旧词典包即可在本地回退。

## 验证

```bash
python -m unittest discover -s tests -v

python tests/audit_native_dictionary.py \
  --source /path/to/reference-appledict.xml \
  --converted output/my-dictionary/dictionary.xml \
  --dictionary "$HOME/Library/Dictionaries/dictionary.dictionary" \
  --mdx /path/to/dictionary.mdx \
  --compare-all \
  --output output/native-audit/report.json
```

审计使用未公开的词典选择 API，并检查同一查询下的所有记录，避免将同形词误判为丢失。
应优先传入 `--mdx` 检查真实源键；已有 SQLite 索引可能含有生成的别名。报告含词典正文，
应保留在本地，不要发布为测试素材。

`tests/probe_webkit.swift` 可渲染原生引擎导出的 HTML 并验证媒体。可选参数
`--secondary-display` 仅在存在副屏时显示不抢焦点的测试窗口，音频测试全程静音。
可用 `--width=480`、`--height=900` 和 `--font-size=20` 检查窄视图与放大字号；
JSON 结果包含实际排版样式和水平裁切的文本。

## 致谢与许可证

- [PyGlossary](https://github.com/ilius/pyglossary)：MDX/MDD 格式读取器。
- [macddk](https://github.com/ikey4u/macddk)：Dictionary Development Kit 镜像。

MIT。词典内容的权利归其各自权利人所有。
