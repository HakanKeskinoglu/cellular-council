# GitHub'a Yayınlama Rehberi

## 1. Repo Oluştur

```bash
# GitHub'da "cellular-council" adında yeni bir public repo oluştur
# Sonra:

cd cellular-council
git init
git add .
git commit -m "feat: initial release of CCA Framework v0.1.0

- BaseCell abstract class with health monitoring
- Specialized cells: Risk, Ethics, Technical, Financial, Security
- ConsensusEngine with 5 strategies (weighted_avg, vote, delphi, unanimous, apex)
- Multi-round structured debate mechanism
- LLM backends: Ollama (local/airgap), OpenAI, Anthropic
- AlertMind reference implementation for data center alarms
- 21 unit tests, 80% code coverage
- Apache 2.0 license"

git branch -M main
git remote add origin https://github.com/HakanKeskinoglu/cellular-council.git
git push -u origin main
```

## 2. pyproject.toml'daki URL'leri Güncelle

```toml
[project.urls]
Homepage = "https://github.com/HakanKeskinoglu/cellular-council"
Repository = "https://github.com/HakanKeskinoglu/cellular-council"
```

## 3. GitHub Repo Ayarları

- **About** kısmına ekle: "Hierarchical multi-agent AI decision framework"
- **Topics** ekle: `multi-agent`, `llm`, `ai`, `python`, `ollama`, `decision-making`, `consensus`
- **Releases** → "Create a new release" → tag: `v0.1.0`

## 4. PyPI'ye Yayınla (opsiyonel, sonra)

```bash
pip install build twine --break-system-packages
python -m build
twine upload dist/*
```

## 5. README'deki username'i Düzelt

`README.md` içindeki tüm `HakanKeskinoglu` → kendi GitHub kullanıcı adın ile değiştir.
