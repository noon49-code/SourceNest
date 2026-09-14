# SourceNest · yapay zekâ kodlama asistanları için taşınabilir proje hafızası

## Projeye döndüğünde her şeyi baştan anlatma

SourceNest, Codex, Claude Code, Cursor ve benzeri yapay zekâ kodlama araçları arasında proje bağlamını korur. Kayıtlı projelerdeki görünür kullanıcı ve asistan mesajlarını yakalar; kararları, tercihleri, düzeltmeleri ve açık işleri kaynak bağlantılarıyla Markdown sayfalarına derler.

Tek bir özel kasa, kod depolarının dışında durur; her projenin hafızası bu kasanın ayrı bir klasöründedir. Çekirdek kayıt biçimi model sağlayıcısına bağlı değildir. Codex ve Claude Code için yaşam döngüsü kancaları, dışa aktarma veya akış sunan diğer araçlar için standart JSONL köprüsü vardır.

**Mevcut kapsam:** erken sürüm; Windows + Codex CLI ile canlı yakalama test edildi. Claude Code kanca dosyaları ve Cursor/standart JSONL adaptörleri sentetik testlerle doğrulandı. Özetler Türkçe üretilir. Yakalanan metin seçilen model sağlayıcısına gönderilir; dosyaların yerelde olması işlemenin çevrimdışı olduğu anlamına gelmez.

