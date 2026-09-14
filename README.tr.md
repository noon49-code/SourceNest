# SourceNest · Türkçe rehber

## Projeye döndüğünde her şeyi baştan anlatma

SourceNest, Windows üzerinde Codex için proje hafızasıdır. Kayıtlı projelerdeki yeni kullanıcı ve asistan mesajlarını yakalar; kararları, tercihleri, düzeltmeleri ve açık işleri kaynak bağlantılarıyla Markdown sayfalarına derler.

Tek bir özel kasa, kod depolarının dışında durur; her projenin hafızası bu kasanın ayrı bir klasöründedir. Modeli değiştirsen bile JSON ve Markdown dosyalarını okuyabilirsin. Başka bir asistan uygulamasına geçiş için o uygulamaya uygun otomatik kayıt bağlantısı gerekir.

**Mevcut kapsam:** erken sürüm; otomatik bağlantı Windows + Codex CLI ile test edildi. Özetler Türkçe üretilir. Yakalanan metin seçilen model sağlayıcısına gönderilir; dosyaların yerelde olması işlemenin çevrimdışı olduğu anlamına gelmez.

![SourceNest veri akışı: oturumdan kaynak kaydına ve proje wiki'sine](docs/architecture.svg)

~~~mermaid
flowchart TD
    A[Codex oturumu] -->|kullanıcı ve asistan metni| B[Yaşam döngüsü kancaları]
    B --> C[Değişmez JSON kaynak kaydı]
    C --> D[Seçilen özetleyici]
    D --> E[Yerel doğrulama]
    E --> F[Proje kayıtları ve Markdown wiki]
~~~

Karpathy'nin kaynak → wiki yaklaşımı ve Avenox'un oturum hafızası fikrinden esinlenen bağımsız proje hafızası. Kayıtlı her proje ayrı tutulur. Kaynaklar JSON, derlenmiş bilgiler Markdown olarak saklanır.

## Gerekenler

Windows, Python 3.11+, Git ve çalışan Codex CLI girişi. `python`, `git`, `codex` komutları terminalden erişilebilir olmalı. Otomatik bağlantı Windows + Codex üzerinde test edildi. Varsayılan `gpt-5.6-luna` modelinin hesabında kullanılabilir olması gerekir; model değiştirilebilir. Özetler şu an Türkçe üretilir.

## Kurulum

Bu depoyu indir ve çıkart; PowerShell'i o klasörde aç. Aşağıdaki komutlar kişisel kasayı deponun dışında oluşturur:

```powershell
$BeyinVault = Join-Path $env:USERPROFILE 'Documents\Beyin'
$BeyinCodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
codex login status
python install.py --target "$BeyinVault" --codex-home "$BeyinCodexHome" --registry projects.example.json
```

Planı kontrol ettikten sonra uygula:

```powershell
python install.py --target "$BeyinVault" --codex-home "$BeyinCodexHome" --registry projects.example.json --apply
```

Hedef klasör önceden varsa kurucu durur. Mevcut kasanın üzerine yeniden kurma.

Örnek proje listesi boştur. Aşağıdaki kayıt komutunu çalıştırana kadar hiçbir proje bağlanmaz. `python` bulunamıyorsa ve `py -3 --version` Python 3.11 veya üzerini gösteriyorsa komutlarda `python` yerine `py -3` kullan.

Terminalde `codex` aç, `/hooks` yaz. Kurduğun kasadaki `engine/beyin.py` dosyasını çalıştıran SessionStart, Stop, PreCompact, SessionEnd ve Interrupt kancalarını inceleyip güvenilir olarak işaretle. Kurucu güven onayını değiştirmez. İlgisiz kancaları topluca onaylama.

## Yeni proje ekle

Yolu mevcut proje klasörünle değiştir:

```powershell
python "$BeyinVault\engine\beyin.py" register --project yeni-proje --path 'D:\Projeler\YeniProje' --name 'Yeni Proje'
python "$BeyinVault\engine\beyin.py" doctor
```

Proje kimliği küçük İngilizce harf, rakam ve tire kullanır. O proje klasöründe yeni Codex sohbeti aç. Her sohbette yeniden kayıt veya `/hooks` onayı gerekmez. Bu işlemi her yeni proje için bir kez yap.

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

Kişisel kasanı ve Git geçmişini herkese açık paylaşma. Düzenli ayrı yedek al. Özetler hatalı olabilir; kaynak ve tarihleri kontrol et. Ayrıntılar: [gizlilik](PRIVACY.md), [komutlar ve kaldırma](README.md), [esin kaynakları](CREDITS.md).

## Compatibility / Uyumluluk

SourceNest is the public project name. The engine retains the Beyin command names, default vault folder and hook markers for compatibility with existing installations.
