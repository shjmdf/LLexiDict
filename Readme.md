# LLexiDict📖
**An LLM-powered multilingual dictionary that understands context and nuance.**

Designed and written by shjmdf.

LLexiDict is an open-source project designed to bridge the gap between the rigidity of traditional dictionaries and the nuanced, contextual understanding required for deep language learning. Powered by Large Language Models (LLMs), LLexiDict provides richer definitions, context-aware examples, and detailed lexical analysis for **English, Japanese, French, and Latin**.

## 💬 Why create LLexiDict?
Traditional dictionaries are invaluable, but they often have limitations. They can be rigid, lacking the contextual awareness needed to understand complex language—a pain point especially clear in language exams like the GRE or TOEFL. They can be good instructors but never promise to cultivate a native speaker.

When I was a senior high school student, I found myself frustrated by the Cloze Tests in my English exams (These words might sting a little for my English teacher, but I have nothing but the utmost respect for her. She's the one who taught me to appreciate the true depth and nuance of the language.). Traditional dictionaries failed to capture the subtle nuances, or it took ages to find a seemingly relevant definition within a vast entry.

Now, as a college student majoring in Computational Linguistics and Computer Science, I hoped those nightmares would be over. But when preparing for the GRE, the Text Completions and Sentence Equivalence questions proved even more excruciating. When I learned about ***Island Constraints***—a linguistic concept that ran contrary to my second-language instincts—I realized that mastering context and subtle nuance is unavoidable. It is the very soul of language learning.

Fortunately, we have LLMs.

LLexiDict was born to tackle this exact problem. It aims to be an intelligent dictionary that combines the power of AI with the precision of human review(This feature is a long-term goal that will heavily rely on community contributions to ensure its quality and scale.), ensuring the accuracy and reliability that language learners need to truly master a word's meaning.
## 🚀 Features
Context-Aware Definitions: Provides meanings that adapt to the context you're querying, not just a flat list of all possible definitions.

Nuanced Distinction: Focuses on lexical choice, offering precise comparisons for synonyms, perfect for tackling advanced vocabulary challenges (GRE, TOEFL, etc.).

Rich Example Sentences: Generates diverse, clear examples that demonstrate a word's practical application in various scenarios.
## Tech Stack
Work in progress.
## 📦 Installation
Work in progress.
## 💡 Usage
Work in progress.
## 🌐 Online demo
Work in progress.
## 🙌 Contributing
Any contributions you make are greatly appreciated.

- Fork the Project.

- Create your Feature Branch (git checkout -b feature/AmazingFeature).

- Commit your Changes (git commit -m 'Add some AmazingFeature').

- Push to the Branch (git push origin feature/AmazingFeature).

- Open a Pull Request.

If you have a major change or a new feature in mind, please open an Issue first to discuss what you would like to change.

## 🙏 Acknowledgements
### Inspiration
This project was significantly inspired by the excellent work on the [TICKurt/english-dictionary-web](https://github.com/TICKurt/english-dictionary-web) project
Their approach to **building a scientific English learning platform based on LLM-defined data** served as one of a key motivation for the development of LLexiDict.
### Open Source Dictionaries and Word Lists
Remained to be added...
### LLM Providers
Remained to be added...

## LICENSE & ATTRIBUTION

**This repository uses a mixed licensing model. Please read the following carefully.**

### PART 1: SOURCE CODE (MIT LICENSE)

All source code, scripts (e.g., Python files in `generate/`, etc.), and project configuration files created by Xie Hurui(shjmdf) are licensed under the MIT License.

Copyright (c) 2025 Xie Hurui(shjmdf)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files, to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

### PART 2: ENGLISH DATA (CC-BY-SA 3.0)

**Files:** `english-dictionary.db`, `wiki-100k.txt`, `frequency.txt`, etc.

* **Frequency Data:** Derived from Peter Norvig's public domain corpus.
* **Word List:** Derived from Wiktionary (CC-BY-SA 3.0).
* **Database License:** The generated database `english-dictionary.db` is licensed under **CC-BY-SA 3.0**.

**Usage:** You are free to use and distribute commercially, provided you attribute the source and distribute modifications under the same license.

---

### PART 3: FRENCH DATA (CC-BY-NC 4.0 - NON-COMMERCIAL)

**Files:** `french_dictionary.db`, `Lexique383.tsv`, etc.

* **Source:** Lexique 3.83 (Boris New & Christophe Pallier).
* **License:** Creative Commons Attribution-NonCommercial 4.0 International (CC-BY-NC 4.0).

**⚠️ RESTRICTION:** These files and the generated database may **NOT** be used for commercial purposes.

---

### PART 4: JAPANESE DATA (CC-BY-NC 4.0 - NON-COMMERCIAL)

**Files:** `japanese_dictionary.db`, `jp-clean.txt`, `jlpt-clean.txt`, etc.

* **JLPT List:** Sourced from `jlpt-word-list` (MIT) / Tanos (CC-BY).
* **JPDB List:** Sourced from `yomitan-dictionaries` / jpdb.io (Third-party asset).
* **Database License:** Due to the mixed nature and inclusion of third-party statistical data, the generated database `japanese_dictionary.db` is licensed under **CC-BY-NC 4.0**.

**⚠️ RESTRICTION:** You may **NOT** use the Japanese database for commercial purposes.

---

### PART 5: LATIN DATA (CC-BY-SA)

**Files:** `latin_dictionary.db`, `dcc-latin-core-list.csv`.

* **Source:** Based on `latin-vocabulary` repository and Dickinson College Commentaries (DCC).
* **License:** Creative Commons Attribution-ShareAlike (CC BY-SA).
* **Database License:** The generated database `latin_dictionary.db` is licensed under **CC BY-SA**.

[![GitHub license](https://img.shields.io/badge/license-MIT%20%26%20CC--BY-blue.svg)](https://github.com/shjmdf/LLexiDict/blob/main/LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
[![GitHub issues](https://img.shields.io/github/issues/shjmdf/LLexiDict)](https://github.com/shjmdf/LLexiDict/issues)
[![GitHub stars](https://img.shields.io/github/stars/shjmdf/LLexiDict?style=social)](https://github.com/shjmdf/LLexiDict/stargazers)