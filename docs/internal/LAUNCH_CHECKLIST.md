# 🚀 CCA GitHub Launch Checklist

Bu dosya seni adım adım GitHub yayınına götürür. Her adımı tamamladıkça işaretle.

---

## Adım 1: Dosyaları Yerleştir

Daha önce indirdiğin `cellular-council-v0.1.0.zip` dosyasını aç.
Bu launch kit'teki dosyaları repo klasörüne kopyala:

```
cellular-council/
├── CONTRIBUTING.md          ← YENİ (bu kit'ten)
├── CODE_OF_CONDUCT.md       ← YENİ (bu kit'ten)
├── CHANGELOG.md             ← YENİ (bu kit'ten)
├── SECURITY.md              ← YENİ (bu kit'ten)
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md    ← YENİ (bu kit'ten)
│   │   └── feature_request.md ← YENİ (bu kit'ten)
│   ├── PULL_REQUEST_TEMPLATE/
│   │   └── pull_request_template.md ← YENİ (bu kit'ten)
│   └── workflows/
│       └── test.yml         ← MEVCUT (zip'te var)
├── cca/                     ← MEVCUT
├── tests/                   ← MEVCUT
├── examples/                ← MEVCUT
├── README.md                ← MEVCUT
├── LICENSE                  ← MEVCUT
├── pyproject.toml           ← MEVCUT
└── .gitignore               ← MEVCUT
```

---

## Adım 2: Kişiselleştir

README.md ve pyproject.toml içindeki placeholder'ları düzelt:

- [ ] `HakanKeskinoglu` → senin GitHub kullanıcı adın
- [ ] `keskinoglu.hakan336@gmail.com` → gerçek email adresin
- [ ] pyproject.toml'daki URL'leri güncelle
- [ ] README.md'deki badge URL'lerini güncelle

---

## Adım 3: Lokal Test

```bash
cd cellular-council

# Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Kurulum
pip install -e ".[dev]"

# Testleri çalıştır
pytest tests/ -v --cov=cca

# Lint kontrol
ruff check cca/
```

- [ ] Tüm testler geçiyor (21/21)
- [ ] Lint hataları yok
- [ ] Import'lar çalışıyor

---

## Adım 4: GitHub Repo Oluştur

1. GitHub.com → New Repository
2. İsim: `cellular-council`
3. Description: "A hierarchical multi-agent AI decision-making framework inspired by biological cell specialization and corporate governance"
4. Public repo
5. README/LICENSE ekleme (zaten var)

```bash
cd cellular-council
git init
git add .
git commit -m "feat: initial release of CCA Framework v0.1.0

- BaseCell abstract class with health monitoring
- 5 specialized cells: Risk, Ethics, Technical, Financial, Security
- ConsensusEngine with 5 strategies
- Multi-round structured debate mechanism
- LLM backends: Ollama, OpenAI, Anthropic
- AlertMind reference implementation
- 21 unit tests, ~80% coverage
- Apache 2.0 license"

git branch -M main
git remote add origin https://github.com/HakanKeskinoglu/cellular-council.git
git push -u origin main
```

- [ ] Repo oluşturuldu
- [ ] Kod push edildi
- [ ] CI/CD (GitHub Actions) yeşil

---

## Adım 5: Repo Ayarları

GitHub repo sayfasında:

- [ ] About → Description ekle
- [ ] Topics ekle: `multi-agent`, `llm`, `ai`, `python`, `ollama`, `decision-making`, `consensus`, `multi-agent-systems`
- [ ] Releases → v0.1.0 tag'i oluştur
- [ ] Issues → Templates aktif olduğunu kontrol et
- [ ] Settings → Discussions'ı aktif et (opsiyonel)

---

## Adım 6: İlk Release

GitHub → Releases → "Create a new release"
- Tag: `v0.1.0`
- Title: `v0.1.0 — Initial Release`
- Description: CHANGELOG.md'deki 0.1.0 bölümünü yapıştır
- [ ] Release yayınlandı

---

## 🎉 Tebrikler!

Repo yayında. Sonraki adımlar:
1. AlertMind entegrasyonu sprint'i
2. İlk akademik paper taslağı
3. README'ye mimari diyagram ekle (Mermaid)
4. PyPI'ye yayınla (opsiyonel)
