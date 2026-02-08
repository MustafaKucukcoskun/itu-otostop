# GitHub Copilot Kota Kullanımı SSS

## 🤔 Hangi Kota Kullanılıyor?

GitHub Copilot kullandığınızda, **GitHub Copilot aboneliğinizdeki kotayı** kullanırsınız, **Claude Pro hesabınızdaki kotayı değil**.

## 📊 Kota Sistemleri Nasıl Çalışır?

### GitHub Copilot Kotası
- GitHub Copilot aboneliğiniz üzerinden sağlanır
- GitHub hesabınıza bağlıdır
- Farklı planlar farklı limitler sunar:
  - **GitHub Copilot Individual**: Aylık belirli sayıda istek ve token limiti
  - **GitHub Copilot Business**: Daha yüksek limitler ve takım özellikleri
  - **GitHub Copilot Enterprise**: En yüksek limitler ve özel özellikler

### Claude Pro Kotası
- Claude.ai web sitesinde veya API'de kullanılır
- Claude Pro aboneliğinize özeldir
- GitHub Copilot kullanırken **bu kota kullanılmaz**

## 🔄 GitHub Copilot Hangi AI Modelini Kullanıyor?

GitHub Copilot, farklı görevler için farklı AI modellerini kullanabilir:

1. **Claude 3.5 Sonnet** (Anthropic) - Kod üretimi ve karmaşık görevler için
2. **GPT-4 / GPT-4 Turbo** (OpenAI) - Çeşitli kodlama görevleri için
3. **Claude 3 Haiku** (Anthropic) - Hızlı yanıtlar için

Ancak, **hangi modeli kullanırsa kullansın, GitHub Copilot aboneliğinizdeki kotadan tüketir**.

## 💡 Nasıl Anlarım?

GitHub Copilot kullanırken:

1. **GitHub hesabınıza bakın**: GitHub Copilot kullanım istatistiklerinizi GitHub hesap ayarlarınızdan görebilirsiniz
2. **Claude.ai'da değişiklik yok**: Claude Pro kotanızda herhangi bir azalma görmezsiniz
3. **Faturalama**: Sadece GitHub üzerinden faturalandırılırsınız

## 🎯 Özetle

| Servis | Kota Kaynağı | Nerede Kullanılır? |
|--------|--------------|-------------------|
| **GitHub Copilot** | GitHub Copilot Aboneliği | VS Code, GitHub.com, IDE'ler |
| **Claude.ai** | Claude Pro Aboneliği | claude.ai web sitesi, Claude API |
| **GitHub Copilot (Agent kullanımı)** | GitHub Copilot Aboneliği | Kodunuzda yapılan tüm işlemler |

## 📝 Bu Projedeki `copilot-instructions.md` Dosyası

`.github/copilot-instructions.md` dosyası:
- GitHub Copilot'a bu proje hakkında **bağlamsal bilgi** sağlar
- Copilot'ın kod önerilerini ve yanıtlarını geliştirmesine yardımcı olur
- **Kota kullanımını etkilemez** - sadece Copilot'ın projenizi daha iyi anlamasını sağlar
- Proje yapısı, mimari, önemli fonksiyonlar ve iş akışları hakkında bilgi içerir

## ❓ Daha Fazla Soru?

- [GitHub Copilot Dokümantasyonu](https://docs.github.com/en/copilot)
- [GitHub Copilot Fiyatlandırma](https://github.com/features/copilot#pricing)
- [Claude Pro Hakkında](https://www.anthropic.com/claude)

---

**Not**: GitHub Copilot ve Claude Pro tamamen ayrı hizmetlerdir. GitHub Copilot kullanımınız sadece GitHub Copilot aboneliğinizi etkiler.