![SourceNest veri akışı: oturumdan kaynak kaydına ve proje wiki'sine](docs/architecture.svg)

~~~mermaid
flowchart TD
    A[Codex / Claude / diğer oturum] -->|kullanıcı ve asistan metni| B[Yaşam kancaları veya JSONL köprüsü]
    B --> C[Değişmez JSON kaynak kaydı]
    C --> D[Seçilen özetleyici]
    D --> E[Yerel doğrulama]
    E --> F[Proje kayıtları ve Markdown wiki]
~~~

Karpathy'nin kaynak → wiki yaklaşımı ve Avenox'un oturum hafızası fikrinden esinlenen bağımsız proje hafızası. Kayıtlı her proje ayrı tutulur. Kaynaklar JSON, derlenmiş bilgiler Markdown olarak saklanır.

## Gerekenler

Windows, Python 3.11+ ve Git gerekir. Codex özetleyicisini kullanacaksan `codex login status` çalışır durumda olmalıdır. Otomatik Codex ve Claude Code bağlantıları Windows için hazırlanır; varsayılan `gpt-5.6-luna` modelinin hesabında kullanılabilir olması gerekir. Model değiştirilebilir. Özetler şu an Türkçe üretilir.

## Kurulum

Bu depoyu indir ve çıkart; PowerShell'i o klasörde aç. Aşağıdaki komutlar kişisel kasayı deponun dışında oluşturur:

En kısa yol için yardımcı betik Python'u, yaygın Codex/Claude klasörlerini ve mevcut kasayı kendisi bulur. Önce yalnızca planı gösterir:

```powershell
powershell.exe -NoProfile -File .\setup.ps1
```

Plan doğruysa `-Apply` ile uygula. Hedefte kasa yoksa oluşturur, varsa güvenli yükseltme yolunu seçer:

```powershell
powershell.exe -NoProfile -File .\setup.ps1 -Apply
```

Farklı konumlar için `-NoCodex`, `-NoClaude`, `-CodexHome 'D:\...'`, `-ClaudeHome 'D:\...'` veya `-Vault 'D:\...'` kullanabilirsin. Sonucu daha sonra `powershell.exe -NoProfile -File .\setup.ps1 -Verify` ile kontrol et.

Aynı yardımcıyı normal Windows komut dosyası olarak `setup.cmd` ile de çalıştırabilirsin.

```powershell
$BeyinVault = Join-Path $env:USERPROFILE 'Documents\Beyin'
$BeyinCodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$BeyinClaudeHome = Join-Path $env:USERPROFILE '.claude'
codex login status
python install.py --target "$BeyinVault" --codex-home "$BeyinCodexHome" --claude-home "$BeyinClaudeHome" --registry projects.example.json
```

Planı kontrol ettikten sonra uygula:

```powershell
python install.py --target "$BeyinVault" --codex-home "$BeyinCodexHome" --claude-home "$BeyinClaudeHome" --registry projects.example.json --apply
```

Hedef klasör önceden varsa kurucu durur. Mevcut kasanın üzerine yeniden kurma.

Örnek proje listesi boştur. Aşağıdaki kayıt komutunu çalıştırana kadar hiçbir proje bağlanmaz. `python` bulunamıyorsa ve `py -3 --version` Python 3.11 veya üzerini gösteriyorsa komutlarda `python` yerine `py -3` kullan.

Kurucu, Codex `hooks.json` ve Claude Code `settings.json` içine kancaları ekler; ayrıca Codex `AGENTS.md` ve Claude `CLAUDE.md` içine sınırlı hafıza yönergesi koyar. Mevcut dosyalar kasanın `.backups` klasöründe yedeklenir. Kurucu güven veya izin kararlarını değiştirmez. Her aracın ayarlarında eklenen komutları inceleyip etkinleştir.

Kasa zaten varsa motoru güncellemek ve seçtiğin asistan bağlantılarını eklemek için:

```powershell
python install.py --target "$BeyinVault" --codex-home "$BeyinCodexHome" --claude-home "$BeyinClaudeHome" --upgrade
```

Araç biçimleri ve dışa aktarma yolu için [asistan bağlantıları](docs/integrations.md) sayfasına bak. Bütün yapay zekâ uygulamalarının ortak kullandığı tek bir kanca standardı yoktur; kanca sunmayan araçlar JSONL köprüsünü kullanır.

## Yeni proje ekle

Yolu mevcut proje klasörünle değiştir:

```powershell
python "$BeyinVault\engine\beyin.py" register --project yeni-proje --path 'D:\Projeler\YeniProje' --name 'Yeni Proje'
python "$BeyinVault\engine\beyin.py" doctor
```

Proje kimliği küçük İngilizce harf, rakam ve tire kullanır. O proje klasöründe yeni Codex veya Claude Code oturumu aç. Her oturumda yeniden kayıt veya kanca kurulumu gerekmez. Bu işlemi her yeni proje için bir kez yap.

## Ne kaydedilir?

Oturumların yeni kullanıcı/asistan metinleri yakalanır. Karar, tercih, öneri, düzeltme ve açık işler kaynaklı kayıtlara dönüştürülür. Sistem mesajları, araç çıktıları ve düşünce içeriği alınmaz. Önceki sohbet arşivin topluca aktarılmaz. Başlangıç bağlamı sınırlıdır; ayrıntı için ilgili kaynaklar okunmalıdır.

Dosyalar kasanın `projects/<proje-kimliği>` klasöründedir. `wiki` bilgi sayfaları, `STATUS.md` son çalışma kayıtlarıdır. Elle yazacağın kalıcı notlar `notes` altında olmalıdır. `PROFILE.md` ortak tercihlerin içindir.

## Model, kota ve bakım

Kasanın `config.json` dosyasında `summarizer.model` modeli belirler. Başlangıç sınırı merkez kasa genelinde UTC gün başına 20, bir çalışmada 4 çağrıdır. Model çağrıları hesabının kotasını kullanır; bunlar parasal harcama sınırı değildir. Kuyruk sonraki kanca olaylarında veya elle işlemeyle devam eder; zamanlanmış iş kurulmaz.

```powershell
python "$BeyinVault\engine\beyin.py" process --retry
python "$BeyinVault\engine\beyin.py" pause
python "$BeyinVault\engine\beyin.py" resume
```

`pause` yeni otomatik yakalamayı kapatır; çalışan işleyiciyi zorla durdurmaz. Başka uygulamaya geçişte o uygulamanın otomatik kayıt bağlantısı ayrıca gerekir. OpenAI API ve özel komut bağlantısı mevcut olsa da sağlayıcılar arası canlı geçiş doğrulanmadı.

Codex ve Claude Code yaşam kancalarını kullanır. Cursor veya dışa aktarma sunan başka bir araç için:

```powershell
python "$BeyinVault\engine\beyin.py" capture-file --project yeni-proje --file 'D:\Exports\session.jsonl' --adapter normalized --session dis-session
```

`cursor` adaptörü `type` + `message.role` + `message.content` biçimini, `normalized` adaptörü ise `role` + `content` biçimini okur. Yakalama biçimi ile özetleyici birbirinden ayrıdır; model değiştirince kasa formatı değişmez.

Kişisel kasanı ve Git geçmişini herkese açık paylaşma. Düzenli ayrı yedek al. Özetler hatalı olabilir; kaynak ve tarihleri kontrol et. Ayrıntılar: [gizlilik](PRIVACY.md), [komutlar ve kaldırma](README.md), [esin kaynakları](CREDITS.md).

## Compatibility / Uyumluluk

SourceNest is the public project name. The engine retains the Beyin command names, default vault folder and hook markers for compatibility with existing installations.
