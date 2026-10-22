# SS OIL S15 — telefon uygulaması düzenleme taslağı

- PC sunucu dosyaları ZIP içindeki orijinal haliyle korunmuştur. Kurulu ve çalışan PC sunucusunu bununla değiştirmeyin.
- Ana sayfa: kategoriler kaldırıldı, stok sayım kısayolu ve doğrudan kasa açma eklendi.
- Kasa: 'yerel tahmin' metinleri kaldırıldı; hesaplama değiştirilmedi.
- Stok: 'Satışları Al' butonu kaldırıldı; ürün detayına ekran yüksekliği sınırı getirildi.
- Stok sayım: Eksik/Fazla kayıt ekranı ve telefonun /shared eşitlemesine eklenen discrepancies bölümü.
- Sipariş: KOM/PAK birim seçimi ve tedarikçiye göre ayrı CSV (Excel ile açılır) dışa aktarım.
- Raporlar: ürünler, siparişler, tedarikçiler, etiketler, Eksik/Fazla CSV dışa aktarımı.
- Etiket: A4 ve 38x25mm özel ölçü seçenekleri; ürünün kayıtlı barkodu ile Code128 çizimi.

## Önemli sınırlamalar

Bu paketteki uygulama Flutter kaynak kodudur; derlenmiş APK değildir. Bu ortamda Flutter SDK bulunmadığı için derleme/cihaz testi yapılamadı. CSV dosyaları Excel ile açılabilir, ancak XLSX değildir. A4 düzeni ve özel ölçü yazıcıda kalibrasyon gerektirebilir. Eksik/Fazla verileri /shared üzerinden mevcut sunucunun 'discrepancies' bölümüne eşitlenir; mevcut sunucudaki ayrı stock_adjustments tablosuna doğrudan yazılmaz. Stok sayım oturumu ve stok sayım sonuçlarını sunucunun /counts uç noktasına kaydetme bu taslakta tamamlanmadı. Çalışan uygulamayı değiştirmeden önce ayrı kopyada test edin.


## Ek entegrasyon (22 Ekim)
- Eski sürümdeki gerçek XLSX üretim yaklaşımı S15'e aktarıldı: stok kontrol, sipariş, ürün veritabanı, manuel stok/eksik-fazla, tedarikçiler, etiketler ve satışlar. Tek dosyada ayrı sayfalar veya tek tek dışa aktarım.
- Etiket genişlik, yükseklik, aralık ve kenar boşluğu (mm) ayarları eklendi; özel etiket yönü değiştirilebilir.
- Var olan Kasa, Dopuna, stok güncelleme, sipariş, tedarikçi, KOM/PAK, barkod ve yerel/bulut ayarları korunmuştur.
- PC sunucu dosyaları üzerinde değişiklik yapılmamıştır.
- Flutter SDK bulunmadığından derleme/telefon testi yapılmamıştır; etiket baskısı fiziksel yazıcıda doğrulanmalıdır.
